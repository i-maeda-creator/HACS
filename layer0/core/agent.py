from __future__ import annotations
from enum import Enum
from typing import Optional, Tuple
from dataclasses import dataclass


class AgentRole(str, Enum):
    WORKER = "Worker"
    GUARDIAN = "Guardian"
    TRADER = "Trader"
    OBSERVER = "Observer"
    GOVERNOR = "Governor"
    MEDIC = "Medic"
    ARCHITECT = "Architect"


class AgentStatus(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    WORKING = "working"
    CHARGING = "charging"


@dataclass
class Agent:
    agent_id: str
    role: AgentRole
    x: int
    y: int
    energy: float = 100.0
    balance: float = 50.0
    status: AgentStatus = AgentStatus.IDLE
    target_x: Optional[int] = None
    target_y: Optional[int] = None
    assigned_task_id: Optional[str] = None
    experience: int = 0          # 完了タスク数（記憶資本 — Memory Marketで売買可能）
    memory_boost: int = 0        # 買った記憶が有効な残りtick数（入札ボーナス付与）
    expires_at: Optional[int] = None  # None=永続 / int=そのtickに時間軸から消滅（CHRONO用）
    arrested_until: Optional[int] = None  # None=自由 / int=そのtickまで逮捕・行動不能

    MOVE_COST = 0.5
    WORK_COST = 2.0
    CHARGE_RATE = 5.0
    MAX_ENERGY = 100.0

    def move_toward(self, tx: int, ty: int) -> Tuple[int, int]:
        dx = tx - self.x
        dy = ty - self.y
        if abs(dx) >= abs(dy) and dx != 0:
            return self.x + (1 if dx > 0 else -1), self.y
        elif dy != 0:
            return self.x, self.y + (1 if dy > 0 else -1)
        return self.x, self.y

    def spend_energy(self, amount: float) -> None:
        self.energy = max(0.0, self.energy - amount)

    def charge(self) -> None:
        self.energy = min(self.MAX_ENERGY, self.energy + self.CHARGE_RATE)

    def is_alive(self) -> bool:
        return self.energy > 0

    def needs_charge(self) -> bool:
        return self.energy < 20.0
