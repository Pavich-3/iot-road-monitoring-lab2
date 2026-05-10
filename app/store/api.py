from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, TypeAdapter, field_validator
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, MetaData, String, Table, create_engine, delete, insert, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import select

from app.shared.sensor_models import SensorMessage, SensorReadingInDB
from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER


app = FastAPI(title="IoT Road Monitoring Store")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
engine = create_engine(DATABASE_URL)
metadata = MetaData()

processed_agent_data = Table(
    "processed_agent_data",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("road_state", String),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
)

sensor_readings = Table(
    "sensor_readings",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),  # Universal table primary key.
    Column("sensor_id", String, nullable=False),  # Indexed logical identifier for querying one sensor.
    Column("sensor_type", String, nullable=False),  # Sensor family used for filtering different domains.
    Column("device_id", String, nullable=False),  # Physical source device identifier.
    Column("schema_version", String, nullable=False),  # Schema version stored with every message.
    Column("latitude", Float, nullable=False),  # Flattened location for quick spatial filtering.
    Column("longitude", Float, nullable=False),  # Flattened location for quick spatial filtering.
    Column("altitude_m", Float),  # Optional flattened altitude.
    Column("area", String),  # Optional flattened area label.
    Column("road_segment_id", String),  # Optional flattened road/intersection reference.
    Column("status", String),  # Flattened device status for monitoring.
    Column("payload", JSONB, nullable=False),  # Domain-specific measurement block.
    Column("metadata", JSONB, nullable=False),  # Full technical metadata block.
    Column("recorded_at", DateTime(timezone=True), nullable=False),  # Original measurement time.
    Column("received_at", DateTime(timezone=True), nullable=False),  # Store receive time.
    Column("created_at", DateTime(timezone=True), nullable=False),  # DB insertion time.
)


class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime


class ProcessedAgentData(BaseModel):
    road_state: str
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    timestamp: datetime

    @classmethod
    @field_validator("timestamp", mode="before")
    def check_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid timestamp format. Expected ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)."
            ) from exc


legacy_subscriptions: set[WebSocket] = set()
sensor_reading_subscriptions: set[WebSocket] = set()

sensor_message_adapter = TypeAdapter(SensorMessage)
sensor_message_batch_adapter = TypeAdapter(list[SensorMessage])


@app.on_event("startup")
def create_tables() -> None:
    # create_all is enough for the lab because we only need lightweight bootstrapping.
    metadata.create_all(engine)  # Create tables automatically for the lab deployment.


@app.websocket("/ws/")
async def legacy_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    legacy_subscriptions.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        legacy_subscriptions.discard(websocket)


@app.websocket("/ws/sensor_readings")
async def sensor_readings_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    sensor_reading_subscriptions.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        sensor_reading_subscriptions.discard(websocket)


async def broadcast_to_subscribers(subscriptions: set[WebSocket], data: dict[str, Any]) -> None:
    disconnected = set()

    for websocket in subscriptions:
        try:
            await websocket.send_json(data)
        except Exception:
            disconnected.add(websocket)

    for websocket in disconnected:
        subscriptions.discard(websocket)


async def send_legacy_data_to_subscribers(data: dict[str, Any]) -> None:
    await broadcast_to_subscribers(legacy_subscriptions, data)


async def send_sensor_reading_to_subscribers(data: dict[str, Any]) -> None:
    await broadcast_to_subscribers(sensor_reading_subscriptions, data)


def processed_agent_data_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row.id,  # Legacy row id.
        "road_state": row.road_state,  # Legacy classified road condition.
        "x": row.x,  # Legacy X axis value.
        "y": row.y,  # Legacy Y axis value.
        "z": row.z,  # Legacy Z axis value.
        "latitude": row.latitude,  # Legacy latitude.
        "longitude": row.longitude,  # Legacy longitude.
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,  # ISO-8601 response serialization.
    }


def sensor_reading_row_to_dict(row) -> dict[str, Any]:
    row_data = row._mapping  # Access SQLAlchemy Row as a mapping for readable key-based extraction.
    return {
        "id": row_data["id"],  # Universal row id.
        "sensor_id": row_data["sensor_id"],  # Logical sensor identifier.
        "sensor_type": row_data["sensor_type"],  # Sensor family value.
        "device_id": row_data["device_id"],  # Physical source device identifier.
        "schema_version": row_data["schema_version"],  # Stored schema version.
        "latitude": row_data["latitude"],  # Flattened latitude.
        "longitude": row_data["longitude"],  # Flattened longitude.
        "altitude_m": row_data["altitude_m"],  # Flattened altitude.
        "area": row_data["area"],  # Flattened area.
        "road_segment_id": row_data["road_segment_id"],  # Flattened transport reference.
        "status": row_data["status"],  # Flattened status.
        "payload": row_data["payload"],  # JSONB payload block.
        "metadata": row_data["metadata"],  # JSONB metadata block.
        "recorded_at": row_data["recorded_at"].isoformat() if row_data["recorded_at"] else None,  # API-safe timestamp.
        "received_at": row_data["received_at"].isoformat() if row_data["received_at"] else None,  # API-safe timestamp.
        "created_at": row_data["created_at"].isoformat() if row_data["created_at"] else None,  # API-safe timestamp.
    }


