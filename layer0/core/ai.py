from __future__ import annotations
import random
from typing import TYPE_CHECKING, Dict, Optional, Tuple

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
    """近くの高報酬タスクを優先し、sector 熱量マップで入札を最適化する。"""

    CHARGE_THRESHOLD = 30.0

    def __init__(self):
        # sector (x//5, y//5) ごとの報酬 EMA — 学習で蓄積
        self._sector_avg: dict = {}

    def decide(self, agent, world, tasks, agents, tick, rng):
        # 可視タスクから sector 報酬を学習
        for t in tasks:
            if hasattr(t, 'status') and t.status.value == 'open':
                key = (t.x // 5, t.y // 5)
                prior = self._sector_avg.get(key, t.reward)
                self._sector_avg[key] = prior * 0.85 + t.reward * 0.15
        if agent.status == AgentStatus.IDLE and agent.energy < self.CHARGE_THRESHOLD:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng):
        if agent.energy < 15:
            return None
        dist = abs(task.x - agent.x) + abs(task.y - agent.y)
        # 学習済み sector 平均と比較して相対的な価値を評価
        key = (task.x // 5, task.y // 5)
        sector_avg = self._sector_avg.get(key, task.reward)
        value_ratio = min(1.4, task.reward / max(1.0, sector_avg))
        enthusiasm = rng.uniform(0.55, 0.95) * value_ratio
        bid = task.reward * enthusiasm - dist * 0.15
        return round(max(task.energy_cost + 0.1, bid), 1)


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
    """市場平均を学習しながら高マージンタスクを選別する商人。"""

    MIN_REWARD = 10.0
    MIN_MARGIN = 3.0

    def __init__(self):
        self._market_avg = 14.0   # 市場平均報酬の EMA
        self._adaptive_min = self.MIN_REWARD  # 動的最低報酬閾値

    def decide(self, agent, world, tasks, agents, tick, rng):
        # 市場平均を学習してフィルタ閾値を動的調整
        open_tasks = [t for t in tasks if hasattr(t, 'status') and t.status.value == 'open']
        if open_tasks:
            avg = sum(t.reward for t in open_tasks) / len(open_tasks)
            self._market_avg = self._market_avg * 0.9 + avg * 0.1
            # 市場平均の 70% 以上のタスクのみ狙う
            self._adaptive_min = max(self.MIN_REWARD, self._market_avg * 0.70)
        if agent.status == AgentStatus.IDLE and agent.energy < 25:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng):
        if task.reward < self._adaptive_min:
            return None
        margin = task.reward - task.energy_cost
        if margin < self.MIN_MARGIN:
            return None
        bid = task.energy_cost + margin * rng.uniform(0.65, 0.95)
        return round(bid, 1)


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
    """KPIを監視して都市を巡回しながらポリシー提案を行う統治者。"""

    CENTER = (10, 10)
    # 都市内の監視拠点（中央→四隅→辺中点）
    POSTS = [(10, 10), (3, 3), (16, 3), (3, 16), (16, 16)]
    POST_DWELL = 15    # 各拠点で待機する tick 数
    PROPOSAL_INTERVAL = 25

    def __init__(self, start_post: int = 0):
        self._post_idx = start_post
        self._dwell = 0
        self._last_proposal: Dict[str, int] = {}  # action -> last tick proposed
        COOLDOWN = 50  # 同一提案の再発火を抑制する tick 数
        self._cooldown = COOLDOWN

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.status != AgentStatus.IDLE:
            return
        tx, ty = self.POSTS[self._post_idx % len(self.POSTS)]
        if agent.x == tx and agent.y == ty:
            self._dwell += 1
            if self._dwell >= self.POST_DWELL:
                self._post_idx += 1
                self._dwell = 0
        else:
            agent.target_x, agent.target_y = tx, ty
            agent.status = AgentStatus.MOVING

    def get_bid(self, task, agent, rng):
        return None

    def policy_proposal(self, tick: int, gini: float,
                         completion_rate: float,
                         worker_idle_ratio: float = 0.0) -> Optional[dict]:
        if tick % self.PROPOSAL_INTERVAL != 0:
            return None

        def _can_propose(action: str) -> bool:
            return tick - self._last_proposal.get(action, -999) >= self._cooldown

        if worker_idle_ratio > 0.5 and _can_propose("worker_support"):
            self._last_proposal["worker_support"] = tick
            return {"action": "worker_support", "value": round(worker_idle_ratio, 2),
                    "reason": f"Worker稼働率低下 - {(1 - worker_idle_ratio) * 100:.0f}%のみ受注"}
        if gini > 0.25 and _can_propose("tax_increase"):
            self._last_proposal["tax_increase"] = tick
            return {"action": "tax_increase", "value": 0.07,
                    "reason": f"Gini={gini:.2f} - 格差拡大を検知"}
        if completion_rate < 0.6 and _can_propose("reward_boost"):
            self._last_proposal["reward_boost"] = tick
            return {"action": "reward_boost", "value": 1.2,
                    "reason": f"完了率={completion_rate:.0%} - タスク不成立多発"}
        return None


# ── ファクトリ ──────────────────────────────────────────────────
def make_ai(role: AgentRole, index: int = 0) -> RoleAI:
    if role == AgentRole.WORKER:   return WorkerAI()
    if role == AgentRole.GUARDIAN: return GuardianAI(route_index=index)
    if role == AgentRole.TRADER:   return TraderAI()
    if role == AgentRole.OBSERVER: return ObserverAI(quadrant=index)
    if role == AgentRole.GOVERNOR: return GovernorAI(start_post=index)
    return RoleAI()
