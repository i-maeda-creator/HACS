from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    TASK_CREATED = "TaskCreated"
    BID_SUBMITTED = "BidSubmitted"
    TASK_ASSIGNED = "TaskAssigned"
    TASK_COMPLETED = "TaskCompleted"
    AGENT_MOVED = "AgentMoved"
    ENERGY_SPENT = "EnergySpent"
    TRANSACTION_RECORDED = "TransactionRecorded"
    POLICY_CHANGED = "PolicyChanged"
    INCIDENT_DETECTED = "IncidentDetected"
    AGENT_CHARGED = "AgentCharged"


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tick: int
    event_type: EventType
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
