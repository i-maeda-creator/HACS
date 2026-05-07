"""
Layer1 PhysicalRobot — Layer0 Agent の物理制約版。
・コマンドキュー（レイテンシあり）
・バッテリー劣化モデル
・地形による移動コスト
・ハードウェア障害モード
"""
from __future__ import annotations
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Optional, Tuple

from layer0.core.agent import AgentRole, AgentStatus
from layer0.schemas.command import Command, CommandAction
from layer1.physical.battery import Battery
from layer1.mapping.home_map import HomeMap


class FailureMode(str, Enum):
    NONE            = "none"
    MOTOR_STUCK     = "motor_stuck"      # 移動できない
    SENSOR_FAULT    = "sensor_fault"     # センサー値が信頼できない
    LOW_BATTERY_CUT = "low_battery_cut"  # 強制シャットダウン寸前


@dataclass
class PhysicalRobot:
    robot_id: str
    role: AgentRole
    x: int
    y: int
    battery: Battery = field(default_factory=Battery)
    status: AgentStatus = AgentStatus.IDLE
    target_x: Optional[int] = None
    target_y: Optional[int] = None
    assigned_task_id: Optional[str] = None

    # 物理制約
    command_latency: int = 2          # コマンド処理までの遅延 [ticks]
    failure_mode: FailureMode = FailureMode.NONE
    failure_prob: float = 0.001       # 毎 tick のランダム障害確率
    odometer: float = 0.0             # 総移動距離 [cells]

    # コマンドキュー: (Command, execute_at_tick)
    _cmd_queue: Deque[Tuple[Command, int]] = field(default_factory=deque, repr=False)

    # Layer0 互換定数
    MOVE_COST = 0.5
    WORK_COST = 2.0

    def receive_command(self, cmd: Command, current_tick: int) -> None:
        """コマンドをキューに追加（レイテンシ後に実行）。"""
        execute_at = current_tick + self.command_latency
        self._cmd_queue.append((cmd, execute_at))

    def process_commands(self, current_tick: int) -> Optional[Command]:
        """実行時刻に達したコマンドを一つ取り出して返す。"""
        if self._cmd_queue and self._cmd_queue[0][1] <= current_tick:
            cmd, _ = self._cmd_queue.popleft()
            return cmd
        return None

    def move_toward(self, tx: int, ty: int, home_map: HomeMap,
                    rng: random.Random) -> Tuple[int, int]:
        """
        目標に1ステップ近づく。地形コストでバッテリー消費。
        障害物があれば回避を試みる（簡易）。
        """
        if self.failure_mode == FailureMode.MOTOR_STUCK:
            return self.x, self.y

        dx = tx - self.x
        dy = ty - self.y

        # 主方向 → 次に直交方向を試みる
        candidates: list[Tuple[int, int]] = []
        if abs(dx) >= abs(dy) and dx != 0:
            nx, ny = self.x + (1 if dx > 0 else -1), self.y
            candidates = [(nx, ny), (self.x, self.y + (1 if dy > 0 else -1))]
        elif dy != 0:
            nx, ny = self.x, self.y + (1 if dy > 0 else -1)
            candidates = [(nx, ny), (self.x + (1 if dx > 0 else -1), self.y)]
        else:
            return self.x, self.y

        for (nx, ny) in candidates:
            if home_map.is_passable(nx, ny):
                factor = home_map.move_cost_factor(nx, ny)
                self.battery.drain(self.MOVE_COST, terrain_factor=factor)
                self.odometer += 1.0
                return nx, ny

        return self.x, self.y  # 動けなかった

    def work(self) -> None:
        self.battery.drain(self.WORK_COST)

    def try_charge(self, home_map: HomeMap) -> bool:
        """充電スポット上なら充電。"""
        if home_map.is_charger(self.x, self.y):
            self.battery.charge()
            self.status = AgentStatus.CHARGING
            return True
        return False

    def check_failure(self, rng: random.Random) -> FailureMode:
        """ランダム障害チェック。障害モードを返す。"""
        if self.battery.is_critical():
            self.failure_mode = FailureMode.LOW_BATTERY_CUT
        elif self.failure_mode == FailureMode.NONE and rng.random() < self.failure_prob:
            self.failure_mode = rng.choice([
                FailureMode.MOTOR_STUCK,
                FailureMode.SENSOR_FAULT,
            ])
        # 障害回復（バッテリー回復後）
        if self.failure_mode == FailureMode.LOW_BATTERY_CUT and not self.battery.is_critical():
            self.failure_mode = FailureMode.NONE
        return self.failure_mode

    def is_alive(self) -> bool:
        return not self.battery.is_dead()

    def needs_charge(self) -> bool:
        return self.battery.is_low()

    def snapshot(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "role": self.role.value,
            "x": self.x,
            "y": self.y,
            "battery_pct": self.battery.percentage,
            "battery_health": self.battery.health(),
            "charge_cycles": self.battery.charge_cycles,
            "status": self.status.value,
            "failure_mode": self.failure_mode.value,
            "odometer": round(self.odometer, 1),
        }
