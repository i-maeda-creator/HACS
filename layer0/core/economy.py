from __future__ import annotations
from dataclasses import dataclass, field
from layer0.schemas.ledger import LedgerEntry


@dataclass
class Economy:
    ledger: list[LedgerEntry] = field(default_factory=list)
    tx_count: int = 0
    tax_pool: float = 0.0   # 税収累計 — セーフティネット・統治報酬の財源

    TAX_RATE             = 0.05
    GOVERNOR_TAX_SHARE   = 0.30  # 税収の 30% を Governor へ分配
    UPKEEP_COST          = 0.20
    SAFETY_NET_THRESHOLD = 15.0
    SAFETY_NET_AMOUNT    = 5.0
    GOVERNANCE_REWARD    = 8.0   # VOTE_PASSED 1件あたり追加報酬
    PATROL_SALARY        = {     # 巡回・観測ロールへの毎 tick 給与
        "Guardian": 0.25,
        "Observer": 0.15,
    }
    BUILDING_INCOME_RATE = 0.50  # 建物1棟あたり毎 tick の不労所得

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

    def pay_reward(self, agent_id: str, reward: float, task_id: str, tick: int,
                   governor_ids: list[str] | None = None) -> float:
        """タスク報酬を支払い、税の 30% を Governor に分配。残りを tax_pool へ。戻り値 = 税額。"""
        tax = round(reward * self.TAX_RATE, 2)
        net = reward - tax
        self.transfer("city", agent_id, net, "task_reward", tick, task_id)
        self.transfer(agent_id, "city", tax, "tax", tick, task_id)
        # Governor 税配分
        gov_cut = round(tax * self.GOVERNOR_TAX_SHARE, 2)
        pool_cut = tax - gov_cut
        self.tax_pool += pool_cut
        return gov_cut  # Simulator 側で Governor へ配分

    def pay_upkeep(self, agent_id: str, tick: int) -> None:
        """維持費を市税プールへ。"""
        self.tax_pool += self.UPKEEP_COST
        self.transfer(agent_id, "city", self.UPKEEP_COST, "upkeep", tick)

    def pay_safety_net(self, agent_id: str, tick: int) -> bool:
        """残高不足エージェントへ補助。財源不足なら失敗。"""
        if self.tax_pool >= self.SAFETY_NET_AMOUNT:
            self.tax_pool -= self.SAFETY_NET_AMOUNT
            self.transfer("city", agent_id, self.SAFETY_NET_AMOUNT, "safety_net", tick)
            return True
        return False

    def pay_governance_reward(self, agent_id: str, tick: int, factor: float = 1.0) -> bool:
        """VOTE_PASSED 時に投票 Governor へ報酬。"""
        amount = round(self.GOVERNANCE_REWARD * factor, 1)
        if self.tax_pool >= amount:
            self.tax_pool -= amount
            self.transfer("city", agent_id, amount, "governance_reward", tick)
            return True
        return False

    def total_transactions(self) -> int:
        return self.tx_count

    def ledger_for(self, agent_id: str) -> list[LedgerEntry]:
        return [e for e in self.ledger if e.from_id == agent_id or e.to_id == agent_id]
