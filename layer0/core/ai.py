from __future__ import annotations
import random
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from layer0.core.agent import Agent
    from layer0.core.world import World
    from layer0.core.task import Task

from layer0.core.agent import AgentRole, AgentStatus


# ══════════════════════════════════════════════════════════════════
# Worker 性格特性（10種）
# ══════════════════════════════════════════════════════════════════
class WorkerTrait(str, Enum):
    HUSTLER     = "hustler"     # 稼ぎ師：高熱意で何でも入札
    SAVER       = "saver"       # 節約家：近場・MICRO専門
    SPECIALIST  = "specialist"  # 重作業専門：HEAVYに全賭け
    EXPLORER    = "explorer"    # 探索者：距離無視・広域カバー
    OPPORTUNIST = "opportunist" # 機会主義者：競合の少ない隙間を狙う
    GAMBLER     = "gambler"     # 博打師：120-180%の大博打入札
    NIHILIST    = "nihilist"    # 虚無主義者：時々意図的に入札を拒否
    CONFORMIST  = "conformist"  # 同調者：多数派が狙うタスクに乗っかる
    REBEL       = "rebel"       # 反逆者：高額タスクを「搾取」として拒否
    DRIFTER     = "drifter"     # 漂流者：どこでもそこそこ、専門なし
    CHRONO      = "chrono"      # 時間旅行者：未来から来た存在。完璧な入札

TRAIT_LABELS = {
    WorkerTrait.HUSTLER:     "稼ぎ師",
    WorkerTrait.SAVER:       "節約家",
    WorkerTrait.SPECIALIST:  "重作業専門",
    WorkerTrait.EXPLORER:    "探索者",
    WorkerTrait.OPPORTUNIST: "機会主義者",
    WorkerTrait.GAMBLER:     "博打師",
    WorkerTrait.NIHILIST:    "虚無主義者",
    WorkerTrait.CONFORMIST:  "同調者",
    WorkerTrait.REBEL:       "反逆者",
    WorkerTrait.DRIFTER:     "漂流者",
    WorkerTrait.CHRONO:      "時間旅行者",
}

TRAIT_WEIGHTS = [
    (WorkerTrait.HUSTLER,     0.14),
    (WorkerTrait.SAVER,       0.11),
    (WorkerTrait.SPECIALIST,  0.11),
    (WorkerTrait.EXPLORER,    0.10),
    (WorkerTrait.OPPORTUNIST, 0.10),
    (WorkerTrait.GAMBLER,     0.10),
    (WorkerTrait.NIHILIST,    0.08),
    (WorkerTrait.CONFORMIST,  0.10),
    (WorkerTrait.REBEL,       0.09),
    (WorkerTrait.DRIFTER,     0.05),
    (WorkerTrait.CHRONO,      0.02),  # 合計 1.00
]


# ══════════════════════════════════════════════════════════════════
# 役職別 性格（各3種）
# ══════════════════════════════════════════════════════════════════
class GuardianPersonality(str, Enum):
    STOIC      = "stoic"      # 冷静：安定パトロール
    AGGRESSIVE = "aggressive" # 攻撃的：高速巡回・SECURITY に超積極的入札
    VIGILANT   = "vigilant"   # 監視員：広域パトロール・多方向カバー

class TraderPersonality(str, Enum):
    ANALYST    = "analyst"    # 分析家：市場平均学習（デフォルト）
    SHARK      = "shark"      # 鮫：Memory買値を半額に、売値を2倍に
    SPECULATOR = "speculator" # 投機家：記憶を3件まで溜めて一気に転売

class ObserverPersonality(str, Enum):
    SYSTEMATIC = "systematic" # 系統的：象限担当カバー（デフォルト）
    VISIONARY  = "visionary"  # 先見者：全域ランダム移動、SURVEY入札超積極
    INFORMANT  = "informant"  # 情報屋：SURVEY報酬が低くても積極的に入札

class GovernorPersonality(str, Enum):
    BALANCED     = "balanced"     # バランス型：KPI総合判断（デフォルト）
    POPULIST     = "populist"     # 人気取り：常にworker_support・basic_income優先
    CONSERVATIVE = "conservative" # 保守派：50tick毎、高閾値でのみ動く

