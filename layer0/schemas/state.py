from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AgentSnapshot(BaseModel):
    agent_id: str
    role: str
    x: int
    y: int
    energy: float
    balance: float
    status: str


class TaskSnapshot(BaseModel):
    task_id: str
    x: int
    y: int
    reward: float
    energy_cost: float
    status: str
    assigned_to: Optional[str] = None


class EconomySnapshot(BaseModel):
    tick: int
    total_energy: float
    total_balance: float
    transactions: int


class StateSnapshot(BaseModel):
    tick: int
    agents: List[AgentSnapshot]
    tasks: List[TaskSnapshot]
    economy: EconomySnapshot
    metrics: Dict[str, Any] = {}
