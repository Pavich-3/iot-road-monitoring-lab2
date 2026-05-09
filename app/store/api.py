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
    Column("id", BigInteger, primary_key=True, index=True),
    Column("sensor_id", String, nullable=False),
    Column("sensor_type", String, nullable=False),
    Column("device_id", String, nullable=False),
    Column("schema_version", String, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("altitude_m", Float),
    Column("area", String),
    Column("road_segment_id", String),
    Column("status", String),
    Column("payload", JSONB, nullable=False),
    Column("metadata", JSONB, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
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
    metadata.create_all(engine)


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
        "id": row.id,
        "road_state": row.road_state,
        "x": row.x,
        "y": row.y,
        "z": row.z,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
    }


def sensor_reading_row_to_dict(row) -> dict[str, Any]:
    row_data = row._mapping
    return {
        "id": row_data["id"],
        "sensor_id": row_data["sensor_id"],
        "sensor_type": row_data["sensor_type"],
        "device_id": row_data["device_id"],
        "schema_version": row_data["schema_version"],
        "latitude": row_data["latitude"],
        "longitude": row_data["longitude"],
        "altitude_m": row_data["altitude_m"],
        "area": row_data["area"],
        "road_segment_id": row_data["road_segment_id"],
        "status": row_data["status"],
        "payload": row_data["payload"],
        "metadata": row_data["metadata"],
        "recorded_at": row_data["recorded_at"].isoformat() if row_data["recorded_at"] else None,
        "received_at": row_data["received_at"].isoformat() if row_data["received_at"] else None,
        "created_at": row_data["created_at"].isoformat() if row_data["created_at"] else None,
    }


def sensor_message_to_insert_values(sensor: SensorMessage) -> dict[str, Any]:
    return {
        "sensor_id": sensor.metadata.sensor_id,
        "sensor_type": sensor.sensor_type.value,
        "device_id": sensor.metadata.device_id,
        "schema_version": sensor.schema_version,
        "latitude": sensor.location.latitude,
        "longitude": sensor.location.longitude,
        "altitude_m": sensor.location.altitude_m,
        "area": sensor.location.area,
        "road_segment_id": sensor.location.road_segment_id,
        "status": sensor.metadata.status,
        "payload": sensor.payload.model_dump(mode="json"),
        "metadata": sensor.metadata.model_dump(mode="json"),
        "recorded_at": sensor.timestamp,
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
    sensor_reading = sensor_message_adapter.validate_python(sensor_reading_raw)
    with engine.begin() as connection:
        stmt = (
            insert(sensor_readings)
            .values(**sensor_message_to_insert_values(sensor_reading))
            .returning(sensor_readings)
        )
        row = connection.execute(stmt).fetchone()

    created_item = sensor_reading_row_to_dict(row)
    await send_sensor_reading_to_subscribers(created_item)
    return created_item


@app.post("/sensor_readings/batch", response_model=list[SensorReadingInDB])
async def create_sensor_readings_batch(sensor_readings_batch_raw: list[dict[str, Any]] = Body(...)):
    sensor_readings_batch = sensor_message_batch_adapter.validate_python(sensor_readings_batch_raw)
    if not sensor_readings_batch:
        return []

    created_rows = []
    with engine.begin() as connection:
        for item in sensor_readings_batch:
            stmt = (
                insert(sensor_readings)
                .values(**sensor_message_to_insert_values(item))
                .returning(sensor_readings)
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
