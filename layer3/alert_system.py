from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from layer0.schemas.state import StateSnapshot


class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    level:    AlertLevel
    category: str          # ENERGY | ECONOMY | TASK | SAFETY | GOVERNANCE
    message:  str
    tick:     int
    agent_id: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        return self.level == AlertLevel.CRITICAL


class AlertSystem:
    """毎 tick のスナップショットを監視してアラートを生成する。"""

    ENERGY_WARN     = 15.0
    ENERGY_CRIT     = 5.0
    TASK_BACKLOG    = 6      # open tasks が この数を超えると WARNING
    GINI_WARN       = 0.30
    GINI_CRIT       = 0.50
    WORKER_IDLE_WARN = 0.60  # Worker の 60% 以上が未収入

    def __init__(self):
        self.history: List[Alert] = []
        self._emergency_level: int = 0  # 0=Normal … 3=Emergency

    def check(self, snap: StateSnapshot) -> List[Alert]:
        alerts: List[Alert] = []
        tick = snap.tick

        # ── エネルギー ──────────────────────────────────────────
        for a in snap.agents:
            if a.energy <= self.ENERGY_CRIT:
                alerts.append(Alert(AlertLevel.CRITICAL, "ENERGY",
                                    f"{a.agent_id} エネルギー危機 ({a.energy:.1f})", tick, a.agent_id))
            elif a.energy <= self.ENERGY_WARN:
                alerts.append(Alert(AlertLevel.WARNING, "ENERGY",
                                    f"{a.agent_id} 低エネルギー ({a.energy:.1f})", tick, a.agent_id))

        # ── タスク積滞 ──────────────────────────────────────────
        open_count = sum(1 for t in snap.tasks if t.status == "open")
        if open_count > self.TASK_BACKLOG:
            alerts.append(Alert(AlertLevel.WARNING, "TASK",
                                f"タスク積滞 {open_count}件", tick))

        # ── 格差 ────────────────────────────────────────────────
        gini = snap.metrics.get("gini", 0.0)
        if gini > self.GINI_CRIT:
            alerts.append(Alert(AlertLevel.CRITICAL, "ECONOMY",
                                f"格差危機 Gini={gini:.3f}", tick))
        elif gini > self.GINI_WARN:
            alerts.append(Alert(AlertLevel.WARNING, "ECONOMY",
                                f"格差拡大 Gini={gini:.3f}", tick))

        # ── Policy 違反 ─────────────────────────────────────────
        violations = snap.metrics.get("policy_violations", 0)
        if violations > 20:
            alerts.append(Alert(AlertLevel.WARNING, "SAFETY",
                                f"Policy 違反累積 {violations}件", tick))

        self.history.extend(alerts)
        self._update_emergency_level(alerts)
        return alerts

    def _update_emergency_level(self, new_alerts: List[Alert]) -> None:
        criticals = sum(1 for a in new_alerts if a.is_critical)
        if criticals >= 3:
            self._emergency_level = 3
        elif criticals >= 1:
            self._emergency_level = max(2, self._emergency_level)
        elif new_alerts:
            self._emergency_level = max(1, self._emergency_level)
        else:
            self._emergency_level = max(0, self._emergency_level - 1)

    @property
    def emergency_level(self) -> int:
        return self._emergency_level

    def critical_count(self, last_n_ticks: int = 10) -> int:
        return sum(1 for a in self.history[-last_n_ticks * 5:] if a.is_critical)

    def summary(self) -> dict:
        from collections import Counter
        cats = Counter(a.category for a in self.history)
        lvls = Counter(a.level.value for a in self.history)
        return {"total": len(self.history), "by_category": dict(cats), "by_level": dict(lvls),
                "emergency_level": self._emergency_level}
