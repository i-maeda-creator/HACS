from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import uuid


class TaskStatus(str, Enum):
    OPEN      = "open"
    ASSIGNED  = "assigned"
    COMPLETED = "completed"
    EXPIRED   = "expired"


class TaskType(str, Enum):
    STANDARD    = "standard"    # 通常作業   — Worker / Trader
    HEAVY       = "heavy"       # 重作業     — Worker 優先（高コスト高報酬）
    URGENT      = "urgent"      # 緊急対応   — 全役職・15tick で期限切れ
    TRADE       = "trade"       # 市場取引   — Trader 優先
    SECURITY    = "security"    # 治安対応   — Guardian も入札可
    SURVEY      = "survey"      # 調査収集   — Observer も入札可
    MICRO       = "micro"       # 近場の小作業 — SAVER 優先（エージェント付近にスポーン）
    CONSTRUCT   = "construct"   # 建設作業     — Architect 専門（建物を生成）
    # ── 違法タスク（闇市）─────────────────────────────────────────
    SMUGGLE     = "smuggle"     # 密輸 — 高報酬・無税・発覚すると逮捕リスク
    HACK        = "hack"        # ハッキング — 近隣エージェントのECを直接窃取
    # ── 生産チェーン ─────────────────────────────────────────────
    GATHER      = "gather"      # 採集 — リソースノードから原材料を収集
    UPGRADE     = "upgrade"     # 建物強化 — 建物をL+1にアップグレード


# ── タイプ別パラメータ定義 ────────────────────────────────────────────────────
TASK_PARAMS: Dict[str, dict] = {
    TaskType.STANDARD: dict(
        reward_range=(8.0,  20.0),
        cost_range  =(1.0,   5.0),
        expires_in  =None,          # 期限なし
        color       ="#AAAAAA",
    ),
    TaskType.HEAVY: dict(
        reward_range=(25.0, 50.0),
        cost_range  =(10.0, 20.0),
        expires_in  =None,
        color       ="#FF6D00",
    ),
    TaskType.URGENT: dict(
        reward_range=(20.0, 35.0),
        cost_range  =(3.0,   8.0),
        expires_in  =15,            # 15 tick 以内にアサインされなければ失効
        color       ="#FF4444",
    ),
    TaskType.TRADE: dict(
        reward_range=(12.0, 28.0),
        cost_range  =(1.0,   3.0),
        expires_in  =None,
        color       ="#00E676",
    ),
    TaskType.SECURITY: dict(
        reward_range=(10.0, 22.0),
        cost_range  =(4.0,   8.0),
        expires_in  =None,
        color       ="#FF4444",
    ),
    TaskType.SURVEY: dict(
        reward_range=(5.0,  12.0),
        cost_range  =(2.0,   4.0),
        expires_in  =None,
        color       ="#00B0FF",
    ),
    TaskType.MICRO: dict(
        reward_range=(2.0,   6.0),
        cost_range  =(0.5,   1.5),
        expires_in  =20,
        color       ="#CCFF90",
    ),
    TaskType.CONSTRUCT: dict(
        reward_range=(25.0, 45.0),
        cost_range  =(10.0, 18.0),
        expires_in  =None,
        color       ="#FF6F00",
    ),
    TaskType.SMUGGLE: dict(
        reward_range=(20.0, 40.0),
        cost_range  =(5.0,  10.0),
        expires_in  =20,
        color       ="#660066",
    ),
    TaskType.HACK: dict(
        reward_range=(10.0, 20.0),  # + 近隣からの窃取額が加算される
        cost_range  =(3.0,   6.0),
        expires_in  =15,
        color       ="#AA0000",
    ),
    TaskType.GATHER: dict(
        reward_range=(3.0,   8.0),  # 採集基本報酬（リソース価値が加算）
        cost_range  =(1.0,   3.0),
        expires_in  =30,            # ノードが消える前に採集
        color       ="#76FF03",
    ),
    TaskType.UPGRADE: dict(
        reward_range=(20.0, 60.0),  # 建物レベルで変動
        cost_range  =(8.0,  15.0),
        expires_in  =None,
        color       ="#FFC400",
    ),
}

# タイプ別スポーン確率（合計 1.0）
TASK_TYPE_WEIGHTS = [
    (TaskType.STANDARD, 0.22),
    (TaskType.HEAVY,    0.08),
    (TaskType.URGENT,   0.11),
    (TaskType.TRADE,    0.12),
    (TaskType.SECURITY, 0.09),
    (TaskType.SURVEY,   0.09),
    (TaskType.MICRO,    0.11),
    (TaskType.CONSTRUCT,0.10),
    (TaskType.GATHER,   0.08),
]