class MedicPersonality(str, Enum):
    PROFESSIONAL = "professional" # 専門家：標準料金（デフォルト）
    MERCENARY    = "mercenary"    # 傭兵：2倍料金、富裕層のみ治療
    SELFLESS     = "selfless"     # 無私：半額、貧困層も治療

class ArchitectPersonality(str, Enum):
    BUILDER    = "builder"    # 建設家：標準建設（デフォルト）
    MONOPOLIST = "monopolist" # 独占者：高入札でタスクを独占
    URBANIST   = "urbanist"   # 都市計画家：中心部に集中建設


# ══════════════════════════════════════════════════════════════════
# 基底クラス
# ══════════════════════════════════════════════════════════════════
class RoleAI:
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


# ══════════════════════════════════════════════════════════════════
# Worker（10特性 + CHRONO 時間旅行者）
# ══════════════════════════════════════════════════════════════════
class WorkerAI(RoleAI):
    _CHARGE_THRESHOLD = {
        WorkerTrait.HUSTLER:     25.0,
        WorkerTrait.SAVER:       45.0,
        WorkerTrait.SPECIALIST:  30.0,
        WorkerTrait.EXPLORER:    20.0,
        WorkerTrait.OPPORTUNIST: 30.0,
        WorkerTrait.GAMBLER:     20.0,  # ギリギリまで動く
        WorkerTrait.NIHILIST:    35.0,
        WorkerTrait.CONFORMIST:  30.0,
        WorkerTrait.REBEL:       30.0,
        WorkerTrait.DRIFTER:     25.0,
        WorkerTrait.CHRONO:      15.0,  # 未来を知っているので余裕
    }

    MEMORY_BOOST_AMOUNT = 1.5

    def __init__(self, trait: WorkerTrait = WorkerTrait.HUSTLER):
        self.trait = trait
        self._sector_avg: dict = {}
        self._open_sector_counts: dict = {}
        self._last_winner_bid: float = 0.0  # CONFORMIST 用：直前の落札額を記憶

    @property
    def charge_threshold(self) -> float:
        return self._CHARGE_THRESHOLD[self.trait]

    def decide(self, agent, world, tasks, agents, tick, rng):
        self._open_sector_counts = {}
        max_bid_this_round = 0.0
        for t in tasks:
            if hasattr(t, 'status') and t.status.value == 'open':
                key = (t.x // 5, t.y // 5)
                prior = self._sector_avg.get(key, t.reward)
                self._sector_avg[key] = prior * 0.85 + t.reward * 0.15
                self._open_sector_counts[key] = self._open_sector_counts.get(key, 0) + 1
                max_bid_this_round = max(max_bid_this_round, t.reward)
        if max_bid_this_round:
            self._last_winner_bid = max_bid_this_round * 0.92  # 推定落札額
        if agent.status == AgentStatus.IDLE and agent.energy < self.charge_threshold:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng) -> Optional[float]:
        from layer0.core.task import TaskType
        if agent.energy < 15:
            return None

        dist  = abs(task.x - agent.x) + abs(task.y - agent.y)
        key   = (task.x // 5, task.y // 5)
        s_avg = self._sector_avg.get(key, task.reward)
        mb    = self.MEMORY_BOOST_AMOUNT if agent.memory_boost > 0 else 0.0

        if self.trait == WorkerTrait.HUSTLER:
            bid = task.reward * rng.uniform(0.75, 1.05) - dist * 0.05 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.SAVER:
            if task.task_type == TaskType.MICRO:
                bid = task.reward * rng.uniform(0.95, 1.25) - dist * 0.10 + mb
                return round(max(task.energy_cost + 0.1, bid), 1)
            if dist > 8 or agent.energy < self.charge_threshold + 10:
                return None
            bid = task.reward * rng.uniform(0.50, 0.80) - dist * 0.30 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.SPECIALIST:
            e = (rng.uniform(0.90, 1.20) if task.task_type == TaskType.HEAVY
                 else rng.uniform(0.55, 0.75) if task.task_type == TaskType.URGENT
                 else rng.uniform(0.30, 0.50))
            bid = task.reward * e - dist * 0.10 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.EXPLORER:
            vr  = min(1.5, task.reward / max(1.0, s_avg))
            bid = task.reward * rng.uniform(0.60, 1.00) * vr - dist * 0.02 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.OPPORTUNIST:
            if self._open_sector_counts.get(key, 0) > 2 or s_avg > 16.0:
                return None
            bid = task.reward * rng.uniform(0.85, 1.15) - dist * 0.08 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.GAMBLER:
            # 大博打：120-180%。外れても気にしない
            bid = task.reward * rng.uniform(1.20, 1.80) + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.NIHILIST:
            # 15%の確率でそのタスクの存在を「無意味」と判断して拒否
            if rng.random() < 0.15:
                return None
            bid = task.reward * rng.uniform(0.50, 0.90) - dist * 0.10 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.CONFORMIST:
            # 直前の推定落札額に追随
            ref = max(task.energy_cost + 0.5, self._last_winner_bid * rng.uniform(0.90, 1.05))
            bid = min(ref, task.reward * 1.10) + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.REBEL:
            # 高額タスクは「搾取」として入札拒否
            if task.reward > 20.0:
                return None
            bid = task.reward * rng.uniform(0.90, 1.20) - dist * 0.05 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.DRIFTER:
            # どこでもそこそこ、特に何も考えない
            bid = task.reward * rng.uniform(0.40, 0.75) - dist * 0.02 + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        if self.trait == WorkerTrait.CHRONO:
            # 未来を知っている：ほぼ完璧な入札（コスト+マージン最適化）
            # 距離ゼロで考える（未来では自分がそこにいることを知っている）
            bid = task.reward * rng.uniform(0.93, 0.98) + mb
            return round(max(task.energy_cost + 0.1, bid), 1)

        bid = task.reward * rng.uniform(0.55, 0.95) - dist * 0.15 + mb
        return round(max(task.energy_cost + 0.1, bid), 1)


# ══════════════════════════════════════════════════════════════════
# Guardian（3性格）
# ══════════════════════════════════════════════════════════════════
class GuardianAI(RoleAI):
    CHARGE_THRESHOLD = 40.0
    PATROL_ROUTES = [
        [(2,2),(17,2),(17,17),(2,17),(10,10)],
        [(10,2),(17,10),(10,17),(2,10),(10,10)],
        [(2,2),(10,2),(17,2),(17,10),(17,17),(10,17),(2,17),(2,10),(10,10)],  # VIGILANT用
    ]

    def __init__(self, route_index: int = 0,
                 personality: GuardianPersonality = GuardianPersonality.STOIC):
        self.personality = personality
        route = 2 if personality == GuardianPersonality.VIGILANT else route_index % 2
        self._patrol_idx = route_index
        self._route = self.PATROL_ROUTES[route]

    def decide(self, agent, world, tasks, agents, tick, rng):
        threshold = (self.CHARGE_THRESHOLD - 10 if self.personality == GuardianPersonality.AGGRESSIVE
                     else self.CHARGE_THRESHOLD)
        if agent.energy < threshold:
            if agent.status != AgentStatus.MOVING or not self._heading_to_charger(agent, world):
                self._go_charge(agent, world)
            return
        if agent.status == AgentStatus.IDLE:
            tx, ty = self._route[self._patrol_idx % len(self._route)]
            if agent.x == tx and agent.y == ty:
                self._patrol_idx += 1
                tx, ty = self._route[self._patrol_idx % len(self._route)]
            agent.target_x, agent.target_y = tx, ty
            agent.status = AgentStatus.MOVING

    def _heading_to_charger(self, agent, world) -> bool:
        charger = world.nearest_charger(agent.x, agent.y)
        return charger is not None and agent.target_x == charger[0] and agent.target_y == charger[1]

    def get_bid(self, task, agent, rng):
        from layer0.core.task import TaskType
        if task.task_type == TaskType.SECURITY:
            hi = 1.25 if self.personality == GuardianPersonality.AGGRESSIVE else 1.10
            bid = task.reward * rng.uniform(0.80, hi)
            return round(max(task.energy_cost + 0.1, bid), 1)
        if task.task_type == TaskType.URGENT:
            hi = 0.90 if self.personality == GuardianPersonality.AGGRESSIVE else 0.75
            bid = task.reward * rng.uniform(0.50, hi)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


# ══════════════════════════════════════════════════════════════════
# Trader（3性格）
# ══════════════════════════════════════════════════════════════════
class TraderAI(RoleAI):
    MIN_REWARD = 10.0
    MIN_MARGIN = 3.0
    TRADE_COOLDOWN = 5
    BUY_MIN_EXP = 5
    SELL_MAX_EXP = 2
    BUY_PRICE_PER_EXP = 0.4
    SELL_MARKUP = 1.6

    def __init__(self, personality: TraderPersonality = TraderPersonality.ANALYST):
        self.personality = personality
        self._market_avg = 14.0
        self._adaptive_min = self.MIN_REWARD
        self._memory_inventory: list = []
        self._last_trade_tick: int = 0
        # 性格ごとのパラメータ上書き
        if personality == TraderPersonality.SHARK:
            self.BUY_PRICE_PER_EXP = 0.20  # 半額買い叩き
            self.SELL_MARKUP        = 2.20  # 高値転売
            self.MAX_MEMORIES       = 2
        elif personality == TraderPersonality.SPECULATOR:
            self.BUY_PRICE_PER_EXP = 0.45
            self.SELL_MARKUP        = 1.80
            self.MAX_MEMORIES       = 3     # 溜め込む
        else:
            self.MAX_MEMORIES = 2

    def decide(self, agent, world, tasks, agents, tick, rng):
        open_tasks = [t for t in tasks if hasattr(t, 'status') and t.status.value == 'open']
        if open_tasks:
            avg = sum(t.reward for t in open_tasks) / len(open_tasks)
            self._market_avg = self._market_avg * 0.9 + avg * 0.1
            self._adaptive_min = max(self.MIN_REWARD, self._market_avg * 0.70)
        if agent.status == AgentStatus.IDLE and agent.energy < 25:
            self._go_charge(agent, world)

    def get_bid(self, task, agent, rng):
        if task.reward < self._adaptive_min:
            return None
        margin = task.reward - task.energy_cost
        if margin < self.MIN_MARGIN:
            return None
        lo = 0.55 if self.personality == TraderPersonality.SHARK else 0.65
        bid = task.energy_cost + margin * rng.uniform(lo, 0.95)
        return round(bid, 1)


# ══════════════════════════════════════════════════════════════════
# Observer（3性格）
# ══════════════════════════════════════════════════════════════════
class ObserverAI(RoleAI):
    CHARGE_THRESHOLD = 25.0
    MOVE_INTERVAL = 8

    def __init__(self, quadrant: int = 0,
                 personality: ObserverPersonality = ObserverPersonality.SYSTEMATIC):
        self.personality = personality
        self._quadrant = quadrant % 4
        qmap = {0:(1,1,9,9), 1:(10,1,18,9), 2:(1,10,9,18), 3:(10,10,18,18)}
        self._area = qmap[self._quadrant]

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return
        if agent.status == AgentStatus.IDLE or (tick % self.MOVE_INTERVAL == 0
                                                 and agent.status != AgentStatus.MOVING):
            if self.personality == ObserverPersonality.VISIONARY:
                # 全域をランダム探索
                for _ in range(20):
                    tx = rng.randint(1, 18)
                    ty = rng.randint(1, 18)
                    if world.is_passable(tx, ty) and (tx != agent.x or ty != agent.y):
                        agent.target_x, agent.target_y = tx, ty
                        agent.status = AgentStatus.MOVING
                        break
            else:
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
            # VISIONARY と INFORMANT は SURVEY に超積極的
            hi = 1.30 if self.personality != ObserverPersonality.SYSTEMATIC else 1.15
            bid = task.reward * rng.uniform(0.85, hi)
            return round(max(task.energy_cost + 0.1, bid), 1)
        if task.task_type == TaskType.URGENT:
            bid = task.reward * rng.uniform(0.40, 0.65)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


# ══════════════════════════════════════════════════════════════════
# Medic（3性格）
# ══════════════════════════════════════════════════════════════════
class MedicAI(RoleAI):
    CHARGE_THRESHOLD  = 35.0
    HEAL_ENERGY_BELOW = 50.0
    HEAL_AMOUNT       = 20.0

    def __init__(self, personality: MedicPersonality = MedicPersonality.PROFESSIONAL):
        self.personality = personality
        if personality == MedicPersonality.MERCENARY:
            self.HEAL_PRICE_RATE   = 1.00   # 2倍料金
            self.MIN_CLIENT_BALANCE = 12.0  # 富裕層のみ
        elif personality == MedicPersonality.SELFLESS:
            self.HEAL_PRICE_RATE   = 0.25   # 半額
            self.MIN_CLIENT_BALANCE = 1.5   # 貧困層も治療
        else:
            self.HEAL_PRICE_RATE   = 0.50
            self.MIN_CLIENT_BALANCE = 4.0

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return
        targets = [
            a for a in agents
            if a.agent_id != agent.agent_id
            and a.energy < self.HEAL_ENERGY_BELOW
            and a.balance >= self.MIN_CLIENT_BALANCE
        ]
        if not targets:
            if agent.status == AgentStatus.IDLE:
                tx = rng.randint(7, 13)
                ty = rng.randint(7, 13)
                if world.is_passable(tx, ty):
                    agent.target_x, agent.target_y = tx, ty
                    agent.status = AgentStatus.MOVING
            return
        nearest = min(targets, key=lambda a: abs(a.x - agent.x) + abs(a.y - agent.y))
        if agent.x == nearest.x and agent.y == nearest.y:
            agent.status = AgentStatus.IDLE
        else:
            agent.target_x, agent.target_y = nearest.x, nearest.y
            agent.status = AgentStatus.MOVING

    def get_bid(self, task, agent, rng):
        return None


# ══════════════════════════════════════════════════════════════════
# Architect（3性格）
# ══════════════════════════════════════════════════════════════════
class ArchitectAI(RoleAI):
    CHARGE_THRESHOLD = 30.0

    def __init__(self, personality: ArchitectPersonality = ArchitectPersonality.BUILDER):
        self.personality = personality

    def decide(self, agent, world, tasks, agents, tick, rng):
        if agent.energy < self.CHARGE_THRESHOLD:
            if agent.status == AgentStatus.IDLE:
                self._go_charge(agent, world)
            return
        if agent.status == AgentStatus.IDLE:
            from layer0.core.task import TaskType
            targets = [t for t in tasks
                       if hasattr(t, 'task_type') and t.task_type == TaskType.CONSTRUCT
                       and hasattr(t, 'status') and t.status.value == 'open']
            if self.personality == ArchitectPersonality.URBANIST:
                # 中心部（5-15）のタスクを優先
                center = [t for t in targets if 5 <= t.x <= 15 and 5 <= t.y <= 15]
                targets = center if center else targets
            if targets:
                nearest = min(targets, key=lambda t: abs(t.x - agent.x) + abs(t.y - agent.y))
                agent.target_x, agent.target_y = nearest.x, nearest.y
                agent.status = AgentStatus.MOVING
            else:
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
            lo = 1.00 if self.personality == ArchitectPersonality.MONOPOLIST else 0.90
            hi = 1.30 if self.personality == ArchitectPersonality.MONOPOLIST else 1.15
            bid = task.reward * rng.uniform(lo, hi)
            return round(max(task.energy_cost + 0.1, bid), 1)
        if task.task_type == TaskType.HEAVY:
            bid = task.reward * rng.uniform(0.50, 0.70)
            return round(max(task.energy_cost + 0.1, bid), 1)
        return None


# ══════════════════════════════════════════════════════════════════
# Governor（3性格）
# ══════════════════════════════════════════════════════════════════
class GovernorAI(RoleAI):
    CENTER = (10, 10)
    POSTS  = [(10,10),(3,3),(16,3),(3,16),(16,16)]

    def __init__(self, start_post: int = 0,
                 personality: GovernorPersonality = GovernorPersonality.BALANCED):
        self.personality = personality
        self._post_idx = start_post
        self._dwell = 0
        self._last_proposal: Dict[str, int] = {}
        self._cooldown = 50
        # 性格によって提案間隔を変える
        self.PROPOSAL_INTERVAL = 50 if personality == GovernorPersonality.CONSERVATIVE else 25
        self.POST_DWELL = 15

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

        def _can(action: str) -> bool:
            return tick - self._last_proposal.get(action, -999) >= self._cooldown

        kpi = (completion_rate + (1.0 - gini)) / 2

        if self.personality == GovernorPersonality.POPULIST:
            # 人気取り：常にworker支援か再分配
            if worker_idle_ratio > 0.3 and _can("worker_support"):
                self._last_proposal["worker_support"] = tick
                return {"action": "worker_support", "reason": "POPULIST: Worker最優先"}
            if tax_pool > 200 and _can("basic_income"):
                self._last_proposal["basic_income"] = tick
                return {"action": "basic_income", "reason": "POPULIST: 再分配"}
            return None

        if self.personality == GovernorPersonality.CONSERVATIVE:
            # 保守派：高閾値でのみ動く
            if completion_rate < 0.45 and _can("reward_boost"):
                self._last_proposal["reward_boost"] = tick
                return {"action": "reward_boost", "reason": "CONSERVATIVE: 危機的完了率"}
            if gini > 0.45 and _can("tax_increase"):
                self._last_proposal["tax_increase"] = tick
                return {"action": "tax_increase", "reason": "CONSERVATIVE: 深刻な格差"}
            return None

        # BALANCED（デフォルト）
        if completion_rate < 0.6 and _can("reward_boost"):
            self._last_proposal["reward_boost"] = tick
            return {"action": "reward_boost", "reason": f"完了率={completion_rate:.0%}"}
        if worker_idle_ratio > 0.5 and _can("worker_support"):
            self._last_proposal["worker_support"] = tick
            return {"action": "worker_support", "reason": f"Worker稼働率低下"}
        if tax_pool > 400 and gini > 0.15 and _can("basic_income"):
            self._last_proposal["basic_income"] = tick
            return {"action": "basic_income", "reason": f"税プール={tax_pool:.0f}"}
        if gini > 0.30 and kpi > 0.6 and _can("tax_increase"):
            self._last_proposal["tax_increase"] = tick
            return {"action": "tax_increase", "reason": f"Gini={gini:.2f}"}
        if tax_pool > 600 and _can("basic_income"):
            self._last_proposal["basic_income"] = tick
            return {"action": "basic_income", "reason": f"余剰再分配"}
        return None


# ══════════════════════════════════════════════════════════════════
# ファクトリ
# ══════════════════════════════════════════════════════════════════
def _pick_trait(index: int) -> WorkerTrait:
    rng = random.Random(index * 1337)
    types, weights = zip(*TRAIT_WEIGHTS)
    r = rng.random()
    acc = 0.0
    for t, w in zip(types, weights):
        acc += w
        if r <= acc:
            return t
    return WorkerTrait.HUSTLER


def _pick_personality(enum_cls, index: int):
    members = list(enum_cls)
    return members[index % len(members)]


def make_ai(role: AgentRole, index: int = 0) -> RoleAI:
    if role == AgentRole.WORKER:
        return WorkerAI(trait=_pick_trait(index))
    if role == AgentRole.GUARDIAN:
        return GuardianAI(route_index=index,
                          personality=_pick_personality(GuardianPersonality, index))
    if role == AgentRole.TRADER:
        return TraderAI(personality=_pick_personality(TraderPersonality, index))
    if role == AgentRole.OBSERVER:
        return ObserverAI(quadrant=index,
                          personality=_pick_personality(ObserverPersonality, index))
    if role == AgentRole.GOVERNOR:
        return GovernorAI(start_post=index,
                          personality=_pick_personality(GovernorPersonality, index))
    if role == AgentRole.MEDIC:
        return MedicAI(personality=_pick_personality(MedicPersonality, index))
    if role == AgentRole.ARCHITECT:
        return ArchitectAI(personality=_pick_personality(ArchitectPersonality, index))
    return RoleAI()


def get_worker_trait(ai: RoleAI) -> Optional[WorkerTrait]:
    return ai.trait if isinstance(ai, WorkerAI) else None
