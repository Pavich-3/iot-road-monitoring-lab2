CREATE TABLE processed_agent_data (
    id SERIAL PRIMARY KEY,
    road_state VARCHAR(255),
    x DOUBLE PRECISION,
    y DOUBLE PRECISION,
    z DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    timestamp TIMESTAMP
);

CREATE TABLE sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    sensor_id VARCHAR(100) NOT NULL,
    sensor_type VARCHAR(50) NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude_m DOUBLE PRECISION,
    area VARCHAR(255),
    road_segment_id VARCHAR(100),
    status VARCHAR(32),
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sensor_readings_sensor_type
    ON sensor_readings(sensor_type);

CREATE INDEX idx_sensor_readings_sensor_id
    ON sensor_readings(sensor_id);

CREATE INDEX idx_sensor_readings_recorded_at
    ON sensor_readings(recorded_at DESC);

CREATE INDEX idx_sensor_readings_payload_gin
    ON sensor_readings USING GIN(payload);

CREATE INDEX idx_sensor_readings_metadata_gin
    ON sensor_readings USING GIN(metadata);
