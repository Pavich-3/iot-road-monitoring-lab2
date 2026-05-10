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
        self._items: list[SensorMessage] = []  # Queue-like buffer used instead of Redis in the lab version.

    def add(self, item: SensorMessage) -> int:
        self._items.append(item)  # Append new validated message to the end of the buffer.
        return len(self._items)  # Return size for logging.

    def size(self) -> int:
        return len(self._items)  # Current number of buffered messages.

    def drain(self, count: int) -> list[SensorMessage]:
        batch = self._items[:count]  # Select the oldest items for batch sending.
        self._items = self._items[count:]  # Remove sent items from the in-memory buffer.
        return batch

    def push_front(self, items: list[SensorMessage]) -> None:
        self._items = items + self._items  # Put failed batch back to the front to preserve order.


class HubService:
    def __init__(self) -> None:
        self.enabled = HUB_ENABLED  # Allows enabling/disabling Hub from env without code changes.
        self.buffer_backend = HUB_BUFFER_BACKEND  # Exposed in config so memory can later be swapped for Redis.
        self.batch_size = HUB_BATCH_SIZE  # Number of messages to accumulate before POST to Store.
        self.store_batch_url = HUB_STORE_BATCH_URL  # Store endpoint used for batch delivery.
        self.topic = HUB_SENSOR_READINGS_TOPIC  # MQTT topic consumed by the Hub.
        self.client = mqtt.Client()  # Dedicated MQTT client for Hub subscriptions.
        self.sensor_message_adapter = TypeAdapter(SensorMessage)  # Re-validates messages before buffering.
        self.buffer = InMemorySensorBuffer()  # Lab-friendly buffering backend.

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Hub connected to MQTT broker")
            self.client.subscribe(self.topic)
            logging.info("Hub subscribed to topic: %s", self.topic)
        else:
            logging.error("Hub failed to connect to MQTT broker with code: %s", rc)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")  # Convert MQTT bytes into JSON string.
            logging.info("Hub received sensor reading from topic %s", msg.topic)

            sensor_message = self.sensor_message_adapter.validate_json(payload)  # Defend Store from malformed upstream messages.
            logging.info(
                "Hub validated sensor reading: sensor_id=%s type=%s",
                sensor_message.metadata.sensor_id,
                sensor_message.sensor_type.value,
            )

            buffer_size = self.buffer.add(sensor_message)  # Persist temporarily until batch threshold is reached.
            logging.info(
                "Hub added sensor reading to buffer: backend=%s size=%s",
                self.buffer_backend,
                buffer_size,
            )

            self.flush_if_needed()  # Try sending a batch immediately after every insert.
        except Exception as exc:
            logging.exception("Hub failed to process sensor reading: %s", exc)

    def connect(self) -> None:
        self.client.on_connect = self.on_connect  # Register MQTT connect callback.
        self.client.on_message = self.on_message  # Register MQTT message callback.
        self.client.connect(HUB_MQTT_HOST, HUB_MQTT_PORT, 60)  # Open MQTT connection.

    def start(self) -> None:
        if not self.enabled:
            logging.info("Hub service is disabled via HUB_ENABLED")
            return
        self.client.loop_start()  # Start MQTT networking loop in background thread.

    def stop(self) -> None:
        if not self.enabled:
            return
        self.client.loop_stop()  # Stop MQTT networking loop.
        self.client.disconnect()  # Disconnect from broker.

    def run_forever(self) -> None:
        if not self.enabled:
            logging.info("Hub service is disabled; exiting")
            return

        self.connect()
        self.start()
        try:
            while True:
                time.sleep(1)  # Keep process alive while MQTT callbacks run in the background.
        except KeyboardInterrupt:
            self.stop()  # Graceful manual shutdown for local runs.

    def flush_if_needed(self) -> None:
        if self.buffer.size() < self.batch_size:
            return  # Keep buffering until the configured threshold is reached.

        batch = self.buffer.drain(self.batch_size)  # Take one ready batch from the head of the buffer.
        payload = [item.model_dump(mode="json") for item in batch]  # Convert objects into HTTP-safe JSON payloads.

        try:
            response = requests.post(
                self.store_batch_url,  # Send to Store batch endpoint.
                json=payload,  # JSON array of SensorMessage documents.
                timeout=10,  # Short timeout is enough for the lab deployment.
            )
            logging.info("Hub sent batch to Store: size=%s", len(batch))
            logging.info("Store response status: %s", response.status_code)
            response.raise_for_status()  # Trigger retry path on any non-2xx response.
        except requests.RequestException as exc:
            self.buffer.push_front(batch)  # Preserve data if Store is temporarily unavailable.
            logging.exception("Hub failed to send batch to Store: %s", exc)
