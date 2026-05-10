from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SensorType(str, Enum):
    ROAD_SURFACE = "road_surface"  # Legacy-compatible road monitoring sensor type.
    PARKING = "parking"  # Parking occupancy / access control sensor type.
    TRAFFIC_LIGHT = "traffic_light"  # Traffic signal controller / intersection sensor type.
    ENVIRONMENTAL = "environmental"  # Combined environmental monitoring type used in this lab.
    WEATHER = "weather"  # Reserved weather sensor type for future extension.
    SMART_GRID = "smart_grid"  # Electrical infrastructure / smart energy sensor type.
    AIR_QUALITY = "air_quality"  # Reserved dedicated air-quality sensor type.
    WATER_MONITORING = "water_monitoring"  # Reserved water monitoring sensor type.


class SensorLocation(BaseModel):
    latitude: float  # Main geospatial coordinate for mapping and storage.
    longitude: float  # Main geospatial coordinate for mapping and storage.
    altitude_m: float | None = None  # Optional altitude for 3D-aware sensors.
    area: str | None = None  # Human-readable zone, district or parking area name.
    road_segment_id: str | None = None  # Optional road/intersection identifier for transport sensors.


class SensorMetadata(BaseModel):
    sensor_id: str  # Logical identifier of the sensor in the monitored domain.
    device_id: str  # Physical or software device identifier that produced the message.
    gateway_id: str | None = None  # Optional upstream gateway identifier.
    vendor: str | None = None  # Vendor name for traceability.
    model: str | None = None  # Sensor or controller model name.
    firmware_version: str | None = None  # Optional software version for diagnostics.
    sampling_interval_sec: int | None = None  # Expected measurement interval in seconds.
    status: Literal["active", "inactive", "maintenance"] = "active"  # Device operational status.
    tags: list[str] = Field(default_factory=list)  # Flexible labels for grouping and filtering.


class SensorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Unknown payload keys are rejected during validation.


class RoadSurfacePayload(SensorPayload):
    x: float  # Acceleration component on X axis.
    y: float  # Acceleration component on Y axis.
    z: float  # Acceleration component on Z axis.
    road_state: str | None = None  # Derived road condition assigned during edge processing.


class ParkingPayload(SensorPayload):
    total_slots: int  # Parking capacity of the monitored zone.
    occupied_slots: int  # Number of slots currently occupied.
    free_slots: int  # Number of slots currently available.
    occupancy_rate: float  # Relative occupancy in the range 0.0..1.0.
    barrier_state: Literal["open", "closed", "unknown"] = "unknown"  # Entrance barrier state.
    queue_length: int = 0  # Approximate number of vehicles waiting to enter.

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.total_slots < 0 or self.occupied_slots < 0 or self.free_slots < 0:  # Negative capacity values are invalid.
            raise ValueError("Parking capacity values must be non-negative.")
        if self.occupied_slots + self.free_slots != self.total_slots:  # Parking capacity must balance arithmetically.
            raise ValueError("occupied_slots + free_slots must equal total_slots.")
        if not 0.0 <= self.occupancy_rate <= 1.0:  # Normalized occupancy cannot exceed logical bounds.
            raise ValueError("occupancy_rate must be between 0.0 and 1.0.")
        return self


class TrafficLightPayload(SensorPayload):
    current_phase: Literal["red", "yellow", "green", "blinking"]  # Current visible traffic signal phase.
    vehicle_count: int = 0  # Approximate approaching vehicle count from reference/open traffic data.
    remaining_time_sec: int  # Remaining time of the active phase.
    cycle_time_sec: int  # Full cycle length of the traffic light.
    pedestrian_request: bool = False  # Whether a crossing request is currently pending.
    fault_detected: bool = False  # Simplified health flag for the controller.

    @model_validator(mode="after")
    def validate_cycle(self):
        if self.remaining_time_sec < 0 or self.cycle_time_sec <= 0:  # Time values must stay physically meaningful.
            raise ValueError("Traffic light timing values must be positive.")
        if self.remaining_time_sec > self.cycle_time_sec:  # Remaining phase time cannot exceed full cycle duration.
            raise ValueError("remaining_time_sec cannot exceed cycle_time_sec.")
        if self.vehicle_count < 0:  # Negative traffic counts are invalid.
            raise ValueError("vehicle_count must be non-negative.")
        return self


