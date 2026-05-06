from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class CommandAction(str, Enum):
    MOVE           = "move"
    WORK           = "work"
    CHARGE         = "charge"
    STOP           = "stop"
    EMERGENCY_STOP = "emergency_stop"
    BID            = "bid"
    POLICY_UPDATE  = "policy_update"


class CommandStatus(str, Enum):
    PENDING   = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED  = "rejected"    # Safety Gate に弾かれた


class Command(BaseModel):
    # ── 識別 ──────────────────────────────────────────────────
    command_id:     str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    correlation_id: Optional[str] = None  # 関連 Event の event_id

    # ── 内容 ──────────────────────────────────────────────────
    target:       str             # agent_id または "all"（緊急停止時）
    action:       CommandAction
    parameters:   Dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "simulator"   # Layer1 では "city_os" / "human" になる

    # ── 時空間 ────────────────────────────────────────────────
    tick:      int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── 状態 ──────────────────────────────────────────────────
    status: CommandStatus = CommandStatus.PENDING

    # ── MQTT トピック ─────────────────────────────────────────
    @property
    def mqtt_topic(self) -> str:
        if self.action == CommandAction.EMERGENCY_STOP:
            return "safety/emergency_stop"
        return f"agent/{self.target}/command"


# ── ファクトリ関数（よく使うコマンドをすぐ作れるように）──────────
def cmd_move(target: str, x: int, y: int, tick: int = 0,
             requested_by: str = "simulator", correlation_id: Optional[str] = None) -> Command:
    return Command(target=target, action=CommandAction.MOVE,
                   parameters={"x": x, "y": y}, tick=tick,
                   requested_by=requested_by, correlation_id=correlation_id)

def cmd_work(target: str, task_id: str, tick: int = 0,
             requested_by: str = "simulator") -> Command:
    return Command(target=target, action=CommandAction.WORK,
                   parameters={"task_id": task_id}, tick=tick,
                   requested_by=requested_by)

def cmd_charge(target: str, tick: int = 0) -> Command:
    return Command(target=target, action=CommandAction.CHARGE,
                   parameters={}, tick=tick)

def cmd_stop(target: str, tick: int = 0, requested_by: str = "simulator") -> Command:
    return Command(target=target, action=CommandAction.STOP,
                   parameters={}, tick=tick, requested_by=requested_by)

def cmd_emergency_stop(requested_by: str = "safety_gate", tick: int = 0) -> Command:
    return Command(target="all", action=CommandAction.EMERGENCY_STOP,
                   parameters={"reason": "safety_violation"}, tick=tick,
                   requested_by=requested_by)
