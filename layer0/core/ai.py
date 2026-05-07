from __future__ import annotations
import random
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from layer0.core.agent import Agent
    from layer0.core.world import World
    from layer0.core.task import Task

from layer0.core.agent import AgentRole, AgentStatus


# ── Worker 性格特性 ──────────────────────────────────────────────
class WorkerTrait(str, Enum):
    HUSTLER     = "hustler"     # 稼ぎ重視。高い熱意で何でも入札
    SAVER       = "saver"       # エネルギー節約家。充電閾値高め・近場専門
    SPECIALIST  = "specialist"  # HEAVY タスクのエキスパート
    EXPLORER    = "explorer"    # 遠いタスクも厭わず広域をカバー
    OPPORTUNIST = "opportunist" # 競争率の低いタスクを狙うスナイパー

TRAIT_LABELS = {
    WorkerTrait.HUSTLER:     "稼ぎ師",
    WorkerTrait.SAVER:       "節約家",
    WorkerTrait.SPECIALIST:  "重作業専門",
    WorkerTrait.EXPLORER:    "探索者",
    WorkerTrait.OPPORTUNIST: "機会主義者",
}

# 各特性の出現比率
TRAIT_WEIGHTS = [
    (WorkerTrait.HUSTLER,     0.25),
    (WorkerTrait.SAVER,       0.20),
    (WorkerTrait.SPECIALIST,  0.20),
    (WorkerTrait.EXPLORER,    0.20),
    (WorkerTrait.OPPORTUNIST, 0.15),
]


