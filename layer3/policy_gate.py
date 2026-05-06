from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from layer0.schemas.command import Command, CommandAction

if TYPE_CHECKING:
    from layer0.engine.simulator import Simulator


@dataclass
class ValidationResult:
    allowed: bool
    reason:  str = ""

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(allowed=True)

    @classmethod
    def reject(cls, reason: str) -> "ValidationResult":
        return cls(allowed=False, reason=reason)


class PolicyGate:
    """コマンドが Policy / Safety ルールに違反しないか検証する。"""

    def validate(self, command: Command, sim: "Simulator") -> ValidationResult:
        # 緊急停止は常に許可
        if command.action == CommandAction.EMERGENCY_STOP:
            return ValidationResult.ok()

        # 緊急状態中は STOP のみ許可
        if sim.safety.is_emergency_active():
            if command.action != CommandAction.STOP:
                return ValidationResult.reject("緊急状態中は STOP のみ許可")

        # エージェント存在確認 (target="all" の緊急停止は除く)
        if command.target != "all":
            agent = sim._get_agent(command.target)
            if agent is None:
                return ValidationResult.reject(f"エージェント {command.target} が存在しない")
        else:
            agent = None

        # MOVE コマンド: 移動先の通行可能チェック
        if command.action == CommandAction.MOVE:
            x = command.parameters.get("x")
            y = command.parameters.get("y")
            if x is None or y is None:
                return ValidationResult.reject("MOVE コマンドに座標がない")
            if not sim.world.is_passable(int(x), int(y)):
                return ValidationResult.reject(f"座標 ({x},{y}) は通行不可")

        # WORK コマンド: エネルギー確認
        if command.action == CommandAction.WORK and agent is not None:
            if agent.energy < 5.0:
                return ValidationResult.reject(f"{command.target} エネルギー不足 ({agent.energy:.1f})")

        return ValidationResult.ok()
