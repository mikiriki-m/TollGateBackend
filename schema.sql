-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. Users & Balances
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    rfid_uid VARCHAR(32) UNIQUE NOT NULL,
    balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00
);

-- 2. Toll Gates (Mode toggled by Admin Panel)
CREATE TABLE gates (
    gate_id VARCHAR(32) PRIMARY KEY,
    location_name VARCHAR(100) NOT NULL,
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('ENTRY', 'EXIT'))
);

-- 3. Route Pricing Table
CREATE TABLE route_prices (
    entry_gate_id VARCHAR(32) REFERENCES gates(gate_id),
    exit_gate_id VARCHAR(32) REFERENCES gates(gate_id),
    price DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (entry_gate_id, exit_gate_id)
);

-- 4. Active Trips (Tracks vehicles currently between entry & exit)
CREATE TABLE active_trips (
    id SERIAL PRIMARY KEY,
    rfid_uid VARCHAR(32) REFERENCES users(rfid_uid),
    entry_gate_id VARCHAR(32) REFERENCES gates(gate_id),
    entry_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(15) NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETED'))
);

-- 5. Time-Series Telemetry Table
CREATE TABLE gate_telemetry (
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gate_id VARCHAR(32) REFERENCES gates(gate_id),
    rfid_uid VARCHAR(32),
    event_type VARCHAR(30) NOT NULL, -- 'ENTRY_OK', 'EXIT_PAID', 'INSUFFICIENT_FUNDS', 'UNKNOWN_CARD'
    distance_cm REAL,
    amount_charged DECIMAL(10, 2) DEFAULT 0.00
);

-- Convert gate_telemetry into a TimescaleDB Hypertable
SELECT create_hypertable('gate_telemetry', 'time');

-- Seed initial test data so you can test immediately
INSERT INTO gates (gate_id, location_name, mode) VALUES 
    ('GATE_NORTH', 'Belgrade North', 'ENTRY'),
    ('GATE_SOUTH', 'Nis South', 'EXIT');

INSERT INTO route_prices (entry_gate_id, exit_gate_id, price) VALUES 
    ('GATE_NORTH', 'GATE_SOUTH', 450.00),
    ('GATE_SOUTH', 'GATE_NORTH', 450.00);

INSERT INTO users (full_name, rfid_uid, balance) VALUES 
    ('Marko Markovic', 'A1B2C3D4', 1000.00),
    ('Ana Anic', 'DEADBEEF', 100.00); -- Insufficient funds for 450 RSD route