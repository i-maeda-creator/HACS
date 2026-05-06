from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LedgerEntry(BaseModel):
    tx_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tick: int
    from_id: str
    to_id: str
    amount: float
    reason: str
    task_id: Optional[str] = None