class EnvironmentalPayload(SensorPayload):
    temperature_c: float  # Ambient air temperature in Celsius.
    humidity_pct: float  # Relative humidity in percent.
    pm2_5: float  # Fine particulate matter concentration.
    pm10: float  # Coarser particulate matter concentration.
    co2_ppm: float  # Carbon dioxide concentration.


class WeatherPayload(SensorPayload):
    temperature_c: float  # Atmospheric temperature.
    humidity_pct: float  # Atmospheric humidity.
    pressure_hpa: float  # Air pressure in hectopascals.
    wind_speed_mps: float  # Wind speed in meters per second.
    precipitation_mm: float = 0.0  # Precipitation amount.
    visibility_m: float | None = None  # Visibility distance.


class SmartGridPayload(SensorPayload):
    voltage_v: float  # Grid voltage.
    current_a: float  # Electrical current.
    power_kw: float  # Instantaneous active power.
    frequency_hz: float  # Grid frequency.
    transformer_temp_c: float | None = None  # Transformer operating temperature.
    outage_detected: bool = False  # Simplified outage flag.


class AirQualityPayload(SensorPayload):
    pm2_5: float  # Fine particulate matter concentration.
    pm10: float  # Coarse particulate matter concentration.
    co2_ppm: float  # Carbon dioxide concentration.
    no2_ppb: float | None = None  # Nitrogen dioxide concentration.
    aqi: int  # Air Quality Index.


class WaterMonitoringPayload(SensorPayload):
    ph: float  # Water acidity/alkalinity.
    turbidity_ntu: float  # Water turbidity in NTU.
    flow_rate_l_s: float  # Water flow rate.
    temperature_c: float | None = None  # Water temperature.
    dissolved_oxygen_mg_l: float | None = None  # Dissolved oxygen level.
    contamination_detected: bool = False  # Simplified contamination flag.


class BaseSensor(BaseModel):
    schema_version: str = "1.0"  # Payload schema version for forward compatibility.
    sensor_type: SensorType  # Declares which payload schema must be used.
    metadata: SensorMetadata  # Source/device metadata shared by all sensor families.
    location: SensorLocation  # Physical or logical location of the sensor.
    timestamp: datetime  # Measurement timestamp.


class RoadSurfaceSensor(BaseSensor):
    sensor_type: Literal[SensorType.ROAD_SURFACE]
    payload: RoadSurfacePayload


class ParkingSensor(BaseSensor):
    sensor_type: Literal[SensorType.PARKING]
    payload: ParkingPayload


class TrafficLightSensor(BaseSensor):
    sensor_type: Literal[SensorType.TRAFFIC_LIGHT]
    payload: TrafficLightPayload


class EnvironmentalSensor(BaseSensor):
    sensor_type: Literal[SensorType.ENVIRONMENTAL]
    payload: EnvironmentalPayload


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
        EnvironmentalSensor,
        WeatherSensor,
        SmartGridSensor,
        AirQualitySensor,
        WaterMonitoringSensor,
    ],
    Field(discriminator="sensor_type"),  # Pydantic chooses the concrete model from sensor_type.
]


class SensorReadingInDB(BaseModel):
    id: int  # Database primary key.
    sensor_id: str  # Persisted logical sensor identifier.
    sensor_type: SensorType  # Persisted sensor family.
    device_id: str  # Persisted source device identifier.
    schema_version: str  # Version of the stored schema.
    latitude: float  # Indexed latitude copied out of the location block.
    longitude: float  # Indexed longitude copied out of the location block.
    altitude_m: float | None = None  # Optional stored altitude.
    area: str | None = None  # Optional stored area label.
    road_segment_id: str | None = None  # Optional stored transport segment identifier.
    status: str | None = None  # Operational status copied from metadata.
    payload: dict[str, Any]  # Raw domain-specific payload stored as JSON-compatible dict.
    metadata: dict[str, Any]  # Full metadata stored as JSON-compatible dict.
    recorded_at: datetime  # Original measurement timestamp.
    received_at: datetime  # Store-side receive timestamp.
    created_at: datetime  # Store-side insertion timestamp.


SmartEnergyPayload = SmartGridPayload
SmartEnergySensor = SmartGridSensor
