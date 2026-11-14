import psycopg
from psycopg.rows import dict_row

CONN_STR = "postgresql://toll_admin:secretpassword@localhost:5433/tollgate"

def process_rfid_scan(gate_id: str, rfid_uid: str, distance_cm: float):
    with psycopg.connect(CONN_STR, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # 1. Check gate mode ('ENTRY' or 'EXIT')
            cur.execute("SELECT mode FROM gates WHERE gate_id = %s", (gate_id,))
            gate = cur.fetchone()
            if not gate:
                return {"action": "DENY", "reason": "INVALID_GATE"}, 404

            # 2. Verify user exists
            cur.execute("SELECT * FROM users WHERE rfid_uid = %s FOR UPDATE", (rfid_uid,))
            user = cur.fetchone()
            if not user:
                cur.execute(
                    "INSERT INTO gate_telemetry (gate_id, rfid_uid, event_type, distance_cm) VALUES (%s, %s, 'UNKNOWN_CARD', %s)",
                    (gate_id, rfid_uid, distance_cm)
                )
                return {"action": "DENY", "lcd": "Unknown Card"}, 403

            # --- ENTRY GATE WORKFLOW ---
            if gate["mode"] == "ENTRY":
                cur.execute(
                    "INSERT INTO active_trips (rfid_uid, entry_gate_id, status) VALUES (%s, %s, 'IN_PROGRESS')",
                    (rfid_uid, gate_id)
                )
                cur.execute(
                    "INSERT INTO gate_telemetry (gate_id, rfid_uid, event_type, distance_cm) VALUES (%s, %s, 'ENTRY_OK', %s)",
                    (gate_id, rfid_uid, distance_cm)
                )
                return {"action": "OPEN", "lcd": f"Welcome {user['full_name']}"}, 200

            # --- EXIT GATE WORKFLOW ---
            elif gate["mode"] == "EXIT":
                # Find active trip
                cur.execute(
                    "SELECT * FROM active_trips WHERE rfid_uid = %s AND status = 'IN_PROGRESS' ORDER BY entry_time DESC LIMIT 1",
                    (rfid_uid,)
                )
                trip = cur.fetchone()
                if not trip:
                    return {"action": "DENY", "lcd": "No Entry Record"}, 400

                # Lookup route price
                cur.execute(
                    "SELECT price FROM route_prices WHERE entry_gate_id = %s AND exit_gate_id = %s",
                    (trip["entry_gate_id"], gate_id)
                )
                route = cur.fetchone()
                price = route["price"] if route else 0

                # Check funds
                if user["balance"] < price:
                    cur.execute(
                        "INSERT INTO gate_telemetry (gate_id, rfid_uid, event_type, distance_cm) VALUES (%s, %s, 'INSUFFICIENT_FUNDS', %s)",
                        (gate_id, rfid_uid, distance_cm)
                    )
                    return {"action": "DENY", "lcd": "Low Balance"}, 402  # 402 Payment Required

                # Deduct balance, close trip, log telemetry
                new_balance = user["balance"] - price
                cur.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, user["id"]))
                cur.execute("UPDATE active_trips SET status = 'COMPLETED' WHERE id = %s", (trip["id"],))
                cur.execute(
                    "INSERT INTO gate_telemetry (gate_id, rfid_uid, event_type, distance_cm, amount_charged) VALUES (%s, %s, 'EXIT_PAID', %s, %s)",
                    (gate_id, rfid_uid, distance_cm, price)
                )
                return {"action": "OPEN", "lcd": f"Paid: {price} RSD", "balance": float(new_balance)}, 200