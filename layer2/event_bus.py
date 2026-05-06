from __future__ import annotations
import json
import threading
import time
from typing import Callable, Dict, List, Optional
import paho.mqtt.client as mqtt
from layer0.schemas.event import Event
from layer0.schemas.command import Command


class EventBus:
    """Layer2-1: MQTT ベース Event Bus.

    全データは必ずここを経由する。直接通信は禁止。
    """

    BROKER_HOST = "localhost"
    BROKER_PORT = 1883
    KEEPALIVE   = 60

    def __init__(self, client_id: str = "hacs_event_bus"):
        self.client_id = client_id
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._handlers: Dict[str, List[Callable]] = {}
        self._connected = False
        self._published = 0
        self._received  = 0

    # ── 接続管理 ──────────────────────────────────────────────
    def connect(self, timeout: float = 5.0) -> bool:
        self._client.connect(self.BROKER_HOST, self.BROKER_PORT, self.KEEPALIVE)
        self._client.loop_start()
        deadline = time.time() + timeout
        while not self._connected and time.time() < deadline:
            time.sleep(0.05)
        return self._connected

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ── Publish ──────────────────────────────────────────────
    def publish_event(self, event: Event) -> None:
        payload = event.model_dump_json()
        self._client.publish(event.mqtt_topic, payload, qos=1)
        self._published += 1

    def publish_command(self, command: Command) -> None:
        payload = command.model_dump_json()
        self._client.publish(command.mqtt_topic, payload, qos=1)
        self._published += 1

    # ── Subscribe ────────────────────────────────────────────
    def subscribe(self, topic: str, handler: Callable[[str, dict], None]) -> None:
        if topic not in self._handlers:
            self._handlers[topic] = []
            self._client.subscribe(topic, qos=1)
        self._handlers[topic].append(handler)

    def subscribe_events(self, handler: Callable[[Event], None]) -> None:
        """全 city/ agent/ energy/ safety/ network/ トピックを一括購読."""
        wildcards = ["city/#", "agent/#", "energy/#", "safety/#", "network/#"]
        for w in wildcards:
            self.subscribe(w, lambda t, p, h=handler: h(_parse_event(p)))

    # ── 統計 ─────────────────────────────────────────────────
    def stats(self) -> dict:
        return {"published": self._published, "received": self._received,
                "connected": self._connected}

    # ── MQTT コールバック ─────────────────────────────────────
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self._connected = (reason_code == 0)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self._connected = False

    def _on_message(self, client, userdata, msg):
        self._received += 1
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            return
        topic = msg.topic
        for pattern, handlers in self._handlers.items():
            if _topic_match(pattern, topic):
                for h in handlers:
                    try:
                        h(topic, payload)
                    except Exception:
                        pass


def _parse_event(payload: dict) -> Optional[Event]:
    try:
        return Event(**payload)
    except Exception:
        return None


def _topic_match(pattern: str, topic: str) -> bool:
    """MQTT ワイルドカード (#, +) マッチング."""
    p_parts = pattern.split("/")
    t_parts = topic.split("/")
    for i, p in enumerate(p_parts):
        if p == "#":
            return True
        if i >= len(t_parts):
            return False
        if p != "+" and p != t_parts[i]:
            return False
    return len(p_parts) == len(t_parts)
