import os


def try_parse_int(value: str):
    try:
        return int(value)
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
