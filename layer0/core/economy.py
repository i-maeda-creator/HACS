from __future__ import annotations
from dataclasses import dataclass, field
from layer0.schemas.ledger import LedgerEntry


@dataclass
class Economy:
    ledger: list[LedgerEntry] = field(default_factory=list)
    tx_count: int = 0

    TAX_RATE = 0.05

    def transfer(self, from_id: str, to_id: str, amount: float, reason: str, tick: int, task_id: str | None = None) -> LedgerEntry:
        entry = LedgerEntry(
            tick=tick,
            from_id=from_id,
            to_id=to_id,
            amount=amount,
            reason=reason,
            task_id=task_id,
        )
        self.ledger.append(entry)
        self.tx_count += 1
        return entry

    def pay_reward(self, agent_id: str, reward: float, task_id: str, tick: int) -> None:
        tax = reward * self.TAX_RATE
        net = reward - tax
        self.transfer("city", agent_id, net, "task_reward", tick, task_id)
        self.transfer(agent_id, "city", tax, "tax", tick, task_id)

    def total_transactions(self) -> int:
        return self.tx_count

    def ledger_for(self, agent_id: str) -> list[LedgerEntry]:
        return [e for e in self.ledger if e.from_id == agent_id or e.to_id == agent_id]
