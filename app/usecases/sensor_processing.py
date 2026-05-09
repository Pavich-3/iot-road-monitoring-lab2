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
    peak_value = max(abs(x), abs(y), abs(z))

    if peak_value > 4.0:
        return "pothole"
    if peak_value > 1.5:
        return "roughness"
    return "normal"


def process_sensor_message(sensor_message: SensorMessage) -> SensorMessage:
    if sensor_message.sensor_type == SensorType.ROAD_SURFACE:
        assert isinstance(sensor_message, RoadSurfaceSensor)
        payload = sensor_message.payload
        road_state = classify_road_state(payload.x, payload.y, payload.z)
        return sensor_message.model_copy(
            update={
                "payload": RoadSurfacePayload(
                    x=payload.x,
                    y=payload.y,
                    z=payload.z,
                    road_state=road_state,
                )
            }
        )

    if sensor_message.sensor_type == SensorType.PARKING:
        assert isinstance(sensor_message, ParkingSensor)
        return sensor_message

    if sensor_message.sensor_type == SensorType.TRAFFIC_LIGHT:
        assert isinstance(sensor_message, TrafficLightSensor)
        return sensor_message

    return sensor_message
