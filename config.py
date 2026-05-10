import os


def try_parse_int(value: str):
    try:
        return int(value)
    except Exception:
        return None


def try_parse_float(value: str):
    try:
        return float(value)
    except Exception:
        return None


# Configuration for agent MQTT
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST") or "localhost"
MQTT_BROKER_PORT = try_parse_int(os.environ.get("MQTT_BROKER_PORT")) or 1883
MQTT_TOPIC = os.environ.get("MQTT_TOPIC") or "agent_data_topic"

# Configuration for hub MQTT
HUB_MQTT_BROKER_HOST = os.environ.get("HUB_MQTT_BROKER_HOST") or "localhost"
HUB_MQTT_BROKER_PORT = try_parse_int(os.environ.get("HUB_MQTT_BROKER_PORT")) or 1883
HUB_MQTT_TOPIC = os.environ.get("HUB_MQTT_TOPIC") or "processed_agent_data_topic"

# Configuration for the Hub
HUB_HOST = os.environ.get("HUB_HOST") or "localhost"
HUB_PORT = try_parse_int(os.environ.get("HUB_PORT")) or 12000
HUB_URL = f"http://{HUB_HOST}:{HUB_PORT}"

# Configuration for PostgreSQL / Store
POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or "localhost"
POSTGRES_PORT = try_parse_int(os.environ.get("POSTGRES_PORT")) or 5432
POSTGRES_USER = os.environ.get("POSTGRES_USER") or "user"
POSTGRES_PASSWORD = (
    os.environ.get("POSTGRES_PASSWORD")
    or os.environ.get("POSTGRES_PASS")
    or "pass"
)
POSTGRES_DB = os.environ.get("POSTGRES_DB") or "test_db"

STORE_HOST = os.environ.get("STORE_HOST") or "0.0.0.0"
STORE_PORT = try_parse_int(os.environ.get("STORE_PORT")) or 8000

# Configuration for universal sensor flow
SENSOR_DATA_TOPIC = os.environ.get("SENSOR_DATA_TOPIC") or "sensor_data_topic"
SENSOR_READINGS_TOPIC = os.environ.get("SENSOR_READINGS_TOPIC") or "sensor_readings_topic"
ENABLE_SYNTHETIC_SENSOR_GENERATOR = (
    os.environ.get("ENABLE_SYNTHETIC_SENSOR_GENERATOR", "true").lower() == "true"
)
SENSOR_GENERATOR_INTERVAL_SEC = (
    try_parse_float(os.environ.get("SENSOR_GENERATOR_INTERVAL_SEC")) or 2.0
)

# Configuration for isolated Hub service
HUB_ENABLED = os.environ.get("HUB_ENABLED", "true").lower() == "true"
HUB_MQTT_HOST = os.environ.get("HUB_MQTT_HOST") or MQTT_BROKER_HOST
HUB_MQTT_PORT = try_parse_int(os.environ.get("HUB_MQTT_PORT")) or MQTT_BROKER_PORT
HUB_SENSOR_READINGS_TOPIC = (
    os.environ.get("HUB_SENSOR_READINGS_TOPIC") or SENSOR_READINGS_TOPIC
)
HUB_STORE_BATCH_URL = (
    os.environ.get("HUB_STORE_BATCH_URL")
    or "http://store:8000/sensor_readings/batch"
)
HUB_BATCH_SIZE = try_parse_int(os.environ.get("HUB_BATCH_SIZE")) or 5
HUB_BUFFER_BACKEND = os.environ.get("HUB_BUFFER_BACKEND") or "memory"
