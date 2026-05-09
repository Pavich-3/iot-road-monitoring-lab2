from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SensorType(str, Enum):
    ROAD_SURFACE = "road_surface"
    PARKING = "parking"
    TRAFFIC_LIGHT = "traffic_light"
    WEATHER = "weather"
    SMART_GRID = "smart_grid"
    AIR_QUALITY = "air_quality"
    WATER_MONITORING = "water_monitoring"


class SensorLocation(BaseModel):
    latitude: float
    longitude: float
    altitude_m: float | None = None
    area: str | None = None
    road_segment_id: str | None = None


class SensorMetadata(BaseModel):
    sensor_id: str
    device_id: str
    gateway_id: str | None = None
    vendor: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    sampling_interval_sec: int | None = None
    status: Literal["active", "inactive", "maintenance"] = "active"
    tags: list[str] = Field(default_factory=list)


class SensorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoadSurfacePayload(SensorPayload):
    x: float
    y: float
    z: float
    road_state: str | None = None


class ParkingPayload(SensorPayload):
    total_slots: int
    occupied_slots: int
    free_slots: int
    occupancy_rate: float
    barrier_state: Literal["open", "closed", "unknown"] = "unknown"
    queue_length: int = 0

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.total_slots < 0 or self.occupied_slots < 0 or self.free_slots < 0:
            raise ValueError("Parking capacity values must be non-negative.")
        if self.occupied_slots + self.free_slots != self.total_slots:
            raise ValueError("occupied_slots + free_slots must equal total_slots.")
        if not 0.0 <= self.occupancy_rate <= 1.0:
            raise ValueError("occupancy_rate must be between 0.0 and 1.0.")
        return self


class TrafficLightPayload(SensorPayload):
    current_phase: Literal["red", "yellow", "green", "blinking"]
    remaining_time_sec: int
    cycle_time_sec: int
    pedestrian_request: bool = False
    fault_detected: bool = False

    @model_validator(mode="after")
    def validate_cycle(self):
        if self.remaining_time_sec < 0 or self.cycle_time_sec <= 0:
            raise ValueError("Traffic light timing values must be positive.")
        if self.remaining_time_sec > self.cycle_time_sec:
            raise ValueError("remaining_time_sec cannot exceed cycle_time_sec.")
        return self


class WeatherPayload(SensorPayload):
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    wind_speed_mps: float
    precipitation_mm: float = 0.0
    visibility_m: float | None = None


class SmartGridPayload(SensorPayload):
    voltage_v: float
    current_a: float
    power_kw: float
    frequency_hz: float
    transformer_temp_c: float | None = None
    outage_detected: bool = False


class AirQualityPayload(SensorPayload):
    pm2_5: float
    pm10: float
    co2_ppm: float
    no2_ppb: float | None = None
    aqi: int


class WaterMonitoringPayload(SensorPayload):
    ph: float
    turbidity_ntu: float
    flow_rate_l_s: float
    temperature_c: float | None = None
    dissolved_oxygen_mg_l: float | None = None
    contamination_detected: bool = False


class BaseSensor(BaseModel):
    schema_version: str = "1.0"
    sensor_type: SensorType
    metadata: SensorMetadata
    location: SensorLocation
    timestamp: datetime


class RoadSurfaceSensor(BaseSensor):
    sensor_type: Literal[SensorType.ROAD_SURFACE]
    payload: RoadSurfacePayload


class ParkingSensor(BaseSensor):
    sensor_type: Literal[SensorType.PARKING]
    payload: ParkingPayload


class TrafficLightSensor(BaseSensor):
    sensor_type: Literal[SensorType.TRAFFIC_LIGHT]
    payload: TrafficLightPayload


class WeatherSensor(BaseSensor):
    sensor_type: Literal[SensorType.WEATHER]
    payload: WeatherPayload


class SmartGridSensor(BaseSensor):
    sensor_type: Literal[SensorType.SMART_GRID]
    payload: SmartGridPayload


class AirQualitySensor(BaseSensor):
    sensor_type: Literal[SensorType.AIR_QUALITY]
    payload: AirQualityPayload


class WaterMonitoringSensor(BaseSensor):
    sensor_type: Literal[SensorType.WATER_MONITORING]
    payload: WaterMonitoringPayload


SensorMessage = Annotated[
    Union[
        RoadSurfaceSensor,
        ParkingSensor,
        TrafficLightSensor,
        WeatherSensor,
        SmartGridSensor,
        AirQualitySensor,
        WaterMonitoringSensor,
    ],
    Field(discriminator="sensor_type"),
]


class SensorReadingInDB(BaseModel):
    id: int
    sensor_id: str
    sensor_type: SensorType
    device_id: str
    schema_version: str
    latitude: float
    longitude: float
    altitude_m: float | None = None
    area: str | None = None
    road_segment_id: str | None = None
    status: str | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any]
    recorded_at: datetime
    received_at: datetime
    created_at: datetime
