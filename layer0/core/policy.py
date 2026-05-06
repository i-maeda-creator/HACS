from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from layer0.core.agent import Agent, AgentStatus
from layer0.core.task import Task
from layer0.schemas.event import Event, EventType


@dataclass
class PolicyViolation:
    tick: int
    agent_id: str
    rule: str
    penalty: float = 0.0


@dataclass
class HardConstraint:
    name: str
    check: Callable[[Agent, int], bool]
    action: Callable[[Agent], None]


@dataclass
class SoftConstraint:
    name: str
    check: Callable[[Agent, int], bool]
    penalty: float


@dataclass
class Objective:
    name: str
    measure: Callable[[List[Agent], List[Task]], float]


class PolicyEngine:
    def __init__(self):
        self.hard: List[HardConstraint] = []
        self.soft: List[SoftConstraint] = []
        self.objectives: List[Objective] = []
        self.violations: List[PolicyViolation] = []
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        # Hard: エネルギー切れ agent は動けない
        self.hard.append(HardConstraint(
            name="no_move_on_empty_energy",
            check=lambda a, t: a.energy <= 0 and a.status == AgentStatus.MOVING,
            action=lambda a: setattr(a, "status", AgentStatus.IDLE),
        ))

        # Hard: 夜間（tick が 100 の倍数 ±10）は新規タスク受け付けを制限
        # （今は Guardian は動けない）
        self.hard.append(HardConstraint(
            name="guardian_rest_period",
            check=lambda a, t: a.role.value == "Guardian" and (t % 50 < 5),
            action=lambda a: setattr(a, "status", AgentStatus.IDLE),
        ))

        # Soft: 残高がマイナスになりそうな低残高は警告
        self.soft.append(SoftConstraint(
            name="low_balance_penalty",
            check=lambda a, t: a.balance < 5.0,
            penalty=0.5,
        ))

        # Objectives
        self.objectives.append(Objective(
            name="efficiency",
            measure=lambda agents, tasks: len([t for t in tasks if t.status == "completed"]) / max(len(tasks), 1),
        ))
        self.objectives.append(Objective(
            name="equality",
            measure=lambda agents, tasks: 1.0 - _gini([a.balance for a in agents]),
        ))

    def apply(self, agents: List[Agent], tasks: List[Task], tick: int) -> List[Event]:
        events: List[Event] = []

        for agent in agents:
            for hc in self.hard:
                if hc.check(agent, tick):
                    hc.action(agent)
                    v = PolicyViolation(tick=tick, agent_id=agent.agent_id, rule=hc.name)
                    self.violations.append(v)
                    events.append(Event(
                        tick=tick,
                        event_type=EventType.POLICY_CHANGED,
                        source="policy_engine",
                        agent_id=agent.agent_id,
                        payload={"rule": hc.name, "type": "hard"},
                    ))

            for sc in self.soft:
                if sc.check(agent, tick):
                    agent.balance = max(0.0, agent.balance - sc.penalty)
                    v = PolicyViolation(tick=tick, agent_id=agent.agent_id, rule=sc.name, penalty=sc.penalty)
                    self.violations.append(v)
                    events.append(Event(
                        tick=tick,
                        event_type=EventType.POLICY_CHANGED,
                        source="policy_engine",
                        agent_id=agent.agent_id,
                        payload={"rule": sc.name, "type": "soft", "penalty": sc.penalty},
                    ))

        return events

    def score(self, agents: List[Agent], tasks: List[Task]) -> dict:
        return {obj.name: round(obj.measure(agents, tasks), 4) for obj in self.objectives}


def _gini(values: List[float]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    return sum(abs(a - b) for a in values for b in values) / (2 * n ** 2 * mean)
