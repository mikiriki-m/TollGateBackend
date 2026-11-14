from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal
import psycopg
from psycopg.rows import dict_row
import db

app = FastAPI(title="IoT Smart Toll Gate Server")

# Allow your Admin Panel frontend to call this API from any origin/port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Request Schemas ---

class ScanRequest(BaseModel):
    gate_id: str
    rfid_uid: str
    distance_cm: float

class ModeUpdate(BaseModel):
    mode: Literal["ENTRY", "EXIT"]

class PriceUpdate(BaseModel):
    entry_gate_id: str
    exit_gate_id: str
    price: float = Field(ge=0)

class TopUpRequest(BaseModel):
    amount: float = Field(gt=0)


# ==========================================
# 1. ESP32 HARDWARE ENDPOINT
# ==========================================

@app.post("/api/scan")
def handle_scan(req: ScanRequest):
    """
    Called by ESP32 when ultrasonic sensor < 40cm and RFID card is scanned.
    Returns HTTP status codes:
      - 200: Open gate (Entry logged OR Exit toll paid)
      - 400: No active entry record found at Exit gate
      - 402: Insufficient funds (Payment Required)
      - 403: Unknown RFID card
      - 404: Invalid gate_id
    """
    payload, status_code = db.process_rfid_scan(
        gate_id=req.gate_id,
        rfid_uid=req.rfid_uid,
        distance_cm=req.distance_cm
    )
    return JSONResponse(content=payload, status_code=status_code)


# ==========================================
# 2. ADMIN PANEL: GATES & ROUTE PRICING
# ==========================================

@app.get("/api/gates")
def list_gates():
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        return conn.execute("SELECT * FROM gates ORDER BY gate_id").fetchall()

@app.patch("/api/gates/{gate_id}")
def switch_gate_mode(gate_id: str, body: ModeUpdate):
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        updated = conn.execute(
            "UPDATE gates SET mode = %s WHERE gate_id = %s RETURNING *",
            (body.mode, gate_id)
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Gate not found")
        return updated

@app.get("/api/prices")
def list_prices():
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        return conn.execute("SELECT * FROM route_prices").fetchall()

@app.put("/api/prices")
def update_price(body: PriceUpdate):
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            INSERT INTO route_prices (entry_gate_id, exit_gate_id, price)
            VALUES (%s, %s, %s)
            ON CONFLICT (entry_gate_id, exit_gate_id)
            DO UPDATE SET price = EXCLUDED.price
            RETURNING *
            """,
            (body.entry_gate_id, body.exit_gate_id, body.price)
        ).fetchone()
        return row


# ==========================================
# 3. ADMIN PANEL: USERS & BALANCES
# ==========================================

@app.get("/api/users")
def list_users():
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        return conn.execute("SELECT * FROM users ORDER BY id").fetchall()

@app.post("/api/users/{rfid_uid}/topup")
def topup_user(rfid_uid: str, body: TopUpRequest):
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        user = conn.execute(
            "UPDATE users SET balance = balance + %s WHERE rfid_uid = %s RETURNING *",
            (body.amount, rfid_uid)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


# ==========================================
# 4. TIMESCALEDB TELEMETRY & CHART ANALYTICS
# ==========================================

@app.get("/api/telemetry")
def get_recent_telemetry(limit: int = 100):
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT * FROM gate_telemetry ORDER BY time DESC LIMIT %s",
            (limit,)
        ).fetchall()

@app.get("/api/stats/hourly")
def get_hourly_stats(hours: int = 24):
    """
    Uses TimescaleDB time_bucket() to aggregate traffic and revenue
    for Admin Panel line/bar charts.
    """
    with psycopg.connect(db.CONN_STR, row_factory=dict_row) as conn:
        return conn.execute(
            """
            SELECT
                time_bucket('1 hour', time) AS bucket,
                gate_id,
                COUNT(*) FILTER (WHERE event_type IN ('ENTRY_OK', 'EXIT_PAID')) AS passed_count,
                COUNT(*) FILTER (WHERE event_type = 'INSUFFICIENT_FUNDS') AS denied_count,
                COALESCE(SUM(amount_charged), 0)::FLOAT AS revenue
            FROM gate_telemetry
            WHERE time > NOW() - (%s || ' hours')::INTERVAL
            GROUP BY bucket, gate_id
            ORDER BY bucket ASC
            """,
            (hours,)
        ).fetchall()