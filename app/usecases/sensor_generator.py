from __future__ import annotations

import csv
import random
import threading
import time
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path

import paho.mqtt.client as mqtt

from app.shared.sensor_models import (
    EnvironmentalPayload,
    EnvironmentalSensor,
    ParkingPayload,
    ParkingSensor,
    RoadSurfacePayload,
    RoadSurfaceSensor,
    SensorLocation,
    SensorMetadata,
    SmartEnergySensor,
    SmartEnergyPayload,
    SensorType,
    TrafficLightPayload,
    TrafficLightSensor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = REPO_ROOT / "data" / "reference_samples"


class ReferenceBasedSyntheticFactory:
    def __init__(self, reference_dir: Path | None = None, seed: int = 42):
        self.reference_dir = reference_dir or REFERENCE_DIR
        self.rng = random.Random(seed)
        self.parking_rows = self._load_csv("transport_parking_reference.csv")
        self.traffic_light_rows = self._load_csv("traffic_light_reference.csv")
        self.environmental_rows = self._load_csv("environmental_reference.csv")
        self.energy_rows = self._load_csv("energy_reference.csv")
        self._parking_index = 0
        self._traffic_index = 0
        self._environmental_index = 0
        self._energy_index = 0

    def _load_csv(self, filename: str) -> list[dict[str, str]]:
        csv_path = self.reference_dir / filename
        with csv_path.open("r", encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))

    def _next_row(self, rows: list[dict[str, str]], index_attr: str) -> dict[str, str]:
        if not rows:
            raise ValueError("Reference dataset is empty.")
        index = getattr(self, index_attr)
        row = rows[index % len(rows)]
        setattr(self, index_attr, index + 1)
        return row

    def _noise(self, base: float, delta: float, minimum: float | None = None) -> float:
        value = base + self.rng.uniform(-delta, delta)
        if minimum is not None:
            value = max(minimum, value)
        return value

    def _jitter_location(self, latitude: float, longitude: float) -> tuple[float, float]:
        return (
            round(self._noise(latitude, 0.0002), 6),
            round(self._noise(longitude, 0.0002), 6),
        )

    @staticmethod
    def _base_metadata(sensor_id: str, device_id: str, tags: list[str]) -> SensorMetadata:
        return SensorMetadata(
            sensor_id=sensor_id,
            device_id=device_id,
            vendor="AcademicSynthetic",
            model="reference-noise-v1",
            sampling_interval_sec=2,
            status="active",
            tags=tags,
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def build_road_surface_sensor(self) -> RoadSurfaceSensor:
        latitude, longitude = self._jitter_location(50.4501, 30.5234)
        return RoadSurfaceSensor(
            sensor_type=SensorType.ROAD_SURFACE,
            metadata=self._base_metadata("road-sensor-01", "vehicle-01", ["road", "legacy"]),
            location=SensorLocation(
                latitude=latitude,
                longitude=longitude,
                road_segment_id="R-102",
            ),
            timestamp=datetime.now(timezone.utc),
            payload=RoadSurfacePayload(
                x=round(self._noise(2.0, 3.0), 2),
                y=round(self._noise(0.5, 2.5), 2),
                z=round(self._noise(2.5, 2.5, minimum=0.1), 2),
            ),
        )

    def build_parking_sensor(self) -> ParkingSensor:
        row = self._next_row(self.parking_rows, "_parking_index")
        total_slots = int(row["total_slots"])
        occupied_slots = int(
            min(
                total_slots,
                max(
                    0,
                    round(self._noise(float(row["occupied_slots"]), 4.0)),
                ),
            )
        )
        free_slots = total_slots - occupied_slots
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))
        return ParkingSensor(
            sensor_type=SensorType.PARKING,
            metadata=self._base_metadata("parking-01", "parking-camera-01", ["parking", row["area"].lower().replace(" ", "-")]),
            location=SensorLocation(
                latitude=latitude,
                longitude=longitude,
                area=row["area"],
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),
            payload=ParkingPayload(
                total_slots=total_slots,
                occupied_slots=occupied_slots,
                free_slots=free_slots,
                occupancy_rate=round(occupied_slots / total_slots, 3),
                barrier_state=self.rng.choice(["open", "closed"]),
                queue_length=self.rng.randint(0, 8),
            ),
        )

    def build_traffic_light_sensor(self) -> TrafficLightSensor:
        row = self._next_row(self.traffic_light_rows, "_traffic_index")
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))
        vehicle_count = int(max(0, round(self._noise(float(row["vehicle_count"]), 6.0))))
        cycle_time_sec = 60
        remaining_time_sec = self.rng.randint(0, cycle_time_sec)
        return TrafficLightSensor(
            sensor_type=SensorType.TRAFFIC_LIGHT,
            metadata=self._base_metadata(
                row["intersection_id"],
                f"controller-{row['intersection_id'].lower()}",
                ["intersection", "traffic-light"],
            ),
            location=SensorLocation(
                latitude=latitude,
                longitude=longitude,
                road_segment_id=row["intersection_id"],
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),
            payload=TrafficLightPayload(
                current_phase=row["current_phase"],
                vehicle_count=vehicle_count,
                remaining_time_sec=remaining_time_sec,
                cycle_time_sec=cycle_time_sec,
                pedestrian_request=row["pedestrian_request"].strip().lower() == "true",
                fault_detected=False,
            ),
        )

    def build_environmental_sensor(self) -> EnvironmentalSensor:
        row = self._next_row(self.environmental_rows, "_environmental_index")
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))
        return EnvironmentalSensor(
            sensor_type=SensorType.ENVIRONMENTAL,
            metadata=self._base_metadata("env-station-01", "env-station-01", ["environmental", "air-weather"]),
            location=SensorLocation(
                latitude=latitude,
                longitude=longitude,
                area="Environmental Zone",
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),
            payload=EnvironmentalPayload(
                temperature_c=round(self._noise(float(row["temperature_c"]), 1.5), 2),
                humidity_pct=round(self._noise(float(row["humidity_pct"]), 3.5, minimum=0.0), 2),
                pm2_5=round(self._noise(float(row["pm2_5"]), 2.0, minimum=0.0), 2),
                pm10=round(self._noise(float(row["pm10"]), 3.0, minimum=0.0), 2),
                co2_ppm=round(self._noise(float(row["co2_ppm"]), 35.0, minimum=250.0), 2),
            ),
        )

    def build_energy_sensor(self) -> SmartEnergySensor:
        row = self._next_row(self.energy_rows, "_energy_index")
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))
        return SmartEnergySensor(
            sensor_type=SensorType.SMART_GRID,
            metadata=self._base_metadata("grid-node-01", "transformer-01", ["energy", "smart-grid"]),
            location=SensorLocation(
                latitude=latitude,
                longitude=longitude,
                area="Grid Sector A",
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),
            payload=SmartEnergyPayload(
                voltage_v=round(self._noise(float(row["voltage_v"]), 4.0, minimum=0.0), 2),
                current_a=round(self._noise(float(row["current_a"]), 1.2, minimum=0.0), 2),
                power_kw=round(self._noise(float(row["power_kw"]), 2.5, minimum=0.0), 2),
                frequency_hz=round(self._noise(float(row["frequency_hz"]), 0.08, minimum=45.0), 2),
                transformer_temp_c=round(
                    self._noise(float(row["transformer_temp_c"]), 2.0, minimum=-20.0),
                    2,
                ),
                outage_detected=False,
            ),
        )


class SyntheticSensorGenerator:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        topic: str,
        interval_sec: float = 2.0,
        enabled: bool = False,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.interval_sec = interval_sec
        self.enabled = enabled
        self.client = mqtt.Client()
        self.factory = ReferenceBasedSyntheticFactory()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._generator_cycle = cycle(
            [
                self.factory.build_road_surface_sensor,
                self.factory.build_parking_sensor,
                self.factory.build_traffic_light_sensor,
                self.factory.build_environmental_sensor,
                self.factory.build_energy_sensor,
            ]
        )

    def start(self) -> None:
        if not self.enabled:
            return

        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.client.loop_stop()
        self.client.disconnect()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            builder = next(self._generator_cycle)
            message = builder()
            self.client.publish(self.topic, message.model_dump_json())
            time.sleep(self.interval_sec)
