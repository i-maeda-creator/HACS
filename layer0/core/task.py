from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import uuid


class TaskStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    COMPLETED = "completed"


@dataclass
class Bid:
    agent_id: str
    amount: float


@dataclass
class Task:
    task_id: str
    x: int
    y: int
    reward: float
    energy_cost: float
    status: TaskStatus = TaskStatus.OPEN
    assigned_to: Optional[str] = None
    bids: List[Bid] = field(default_factory=list)
    created_tick: int = 0
    completed_tick: Optional[int] = None

    def submit_bid(self, agent_id: str, amount: float) -> None:
        self.bids.append(Bid(agent_id=agent_id, amount=amount))

    def resolve_auction(self) -> Optional[str]:
        if not self.bids:
            return None
        winner = max(self.bids, key=lambda b: b.amount)
        self.assigned_to = winner.agent_id
        self.status = TaskStatus.ASSIGNED
        return winner.agent_id

    def profit_for(self, agent_id: str) -> float:
        bid = next((b for b in self.bids if b.agent_id == agent_id), None)
        if bid is None:
            return self.reward - self.energy_cost
        return self.reward - bid.amount


def make_task(x: int, y: int, reward: float = 10.0, energy_cost: float = 3.0, tick: int = 0) -> Task:
    return Task(
        task_id=str(uuid.uuid4())[:8],
        x=x, y=y,
        reward=reward,
        energy_cost=energy_cost,
        created_tick=tick,
    )