def sensor_message_to_insert_values(sensor: SensorMessage) -> dict[str, Any]:
    return {
        "sensor_id": sensor.metadata.sensor_id,  # Flattened indexed field.
        "sensor_type": sensor.sensor_type.value,  # Flattened indexed field.
        "device_id": sensor.metadata.device_id,  # Flattened indexed field.
        "schema_version": sensor.schema_version,  # Persist schema version for compatibility.
        "latitude": sensor.location.latitude,  # Flattened location field.
        "longitude": sensor.location.longitude,  # Flattened location field.
        "altitude_m": sensor.location.altitude_m,  # Flattened optional field.
        "area": sensor.location.area,  # Flattened optional field.
        "road_segment_id": sensor.location.road_segment_id,  # Flattened optional field.
        "status": sensor.metadata.status,  # Flattened operational state.
        "payload": sensor.payload.model_dump(mode="json"),  # Keep payload flexible in JSONB.
        "metadata": sensor.metadata.model_dump(mode="json"),  # Keep full metadata in JSONB.
        "recorded_at": sensor.timestamp,  # Original sensor timestamp.
    }


@app.get("/")
def root():
    return {"message": "IoT Road Monitoring Store API is running"}


@app.post("/processed_agent_data/", response_model=ProcessedAgentDataInDB)
async def create_processed_agent_data(data: ProcessedAgentData):
    with engine.begin() as connection:
        stmt = (
            insert(processed_agent_data)
            .values(
                road_state=data.road_state,
                x=data.x,
                y=data.y,
                z=data.z,
                latitude=data.latitude,
                longitude=data.longitude,
                timestamp=data.timestamp,
            )
            .returning(processed_agent_data)
        )
        row = connection.execute(stmt).fetchone()

    created_item = processed_agent_data_row_to_dict(row)
    await send_legacy_data_to_subscribers(created_item)
    return created_item


@app.get("/processed_agent_data/{processed_agent_data_id}", response_model=ProcessedAgentDataInDB)
def read_processed_agent_data(processed_agent_data_id: int):
    with engine.begin() as connection:
        stmt = select(processed_agent_data).where(
            processed_agent_data.c.id == processed_agent_data_id
        )
        row = connection.execute(stmt).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")

    return processed_agent_data_row_to_dict(row)


@app.get("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
def list_processed_agent_data():
    with engine.begin() as connection:
        stmt = select(processed_agent_data).order_by(processed_agent_data.c.id)
        rows = connection.execute(stmt).fetchall()

    return [processed_agent_data_row_to_dict(row) for row in rows]


@app.put("/processed_agent_data/{processed_agent_data_id}", response_model=ProcessedAgentDataInDB)
def update_processed_agent_data(processed_agent_data_id: int, data: ProcessedAgentData):
    with engine.begin() as connection:
        stmt = (
            update(processed_agent_data)
            .where(processed_agent_data.c.id == processed_agent_data_id)
            .values(
                road_state=data.road_state,
                x=data.x,
                y=data.y,
                z=data.z,
                latitude=data.latitude,
                longitude=data.longitude,
                timestamp=data.timestamp,
            )
            .returning(processed_agent_data)
        )
        row = connection.execute(stmt).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")

    return processed_agent_data_row_to_dict(row)


@app.delete("/processed_agent_data/{processed_agent_data_id}", response_model=ProcessedAgentDataInDB)
def delete_processed_agent_data(processed_agent_data_id: int):
    with engine.begin() as connection:
        stmt = (
            delete(processed_agent_data)
            .where(processed_agent_data.c.id == processed_agent_data_id)
            .returning(processed_agent_data)
        )
        row = connection.execute(stmt).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="ProcessedAgentData not found")

    return processed_agent_data_row_to_dict(row)


@app.post("/sensor_readings", response_model=SensorReadingInDB)
async def create_sensor_reading(sensor_reading_raw: dict[str, Any] = Body(...)):
    sensor_reading = sensor_message_adapter.validate_python(sensor_reading_raw)  # Validate single SensorMessage before insert.
    with engine.begin() as connection:
        stmt = (
            insert(sensor_readings)
                .values(**sensor_message_to_insert_values(sensor_reading))  # Convert message into DB insert shape.
                .returning(sensor_readings)  # Ask PostgreSQL to return the inserted row.
            )
        row = connection.execute(stmt).fetchone()

    created_item = sensor_reading_row_to_dict(row)
    await send_sensor_reading_to_subscribers(created_item)
    return created_item


@app.post("/sensor_readings/batch", response_model=list[SensorReadingInDB])
async def create_sensor_readings_batch(sensor_readings_batch_raw: list[dict[str, Any]] = Body(...)):
    sensor_readings_batch = sensor_message_batch_adapter.validate_python(sensor_readings_batch_raw)  # Validate whole batch before writing.
    if not sensor_readings_batch:
        return []

    created_rows = []
    with engine.begin() as connection:
        for item in sensor_readings_batch:
            stmt = (
                insert(sensor_readings)
                .values(**sensor_message_to_insert_values(item))  # Prepare one insert per validated message.
                .returning(sensor_readings)  # Return inserted row for response/WebSocket.
            )
            created_rows.append(connection.execute(stmt).fetchone())

    created_items = [sensor_reading_row_to_dict(row) for row in created_rows]
    for item in created_items:
        await send_sensor_reading_to_subscribers(item)
    return created_items


@app.get("/sensor_readings", response_model=list[SensorReadingInDB])
def list_sensor_readings():
    with engine.begin() as connection:
        stmt = select(sensor_readings).order_by(sensor_readings.c.id)
        rows = connection.execute(stmt).fetchall()

    return [sensor_reading_row_to_dict(row) for row in rows]


@app.get("/sensor_readings/{sensor_reading_id}", response_model=SensorReadingInDB)
def read_sensor_reading(sensor_reading_id: int):
    with engine.begin() as connection:
        stmt = select(sensor_readings).where(sensor_readings.c.id == sensor_reading_id)
        row = connection.execute(stmt).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Sensor reading not found")

    return sensor_reading_row_to_dict(row)
