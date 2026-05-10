from __future__ import annotations

import logging

import paho.mqtt.client as mqtt
from pydantic import TypeAdapter

from app.shared.sensor_models import SensorMessage
from app.usecases.sensor_processing import process_sensor_message


class UniversalSensorMQTTAdapter:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        sensor_data_topic: str,
        sensor_readings_topic: str,
    ):
        self.broker_host = broker_host  # MQTT host used for subscribing and publishing.
        self.broker_port = broker_port  # MQTT port used for subscribing and publishing.
        self.sensor_data_topic = sensor_data_topic  # Raw incoming universal sensor topic.
        self.sensor_readings_topic = sensor_readings_topic  # Outgoing processed topic consumed by Hub.
        self.client = mqtt.Client()  # Dedicated MQTT client for the universal flow.
        self.sensor_message_adapter = TypeAdapter(SensorMessage)  # Validates the full discriminated sensor union.

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Universal sensor adapter connected to MQTT broker")
            self.client.subscribe(self.sensor_data_topic)
            logging.info("Subscribed to universal sensor topic: %s", self.sensor_data_topic)
        else:
            logging.error("Failed to connect universal sensor adapter to MQTT broker: %s", rc)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")  # Convert MQTT bytes to JSON string.
            sensor_message = self.sensor_message_adapter.validate_json(payload)  # Parse and validate SensorMessage.
            processed_message = process_sensor_message(sensor_message)  # Apply lightweight edge logic.
            publish_result = self.client.publish(
                self.sensor_readings_topic,  # Send validated/enriched message to downstream topic.
                processed_message.model_dump_json(),  # Serialize back to JSON for MQTT transport.
            )
            if publish_result[0] != 0:
                logging.error(
                    "Failed to publish processed universal sensor message to %s",
                    self.sensor_readings_topic,
                )
        except Exception as exc:
            logging.exception("Error processing universal sensor message: %s", exc)

    def connect(self) -> None:
        self.client.on_connect = self.on_connect  # Register MQTT connect callback.
        self.client.on_message = self.on_message  # Register MQTT message callback.
        self.client.connect(self.broker_host, self.broker_port, 60)  # Open broker connection.

    def start(self) -> None:
        self.client.loop_start()  # Start MQTT networking thread.

    def stop(self) -> None:
        self.client.loop_stop()  # Stop MQTT networking thread.
        self.client.disconnect()  # Disconnect from broker cleanly.
