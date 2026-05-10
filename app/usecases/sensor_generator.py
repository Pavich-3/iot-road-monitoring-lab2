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
        self.reference_dir = reference_dir or REFERENCE_DIR  # Folder with lightweight academic open-data samples.
        self.rng = random.Random(seed)  # Fixed seed gives reproducible synthetic datasets for demos.
        self.parking_rows = self._load_csv("transport_parking_reference.csv")  # Transport/parking baseline rows.
        self.traffic_light_rows = self._load_csv("traffic_light_reference.csv")  # Traffic control baseline rows.
        self.environmental_rows = self._load_csv("environmental_reference.csv")  # Environmental baseline rows.
        self.energy_rows = self._load_csv("energy_reference.csv")  # Energy/grid baseline rows.
        self._parking_index = 0  # Manual cursor used to cycle reference rows.
        self._traffic_index = 0  # Manual cursor used to cycle reference rows.
        self._environmental_index = 0  # Manual cursor used to cycle reference rows.
        self._energy_index = 0  # Manual cursor used to cycle reference rows.

    def _load_csv(self, filename: str) -> list[dict[str, str]]:
        csv_path = self.reference_dir / filename  # Resolve reference file relative to repo data folder.
        with csv_path.open("r", encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))  # Load into memory because reference samples are intentionally tiny.

    def _next_row(self, rows: list[dict[str, str]], index_attr: str) -> dict[str, str]:
        if not rows:
            raise ValueError("Reference dataset is empty.")
        index = getattr(self, index_attr)  # Read current position in the selected sample list.
        row = rows[index % len(rows)]  # Wrap around when requested output is larger than the sample file.
        setattr(self, index_attr, index + 1)  # Advance cyclic cursor for the next generated record.
        return row

    def _noise(self, base: float, delta: float, minimum: float | None = None) -> float:
        value = base + self.rng.uniform(-delta, delta)  # Add bounded random variation around reference value.
        if minimum is not None:
            value = max(minimum, value)  # Prevent impossible negative or too-small values.
        return value

    def _jitter_location(self, latitude: float, longitude: float) -> tuple[float, float]:
        return (
            round(self._noise(latitude, 0.0002), 6),  # Slightly vary latitude within a realistic local area.
            round(self._noise(longitude, 0.0002), 6),  # Slightly vary longitude within a realistic local area.
        )

    @staticmethod
    def _base_metadata(sensor_id: str, device_id: str, tags: list[str]) -> SensorMetadata:
        return SensorMetadata(
            sensor_id=sensor_id,  # Domain-specific logical sensor identifier.
            device_id=device_id,  # Synthetic physical/controller device identifier.
            vendor="AcademicSynthetic",  # Marks data as generated for laboratory work.
            model="reference-noise-v1",  # Documents the synthetic generation approach.
            sampling_interval_sec=2,  # Default synthetic sampling interval.
            status="active",  # Synthetic sensors are treated as operational.
            tags=tags,  # Tags help route or filter generated messages by domain.
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))  # Normalize UTC strings for Pydantic-compatible datetimes.

    def build_road_surface_sensor(self) -> RoadSurfaceSensor:
        latitude, longitude = self._jitter_location(50.4501, 30.5234)  # Base location near the monitored route.
        return RoadSurfaceSensor(
            sensor_type=SensorType.ROAD_SURFACE,  # Legacy-compatible transport sensor family.
            metadata=self._base_metadata("road-sensor-01", "vehicle-01", ["road", "legacy"]),  # Reused in backward-compatible flow.
            location=SensorLocation(
                latitude=latitude,  # Slightly perturbed location.
                longitude=longitude,  # Slightly perturbed location.
                road_segment_id="R-102",  # Fixed segment id for road monitoring examples.
            ),
            timestamp=datetime.now(timezone.utc),  # Generated at current time because it is purely synthetic.
            payload=RoadSurfacePayload(
                x=round(self._noise(2.0, 3.0), 2),  # Simulated X-axis acceleration.
                y=round(self._noise(0.5, 2.5), 2),  # Simulated Y-axis acceleration.
                z=round(self._noise(2.5, 2.5, minimum=0.1), 2),  # Simulated Z-axis acceleration.
            ),
        )

    def build_parking_sensor(self) -> ParkingSensor:
        row = self._next_row(self.parking_rows, "_parking_index")  # Take the next transport reference row.
        total_slots = int(row["total_slots"])  # Capacity comes directly from the reference sample.
        occupied_slots = int(
            min(
                total_slots,  # Occupied slots cannot exceed physical capacity.
                max(
                    0,  # Occupied slots cannot be negative.
                    round(self._noise(float(row["occupied_slots"]), 4.0)),  # Add small occupancy variation around the reference value.
                ),
            )
        )
        free_slots = total_slots - occupied_slots  # Keep arithmetic consistency between capacity and occupancy.
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))  # Vary sensor coordinates slightly.
        return ParkingSensor(
            sensor_type=SensorType.PARKING,  # Universal parking sensor type.
            metadata=self._base_metadata("parking-01", "parking-camera-01", ["parking", row["area"].lower().replace(" ", "-")]),  # Tags reflect parking zone.
            location=SensorLocation(
                latitude=latitude,  # Slightly perturbed location.
                longitude=longitude,  # Slightly perturbed location.
                area=row["area"],  # Preserve area name from reference data.
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),  # Reuse temporal structure from the reference row.
            payload=ParkingPayload(
                total_slots=total_slots,  # Persist reference capacity.
                occupied_slots=occupied_slots,  # Persist noise-adjusted occupancy.
                free_slots=free_slots,  # Derived from total_slots and occupied_slots.
                occupancy_rate=round(occupied_slots / total_slots, 3),  # Derived normalized occupancy.
                barrier_state=self.rng.choice(["open", "closed"]),  # Simulated barrier state.
                queue_length=self.rng.randint(0, 8),  # Simulated queue length.
            ),
        )

    def build_traffic_light_sensor(self) -> TrafficLightSensor:
        row = self._next_row(self.traffic_light_rows, "_traffic_index")  # Take the next traffic-control reference row.
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))  # Slight coordinate noise.
        vehicle_count = int(max(0, round(self._noise(float(row["vehicle_count"]), 6.0))))  # Simulate varying traffic volume.
        cycle_time_sec = 60  # Fixed simple cycle for the laboratory version.
        remaining_time_sec = self.rng.randint(0, cycle_time_sec)  # Simulate current position inside the cycle.
        return TrafficLightSensor(
            sensor_type=SensorType.TRAFFIC_LIGHT,  # Universal traffic light sensor type.
            metadata=self._base_metadata(
                row["intersection_id"],  # Reference intersection id becomes sensor id.
                f"controller-{row['intersection_id'].lower()}",  # Derived controller device id.
                ["intersection", "traffic-light"],  # Domain tags for filtering.
            ),
            location=SensorLocation(
                latitude=latitude,  # Slightly perturbed location.
                longitude=longitude,  # Slightly perturbed location.
                road_segment_id=row["intersection_id"],  # Logical relation to the controlled road node.
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),  # Preserve temporal structure from reference sample.
            payload=TrafficLightPayload(
                current_phase=row["current_phase"],  # Preserve observed phase from reference data.
                vehicle_count=vehicle_count,  # Use noise-adjusted traffic load.
                remaining_time_sec=remaining_time_sec,  # Simulated remaining time.
                cycle_time_sec=cycle_time_sec,  # Fixed cycle length.
                pedestrian_request=row["pedestrian_request"].strip().lower() == "true",  # Convert CSV string to boolean.
                fault_detected=False,  # Keep the academic example in nominal state.
            ),
        )

    def build_environmental_sensor(self) -> EnvironmentalSensor:
        row = self._next_row(self.environmental_rows, "_environmental_index")  # Take the next environmental reference row.
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))  # Slight coordinate noise.
        return EnvironmentalSensor(
            sensor_type=SensorType.ENVIRONMENTAL,  # Combined environmental monitoring type.
            metadata=self._base_metadata("env-station-01", "env-station-01", ["environmental", "air-weather"]),  # Environmental station identity.
            location=SensorLocation(
                latitude=latitude,  # Slightly perturbed location.
                longitude=longitude,  # Slightly perturbed location.
                area="Environmental Zone",  # Simple human-readable zone label.
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),  # Preserve timestamp shape from reference data.
            payload=EnvironmentalPayload(
                temperature_c=round(self._noise(float(row["temperature_c"]), 1.5), 2),  # Temperature noise around open-data baseline.
                humidity_pct=round(self._noise(float(row["humidity_pct"]), 3.5, minimum=0.0), 2),  # Humidity noise around open-data baseline.
                pm2_5=round(self._noise(float(row["pm2_5"]), 2.0, minimum=0.0), 2),  # PM2.5 noise around open-data baseline.
                pm10=round(self._noise(float(row["pm10"]), 3.0, minimum=0.0), 2),  # PM10 noise around open-data baseline.
                co2_ppm=round(self._noise(float(row["co2_ppm"]), 35.0, minimum=250.0), 2),  # CO2 noise around open-data baseline.
            ),
        )

    def build_energy_sensor(self) -> SmartEnergySensor:
        row = self._next_row(self.energy_rows, "_energy_index")  # Take the next energy reference row.
        latitude, longitude = self._jitter_location(float(row["latitude"]), float(row["longitude"]))  # Slight coordinate noise.
        return SmartEnergySensor(
            sensor_type=SensorType.SMART_GRID,  # Universal smart-grid sensor type.
            metadata=self._base_metadata("grid-node-01", "transformer-01", ["energy", "smart-grid"]),  # Grid device identity.
            location=SensorLocation(
                latitude=latitude,  # Slightly perturbed location.
                longitude=longitude,  # Slightly perturbed location.
                area="Grid Sector A",  # Human-readable electrical zone label.
            ),
            timestamp=self._parse_timestamp(row["timestamp"]),  # Preserve temporal structure from reference data.
            payload=SmartEnergyPayload(
                voltage_v=round(self._noise(float(row["voltage_v"]), 4.0, minimum=0.0), 2),  # Voltage noise around open-data baseline.
                current_a=round(self._noise(float(row["current_a"]), 1.2, minimum=0.0), 2),  # Current noise around open-data baseline.
                power_kw=round(self._noise(float(row["power_kw"]), 2.5, minimum=0.0), 2),  # Power noise around open-data baseline.
                frequency_hz=round(self._noise(float(row["frequency_hz"]), 0.08, minimum=45.0), 2),  # Frequency noise around grid nominal value.
                transformer_temp_c=round(
                    self._noise(float(row["transformer_temp_c"]), 2.0, minimum=-20.0),  # Temperature noise around transformer baseline.
                    2,
                ),
                outage_detected=False,  # Synthetic normal-operation state.
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
        self.broker_host = broker_host  # MQTT broker host for publishing synthetic messages.
        self.broker_port = broker_port  # MQTT broker port for publishing synthetic messages.
        self.topic = topic  # Raw universal topic used by the Edge adapter.
        self.interval_sec = interval_sec  # Delay between synthetic MQTT messages.
        self.enabled = enabled  # Allows disabling generator without removing code.
        self.client = mqtt.Client()  # Separate MQTT client used only for publishing.
        self.factory = ReferenceBasedSyntheticFactory()  # Reference-based sensor message builder.
        self._stop_event = threading.Event()  # Cooperative stop flag for the background thread.
        self._thread: threading.Thread | None = None  # Background publishing thread handle.
        self._generator_cycle = cycle(
            [
                self.factory.build_road_surface_sensor,  # Legacy-compatible road message.
                self.factory.build_parking_sensor,  # Transport / parking message.
                self.factory.build_traffic_light_sensor,  # Traffic control message.
                self.factory.build_environmental_sensor,  # Environmental message.
                self.factory.build_energy_sensor,  # Energy / smart-grid message.
            ]
        )

    def start(self) -> None:
        if not self.enabled:
            return

        self.client.connect(self.broker_host, self.broker_port, 60)  # Open MQTT connection once before the loop starts.
        self.client.loop_start()  # Start MQTT networking in the background.
        self._thread = threading.Thread(target=self._run, daemon=True)  # Separate thread avoids blocking main edge loop.
        self._thread.start()  # Start continuous synthetic publishing.

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()  # Signal background thread to stop.
        if self._thread is not None:
            self._thread.join(timeout=2)  # Wait briefly for graceful shutdown.
        self.client.loop_stop()  # Stop MQTT networking loop.
        self.client.disconnect()  # Close broker connection cleanly.

    def _run(self) -> None:
        while not self._stop_event.is_set():
            builder = next(self._generator_cycle)  # Select next sensor family in round-robin order.
            message = builder()  # Build a validated SensorMessage object.
            self.client.publish(self.topic, message.model_dump_json())  # Publish ready JSON straight to MQTT.
            time.sleep(self.interval_sec)  # Control synthetic data rate.
