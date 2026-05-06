from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from layer0.core.agent import Agent, AgentStatus
from layer0.schemas.event import Event, EventType


@dataclass
class SafetyViolation:
    tick: int
    rule: str
    agent_id: Optional[str] = None
    severity: str = "high"


class SafetyGate:
    """Safety > Economy > Efficiency を保証するゲート層.

    PolicyEngine より先に呼ばれ、Safety 違反を即時修正する。
    AI や Economy ロジックはこのゲートを通過した後にのみ動作可能。
    """

    # エネルギー閾値: これ以下は強制停止
    CRITICAL_ENERGY = 0.0
    # 夜間フェーズ: tick % 100 が 0-4 の間
    NIGHT_PHASE_MOD = 100
    NIGHT_PHASE_LEN = 5

    def __init__(self):
        self.violations: List[SafetyViolation] = []
        self._emergency_active: bool = False

    # ── メインチェック（毎 tick 呼ぶ）──────────────────────────
    def check(self, agents: List[Agent], tick: int) -> List[Event]:
        if self._emergency_active:
            return self._apply_emergency_stop(agents, tick)

        events: List[Event] = []
        for agent in agents:
            events.extend(self._check_energy(agent, tick))
            events.extend(self._check_night_restriction(agent, tick))
        return events

    # ── 緊急停止（外部から呼び出し可能）──────────────────────────
    def trigger_emergency_stop(self, tick: int, reason: str = "manual") -> List[Event]:
        self._emergency_active = True
        self.violations.append(SafetyViolation(
            tick=tick, rule="emergency_stop", severity="critical"
        ))
        return [Event(
            tick=tick,
            event_type=EventType.SAFETY_TRIGGERED,
            source="safety_gate",
            payload={"rule": "emergency_stop", "reason": reason, "severity": "critical"},
        )]

    def reset_emergency(self) -> None:
        self._emergency_active = False

    def is_emergency_active(self) -> bool:
        return self._emergency_active

    # ── 個別ルール ────────────────────────────────────────────
    def _check_energy(self, agent: Agent, tick: int) -> List[Event]:
        if agent.energy <= self.CRITICAL_ENERGY and agent.status != AgentStatus.IDLE:
            agent.status = AgentStatus.IDLE
            self.violations.append(SafetyViolation(
                tick=tick, rule="energy_depleted",
                agent_id=agent.agent_id, severity="high"
            ))
            return [Event(
                tick=tick,
                event_type=EventType.SAFETY_TRIGGERED,
                source="safety_gate",
                agent_id=agent.agent_id,
                payload={"rule": "energy_depleted", "severity": "high"},
            )]
        return []

    def _check_night_restriction(self, agent: Agent, tick: int) -> List[Event]:
        is_night = (tick % self.NIGHT_PHASE_MOD) < self.NIGHT_PHASE_LEN
        if is_night and agent.role.value == "Guardian" and agent.status == AgentStatus.MOVING:
            agent.status = AgentStatus.IDLE
            self.violations.append(SafetyViolation(
                tick=tick, rule="night_restriction",
                agent_id=agent.agent_id, severity="medium"
            ))
            return [Event(
                tick=tick,
                event_type=EventType.SAFETY_TRIGGERED,
                source="safety_gate",
                agent_id=agent.agent_id,
                payload={"rule": "night_restriction", "severity": "medium"},
            )]
        return []

    def _apply_emergency_stop(self, agents: List[Agent], tick: int) -> List[Event]:
        events: List[Event] = []
        for agent in agents:
            if agent.status != AgentStatus.IDLE:
                agent.status = AgentStatus.IDLE
                events.append(Event(
                    tick=tick,
                    event_type=EventType.SAFETY_TRIGGERED,
                    source="safety_gate",
                    agent_id=agent.agent_id,
                    payload={"rule": "emergency_stop", "severity": "critical"},
                ))
        return events
