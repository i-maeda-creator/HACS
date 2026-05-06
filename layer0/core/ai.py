from __future__ import annotations
import random
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from layer0.core.agent import Agent
    from layer0.core.world import World
    from layer0.core.task import Task

from layer0.core.agent import AgentRole, AgentStatus


class RoleAI:
    """全役職の基底クラス。"""

    def decide(self, agent: "Agent", world: "World",
               tasks: list, agents: list,
               tick: int, rng: random.Random) -> None:
        """毎 tick 呼ばれる。agent の target_x/y / status を直接更新してよい。"""

    def get_bid(self, task: "Task", agent: "Agent",
                rng: random.Random) -> Optional[float]:
        """入札額を返す。None なら入札しない。"""
        return task.energy_cost + rng.uniform(0, 2)

    def _go_charge(self, agent: "Agent", world: "World") -> bool:
        charger = world.nearest_charger(agent.x, agent.y)
        if charger:
            agent.target_x, agent.target_y = charger
            agent.status = AgentStatus.MOVING
            return True
        return False


# ── Worker ──────────────────────────────────────────────────────
class WorkerAI(RoleAI):
    """近くの高報酬タスクを優先して効率よく稼ぐ。"""

    CHARGE_THRESHOLD = 30.0

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.status == AgentStatus.IDLE and agent.energy < self.CHARGE_THRESHOLD:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng):
        if agent.energy < 15:
            return None  # エネルギー不足なら入札しない
        # 近いタスクには積極的に、遠いタスクには控えめに
        dist = abs(task.x - agent.x) + abs(task.y - agent.y)
        penalty = dist * 0.05
        return task.energy_cost + rng.uniform(0.2, 1.5) + penalty


# ── Guardian ────────────────────────────────────────────────────
class GuardianAI(RoleAI):
    """マップをパトロールして安全を確保する。タスクには入札しない。"""

    CHARGE_THRESHOLD = 40.0
    # 外周パトロールルート（5点）
    PATROL_ROUTES = [
        [(2,2),(17,2),(17,17),(2,17),(10,10)],
        [(10,2),(17,10),(10,17),(2,10),(10,10)],
    ]

    def __init__(self, route_index: int = 0):
        self._patrol_idx = route_index  # 開始点をずらして分散
        self._route = self.PATROL_ROUTES[route_index % len(self.PATROL_ROUTES)]

    def decide(self, agent, world, tasks, agents, tick, rng):
        # 低エネルギー → まず充電
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status != AgentStatus.MOVING or not self._heading_to_charger(agent, world):
                self._go_charge(agent, world)
            return

        if agent.status == AgentStatus.IDLE:
            tx, ty = self._route[self._patrol_idx % len(self._route)]
            # 目的地に到着したら次のポイントへ
            if agent.x == tx and agent.y == ty:
                self._patrol_idx += 1
                tx, ty = self._route[self._patrol_idx % len(self._route)]
            agent.target_x, agent.target_y = tx, ty
            agent.status = AgentStatus.MOVING

    def _heading_to_charger(self, agent, world) -> bool:
        charger = world.nearest_charger(agent.x, agent.y)
        if charger is None:
            return False
        return agent.target_x == charger[0] and agent.target_y == charger[1]

    def get_bid(self, task, agent, rng):
        return None  # Guardian は通常タスクに入札しない


# ── Trader ──────────────────────────────────────────────────────
class TraderAI(RoleAI):
    """高報酬タスクを選別して利益を最大化する商人。"""

    MIN_REWARD = 10.0    # 最低報酬ライン
    MIN_MARGIN = 3.0     # 最低利益マージン

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.status == AgentStatus.IDLE and agent.energy < 25:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng):
        if task.reward < self.MIN_REWARD:
            return None  # 低報酬は無視
        margin = task.reward - task.energy_cost
        if margin < self.MIN_MARGIN:
            return None  # 利益薄は無視

        # 残高が少ないほど積極的に入札（生存本能）
        aggression = max(0.1, 1.0 - agent.balance / 100.0)
        return task.energy_cost + max(0.1, rng.uniform(0.1, 1.0) * aggression)


# ── Observer ────────────────────────────────────────────────────
class ObserverAI(RoleAI):
    """担当象限をカバーしながら情報収集する。タスクには入札しない。"""

    CHARGE_THRESHOLD = 25.0
    MOVE_INTERVAL = 8  # N tick ごとに移動先を更新

    def __init__(self, quadrant: int = 0):
        self._quadrant = quadrant % 4
        # 象限ごとのカバーエリア（内側のみ）
        qmap = {0:(1,1,9,9), 1:(10,1,18,9), 2:(1,10,9,18), 3:(10,10,18,18)}
        self._area = qmap[self._quadrant]

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return

        # 一定 tick ごとに担当エリア内のランダム地点へ移動
        if agent.status == AgentStatus.IDLE or (tick % self.MOVE_INTERVAL == 0
                                                 and agent.status != AgentStatus.MOVING):
            x1, y1, x2, y2 = self._area
            for _ in range(20):
                tx = rng.randint(x1, x2)
                ty = rng.randint(y1, y2)
                if world.is_passable(tx, ty) and (tx != agent.x or ty != agent.y):
                    agent.target_x, agent.target_y = tx, ty
                    agent.status = AgentStatus.MOVING
                    break

    def get_bid(self, task, agent, rng):
        return None  # Observer は入札しない


# ── Governor ────────────────────────────────────────────────────
class GovernorAI(RoleAI):
    """KPIを監視してポリシー変更を提案する都市統治者。"""

    CENTER = (10, 10)
    PROPOSAL_INTERVAL = 25  # 25 tick ごとに判断

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.status == AgentStatus.IDLE:
            cx, cy = self.CENTER
            if agent.x != cx or agent.y != cy:
                agent.target_x, agent.target_y = cx, cy
                agent.status = AgentStatus.MOVING

    def get_bid(self, task, agent, rng):
        return None  # Governor は入札しない

    def policy_proposal(self, tick: int, gini: float,
                         completion_rate: float) -> Optional[dict]:
        """KPI に基づいてポリシー提案を返す。None なら何もしない。"""
        if tick % self.PROPOSAL_INTERVAL != 0:
            return None
        if gini > 0.35:
            return {"action": "tax_increase", "value": 0.07,
                    "reason": f"Gini={gini:.2f} — 格差拡大を検知"}
        if completion_rate < 0.55:
            return {"action": "reward_boost", "value": 1.2,
                    "reason": f"完了率={completion_rate:.0%} — タスク不成立多発"}
        return None


# ── ファクトリ ──────────────────────────────────────────────────
def make_ai(role: AgentRole, index: int = 0) -> RoleAI:
    if role == AgentRole.WORKER:   return WorkerAI()
    if role == AgentRole.GUARDIAN: return GuardianAI(route_index=index)
    if role == AgentRole.TRADER:   return TraderAI()
    if role == AgentRole.OBSERVER: return ObserverAI(quadrant=index)
    if role == AgentRole.GOVERNOR: return GovernorAI()
    return RoleAI()
