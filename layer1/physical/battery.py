"""
Layer1 Battery — バッテリーモデル（容量劣化あり）。
充電サイクル毎に最大容量が微減する。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Battery:
    capacity_max: float = 100.0   # 最大容量 [Wh]（劣化で減少）
    level: float = 100.0          # 現在残量 [Wh]
    charge_cycles: int = 0        # 累計充電サイクル数
    _charging: bool = field(default=False, repr=False)  # 充電中フラグ

    # 物理定数
    DEGRADATION_PER_CYCLE: float = 0.005   # 1サイクルあたり 0.5% 劣化
    MIN_CAPACITY: float = 60.0             # 最低容量（劣化上限）
    CHARGE_RATE: float = 5.0              # 充電速度 [Wh/tick]

    def drain(self, amount: float, terrain_factor: float = 1.0) -> float:
        """地形係数を加味してエネルギーを消費する。消費量を返す。"""
        actual = amount * terrain_factor
        self.level = max(0.0, self.level - actual)
        self._charging = False
        return actual

    def charge(self, rate: float = None) -> bool:
        """充電する。満充電になったらサイクルを記録して True を返す。"""
        r = rate or self.CHARGE_RATE
        self.level = min(self.capacity_max, self.level + r)
        self._charging = True
        if self.level >= self.capacity_max:
            self._on_full_charge()
            return True
        return False

    def _on_full_charge(self) -> None:
        self.charge_cycles += 1
        degradation = self.DEGRADATION_PER_CYCLE * self.charge_cycles
        self.capacity_max = max(
            self.MIN_CAPACITY,
            100.0 * (1.0 - degradation),
        )

    @property
    def percentage(self) -> float:
        return round(self.level / self.capacity_max * 100, 1)

    def is_low(self, threshold: float = 20.0) -> bool:
        return self.percentage < threshold

    def is_critical(self, threshold: float = 10.0) -> bool:
        return self.percentage < threshold

    def is_dead(self) -> bool:
        return self.level <= 0.0

    def is_charging(self) -> bool:
        return self._charging

    def health(self) -> float:
        """バッテリー健全度（0〜1）。"""
        return round(self.capacity_max / 100.0, 3)
