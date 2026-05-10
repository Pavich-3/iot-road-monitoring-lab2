from __future__ import annotations

import logging
import time
from typing import Any

import paho.mqtt.client as mqtt
import requests
from pydantic import TypeAdapter

from app.shared.sensor_models import SensorMessage
from config import (
    HUB_BATCH_SIZE,
    HUB_BUFFER_BACKEND,
    HUB_ENABLED,
    HUB_MQTT_HOST,
    HUB_MQTT_PORT,
    HUB_SENSOR_READINGS_TOPIC,
    HUB_STORE_BATCH_URL,
)


class InMemorySensorBuffer:
    def __init__(self) -> None:
        self._items: list[SensorMessage] = []

    def add(self, item: SensorMessage) -> int:
        self._items.append(item)
        return len(self._items)

    def size(self) -> int:
        return len(self._items)

    def drain(self, count: int) -> list[SensorMessage]:
        batch = self._items[:count]
        self._items = self._items[count:]
        return batch

    def push_front(self, items: list[SensorMessage]) -> None:
        self._items = items + self._items


class HubService:
    def __init__(self) -> None:
        self.enabled = HUB_ENABLED
        self.buffer_backend = HUB_BUFFER_BACKEND
        self.batch_size = HUB_BATCH_SIZE
        self.store_batch_url = HUB_STORE_BATCH_URL
        self.topic = HUB_SENSOR_READINGS_TOPIC
        self.client = mqtt.Client()
        self.sensor_message_adapter = TypeAdapter(SensorMessage)
        self.buffer = InMemorySensorBuffer()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Hub connected to MQTT broker")
            self.client.subscribe(self.topic)
            logging.info("Hub subscribed to topic: %s", self.topic)
        else:
            logging.error("Hub failed to connect to MQTT broker with code: %s", rc)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            logging.info("Hub received sensor reading from topic %s", msg.topic)

            sensor_message = self.sensor_message_adapter.validate_json(payload)
            logging.info(
                "Hub validated sensor reading: sensor_id=%s type=%s",
                sensor_message.metadata.sensor_id,
                sensor_message.sensor_type.value,
            )

            buffer_size = self.buffer.add(sensor_message)
            logging.info(
                "Hub added sensor reading to buffer: backend=%s size=%s",
                self.buffer_backend,
                buffer_size,
            )

            self.flush_if_needed()
        except Exception as exc:
            logging.exception("Hub failed to process sensor reading: %s", exc)

    def connect(self) -> None:
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(HUB_MQTT_HOST, HUB_MQTT_PORT, 60)

    def start(self) -> None:
        if not self.enabled:
            logging.info("Hub service is disabled via HUB_ENABLED")
            return
        self.client.loop_start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self.client.loop_stop()
        self.client.disconnect()

    def run_forever(self) -> None:
        if not self.enabled:
            logging.info("Hub service is disabled; exiting")
            return

        self.connect()
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def flush_if_needed(self) -> None:
        if self.buffer.size() < self.batch_size:
            return

        batch = self.buffer.drain(self.batch_size)
        payload = [item.model_dump(mode="json") for item in batch]

        try:
            response = requests.post(
                self.store_batch_url,
                json=payload,
                timeout=10,
            )
            logging.info("Hub sent batch to Store: size=%s", len(batch))
            logging.info("Store response status: %s", response.status_code)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.buffer.push_front(batch)
            logging.exception("Hub failed to send batch to Store: %s", exc)

