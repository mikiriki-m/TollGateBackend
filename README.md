# TollGate Backend

Backend API for the Smart Toll Gate system, handling vehicle detection logs, RFID authentication, toll balance verification, and gate access control for ESP32-S3 gate nodes.

## Project Structure

- `main.py` — FastAPI application and HTTP endpoints (`/api/scan`, etc.)
- `db.py` — Database connection and query helpers
- `schema.sql` — Database schema initialization
- `server.js` — Node.js / Firebase service integration
- `docker-compose.yml` — Containerized database/service setup
- `package.json` — Node dependencies

## Prerequisites

- Python 3.10+ with `fastapi` and `uvicorn` installed
- Node.js & npm (if running `server.js`)
- Local Firebase `serviceAccountKey.json` placed in the project root *(excluded from Git)*

## Running the Server

1. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn
   npm install