class RoleAI:
    """全役職の基底クラス。"""

    def decide(self, agent: "Agent", world: "World",
               tasks: list, agents: list,
               tick: int, rng: random.Random) -> None:
        pass

    def get_bid(self, task: "Task", agent: "Agent",
                rng: random.Random) -> Optional[float]:
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
    """性格特性によって入札戦略が異なる Worker。"""

    # 特性別充電閾値
    _CHARGE_THRESHOLD = {
        WorkerTrait.HUSTLER:     25.0,  # ギリギリまで働く
        WorkerTrait.SAVER:       45.0,  # 早めに充電
        WorkerTrait.SPECIALIST:  30.0,
        WorkerTrait.EXPLORER:    20.0,  # 遠征重視で充電後回し
        WorkerTrait.OPPORTUNIST: 30.0,
    }

    def __init__(self, trait: WorkerTrait = WorkerTrait.HUSTLER):
        self.trait = trait
        self._sector_avg: dict = {}
        self._open_sector_counts: dict = {}
        self._bid_counts: Dict[str, int] = {}  # task_id → 競合入札数の観測

    @property
    def charge_threshold(self) -> float:
        return self._CHARGE_THRESHOLD[self.trait]

    def decide(self, agent, world, tasks, agents, tick, rng):
        self._open_sector_counts: dict = {}
        for t in tasks:
            if hasattr(t, 'status') and t.status.value == 'open':
                key = (t.x // 5, t.y // 5)
                prior = self._sector_avg.get(key, t.reward)
                self._sector_avg[key] = prior * 0.85 + t.reward * 0.15
                self._open_sector_counts[key] = self._open_sector_counts.get(key, 0) + 1
        if agent.status == AgentStatus.IDLE and agent.energy < self.charge_threshold:
            self._go_charge(agent, world)

    MEMORY_BOOST_AMOUNT = 1.5  # 記憶ブースト中の入札加算額

    def get_bid(self, task, agent, rng) -> Optional[float]:
        from layer0.core.task import TaskType
        if agent.energy < 15:
            return None

        dist  = abs(task.x - agent.x) + abs(task.y - agent.y)
        key   = (task.x // 5, task.y // 5)
        s_avg = self._sector_avg.get(key, task.reward)
        memory_bonus = self.MEMORY_BOOST_AMOUNT if agent.memory_boost > 0 else 0.0

        # ── HUSTLER: 高熱意・距離無視 ──────────────────────────
        if self.trait == WorkerTrait.HUSTLER:
            enthusiasm = rng.uniform(0.75, 1.05)
            bid = task.reward * enthusiasm - dist * 0.05 + memory_bonus
            return round(max(task.energy_cost + 0.1, bid), 1)

        # ── SAVER: エネルギー温存・近場のみ ───────────────────
        if self.trait == WorkerTrait.SAVER:
            if task.task_type == TaskType.MICRO:
                enthusiasm = rng.uniform(0.95, 1.25)
                bid = task.reward * enthusiasm - dist * 0.10 + memory_bonus
                return round(max(task.energy_cost + 0.1, bid), 1)
            if dist > 8:
                return None
            if agent.energy < self.charge_threshold + 10:
                return None
            enthusiasm = rng.uniform(0.50, 0.80)
            bid = task.reward * enthusiasm - dist * 0.30 + memory_bonus
            return round(max(task.energy_cost + 0.1, bid), 1)

        # ── SPECIALIST: HEAVY に集中、他は消極的 ──────────────
        if self.trait == WorkerTrait.SPECIALIST:
            if task.task_type == TaskType.HEAVY:
                enthusiasm = rng.uniform(0.90, 1.20)
            elif task.task_type == TaskType.URGENT:
                enthusiasm = rng.uniform(0.55, 0.75)
            else:
                enthusiasm = rng.uniform(0.30, 0.50)
            bid = task.reward * enthusiasm - dist * 0.10 + memory_bonus
            return round(max(task.energy_cost + 0.1, bid), 1)

        # ── EXPLORER: 距離ペナルティほぼゼロ、広域カバー ──────
        if self.trait == WorkerTrait.EXPLORER:
            value_ratio = min(1.5, task.reward / max(1.0, s_avg))
            enthusiasm  = rng.uniform(0.60, 1.00) * value_ratio
            bid = task.reward * enthusiasm - dist * 0.02 + memory_bonus
            return round(max(task.energy_cost + 0.1, bid), 1)

        # ── OPPORTUNIST: 競合が少ないニッチなタスクを高く入札 ──
        if self.trait == WorkerTrait.OPPORTUNIST:
            sector_density = self._open_sector_counts.get(key, 0)
            if sector_density > 2 or s_avg > 16.0:
                return None
            enthusiasm = rng.uniform(0.85, 1.15)
            bid = task.reward * enthusiasm - dist * 0.08 + memory_bonus
            return round(max(task.energy_cost + 0.1, bid), 1)

        # fallback
        enthusiasm = rng.uniform(0.55, 0.95)
        bid = task.reward * enthusiasm - dist * 0.15 + memory_bonus
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
        from layer0.core.task import TaskType
        # SECURITY タスクのみ入札（Guardian の本領）
        if task.task_type == TaskType.SECURITY:
            bid = task.reward * rng.uniform(0.80, 1.10)
            return round(max(task.energy_cost + 0.1, bid), 1)
        # URGENT も緊急出動として入札（ボーナスは小さい）
        if task.task_type == TaskType.URGENT:
            bid = task.reward * rng.uniform(0.50, 0.75)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


# ── Trader ──────────────────────────────────────────────────────
class TraderAI(RoleAI):
    """市場平均を学習しながら高マージンタスクを選別する商人。記憶売買ブローカーも兼務。"""

    MIN_REWARD = 10.0
    MIN_MARGIN = 3.0
    MAX_MEMORIES = 2       # 同時に保有できる記憶の上限
    TRADE_COOLDOWN = 5     # 同一エージェントへの連続売買抑制（tick）
    BUY_MIN_EXP = 5        # 購入対象の最低経験値
    SELL_MAX_EXP = 2       # 販売対象の最高経験値（新人限定）
    BUY_PRICE_PER_EXP = 0.4
    SELL_MARKUP = 1.6      # 買値 × この倍率で転売

    def __init__(self):
        self._market_avg = 14.0
        self._adaptive_min = self.MIN_REWARD
        self._memory_inventory: list = []  # [{"experience": int, "price_paid": float}]
        self._last_trade_tick: int = 0

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
        from layer0.core.task import TaskType
        if task.task_type == TaskType.SURVEY:
            bid = task.reward * rng.uniform(0.85, 1.15)
            return round(max(task.energy_cost + 0.1, bid), 1)
        if task.task_type == TaskType.URGENT:
            bid = task.reward * rng.uniform(0.40, 0.65)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


# ── Medic ───────────────────────────────────────────────────────
class MedicAI(RoleAI):
    """低エネルギーのエージェントに近づき治療サービスを提供する。タスクには入札しない。"""

    CHARGE_THRESHOLD  = 35.0
    HEAL_ENERGY_BELOW = 50.0  # この値を下回るエージェントを治療対象とする
    MIN_CLIENT_BALANCE = 4.0  # クライアントの最低残高（支払い能力確認）
    HEAL_AMOUNT       = 20.0  # 1回の治療で回復するエネルギー量
    HEAL_PRICE_RATE   = 0.50  # 回復量 × この係数 = 治療費 EC

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return

        # 治療対象（低エネルギー & 支払い能力あり）を探す
        targets = [
            a for a in agents
            if a.agent_id != agent.agent_id
            and a.energy < self.HEAL_ENERGY_BELOW
            and a.balance >= self.MIN_CLIENT_BALANCE
        ]
        if not targets:
            # ターゲットなし → マップ中央付近をウロウロ
            if agent.status == AgentStatus.IDLE:
                tx = rng.randint(7, 13)
                ty = rng.randint(7, 13)
                if world.is_passable(tx, ty):
                    agent.target_x, agent.target_y = tx, ty
                    agent.status = AgentStatus.MOVING
            return

        # 最近傍ターゲットへ移動
        nearest = min(targets, key=lambda a: abs(a.x - agent.x) + abs(a.y - agent.y))
        if agent.x == nearest.x and agent.y == nearest.y:
            agent.status = AgentStatus.IDLE  # 到着 → simulator が治療処理
        else:
            agent.target_x, agent.target_y = nearest.x, nearest.y
            agent.status = AgentStatus.MOVING

    def get_bid(self, task, agent, rng):
        return None  # Medic はタスク入札しない


# ── Architect ───────────────────────────────────────────────────
class ArchitectAI(RoleAI):
    """CONSTRUCT タスクを専門に受注し、建物で不労所得を得る建設家。"""

    CHARGE_THRESHOLD = 30.0

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return
        if agent.status == AgentStatus.IDLE:
            from layer0.core.task import TaskType
            # CONSTRUCT タスクがあれば向かう
            targets = [t for t in tasks
                       if hasattr(t, 'task_type') and t.task_type == TaskType.CONSTRUCT
                       and hasattr(t, 'status') and t.status.value == 'open']
            if targets:
                nearest = min(targets, key=lambda t: abs(t.x - agent.x) + abs(t.y - agent.y))
                agent.target_x, agent.target_y = nearest.x, nearest.y
                agent.status = AgentStatus.MOVING
            else:
                # タスクなし → マップ中心付近をウロウロ
                for _ in range(10):
                    tx = rng.randint(4, 15)
                    ty = rng.randint(4, 15)
                    if world.is_passable(tx, ty) and (tx != agent.x or ty != agent.y):
                        agent.target_x, agent.target_y = tx, ty
                        agent.status = AgentStatus.MOVING
                        break

    def get_bid(self, task, agent, rng) -> Optional[float]:
        from layer0.core.task import TaskType
        if task.task_type == TaskType.CONSTRUCT:
            bid = task.reward * rng.uniform(0.90, 1.15)
            return round(max(task.energy_cost + 0.1, bid), 1)
        if task.task_type == TaskType.HEAVY:
            bid = task.reward * rng.uniform(0.50, 0.70)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


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
                         worker_idle_ratio: float = 0.0,
                         tax_pool: float = 0.0) -> Optional[dict]:
        if tick % self.PROPOSAL_INTERVAL != 0:
            return None

        def _can_propose(action: str) -> bool:
            return tick - self._last_proposal.get(action, -999) >= self._cooldown

        # KPI = (効率性 + 平等性) / 2 — Governor の取り分に直結するため優先度が高い
        kpi = (completion_rate + (1.0 - gini)) / 2

        # KPIが低い緊急時は市場刺激を最優先
        if completion_rate < 0.6 and _can_propose("reward_boost"):
            self._last_proposal["reward_boost"] = tick
            return {"action": "reward_boost", "value": 1.2,
                    "reason": f"完了率={completion_rate:.0%} — KPI危機: タスク不成立多発"}
        # Worker 稼働率低下（→ KPI低下 → 自分の取り分も減る）
        if worker_idle_ratio > 0.5 and _can_propose("worker_support"):
            self._last_proposal["worker_support"] = tick
            return {"action": "worker_support", "value": round(worker_idle_ratio, 2),
                    "reason": f"Worker稼働率低下 - {(1 - worker_idle_ratio) * 100:.0f}%のみ受注"}
        # 税プール過剰 → 再分配（Gini改善 → 平等性UP → KPI UP → 自分の取り分UP）
        if tax_pool > 400 and gini > 0.15 and _can_propose("basic_income"):
            self._last_proposal["basic_income"] = tick
            return {"action": "basic_income", "value": tax_pool,
                    "reason": f"税プール={tax_pool:.0f} EC & Gini={gini:.2f} — 再分配でKPI改善"}
        # 格差拡大は KPI 平等性を直撃（ただし乱発すると worker が動けなくなる）
        if gini > 0.30 and kpi > 0.6 and _can_propose("tax_increase"):
            self._last_proposal["tax_increase"] = tick
            return {"action": "tax_increase", "value": 0.07,
                    "reason": f"Gini={gini:.2f} — 格差是正 (KPI={kpi:.2f})"}
        # 税プール安全圏での余裕ある再分配
        if tax_pool > 600 and _can_propose("basic_income"):
            self._last_proposal["basic_income"] = tick
            return {"action": "basic_income", "value": tax_pool,
                    "reason": f"税プール={tax_pool:.0f} EC — 余剰再分配"}
        return None


# ── ファクトリ ──────────────────────────────────────────────────
def _pick_trait(index: int) -> WorkerTrait:
    """index を seed にして特性を重み付き選択（再現性あり）。"""
    rng = random.Random(index * 1337)
    types, weights = zip(*TRAIT_WEIGHTS)
    r = rng.random()
    acc = 0.0
    for t, w in zip(types, weights):
        acc += w
        if r <= acc:
            return t
    return WorkerTrait.HUSTLER


def make_ai(role: AgentRole, index: int = 0) -> RoleAI:
    if role == AgentRole.WORKER:   return WorkerAI(trait=_pick_trait(index))
    if role == AgentRole.GUARDIAN: return GuardianAI(route_index=index)
    if role == AgentRole.TRADER:   return TraderAI()
    if role == AgentRole.OBSERVER: return ObserverAI(quadrant=index)
    if role == AgentRole.GOVERNOR: return GovernorAI(start_post=index)
    if role == AgentRole.MEDIC:      return MedicAI()
    if role == AgentRole.ARCHITECT:  return ArchitectAI()
    return RoleAI()


def get_worker_trait(ai: RoleAI) -> Optional[WorkerTrait]:
    """WorkerAI なら特性を返す。"""
    return ai.trait if isinstance(ai, WorkerAI) else None
