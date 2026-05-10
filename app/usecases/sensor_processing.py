from __future__ import annotations

from app.shared.sensor_models import (
    ParkingSensor,
    RoadSurfacePayload,
    RoadSurfaceSensor,
    SensorMessage,
    SensorType,
    TrafficLightSensor,
)


def classify_road_state(x: float, y: float, z: float) -> str:
    peak_value = max(abs(x), abs(y), abs(z))  # Legacy heuristic uses the strongest acceleration spike.

    if peak_value > 4.0:  # Strong impact usually represents a pothole.
        return "pothole"
    if peak_value > 1.5:  # Medium vibration usually represents road roughness.
        return "roughness"
    return "normal"  # Low vibration is treated as normal road surface.


def process_sensor_message(sensor_message: SensorMessage) -> SensorMessage:
    if sensor_message.sensor_type == SensorType.ROAD_SURFACE:
        assert isinstance(sensor_message, RoadSurfaceSensor)  # Narrow union type for safe payload access.
        payload = sensor_message.payload  # Extract current accelerometer-like values.
        road_state = classify_road_state(payload.x, payload.y, payload.z)  # Derive semantic road condition.
        return sensor_message.model_copy(
            update={
                "payload": RoadSurfacePayload(
                    x=payload.x,  # Preserve original x component.
                    y=payload.y,  # Preserve original y component.
                    z=payload.z,  # Preserve original z component.
                    road_state=road_state,  # Add derived state for downstream consumers.
                )
            }
        )

    if sensor_message.sensor_type == SensorType.PARKING:
        assert isinstance(sensor_message, ParkingSensor)  # Explicit narrowing kept for readability on defense.
        return sensor_message  # Parking messages are already valid after Pydantic validation.

    if sensor_message.sensor_type == SensorType.TRAFFIC_LIGHT:
        assert isinstance(sensor_message, TrafficLightSensor)  # Explicit narrowing kept for readability on defense.
        return sensor_message  # Traffic light messages use pass-through processing in this lab.

    return sensor_message  # Other supported types can flow through unchanged.