# 役職ごとの入札ボーナス係数（タスクタイプ別）
# 1.0 = 通常 / >1.0 = ボーナス / 0.0 = 入札不可
from layer0.core.agent import AgentRole

_Z = 0.0  # 入札不可

ROLE_TASK_BONUS: Dict[TaskType, Dict[AgentRole, float]] = {
    #                          WRK   TRD   GRD   OBS   GOV   MED   ARC
    TaskType.STANDARD:  {AgentRole.WORKER:1.0, AgentRole.TRADER:1.0,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:0.6},
    TaskType.HEAVY:     {AgentRole.WORKER:1.4, AgentRole.TRADER:0.7,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:0.8},
    TaskType.URGENT:    {AgentRole.WORKER:1.2, AgentRole.TRADER:1.1,   AgentRole.GUARDIAN:0.8, AgentRole.OBSERVER:0.6, AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.TRADE:     {AgentRole.WORKER:0.8, AgentRole.TRADER:1.6,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.SECURITY:  {AgentRole.WORKER:0.7, AgentRole.TRADER:0.5,   AgentRole.GUARDIAN:1.5, AgentRole.OBSERVER:0.6, AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.SURVEY:    {AgentRole.WORKER:0.6, AgentRole.TRADER:0.4,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:1.5, AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.MICRO:     {AgentRole.WORKER:1.0, AgentRole.TRADER:0.5,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.CONSTRUCT: {AgentRole.WORKER:0.6, AgentRole.TRADER:_Z,    AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:2.2},
    TaskType.GATHER:    {AgentRole.WORKER:1.3, AgentRole.TRADER:0.7,   AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:0.8, AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:_Z},
    TaskType.UPGRADE:   {AgentRole.WORKER:0.8, AgentRole.TRADER:_Z,    AgentRole.GUARDIAN:_Z,  AgentRole.OBSERVER:_Z,  AgentRole.GOVERNOR:_Z, AgentRole.MEDIC:_Z, AgentRole.ARCHITECT:2.0},
}


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
    task_type: TaskType = TaskType.STANDARD
    status: TaskStatus = TaskStatus.OPEN
    assigned_to: Optional[str] = None
    bids: List[Bid] = field(default_factory=list)
    created_tick: int = 0
    completed_tick: Optional[int] = None
    expires_at: Optional[int] = None   # None = 期限なし
    is_illegal: bool = False           # 違法タスク（闇市）フラグ

    def submit_bid(self, agent_id: str, amount: float) -> None:
        self.bids.append(Bid(agent_id=agent_id, amount=amount))

    def resolve_auction(self, rng=None) -> Optional[str]:
        """Quantum Auction: P(win) ∝ bid amount. Higher bids win more often, but not guaranteed."""
        if not self.bids:
            return None
        if rng is None:
            winner = max(self.bids, key=lambda b: b.amount)
        else:
            total = sum(b.amount for b in self.bids)
            r = rng.random() * total
            cumulative = 0.0
            winner = self.bids[-1]
            for b in self.bids:
                cumulative += b.amount
                if r <= cumulative:
                    winner = b
                    break
        self.assigned_to = winner.agent_id
        self.status = TaskStatus.ASSIGNED
        return winner.agent_id

    def is_expired(self, current_tick: int) -> bool:
        return (self.expires_at is not None
                and current_tick > self.expires_at
                and self.status == TaskStatus.OPEN)

    def role_bid_bonus(self, role: AgentRole) -> float:
        """この役職がこのタスクに入札できるか・ボーナス係数を返す。0.0 = 入札不可。"""
        bonuses = ROLE_TASK_BONUS.get(self.task_type, {})
        return bonuses.get(role, 0.0)

    def profit_for(self, agent_id: str) -> float:
        bid = next((b for b in self.bids if b.agent_id == agent_id), None)
        return self.reward - (bid.amount if bid else self.energy_cost)


def make_task(x: int, y: int, reward: float = 10.0, energy_cost: float = 3.0,
              tick: int = 0, task_type: TaskType = TaskType.STANDARD,
              expires_in: Optional[int] = None) -> Task:
    expires_at = tick + expires_in if expires_in is not None else None
    return Task(
        task_id=str(uuid.uuid4())[:8],
        x=x, y=y,
        reward=reward,
        energy_cost=energy_cost,
        task_type=task_type,
        created_tick=tick,
        expires_at=expires_at,
    )
