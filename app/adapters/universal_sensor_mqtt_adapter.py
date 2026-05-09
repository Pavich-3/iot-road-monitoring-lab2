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
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.sensor_data_topic = sensor_data_topic
        self.sensor_readings_topic = sensor_readings_topic
        self.client = mqtt.Client()
        self.sensor_message_adapter = TypeAdapter(SensorMessage)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Universal sensor adapter connected to MQTT broker")
            self.client.subscribe(self.sensor_data_topic)
            logging.info("Subscribed to universal sensor topic: %s", self.sensor_data_topic)
        else:
            logging.error("Failed to connect universal sensor adapter to MQTT broker: %s", rc)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            sensor_message = self.sensor_message_adapter.validate_json(payload)
            processed_message = process_sensor_message(sensor_message)
            publish_result = self.client.publish(
                self.sensor_readings_topic,
                processed_message.model_dump_json(),
            )
            if publish_result[0] != 0:
                logging.error(
                    "Failed to publish processed universal sensor message to %s",
                    self.sensor_readings_topic,
                )
        except Exception as exc:
            logging.exception("Error processing universal sensor message: %s", exc)

    def connect(self) -> None:
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_host, self.broker_port, 60)

    def start(self) -> None:
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
