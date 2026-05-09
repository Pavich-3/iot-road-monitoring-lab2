from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone
from itertools import cycle

import paho.mqtt.client as mqtt

from app.shared.sensor_models import (
    ParkingPayload,
    ParkingSensor,
    RoadSurfacePayload,
    RoadSurfaceSensor,
    SensorLocation,
    SensorMetadata,
    SensorType,
    TrafficLightPayload,
    TrafficLightSensor,
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
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._generator_cycle = cycle(
            [
                self._build_road_surface_sensor,
                self._build_parking_sensor,
                self._build_traffic_light_sensor,
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

    @staticmethod
    def _build_metadata(sensor_id: str, device_id: str, tags: list[str]) -> SensorMetadata:
        return SensorMetadata(
            sensor_id=sensor_id,
            device_id=device_id,
            vendor="SyntheticLab",
            model="v1",
            sampling_interval_sec=2,
            status="active",
            tags=tags,
        )

    @staticmethod
    def _build_timestamp() -> datetime:
        return datetime.now(timezone.utc)

    def _build_road_surface_sensor(self) -> RoadSurfaceSensor:
        return RoadSurfaceSensor(
            sensor_type=SensorType.ROAD_SURFACE,
            metadata=self._build_metadata("road-sensor-01", "vehicle-01", ["road", "legacy"]),
            location=SensorLocation(
                latitude=50.4501 + random.uniform(-0.001, 0.001),
                longitude=30.5234 + random.uniform(-0.001, 0.001),
                road_segment_id="R-102",
            ),
            timestamp=self._build_timestamp(),
            payload=RoadSurfacePayload(
                x=round(random.uniform(-5.0, 5.0), 2),
                y=round(random.uniform(-5.0, 5.0), 2),
                z=round(random.uniform(0.5, 5.5), 2),
            ),
        )

    def _build_parking_sensor(self) -> ParkingSensor:
        total_slots = 120
        occupied_slots = random.randint(40, 110)
        free_slots = total_slots - occupied_slots
        return ParkingSensor(
            sensor_type=SensorType.PARKING,
            metadata=self._build_metadata("parking-01", "parking-camera-01", ["parking", "zone-a"]),
            location=SensorLocation(
                latitude=50.4505,
                longitude=30.5238,
                area="Zone A",
            ),
            timestamp=self._build_timestamp(),
            payload=ParkingPayload(
                total_slots=total_slots,
                occupied_slots=occupied_slots,
                free_slots=free_slots,
                occupancy_rate=round(occupied_slots / total_slots, 3),
                barrier_state=random.choice(["open", "closed"]),
                queue_length=random.randint(0, 8),
            ),
        )

    def _build_traffic_light_sensor(self) -> TrafficLightSensor:
        cycle_time = 60
        remaining_time = random.randint(0, cycle_time)
        return TrafficLightSensor(
            sensor_type=SensorType.TRAFFIC_LIGHT,
            metadata=self._build_metadata("traffic-light-17", "controller-17", ["intersection"]),
            location=SensorLocation(
                latitude=50.4512,
                longitude=30.5219,
                road_segment_id="A17-B03",
            ),
            timestamp=self._build_timestamp(),
            payload=TrafficLightPayload(
                current_phase=random.choice(["red", "yellow", "green"]),
                remaining_time_sec=remaining_time,
                cycle_time_sec=cycle_time,
                pedestrian_request=random.choice([True, False]),
                fault_detected=False,
            ),
        )
