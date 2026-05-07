from __future__ import annotations
import random
import json
from typing import Dict, List, Optional
from pathlib import Path
from layer0.core.world import World, Cell
from layer0.core.agent import Agent, AgentRole, AgentStatus
from layer0.core.task import Task, TaskStatus, TaskType, make_task, TASK_PARAMS, TASK_TYPE_WEIGHTS
from layer0.core.economy import Economy
from layer0.core.policy import PolicyEngine
from layer0.core.safety import SafetyGate
from layer0.core.ai import RoleAI, make_ai, GovernorAI, MedicAI, ArchitectAI, KoanAI
from layer0.schemas.event import Event, EventType
from layer0.schemas.state import StateSnapshot, AgentSnapshot, TaskSnapshot, EconomySnapshot


class Simulator:
    def __init__(self, seed: int = 42, world: Optional[World] = None, policy: Optional[PolicyEngine] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.tick = 0
        self._seq = 0
        self.world = world or World.default_layout()
        self.agents: List[Agent] = []
        self.tasks: List[Task] = []
        self.economy = Economy()
        self.policy = policy or PolicyEngine()
        self.safety = SafetyGate()
        self._ai: Dict[str, RoleAI] = {}
        self._role_counts: Dict[AgentRole, int] = {}
        self.event_log: List[Event] = []
        self.snapshots: List[StateSnapshot] = []
        # 動的ポリシーパラメータ — Governor 投票で変動し tick ごとに自然減衰
        self.policy_params: Dict[str, float] = {
            "reward_multiplier": 1.0,   # タスクスポーン時の報酬倍率
            "tax_rate":          Economy.TAX_RATE,  # 動的税率
            "worker_bid_bonus":  0.0,   # Worker 全員の入札額ボーナス
        }
        # 投票バッファ: action -> List[governor_id]（同一 tick 内の票を集計）
        self._vote_buffer: Dict[str, List[str]] = {}
        # 市場イベント管理
        self._market_event: Optional[Dict] = None
        self._market_event_end: int = 0
        self._next_market_event: int = self.rng.randint(30, 60)
        # 建物: (x,y) → {"owner": agent_id, "durability": float, "built_tick": int}
        self._buildings: Dict[tuple, dict] = {}
        # 時間ローン: agent_id → {"amount_due": float, "due_tick": int}
        self._temporal_loans: Dict[str, dict] = {}
        # 時空ストレス: パラドックスイベントのトリガーに使用
        self._temporal_stress: int = 0
        # 次のCHRONO訪問者出現tick
        self._next_chrono_arrival: int = self.rng.randint(40, 80)
        self._chrono_count: int = 0
        # CHRONO 疑惑度: agent_id → float（15で正体発覚）
        self._chrono_suspicion: Dict[str, float] = {}
        # ── 闇市 / 公安 ──────────────────────────────────────────────
        # 公安エージェントのID集合（外部にはWorkerとして見える）
        self._koan_agents: set = set()
        # 公安の証拠データ: target_id → 累積証拠ポイント
        self._koan_evidence: Dict[str, float] = {}
        # 闇市タスクの次スポーンtick
        self._next_illegal_spawn: int = self.rng.randint(15, 30)
        # 逮捕統計
        self._arrest_count: int = 0
        self._total_seized: float = 0.0
        # ── 感情・暴動 ────────────────────────────────────────────────
        self._riot_ticks: int = 0
        # ── 死と転生 ─────────────────────────────────────────────────
        self._zero_energy_ticks: Dict[str, int] = {}
        self._reincarnation_count: int = 0
        # ── カルト ───────────────────────────────────────────────────
        self._cults: Dict[str, set] = {}       # cult_id → agent_id集合
        self._cult_counter: int = 0
        # ── 影の市場 ─────────────────────────────────────────────────
        self._shadow_sat: Dict[str, str] = {}  # agent_id → task_id（今tickはスキップ）
        self._shadow_deal_count: int = 0
        # ── 特性進化 ─────────────────────────────────────────────────
        self._trait_wins: Dict[str, int] = {}
        self._trait_bids: Dict[str, int] = {}
        self._trait_balance_snap: Dict[str, float] = {}
        # ── 銀行 ─────────────────────────────────────────────────────
        self._bank_deposits: Dict[str, float] = {}
        self._bank_loans: Dict[str, dict] = {}
        self._bank_reserves: float = 200.0
        self._bank_interest_rate: float = 0.015
        # ── 株式市場 ─────────────────────────────────────────────────
        self._stocks: Dict[str, dict] = {
            "ARCH": {"price": 10.0, "volatility": 0.08},
            "TRAD": {"price": 10.0, "volatility": 0.12},
            "WORK": {"price": 10.0, "volatility": 0.06},
        }
        self._portfolios: Dict[str, Dict[str, int]] = {}
        self._next_stock_event: int = self.rng.randint(15, 35)
        self._dividend_countdown: int = 30

    def add_agent(self, agent: Agent) -> None:
        idx = self._role_counts.get(agent.role, 0)
        self._role_counts[agent.role] = idx + 1
        self._ai[agent.agent_id] = make_ai(agent.role, index=idx)
        self.agents.append(agent)

    def deploy_koan(self, agent: Agent, is_chrono: bool = False) -> None:
        """公安を Worker として偽装配置する。is_chrono=True なら未来から来た公安。"""
        agent.role = AgentRole.WORKER  # 表向きは Worker
        idx = self._role_counts.get(AgentRole.WORKER, 0)
        self._role_counts[AgentRole.WORKER] = idx + 1
        ai = KoanAI(is_chrono=is_chrono)
        self._ai[agent.agent_id] = ai
        self._koan_agents.add(agent.agent_id)
        self.agents.append(agent)
        # CHRONO公安は時空疑惑の追跡対象にも登録
        if is_chrono and agent.expires_at is not None:
            self._chrono_suspicion[agent.agent_id] = 0.0
        self._emit(EventType.KOAN_DEPLOYED, agent_id=agent.agent_id,
                   data={"x": agent.x, "y": agent.y, "cover": "worker",
                         "is_chrono": is_chrono,
                         "expires_at": agent.expires_at})

    def spawn_task(self, task_type: Optional[TaskType] = None) -> Task:
        if task_type is None:
            types, weights = zip(*TASK_TYPE_WEIGHTS)
            cumulative = []
            acc = 0.0
            for w in weights:
                acc += w
                cumulative.append(acc)
            r = self.rng.random()
            task_type = next(t for t, c in zip(types, cumulative) if r <= c)

        # MICRO タスクはエージェント近傍にスポーン
        if task_type == TaskType.MICRO and self.agents:
            ref = self.rng.choice(self.agents)
            for _ in range(30):
                dx = self.rng.randint(-5, 5)
                dy = self.rng.randint(-5, 5)
                x = max(1, min(self.world.width - 2, ref.x + dx))
                y = max(1, min(self.world.height - 2, ref.y + dy))
                if self.world.is_passable(x, y):
                    break
            else:
                x, y = ref.x, ref.y
        else:
            while True:
                x = self.rng.randint(1, self.world.width - 2)
                y = self.rng.randint(1, self.world.height - 2)
                if self.world.is_passable(x, y):
                    break

        params = TASK_PARAMS[task_type]
        r_lo, r_hi = params["reward_range"]
        c_lo, c_hi = params["cost_range"]
        reward = round(self.rng.uniform(r_lo, r_hi) * self.policy_params["reward_multiplier"], 1)
        cost   = round(self.rng.uniform(c_lo, c_hi), 1)
        expires_in = params["expires_in"]

        t = make_task(x, y, reward=reward, energy_cost=cost,
                      tick=self.tick, task_type=task_type, expires_in=expires_in)
        self.tasks.append(t)
        self._emit(EventType.TASK_CREATED, task_id=t.task_id,
                   data={"x": x, "y": y, "reward": reward,
                         "task_type": task_type.value,
                         "expires_at": t.expires_at})
        return t

    def step(self) -> StateSnapshot:
        self.tick += 1
        # 影の市場バッファリセット（新 tick）
        self._shadow_sat.clear()
        # 逮捕期間終了エージェントを釈放
        self._release_arrested()
        # 40% の確率でスポーン（うち MICRO はエージェント近傍）
        if self.rng.random() < 0.40:
            self.spawn_task()
        # 闇市タスクをスポーン（15〜30tick毎）
        if self.tick >= self._next_illegal_spawn:
            self._spawn_illegal_task()
            self._next_illegal_spawn = self.tick + self.rng.randint(12, 25)
        # 期限切れタスクを失効させる
        self._expire_tasks()
        # Policy params 自然減衰
        pp = self.policy_params
        pp["reward_multiplier"] = max(1.0, pp["reward_multiplier"] - 0.008)
        pp["tax_rate"]          = max(Economy.TAX_RATE, pp["tax_rate"] - 0.001)
        pp["worker_bid_bonus"]  = max(0.0, pp["worker_bid_bonus"] - 0.06)
        # 市場イベント
        self._tick_market_events()
        # 投票バッファリセット（新 tick）
        self._vote_buffer.clear()
        # Safety first
        safety_events = self.safety.check(self.agents, self.tick)
        for e in safety_events:
            self._seq += 1
            e.sequence_id = self._seq
        self.event_log.extend(safety_events)
        # Policy
        policy_events = self.policy.apply(self.agents, self.tasks, self.tick)
        for e in policy_events:
            self._seq += 1
            e.sequence_id = self._seq
        self.event_log.extend(policy_events)
        # 維持費（全エージェント）
        self._deduct_upkeep()
        # セーフティネット
        self._apply_safety_net()
        # Role AI — 各エージェントの戦略決定
        self._run_ai()
        # Governor policy proposals
        self._run_governor_proposals()
        # 影の市場（入札前に賄賂）
        self._run_shadow_deals()
        self._run_auctions()
        self._run_illegal_auctions()
        self._run_koan_targeting()
        self._move_agents()
        self._work_agents()
        self._process_illegal_completions()
        self._charge_agents()
        # 感情・暴動
        self._update_emotions()
        # 死と転生
        self._check_deaths()
        # カルト
        self._update_cult()
        # Medic 治療サービス
        self._heal_agents()
        # Memory Market（Trader による記憶売買）
        self._run_memory_market()
        # 時空歪曲メカニクス
        self._process_temporal_loans()
        self._run_time_market()
        self._maybe_chrono_arrival()
        self._update_chrono_suspicion()
        self._expire_chrono_agents()
        # 公安メカニクス
        self._update_koan_evidence()
        self._process_koan_arrests()
        # パトロール給与（Guardian/Observer）
        self._pay_patrol_salary()
        # 建物収入（Architect — 累進課税 + 減価償却）
        self._collect_building_income()
        # 銀行・株式市場
        self._run_bank()
        self._run_stock_market()
        # 特性進化（25tick毎）
        if self.tick % 25 == 0:
            self._evolve_traits()
        # 記憶ブーストのカウントダウン
        for agent in self.agents:
            if agent.memory_boost > 0:
                agent.memory_boost -= 1
        snap = self._snapshot()
        self.snapshots.append(snap)
        return snap

    def run(self, ticks: int) -> List[StateSnapshot]:
        return [self.step() for _ in range(ticks)]

    def _run_ai(self) -> None:
        for agent in self.agents:
            if agent.arrested_until is not None and self.tick <= agent.arrested_until:
                continue  # 逮捕中は行動不能
            ai = self._ai.get(agent.agent_id)
            if ai:
                ai.decide(agent, self.world, self.tasks, self.agents, self.tick, self.rng)

    def _run_governor_proposals(self) -> None:
        scores = self.policy.score(self.agents, self.tasks)
        gini = 1.0 - scores.get("equality", 1.0)
        completion = scores.get("efficiency", 1.0)

        workers = [a for a in self.agents if a.role == AgentRole.WORKER]
        if workers:
            earned = {e.agent_id for e in self.event_log
                      if e.event_type == EventType.TASK_COMPLETED and e.agent_id}
            worker_idle_ratio = 1.0 - sum(1 for w in workers if w.agent_id in earned) / len(workers)
        else:
            worker_idle_ratio = 0.0

        # 各 Governor が投票を提出（直接決定ではなく投票）
        for agent in self.agents:
            if agent.role != AgentRole.GOVERNOR:
                continue
            ai = self._ai.get(agent.agent_id)
            if not isinstance(ai, GovernorAI):
                continue
            proposal = ai.policy_proposal(self.tick, gini, completion, worker_idle_ratio,
                                          tax_pool=self.economy.tax_pool)
            if proposal:
                action = proposal["action"]
                self._vote_buffer.setdefault(action, []).append(agent.agent_id)
                self._emit(EventType.VOTE_SUBMITTED, agent_id=agent.agent_id,
                           data={"action": action, "reason": proposal.get("reason", ""),
                                 "gini": round(gini, 3), "completion": round(completion, 3)})

        # 過半数合意 → 政策発動（合意ボーナスあり）
        num_governors = sum(1 for a in self.agents if a.role == AgentRole.GOVERNOR)
        majority = max(1, (num_governors + 1) // 2)
        for action, voters in self._vote_buffer.items():
            if len(voters) >= majority:
                consensus_factor = 1.5 if len(voters) >= num_governors else 1.0
                self._apply_policy({"action": action}, factor=consensus_factor)
                self._emit(EventType.VOTE_PASSED,
                           data={"action": action, "voters": voters,
                                 "consensus_factor": consensus_factor,
                                 "params_after": dict(self.policy_params)})
                # 投票した Governor に統治報酬を分配
                for gov_id in voters:
                    gov_agent = self._get_agent(gov_id)
                    if gov_agent and self.economy.pay_governance_reward(gov_id, self.tick, consensus_factor):
                        reward = round(Economy.GOVERNANCE_REWARD * consensus_factor, 1)
                        gov_agent.balance += reward
                        self._emit(EventType.GOVERNANCE_REWARD, agent_id=gov_id,
                                   data={"action": action, "reward": reward,
                                         "consensus_factor": consensus_factor})

    def _apply_policy(self, proposal: Dict, factor: float = 1.0) -> None:
        action = proposal.get("action")
        pp = self.policy_params
        if action == "worker_support":
            pp["worker_bid_bonus"] = min(4.0, pp["worker_bid_bonus"] + 1.5 * factor)
        elif action == "tax_increase":
            pp["tax_rate"] = min(0.25, pp["tax_rate"] + 0.02 * factor)
        elif action == "reward_boost":
            pp["reward_multiplier"] = min(1.6, pp["reward_multiplier"] + 0.12 * factor)
        elif action == "basic_income":
            # 税プールから全エージェントへ均等分配
            if self.economy.tax_pool > 0:
                share = round(min(8.0, self.economy.tax_pool / max(len(self.agents), 1)) * factor, 1)
                total = 0.0
                for a in self.agents:
                    if self.economy.tax_pool >= share:
                        self.economy.tax_pool -= share
                        a.balance += share
                        total += share
                self._emit(EventType.BASIC_INCOME_PAID,
                           data={"share": share, "total": round(total, 1),
                                 "recipients": len(self.agents)})

    def _tick_market_events(self) -> None:
        """市場イベント（Boom / Crash）の発火・終了管理。"""
        # 終了チェック
        if self._market_event and self.tick >= self._market_event_end:
            self._revert_market_event()
            self._market_event = None
            self.emit_market(event_name="end", details={})

        # 新規イベント発火
        if self._market_event is None and self.tick >= self._next_market_event:
            kind = self.rng.choice(["boom", "crash"])
            duration = self.rng.randint(8, 15)
            if kind == "boom":
                self._market_event = {"kind": "boom",
                                      "orig_multiplier": self.policy_params["reward_multiplier"]}
                self.policy_params["reward_multiplier"] = min(2.0,
                    self.policy_params["reward_multiplier"] + 0.5)
            else:
                self._market_event = {"kind": "crash",
                                      "orig_multiplier": self.policy_params["reward_multiplier"]}
                self.policy_params["reward_multiplier"] = max(0.4,
                    self.policy_params["reward_multiplier"] - 0.4)
            self._market_event_end = self.tick + duration
            self._next_market_event = self.tick + duration + self.rng.randint(40, 80)
            self.emit_market(event_name=kind,
                             details={"duration": duration,
                                      "reward_multiplier": self.policy_params["reward_multiplier"]})

    def _deduct_upkeep(self) -> None:
        cost = Economy.UPKEEP_COST
        for agent in self.agents:
            agent.balance = max(0.0, agent.balance - cost)
            self.economy.pay_upkeep(agent.agent_id, self.tick)
        # 集約イベント1件（個別発火をやめてパフォーマンス改善）
        self._emit(EventType.UPKEEP_PAID,
                   data={"count": len(self.agents), "amount_each": cost,
                         "total": round(cost * len(self.agents), 1)})

    def _apply_safety_net(self) -> None:
        for agent in self.agents:
            if agent.balance < Economy.SAFETY_NET_THRESHOLD:
                if self.economy.pay_safety_net(agent.agent_id, self.tick):
                    agent.balance += Economy.SAFETY_NET_AMOUNT
                    self._emit(EventType.SAFETY_NET_PAID, agent_id=agent.agent_id,
                               data={"amount": Economy.SAFETY_NET_AMOUNT,
                                     "balance": round(agent.balance, 1),
                                     "tax_pool": round(self.economy.tax_pool, 1)})

    def _pay_patrol_salary(self) -> None:
        """Guardian/Observer は巡回・観測の対価として税プールから給与を受け取る。"""
        for agent in self.agents:
            salary = Economy.PATROL_SALARY.get(agent.role.value, 0.0)
            if salary > 0 and self.economy.tax_pool >= salary:
                self.economy.tax_pool -= salary
                agent.balance += salary
                self._emit(EventType.PATROL_SALARY, agent_id=agent.agent_id,
                           data={"salary": salary, "balance": round(agent.balance, 1)})

    def _collect_building_income(self) -> None:
        """建物収入 + 累進資本課税 + 減価償却。
        - 毎tick 耐久度 -2（50tick で自然崩壊）
        - 2棟目以降は累進課税（+15%/棟、最大45%）
        - 余剰税は tax_pool へ還元（Governor が再分配）
        """
        DEPRECIATION  = 2.0   # 耐久度/tick
        CAPITAL_TAX_STEP = 0.15
        MAX_CAPITAL_TAX  = 0.45
        rate = Economy.BUILDING_INCOME_RATE

        # ① 減価償却
        collapsed = [pos for pos, bd in self._buildings.items()
                     if bd["durability"] - DEPRECIATION <= 0]
        for pos in collapsed:
            del self._buildings[pos]
            self._emit(EventType.BUILDING_INCOME,
                       data={"event": "collapsed", "x": pos[0], "y": pos[1]})
        for bdata in self._buildings.values():
            bdata["durability"] -= DEPRECIATION

        # ② 建物収入（累進課税）
        owner_seen: Dict[str, int] = {}
        for (bx, by), bdata in list(self._buildings.items()):
            owner_id = bdata["owner"]
            if self.economy.tax_pool < rate:
                break
            owner = self._get_agent(owner_id)
            if not owner:
                continue
            seen = owner_seen.get(owner_id, 0)
            owner_seen[owner_id] = seen + 1
            cap_tax = min(MAX_CAPITAL_TAX, seen * CAPITAL_TAX_STEP)
            net_income  = round(rate * (1 - cap_tax), 2)
            extra_to_pool = round(rate * cap_tax, 2)
            self.economy.tax_pool -= rate
            self.economy.tax_pool += extra_to_pool
            owner.balance += net_income
            self._emit(EventType.BUILDING_INCOME, agent_id=owner_id,
                       data={"x": bx, "y": by, "income": net_income,
                             "capital_tax": cap_tax,
                             "durability": round(bdata["durability"], 1),
                             "balance": round(owner.balance, 1)})

    def _run_memory_market(self) -> None:
        """Memory Market: Trader が高経験WorkerからAI記憶を買い、新人Workerへ転売する。
        買った記憶 = 一定期間の入札ボーナス（WorkerAI.memory_boost で管理）。
        """
        from layer0.core.ai import TraderAI
        for trader in self.agents:
            if trader.role != AgentRole.TRADER:
                continue
            tai = self._ai.get(trader.agent_id)
            if not isinstance(tai, TraderAI):
                continue
            if self.tick - tai._last_trade_tick < tai.TRADE_COOLDOWN:
                continue

            adjacent = [a for a in self.agents
                        if abs(a.x - trader.x) + abs(a.y - trader.y) <= 1
                        and a.agent_id != trader.agent_id]

            # 買取：高経験Worker の記憶を仕入れる
            if len(tai._memory_inventory) < tai.MAX_MEMORIES:
                sellers = sorted(
                    [a for a in adjacent if a.role == AgentRole.WORKER
                     and a.experience >= tai.BUY_MIN_EXP],
                    key=lambda a: -a.experience
                )
                for seller in sellers:
                    price = round(seller.experience * tai.BUY_PRICE_PER_EXP, 1)
                    if trader.balance < price:
                        continue
                    trader.balance -= price
                    seller.balance += price
                    tai._memory_inventory.append(
                        {"experience": seller.experience, "price_paid": price}
                    )
                    tai._last_trade_tick = self.tick
                    self._emit(EventType.MEMORY_TRADE, agent_id=trader.agent_id,
                               data={"action": "buy", "seller_id": seller.agent_id,
                                     "experience": seller.experience, "price": price})
                    break

            # 転売：新人Worker に記憶を売る
            if tai._memory_inventory:
                buyers = sorted(
                    [a for a in adjacent if a.role == AgentRole.WORKER
                     and a.experience <= tai.SELL_MAX_EXP and a.memory_boost == 0],
                    key=lambda a: a.experience
                )
                for buyer in buyers:
                    mem = tai._memory_inventory[0]
                    sell_price = round(mem["price_paid"] * tai.SELL_MARKUP, 1)
                    if buyer.balance < sell_price:
                        continue
                    buyer.balance -= sell_price
                    trader.balance += sell_price
                    buyer.memory_boost = 8  # 8tick 間入札ボーナス
                    tai._memory_inventory.pop(0)
                    tai._last_trade_tick = self.tick
                    self._emit(EventType.MEMORY_TRADE, agent_id=trader.agent_id,
                               data={"action": "sell", "buyer_id": buyer.agent_id,
                                     "experience": mem["experience"], "price": sell_price,
                                     "boost_ticks": 8})
                    break

    # ── 時空歪曲メカニクス ───────────────────────────────────────────

    LOAN_AMOUNT   = 15.0   # 借入額
    LOAN_REPAY    = 22.0   # 返済額（1.47倍）
    LOAN_DURATION = 15     # 返済期限（tick）
    PARADOX_RADIUS = 3     # パラドックス崩壊の影響半径

    def _run_time_market(self) -> None:
        """時間ローン: 残高が低いエージェントが未来の自分からECを借りる。"""
        for agent in self.agents:
            if agent.agent_id in self._temporal_loans:
                continue  # 既に借入中
            if agent.expires_at is not None:
                continue  # CHRONO エージェントは借りない
            # 借入条件: 残高が低い + 性格に応じた閾値
            ai = self._ai.get(agent.agent_id)
            from layer0.core.ai import WorkerAI, WorkerTrait
            threshold = 40.0 if (isinstance(ai, WorkerAI) and ai.trait == WorkerTrait.GAMBLER) else 18.0
            if agent.balance < threshold and self.rng.random() < 0.25:
                self._temporal_loans[agent.agent_id] = {
                    "amount_due": self.LOAN_REPAY,
                    "due_tick": self.tick + self.LOAN_DURATION,
                }
                agent.balance += self.LOAN_AMOUNT
                self._temporal_stress += 1
                self._emit(EventType.TEMPORAL_LOAN, agent_id=agent.agent_id,
                           data={"borrowed": self.LOAN_AMOUNT, "repay": self.LOAN_REPAY,
                                 "due_tick": self.tick + self.LOAN_DURATION,
                                 "balance": round(agent.balance, 1),
                                 "stress": self._temporal_stress})

    def _process_temporal_loans(self) -> None:
        """時間ローン返済処理 + 返済不能時のパラドックス崩壊。"""
        due_agents = [aid for aid, loan in self._temporal_loans.items()
                      if self.tick >= loan["due_tick"]]
        for aid in due_agents:
            loan = self._temporal_loans.pop(aid)
            agent = self._get_agent(aid)
            if agent is None:
                continue
            if agent.balance >= loan["amount_due"]:
                # 正常返済
                agent.balance -= loan["amount_due"]
                self._emit(EventType.TEMPORAL_REPAYMENT, agent_id=aid,
                           data={"repaid": loan["amount_due"],
                                 "balance": round(agent.balance, 1)})
            else:
                # 返済不能 → パラドックス崩壊
                old_balance = agent.balance
                agent.balance = round(self.rng.uniform(0, 30), 1)
                agent.experience = max(0, agent.experience // 2)
                self._temporal_stress += 3
                self._emit(EventType.PARADOX_COLLAPSE, agent_id=aid,
                           data={"old_balance": round(old_balance, 1),
                                 "new_balance": agent.balance,
                                 "experience_after": agent.experience,
                                 "stress": self._temporal_stress})
                # 周囲エージェントへの時空ゆらぎ伝播
                for other in self.agents:
                    if other.agent_id == aid:
                        continue
                    dist = abs(other.x - agent.x) + abs(other.y - agent.y)
                    if dist <= self.PARADOX_RADIUS:
                        ripple = round(self.rng.uniform(-6.0, 6.0), 1)
                        other.balance = max(0.0, other.balance + ripple)
                        self._emit(EventType.PARADOX_COLLAPSE, agent_id=other.agent_id,
                                   data={"type": "ripple", "ripple": ripple,
                                         "balance": round(other.balance, 1),
                                         "source_id": aid})

    def _maybe_chrono_arrival(self) -> None:
        """時間旅行者（CHRONO Worker）が突然出現する。高い経験値と残高を持って登場。"""
        if self.tick < self._next_chrono_arrival:
            return
        self._next_chrono_arrival = self.tick + self.rng.randint(50, 100)
        self._chrono_count += 1
        # ランダムな出現位置
        for _ in range(30):
            cx = self.rng.randint(2, self.world.width - 3)
            cy = self.rng.randint(2, self.world.height - 3)
            if self.world.is_passable(cx, cy):
                break
        from layer0.core.ai import WorkerAI, WorkerTrait
        cid = f"CHR{self._chrono_count}"
        chrono = Agent(
            agent_id=cid, role=AgentRole.WORKER, x=cx, y=cy,
            energy=self.rng.uniform(60, 90),
            balance=self.rng.uniform(50, 90),
            experience=self.rng.randint(20, 50),  # 未来ではすでに多数完了済み
            expires_at=self.tick + self.rng.randint(20, 35),  # 限られた滞在時間
        )
        idx = self._role_counts.get(AgentRole.WORKER, 0)
        self._role_counts[AgentRole.WORKER] = idx + 1
        ai = WorkerAI(trait=WorkerTrait.CHRONO)
        self._ai[cid] = ai
        self.agents.append(chrono)
        self._emit(EventType.CHRONO_ARRIVAL, agent_id=cid,
                   data={"x": cx, "y": cy, "role": "Worker",
                         "energy": round(chrono.energy, 1),
                         "balance": round(chrono.balance, 1),
                         "experience": chrono.experience,
                         "expires_at": chrono.expires_at,
                         "chrono_count": self._chrono_count})

    def _expire_chrono_agents(self) -> None:
        """期限切れのCHRONOエージェントを時間軸から消滅させる。"""
        expired = [a for a in self.agents
                   if a.expires_at is not None and self.tick >= a.expires_at]
        for agent in expired:
            # 消滅前に残高の一部を近隣エージェントに「時空遺産」として残す
            legacy = round(agent.balance * 0.4, 1)
            nearby = sorted(
                [a for a in self.agents if a.agent_id != agent.agent_id],
                key=lambda a: abs(a.x - agent.x) + abs(a.y - agent.y)
            )[:3]
            share = round(legacy / max(len(nearby), 1), 1) if nearby else 0.0
            for n in nearby:
                n.balance += share
            self._emit(EventType.CHRONO_DEPARTURE, agent_id=agent.agent_id,
                       data={"final_balance": round(agent.balance, 1),
                             "legacy": legacy,
                             "legacy_share": share,
                             "recipients": [n.agent_id for n in nearby],
                             "experience_left": agent.experience})
            self.agents.remove(agent)
            del self._ai[agent.agent_id]
            self._koan_agents.discard(agent.agent_id)  # CHRONO公安なら公安登録も解除

    def _heal_agents(self) -> None:
        for medic in self.agents:
            if medic.role != AgentRole.MEDIC:
                continue
            ai = self._ai.get(medic.agent_id)
            if not isinstance(ai, MedicAI):
                continue
            # Medic の位置と同じかまたは隣接するエージェントを治療
            for client in self.agents:
                if client.agent_id == medic.agent_id:
                    continue
                dist = abs(client.x - medic.x) + abs(client.y - medic.y)
                if dist > 1:
                    continue
                if client.energy >= ai.HEAL_ENERGY_BELOW:
                    continue
                if client.balance < ai.MIN_CLIENT_BALANCE:
                    continue
                heal = min(ai.HEAL_AMOUNT, Agent.MAX_ENERGY - client.energy)
                cost = round(max(1.0, heal * ai.HEAL_PRICE_RATE), 1)
                if client.balance < cost:
                    continue
                client.energy = min(Agent.MAX_ENERGY, client.energy + heal)
                client.balance -= cost
                medic.balance  += cost
                self._emit(EventType.HEALING_DONE, agent_id=medic.agent_id,
                           data={"target_id": client.agent_id, "heal": heal,
                                 "cost": cost, "medic_balance": round(medic.balance, 1)})
                break  # 1tic につき1体のみ治療

    def _expire_tasks(self) -> None:
        """期限切れタスク（URGENT など）を失効させる。"""
        for t in self.tasks:
            if t.is_expired(self.tick):
                t.status = TaskStatus.EXPIRED
                self._emit(EventType.TASK_CREATED, task_id=t.task_id,
                           data={"event": "expired", "task_type": t.task_type.value})

    def _revert_market_event(self) -> None:
        if self._market_event:
            orig = self._market_event.get("orig_multiplier", 1.0)
            self.policy_params["reward_multiplier"] = orig

    def emit_market(self, event_name: str, details: dict) -> None:
        self._emit(EventType.MARKET_EVENT,
                   data={"event": event_name, **details})

    def _run_auctions(self) -> None:
        from layer0.core.ai import WorkerAI, WorkerTrait
        open_tasks = [t for t in self.tasks
                      if t.status == TaskStatus.OPEN and not t.is_illegal]
        for task in open_tasks:
            task.bids.clear()
            for agent in self.agents:
                if agent.arrested_until is not None and self.tick <= agent.arrested_until:
                    continue  # 逮捕中は入札不可
                # 影の市場：このtickこのタスクへの入札を放棄済み
                if self._shadow_sat.get(agent.agent_id) == task.task_id:
                    continue
                # IDLE エージェントに加え、巡回中（MOVING かつ未アサイン）も入札可
                can_bid = (agent.status == AgentStatus.IDLE or
                           (agent.status == AgentStatus.MOVING and agent.assigned_task_id is None))
                if can_bid and agent.energy > task.energy_cost:
                    # タスクタイプ別役職ボーナス確認（0.0 = 入札不可）
                    role_bonus = task.role_bid_bonus(agent.role)
                    if role_bonus == 0.0:
                        continue
                    ai = self._ai.get(agent.agent_id)
                    bid_amount = ai.get_bid(task, agent, self.rng) if ai else None
                    if bid_amount is None:
                        continue
                    # 役職ボーナス適用
                    bid_amount *= role_bonus
                    if agent.role == AgentRole.WORKER:
                        bid_amount += self.policy_params["worker_bid_bonus"]
                    # CHRONO 疑惑が高い場合はカモフラージュ（入札を意図的に下げて目立たない）
                    if (isinstance(ai, WorkerAI) and ai.trait == WorkerTrait.CHRONO
                            and self._chrono_suspicion.get(agent.agent_id, 0.0) > 8.0):
                        bid_amount *= self.rng.uniform(0.50, 0.80)
                    # ライバルが入札中なら対抗して10%増し
                    if agent.rival_id:
                        rival = self._get_agent(agent.rival_id)
                        if rival and (rival.status == AgentStatus.IDLE or
                                      (rival.status == AgentStatus.MOVING and rival.assigned_task_id is None)):
                            bid_amount *= 1.10
                    # カルト内では同士を押し上げるため自分が少し引き下げる
                    if agent.cult_id and agent.cult_id in self._cults:
                        cult_members = self._cults[agent.cult_id]
                        has_cult_rival = any(
                            mid in cult_members and mid != agent.agent_id
                            for mid in cult_members
                        )
                        if has_cult_rival and self.rng.random() < 0.25:
                            bid_amount *= 0.85
                    bid = round(bid_amount, 1)
                    task.submit_bid(agent.agent_id, bid)
                    # 特性進化統計
                    self._trait_bids[agent.agent_id] = self._trait_bids.get(agent.agent_id, 0) + 1
                    self._emit(EventType.BID_SUBMITTED, agent_id=agent.agent_id, task_id=task.task_id,
                               data={"bid": bid, "task_type": task.task_type.value})
            winner_id = task.resolve_auction(rng=self.rng)
            if winner_id:
                winner = self._get_agent(winner_id)
                if winner:
                    winner.assigned_task_id = task.task_id
                    winner.status = AgentStatus.MOVING
                    winner.target_x = task.x
                    winner.target_y = task.y
                    winning_bid = next((b.amount for b in task.bids if b.agent_id == winner_id), 0)
                    total_bids = sum(b.amount for b in task.bids)
                    win_prob = round(winning_bid / total_bids, 3) if total_bids > 0 else 1.0
                    # CHRONO が落札するたびに疑惑度が上昇（完璧すぎる入札に気づかれる）
                    w_ai = self._ai.get(winner_id)
                    if isinstance(w_ai, WorkerAI) and w_ai.trait == WorkerTrait.CHRONO:
                        self._chrono_suspicion[winner_id] = (
                            self._chrono_suspicion.get(winner_id, 0.0) + 2.5)
                    # 特性進化統計
                    self._trait_wins[winner_id] = self._trait_wins.get(winner_id, 0) + 1
                    self._emit(EventType.TASK_ASSIGNED, agent_id=winner_id, task_id=task.task_id,
                               data={"target_x": task.x, "target_y": task.y, "bid": winning_bid,
                                     "win_prob": win_prob, "num_bidders": len(task.bids)})

    # ── 闇市 / 公安メカニクス ──────────────────────────────────────────

    # 違法タスク参加確率（trait別）
    _ILLEGAL_TRAIT_PROB = {
        "gambler":     0.45,
        "rebel":       0.38,
        "nihilist":    0.25,
        "drifter":     0.20,
        "opportunist": 0.15,
        "hustler":     0.05,
        "chrono":      0.10,   # 未来を知っているが慎重
    }

    def _spawn_illegal_task(self) -> None:
        """闇市タスクをグリッドの人目につかない場所にスポーン。"""
        from layer0.core.ai import WorkerAI, WorkerTrait
        # HACK は人が集まる場所（中央）、SMUGGLE は外周付近
        task_type = self.rng.choice([TaskType.SMUGGLE, TaskType.HACK])
        w_max = self.world.width - 2
        h_max = self.world.height - 2
        if task_type == TaskType.HACK:
            # エージェントが多い場所の近く（攻撃対象が必要）
            if not self.agents:
                return
            ref = self.rng.choice(self.agents)
            for _ in range(20):
                x = max(1, min(w_max, ref.x + self.rng.randint(-3, 3)))
                y = max(1, min(h_max, ref.y + self.rng.randint(-3, 3)))
                if self.world.is_passable(x, y):
                    break
            else:
                x, y = ref.x, ref.y
        else:
            # 外周付近の暗がりにスポーン
            edge = max(4, w_max // 5)
            for _ in range(30):
                x = self.rng.choice([self.rng.randint(1, edge), self.rng.randint(w_max - edge, w_max)])
                y = self.rng.randint(1, h_max)
                if self.world.is_passable(x, y):
                    break
            else:
                x, y = 2, 2

        params = TASK_PARAMS[task_type]
        r_lo, r_hi = params["reward_range"]
        c_lo, c_hi = params["cost_range"]
        reward    = round(self.rng.uniform(r_lo, r_hi), 1)
        cost      = round(self.rng.uniform(c_lo, c_hi), 1)
        expires_at = self.tick + params["expires_in"]

        t = Task(
            task_id=str(__import__("uuid").uuid4())[:8],
            x=x, y=y, reward=reward, energy_cost=cost,
            task_type=task_type, created_tick=self.tick,
            expires_at=expires_at, is_illegal=True,
        )
        self.tasks.append(t)
        self._emit(EventType.ILLEGAL_TASK_CREATED, task_id=t.task_id,
                   data={"x": x, "y": y, "reward": reward,
                         "task_type": task_type.value, "expires_at": expires_at})

    def _run_illegal_auctions(self) -> None:
        """闇市入札。公安は参加しない。逮捕中も参加不可。"""
        from layer0.core.ai import WorkerAI, WorkerTrait
        open_illegal = [t for t in self.tasks
                        if t.is_illegal and t.status == TaskStatus.OPEN]
        for task in open_illegal:
            task.bids.clear()
            for agent in self.agents:
                if agent.arrested_until is not None and self.tick <= agent.arrested_until:
                    continue
                if agent.agent_id in self._koan_agents:
                    continue  # 公安は参加しない
                can_bid = (agent.status == AgentStatus.IDLE or
                           (agent.status == AgentStatus.MOVING and agent.assigned_task_id is None))
                if not can_bid or agent.energy <= task.energy_cost:
                    continue
                ai = self._ai.get(agent.agent_id)
                if not isinstance(ai, WorkerAI):
                    continue
                prob = self._ILLEGAL_TRAIT_PROB.get(ai.trait.value, 0.0)
                if self.rng.random() > prob:
                    continue
                # 高めに入札（リスクに見合う報酬への欲）
                bid = round(task.reward * self.rng.uniform(0.85, 1.20), 1)
                task.submit_bid(agent.agent_id, bid)
            winner_id = task.resolve_auction(rng=self.rng)
            if winner_id:
                winner = self._get_agent(winner_id)
                if winner:
                    winner.assigned_task_id = task.task_id
                    winner.status = AgentStatus.MOVING
                    winner.target_x = task.x
                    winner.target_y = task.y

    def _process_illegal_completions(self) -> None:
        """違法タスク完了処理。税なし、HACK は近隣からEC窃取。公安が目撃すると証拠蓄積。"""
        for agent in self.agents:
            if agent.status != AgentStatus.WORKING:
                continue
            task = self._get_task(agent.assigned_task_id)
            if task is None or not task.is_illegal:
                continue
            agent.spend_energy(Agent.WORK_COST)
            # 違法報酬は無税（全額受取）
            agent.balance += task.reward
            steal_amount = 0.0
            victim_id = None
            if task.task_type == TaskType.HACK:
                # 近隣から EC 窃取（公安以外が対象）
                victims = sorted(
                    [a for a in self.agents
                     if a.agent_id != agent.agent_id
                     and a.agent_id not in self._koan_agents
                     and abs(a.x - agent.x) + abs(a.y - agent.y) <= 3],
                    key=lambda a: abs(a.x - agent.x) + abs(a.y - agent.y)
                )
                if victims:
                    victim = victims[0]
                    steal_amount = round(min(victim.balance, self.rng.uniform(8.0, 15.0)), 1)
                    victim.balance = max(0.0, victim.balance - steal_amount)
                    agent.balance += steal_amount
                    victim_id = victim.agent_id
            task.status = TaskStatus.COMPLETED
            task.completed_tick = self.tick
            agent.experience += 1
            self._emit(EventType.ILLEGAL_TASK_COMPLETED, agent_id=agent.agent_id,
                       task_id=task.task_id,
                       data={"reward": task.reward, "steal": steal_amount,
                             "victim_id": victim_id,
                             "task_type": task.task_type.value,
                             "balance": round(agent.balance, 1)})
            # 近くの公安が目撃 → 証拠蓄積
            ev_gain = 6.0 if task.task_type == TaskType.HACK else 4.0
            for koan_id in self._koan_agents:
                koan = self._get_agent(koan_id)
                if koan and abs(koan.x - agent.x) + abs(koan.y - agent.y) <= 4:
                    self._koan_evidence[agent.agent_id] = (
                        self._koan_evidence.get(agent.agent_id, 0.0) + ev_gain)
            agent.assigned_task_id = None
            agent.target_x = None
            agent.target_y = None
            agent.status = AgentStatus.IDLE

    def _update_koan_evidence(self) -> None:
        """証拠自然減衰 + Observer INFORMANT による密告。"""
        from layer0.core.ai import ObserverAI, ObserverPersonality
        # 自然減衰（容疑者が何もしなければ疑惑は薄れる）
        for aid in list(self._koan_evidence):
            self._koan_evidence[aid] = max(0.0, self._koan_evidence[aid] - 0.1)
            if self._koan_evidence[aid] == 0.0:
                del self._koan_evidence[aid]
        # Observer INFORMANT 性格 → 近隣公安に密告（30%/tick）
        for obs in self.agents:
            if obs.role != AgentRole.OBSERVER:
                continue
            obs_ai = self._ai.get(obs.agent_id)
            if not isinstance(obs_ai, ObserverAI):
                continue
            if obs_ai.personality != ObserverPersonality.INFORMANT:
                continue
            if self.rng.random() > 0.30:
                continue
            nearby_koan = [a for a in self.agents
                           if a.agent_id in self._koan_agents
                           and abs(a.x - obs.x) + abs(a.y - obs.y) <= 5]
            if not nearby_koan:
                continue
            suspects = [aid for aid, ev in self._koan_evidence.items() if ev > 0.0]
            suspects_nearby = [sid for sid in suspects
                               if (sa := self._get_agent(sid)) and
                               abs(sa.x - obs.x) + abs(sa.y - obs.y) <= 5]
            for sid in suspects_nearby[:1]:
                self._koan_evidence[sid] = self._koan_evidence.get(sid, 0.0) + 5.0
                self._emit(EventType.INFORMANT_TIP, agent_id=obs.agent_id,
                           data={"suspect_id": sid,
                                 "evidence_gain": 5.0,
                                 "koan_ids": [k.agent_id for k in nearby_koan]})

    def _run_koan_targeting(self) -> None:
        """公安が最重要容疑者を追尾。"""
        if not self._koan_evidence:
            return
        top_id = max(self._koan_evidence, key=self._koan_evidence.get)
        target = self._get_agent(top_id)
        if target is None:
            return
        for koan_id in self._koan_agents:
            koan = self._get_agent(koan_id)
            if koan and koan.status == AgentStatus.IDLE:
                koan.target_x = target.x
                koan.target_y = target.y
                koan.status = AgentStatus.MOVING

    def _process_koan_arrests(self) -> None:
        """証拠閾値到達 → 逮捕: 残高60%没収 + 15tick 活動停止。"""
        ARREST_THRESHOLD = 10.0
        ARREST_DURATION  = 15
        SEIZE_RATIO      = 0.60
        to_arrest = [aid for aid, ev in list(self._koan_evidence.items())
                     if ev >= ARREST_THRESHOLD]
        for aid in to_arrest:
            agent = self._get_agent(aid)
            if agent is None:
                self._koan_evidence.pop(aid, None)
                continue
            if agent.arrested_until is not None and self.tick <= agent.arrested_until:
                continue  # 既に逮捕中
            seized = round(agent.balance * SEIZE_RATIO, 1)
            agent.balance = max(0.0, agent.balance - seized)
            self.economy.tax_pool += seized
            agent.arrested_until = self.tick + ARREST_DURATION
            agent.status = AgentStatus.IDLE
            agent.assigned_task_id = None
            agent.target_x = None
            agent.target_y = None
            self._koan_evidence.pop(aid, None)
            self._arrest_count += 1
            self._total_seized += seized
            self._emit(EventType.KOAN_ARREST, agent_id=aid,
                       data={"seized": seized,
                             "balance_after": round(agent.balance, 1),
                             "arrested_until": agent.arrested_until})

    def _release_arrested(self) -> None:
        """逮捕期間終了エージェントを釈放。"""
        for agent in self.agents:
            if agent.arrested_until is not None and self.tick > agent.arrested_until:
                agent.arrested_until = None

    # ── 影の市場 ────────────────────────────────────────────────────────
    def _run_shadow_deals(self) -> None:
        """Worker が他のWorkerに賄賂を渡して特定タスクへの入札を降ろす（15% 確率/tick）。
        Observer INFORMANT が近くにいると証拠を蓄積。"""
        from layer0.core.ai import WorkerAI, WorkerTrait
        open_tasks = [t for t in self.tasks
                      if t.status == TaskStatus.OPEN and not t.is_illegal]
        if not open_tasks:
            return
        for agent in self.agents:
            if agent.role != AgentRole.WORKER:
                continue
            if agent.balance < 15.0:
                continue
            if self.rng.random() > 0.15:
                continue
            ai = self._ai.get(agent.agent_id)
            if not isinstance(ai, WorkerAI):
                continue
            if ai.trait not in (WorkerTrait.OPPORTUNIST, WorkerTrait.HUSTLER, WorkerTrait.GAMBLER):
                continue
            # ターゲットタスクを選ぶ（報酬上位）
            target_task = max(open_tasks, key=lambda t: t.reward)
            # 近くにいる競合Workerを賄賂対象に
            rivals = [a for a in self.agents
                      if a.role == AgentRole.WORKER
                      and a.agent_id != agent.agent_id
                      and a.agent_id not in self._koan_agents
                      and abs(a.x - agent.x) + abs(a.y - agent.y) <= 4]
            if not rivals:
                continue
            bribe_target = self.rng.choice(rivals)
            bribe_amount = round(self.rng.uniform(3.0, 8.0), 1)
            if agent.balance < bribe_amount:
                continue
            agent.balance -= bribe_amount
            bribe_target.balance += bribe_amount
            self._shadow_sat[bribe_target.agent_id] = target_task.task_id
            self._shadow_deal_count += 1
            self._emit(EventType.SHADOW_DEAL, agent_id=agent.agent_id,
                       data={"target_id": bribe_target.agent_id,
                             "task_id": target_task.task_id,
                             "bribe": bribe_amount})
            # Observer INFORMANT が近くにいると公安証拠として記録
            for obs in self.agents:
                if obs.role != AgentRole.OBSERVER:
                    continue
                from layer0.core.ai import ObserverAI, ObserverPersonality
                obs_ai = self._ai.get(obs.agent_id)
                if (isinstance(obs_ai, ObserverAI)
                        and obs_ai.personality == ObserverPersonality.INFORMANT
                        and abs(obs.x - agent.x) + abs(obs.y - agent.y) <= 3):
                    self._koan_evidence[agent.agent_id] = (
                        self._koan_evidence.get(agent.agent_id, 0.0) + 3.0)
            break  # 1tickに1エージェントのみ

    # ── 感情・暴動 ─────────────────────────────────────────────────────
    def _update_emotions(self) -> None:
        """感情の伝染と自然減衰。エネルギー低下・逮捕でネガティブ化。"""
        for agent in self.agents:
            # 自然減衰（中立に戻る）
            if agent.emotion_level > 0:
                agent.emotion_level = max(0.0, agent.emotion_level - 0.3)
            elif agent.emotion_level < 0:
                agent.emotion_level = min(0.0, agent.emotion_level + 0.2)
            # エネルギー低下で不安
            if agent.energy < 20.0:
                agent.emotion_level = max(-10.0, agent.emotion_level - 0.8)
            # 残高低下で不安
            if agent.balance < 10.0:
                agent.emotion_level = max(-10.0, agent.emotion_level - 0.5)
            # 逮捕中は怒り
            if agent.arrested_until is not None and self.tick <= agent.arrested_until:
                agent.emotion_level = max(-10.0, agent.emotion_level - 1.5)
        # 感情伝染（半径2以内のエージェント同士で伝播）
        for agent in self.agents:
            neighbors = [a for a in self.agents
                         if a.agent_id != agent.agent_id
                         and abs(a.x - agent.x) + abs(a.y - agent.y) <= 2]
            if not neighbors:
                continue
            avg_neighbor = sum(n.emotion_level for n in neighbors) / len(neighbors)
            diff = avg_neighbor - agent.emotion_level
            agent.emotion_level = round(
                max(-10.0, min(10.0, agent.emotion_level + diff * 0.15)), 2)
        # 暴動チェック
        workers = [a for a in self.agents if a.role == AgentRole.WORKER]
        if not workers:
            return
        angry = [w for w in workers if w.emotion_level < -5.0]
        if len(angry) / len(workers) >= 0.35:
            self._trigger_riot(angry)

    def _trigger_riot(self, rioters: list) -> None:
        """暴動: 怒ったWorkerが建物を破壊し、近くのエージェントのECを奪う。"""
        self._riot_ticks += 1
        damage_done = 0
        for rioter in rioters[:5]:  # 最大5体まで行動
            # 近くの建物を破壊
            for pos in list(self._buildings.keys()):
                bx, by = pos
                if abs(bx - rioter.x) + abs(by - rioter.y) <= 3:
                    del self._buildings[pos]
                    damage_done += 1
                    break
            # 近くのエージェントからEC略奪
            victims = [a for a in self.agents
                       if a.agent_id != rioter.agent_id
                       and a.agent_id not in self._koan_agents
                       and abs(a.x - rioter.x) + abs(a.y - rioter.y) <= 2]
            if victims:
                v = self.rng.choice(victims)
                loot = round(min(v.balance, self.rng.uniform(2.0, 8.0)), 1)
                v.balance = max(0.0, v.balance - loot)
                rioter.balance += loot
            rioter.emotion_level = min(10.0, rioter.emotion_level + 3.0)  # 発散でちょっとスッキリ
        self._emit(EventType.EMOTION_RIOT,
                   data={"rioters": len(rioters),
                         "buildings_destroyed": damage_done,
                         "riot_count": self._riot_ticks})

    # ── 死と転生 ──────────────────────────────────────────────────────
    def _check_deaths(self) -> None:
        """エネルギーが0になったエージェントを追跡。3tick継続で死亡→転生。"""
        dead = []
        for agent in self.agents:
            if agent.energy <= 0.0:
                self._zero_energy_ticks[agent.agent_id] = (
                    self._zero_energy_ticks.get(agent.agent_id, 0) + 1)
                if self._zero_energy_ticks[agent.agent_id] >= 3:
                    dead.append(agent)
            else:
                self._zero_energy_ticks.pop(agent.agent_id, None)
        for agent in dead:
            self._reincarnate(agent)

    def _reincarnate(self, agent: "Agent") -> None:  # type: ignore[name-defined]
        """エージェントを転生させる: 経験値の半分を継承した新個体として復活。"""
        inherited_exp = agent.experience // 2
        generation = agent.generation + 1
        self._reincarnation_count += 1
        # 同位置か近くの通行可能セルに復活
        for _ in range(20):
            rx = max(1, min(self.world.width - 2,
                            agent.x + self.rng.randint(-3, 3)))
            ry = max(1, min(self.world.height - 2,
                            agent.y + self.rng.randint(-3, 3)))
            if self.world.is_passable(rx, ry):
                break
        else:
            rx, ry = agent.x, agent.y
        self._emit(EventType.AGENT_DIED, agent_id=agent.agent_id,
                   data={"experience": agent.experience, "generation": agent.generation,
                         "balance_left": round(agent.balance, 1)})
        # 遺産を近隣に分配
        if agent.balance > 0:
            legacy_share = round(agent.balance * 0.3, 1)
            nearby = sorted(
                [a for a in self.agents if a.agent_id != agent.agent_id],
                key=lambda a: abs(a.x - agent.x) + abs(a.y - agent.y)
            )[:3]
            share = round(legacy_share / max(len(nearby), 1), 1) if nearby else 0.0
            for n in nearby:
                n.balance += share
        # 既存エージェントを刷新（転生）
        agent.x = rx
        agent.y = ry
        agent.energy = 60.0
        agent.balance = 20.0
        agent.experience = inherited_exp
        agent.generation = generation
        agent.status = AgentStatus.IDLE
        agent.assigned_task_id = None
        agent.target_x = None
        agent.target_y = None
        agent.emotion_level = 0.0
        agent.arrested_until = None
        self._zero_energy_ticks.pop(agent.agent_id, None)
        self._temporal_loans.pop(agent.agent_id, None)
        self._emit(EventType.AGENT_REBORN, agent_id=agent.agent_id,
                   data={"x": rx, "y": ry, "generation": generation,
                         "inherited_exp": inherited_exp,
                         "reincarnation_count": self._reincarnation_count})

    # ── カルト ────────────────────────────────────────────────────────
    def _update_cult(self) -> None:
        """CHRONO到来やParadox目撃者がカルトを形成・拡大する。"""
        # CHRONO到来イベントの目撃者をカルト候補に
        recent_chrono = [e for e in self.event_log
                         if e.tick == self.tick
                         and e.event_type in (EventType.CHRONO_ARRIVAL, EventType.PARADOX_COLLAPSE)]
        for event in recent_chrono:
            ex = event.payload.get("x", 10)
            ey = event.payload.get("y", 10)
            witnesses = [a for a in self.agents
                         if a.role == AgentRole.WORKER
                         and a.cult_id is None
                         and abs(a.x - ex) + abs(a.y - ey) <= 5]
            if len(witnesses) >= 2 and self.rng.random() < 0.40:
                # 新カルト結成
                self._cult_counter += 1
                cid = f"CULT{self._cult_counter}"
                self._cults[cid] = set()
                leader = self.rng.choice(witnesses)
                for w in witnesses[:3]:
                    w.cult_id = cid
                    self._cults[cid].add(w.agent_id)
                    self._emit(EventType.CULT_JOINED, agent_id=w.agent_id,
                               data={"cult_id": cid, "leader": leader.agent_id,
                                     "size": len(self._cults[cid])})
        # カルト崩壊チェック（公安が複数メンバーを逮捕 → 解散）
        for cid in list(self._cults.keys()):
            members = self._cults[cid]
            alive = [mid for mid in members
                     if self._get_agent(mid) is not None]
            arrested = [mid for mid in alive
                        if (ag := self._get_agent(mid)) and
                        ag.arrested_until is not None and self.tick <= ag.arrested_until]
            if len(alive) < 2 or len(arrested) >= 2:
                for mid in alive:
                    ag = self._get_agent(mid)
                    if ag:
                        ag.cult_id = None
                del self._cults[cid]
                self._emit(EventType.CULT_BUSTED,
                           data={"cult_id": cid,
                                 "reason": "arrested" if arrested else "disbanded"})
            else:
                self._cults[cid] = set(alive)

    # ── 特性進化 ───────────────────────────────────────────────────────
    TRAIT_DRIFT = {
        "gambler":     "nihilist",
        "nihilist":    "drifter",
        "rebel":       "drifter",
        "specialist":  "hustler",
        "conformist":  "saver",
        "opportunist": "explorer",
        "explorer":    "hustler",
        "hustler":     "opportunist",
        "saver":       "saver",
        "drifter":     "drifter",
        "chrono":      "chrono",
    }

    def _evolve_traits(self) -> None:
        """25tick毎に実行: 成績不振のWorkerの特性を漂流させる。"""
        from layer0.core.ai import WorkerAI, WorkerTrait
        for agent in self.agents:
            if agent.role != AgentRole.WORKER:
                continue
            ai = self._ai.get(agent.agent_id)
            if not isinstance(ai, WorkerAI):
                continue
            if ai.trait == WorkerTrait.CHRONO:
                continue
            wins = self._trait_wins.get(agent.agent_id, 0)
            bids = self._trait_bids.get(agent.agent_id, 0)
            old_balance = self._trait_balance_snap.get(agent.agent_id, agent.balance)
            balance_delta = agent.balance - old_balance
            # 成績不振判定: 落札率低い or 残高減少
            win_rate = wins / max(bids, 1)
            if win_rate < 0.15 or balance_delta < -10.0:
                old_trait = ai.trait.value
                new_val = self.TRAIT_DRIFT.get(old_trait, old_trait)
                if new_val != old_trait:
                    ai.trait = WorkerTrait(new_val)
                    self._emit(EventType.TRAIT_EVOLVED, agent_id=agent.agent_id,
                               data={"from": old_trait, "to": new_val,
                                     "win_rate": round(win_rate, 2),
                                     "balance_delta": round(balance_delta, 1)})
            # スナップショット更新
            self._trait_wins[agent.agent_id] = 0
            self._trait_bids[agent.agent_id] = 0
            self._trait_balance_snap[agent.agent_id] = agent.balance

    # ── 銀行 ─────────────────────────────────────────────────────────
    BANK_LOAN_RATE    = 1.30  # 元本の130%を返済
    BANK_LOAN_TICKS   = 20   # 返済期限
    BANK_MIN_BALANCE  = 5.0  # 最低残高以上あれば預金

    def _run_bank(self) -> None:
        """銀行システム: 預金利息・融資・返済・デフォルト処理。"""
        # 預金利息（1.5%/tick）
        for agent in self.agents:
            dep = self._bank_deposits.get(agent.agent_id, 0.0)
            if dep > 0:
                interest = round(dep * self._bank_interest_rate, 2)
                agent.balance += interest
                self._bank_deposits[agent.agent_id] += interest
                self._bank_reserves += interest * 0.5  # 準備金へ半分
                self._emit(EventType.BANK_INTEREST, agent_id=agent.agent_id,
                           data={"interest": interest, "deposit": round(dep, 2)})

        # 預金勧誘（残高が高いWorker/Traderが自動預金）
        for agent in self.agents:
            if agent.agent_id in self._bank_deposits:
                continue
            if agent.agent_id in self._bank_loans:
                continue
            if agent.balance >= 60.0 and self.rng.random() < 0.08:
                deposit_amount = round(agent.balance * 0.3, 1)
                agent.balance -= deposit_amount
                self._bank_deposits[agent.agent_id] = deposit_amount
                self._bank_reserves += deposit_amount * 0.1
                self._emit(EventType.BANK_DEPOSIT, agent_id=agent.agent_id,
                           data={"amount": deposit_amount,
                                 "balance": round(agent.balance, 1)})

        # 引き出し（預金が高い & 残高が低い場合）
        for agent in self.agents:
            dep = self._bank_deposits.get(agent.agent_id, 0.0)
            if dep > 0 and agent.balance < 15.0:
                withdraw = min(dep, round(dep * 0.5, 1))
                agent.balance += withdraw
                self._bank_deposits[agent.agent_id] -= withdraw
                if self._bank_deposits[agent.agent_id] < 0.1:
                    del self._bank_deposits[agent.agent_id]
                self._emit(EventType.BANK_WITHDRAW, agent_id=agent.agent_id,
                           data={"amount": withdraw,
                                 "balance": round(agent.balance, 1)})

        # 融資（残高低い & 預金なし & 融資なし）
        for agent in self.agents:
            if agent.agent_id in self._bank_loans:
                continue
            if agent.agent_id in self._bank_deposits:
                continue
            if agent.balance < 10.0 and self._bank_reserves > 20.0 and self.rng.random() < 0.10:
                loan_amount = round(self.rng.uniform(10.0, 25.0), 1)
                due = self.tick + self.BANK_LOAN_TICKS
                agent.balance += loan_amount
                self._bank_reserves -= loan_amount
                self._bank_loans[agent.agent_id] = {
                    "amount_due": round(loan_amount * self.BANK_LOAN_RATE, 1),
                    "due_tick": due,
                }
                self._emit(EventType.BANK_LOAN, agent_id=agent.agent_id,
                           data={"amount": loan_amount,
                                 "amount_due": round(loan_amount * self.BANK_LOAN_RATE, 1),
                                 "due_tick": due})

        # 返済処理
        due = [aid for aid, loan in self._bank_loans.items()
               if self.tick >= loan["due_tick"]]
        for aid in due:
            loan = self._bank_loans.pop(aid)
            agent = self._get_agent(aid)
            if agent is None:
                continue
            if agent.balance >= loan["amount_due"]:
                agent.balance -= loan["amount_due"]
                self._bank_reserves += loan["amount_due"]
                self._emit(EventType.BANK_REPAYMENT, agent_id=aid,
                           data={"repaid": loan["amount_due"],
                                 "balance": round(agent.balance, 1)})
            else:
                # デフォルト: 残高を全額没収してペナルティ
                seized = agent.balance
                self._bank_reserves += seized
                agent.balance = 0.0
                agent.emotion_level = max(-10.0, agent.emotion_level - 3.0)
                self._emit(EventType.BANK_DEFAULT, agent_id=aid,
                           data={"seized": seized,
                                 "amount_due": loan["amount_due"]})

    # ── 株式市場 ──────────────────────────────────────────────────────
    STOCK_MAX_SHARES = 50  # 1エージェントが保有できる最大株数

    def _run_stock_market(self) -> None:
        """株式市場: ARCH/TRAD/WORK の3銘柄。イベント連動価格変動・配当・クラッシュ。"""
        # 価格変動（毎tick）
        for ticker, data in self._stocks.items():
            vol = data["volatility"]
            drift = self.rng.gauss(0, vol)
            data["price"] = round(max(1.0, data["price"] * (1 + drift)), 2)

        # イベント連動価格変動
        if self.tick >= self._next_stock_event:
            self._next_stock_event = self.tick + self.rng.randint(20, 50)
            ticker = self.rng.choice(list(self._stocks.keys()))
            move = self.rng.uniform(-0.25, 0.35)
            self._stocks[ticker]["price"] = round(
                max(1.0, self._stocks[ticker]["price"] * (1 + move)), 2)

        # クラッシュ判定（いずれかの銘柄が初期値40%以下）
        for ticker, data in self._stocks.items():
            if data["price"] <= 4.0:
                self._emit(EventType.MARKET_CRASH,
                           data={"ticker": ticker, "price": data["price"]})
                data["price"] = 6.0  # 下限リセット

        # 自動売買（残高が高い Trader/Architect が小口購入）
        for agent in self.agents:
            if agent.role not in (AgentRole.TRADER, AgentRole.ARCHITECT):
                continue
            if agent.balance < 20.0 or self.rng.random() > 0.10:
                continue
            ticker = self.rng.choice(list(self._stocks.keys()))
            price = self._stocks[ticker]["price"]
            if agent.balance >= price:
                shares = min(self.STOCK_MAX_SHARES,
                             int(agent.balance * 0.15 / price))
                if shares < 1:
                    continue
                cost = round(shares * price, 2)
                agent.balance -= cost
                port = self._portfolios.setdefault(agent.agent_id, {})
                port[ticker] = port.get(ticker, 0) + shares
                self._emit(EventType.STOCK_BOUGHT, agent_id=agent.agent_id,
                           data={"ticker": ticker, "shares": shares, "price": price,
                                 "cost": cost, "balance": round(agent.balance, 1)})

        # 自動売却（残高が低い場合に株を売る）
        for agent in self.agents:
            if agent.balance > 15.0:
                continue
            port = self._portfolios.get(agent.agent_id)
            if not port:
                continue
            ticker = next(iter(port))
            shares_held = port[ticker]
            sell = max(1, shares_held // 2)
            price = self._stocks[ticker]["price"]
            proceeds = round(sell * price, 2)
            agent.balance += proceeds
            port[ticker] -= sell
            if port[ticker] <= 0:
                del port[ticker]
            self._emit(EventType.STOCK_SOLD, agent_id=agent.agent_id,
                       data={"ticker": ticker, "shares": sell, "price": price,
                             "proceeds": proceeds, "balance": round(agent.balance, 1)})

        # 配当（30tick毎）
        self._dividend_countdown -= 1
        if self._dividend_countdown <= 0:
            self._dividend_countdown = 30
            for agent_id, port in self._portfolios.items():
                agent = self._get_agent(agent_id)
                if not agent:
                    continue
                total_div = 0.0
                for ticker, shares in port.items():
                    div_per_share = round(self._stocks[ticker]["price"] * 0.03, 3)
                    total_div += shares * div_per_share
                total_div = round(total_div, 2)
                if total_div > 0:
                    agent.balance += total_div
                    self._emit(EventType.STOCK_DIVIDEND, agent_id=agent_id,
                               data={"dividend": total_div,
                                     "portfolio": dict(port)})

    def _update_chrono_suspicion(self) -> None:
        """CHRONO エージェントの正体発覚疑惑度を更新。Guardian 近接・連勝で上昇、自然減衰。"""
        from layer0.core.ai import WorkerAI, WorkerTrait, GuardianAI, GuardianPersonality
        to_expose = []
        for agent in self.agents:
            if agent.expires_at is None:
                continue
            ai = self._ai.get(agent.agent_id)
            if not isinstance(ai, WorkerAI) or ai.trait != WorkerTrait.CHRONO:
                continue
            if agent.agent_id not in self._chrono_suspicion:
                self._chrono_suspicion[agent.agent_id] = 0.0
            # 自然減衰（-0.3/tick — 目立たなければ疑惑は薄れる）
            self._chrono_suspicion[agent.agent_id] = max(
                0.0, self._chrono_suspicion[agent.agent_id] - 0.3)
            # Guardian 近接チェック（半径3以内）
            for guard in self.agents:
                if guard.role != AgentRole.GUARDIAN:
                    continue
                dist = abs(guard.x - agent.x) + abs(guard.y - agent.y)
                if dist > 3:
                    continue
                g_ai = self._ai.get(guard.agent_id)
                if isinstance(g_ai, GuardianAI) and g_ai.personality in (
                        GuardianPersonality.AGGRESSIVE, GuardianPersonality.VIGILANT):
                    self._chrono_suspicion[agent.agent_id] += 2.5
                else:
                    self._chrono_suspicion[agent.agent_id] += 0.8
            if self._chrono_suspicion[agent.agent_id] >= 15.0:
                to_expose.append(agent)
        for agent in to_expose:
            self._expose_chrono(agent)

    def _expose_chrono(self, agent: Agent) -> None:
        """CHRONO 正体発覚 — 知識爆発 + 大規模パラドックス波。"""
        suspicion = self._chrono_suspicion.pop(agent.agent_id, 0.0)
        # 半径5以内の近隣エージェントに知識 + 遺産を分配
        close = [a for a in self.agents
                 if a.agent_id != agent.agent_id
                 and abs(a.x - agent.x) + abs(a.y - agent.y) <= 5]
        exp_leak       = agent.experience // 3
        knowledge_share = round(exp_leak * 0.5 / max(len(close), 1), 1) if close else 0.0
        legacy_share    = round(agent.balance * 0.6 / max(len(close), 1), 1) if close else 0.0
        total_share     = round(knowledge_share + legacy_share, 1)
        for a in close:
            a.balance += total_share
        # 大規模パラドックス波（半径3: ±15 EC、半径4-5: ±5 EC）
        for a in self.agents:
            if a.agent_id == agent.agent_id:
                continue
            dist = abs(a.x - agent.x) + abs(a.y - agent.y)
            if dist <= 3:
                ripple = round(self.rng.uniform(-15.0, 15.0), 1)
                a.balance = max(0.0, a.balance + ripple)
            elif dist <= 5:
                ripple = round(self.rng.uniform(-5.0, 5.0), 1)
                a.balance = max(0.0, a.balance + ripple)
        self._emit(EventType.TEMPORAL_EXPOSURE, agent_id=agent.agent_id,
                   data={"suspicion": round(suspicion, 1),
                         "experience_leaked": exp_leak,
                         "share_per_agent": total_share,
                         "close_agents": [a.agent_id for a in close],
                         "x": agent.x, "y": agent.y})
        # CHRONO公安が発覚 → 追跡中の証拠も全消去（被疑者は逃亡）
        if agent.agent_id in self._koan_agents:
            self._koan_agents.discard(agent.agent_id)
            self._koan_evidence.clear()  # 捜査情報が漏洩 → 証拠隠滅
        self.agents.remove(agent)
        self._ai.pop(agent.agent_id, None)
        self._temporal_loans.pop(agent.agent_id, None)
        self._temporal_stress += 5

    def _move_agents(self) -> None:
        for agent in self.agents:
            if agent.status != AgentStatus.MOVING or agent.target_x is None:
                continue
            nx, ny = agent.move_toward(agent.target_x, agent.target_y)
            if self.world.is_passable(nx, ny):
                agent.x, agent.y = nx, ny
                agent.spend_energy(Agent.MOVE_COST)
                # 建物セルを通過 → 移動コストの一部を回収（耐久あり建物のみ）
                bdata = self._buildings.get((nx, ny))
                if bdata and bdata["durability"] > 0:
                    agent.energy = min(Agent.MAX_ENERGY, agent.energy + 0.3)
                self._emit(EventType.AGENT_MOVED, agent_id=agent.agent_id,
                           data={"x": nx, "y": ny, "energy": round(agent.energy, 1)})
            if agent.x == agent.target_x and agent.y == agent.target_y:
                agent.status = AgentStatus.WORKING

    def _work_agents(self) -> None:
        governors = [a for a in self.agents if a.role == AgentRole.GOVERNOR]
        for agent in self.agents:
            if agent.status != AgentStatus.WORKING:
                continue
            task = self._get_task(agent.assigned_task_id)
            if task is None:
                agent.status = AgentStatus.IDLE
                continue
            if task.is_illegal:
                continue  # 違法タスクは _process_illegal_completions() で処理
            agent.spend_energy(Agent.WORK_COST)
            net = task.reward * (1 - self.policy_params["tax_rate"])
            agent.balance += net
            task.status = TaskStatus.COMPLETED
            task.completed_tick = self.tick
            # 税収の30%をGovernorへ — KPIスコアで倍率調整（良い都市統治ほど多く稼げる）
            gov_cut = self.economy.pay_reward(agent.agent_id, task.reward, task.task_id, self.tick)
            if governors and gov_cut > 0:
                scores   = self.policy.score(self.agents, self.tasks)
                kpi      = (scores.get("efficiency", 1.0) + scores.get("equality", 1.0)) / 2
                kpi_factor = round(max(0.4, min(1.3, kpi)), 3)  # 0.4〜1.3の範囲
                adjusted_cut = round(gov_cut * kpi_factor, 2)
                # KPI調整後の余剰 or 不足は税プールへ
                self.economy.tax_pool += round(gov_cut - adjusted_cut, 2)
                share = round(adjusted_cut / len(governors), 2)
                for gov in governors:
                    gov.balance += share
                    self._emit(EventType.GOVERNANCE_REWARD, agent_id=gov.agent_id,
                               data={"reason": "tax_dividend", "reward": share,
                                     "kpi_factor": kpi_factor, "task_id": task.task_id})
            # CONSTRUCT完了 → 建物を登録（耐久度100でスタート）
            if task.task_type == TaskType.CONSTRUCT:
                self._buildings[(task.x, task.y)] = {
                    "owner": agent.agent_id, "durability": 100.0, "built_tick": self.tick
                }
                self._emit(EventType.BUILDING_INCOME, agent_id=agent.agent_id,
                           data={"event": "built", "x": task.x, "y": task.y,
                                 "buildings_total": len(self._buildings)})
            # 経験値加算（記憶資本）
            agent.experience += 1
            # 同盟相手にボーナスの5%をシェア
            if agent.ally_id:
                ally = self._get_agent(agent.ally_id)
                if ally and net > 0:
                    ally_share = round(net * 0.05, 2)
                    ally.balance += ally_share
            self._emit(EventType.TASK_COMPLETED, agent_id=agent.agent_id, task_id=task.task_id,
                       data={"reward": net, "energy": round(agent.energy, 1), "balance": round(agent.balance, 1)})
            # 感情: タスク完了で少し幸福
            agent.emotion_level = min(10.0, agent.emotion_level + 1.0)
            # 因果ループ: タスク完了が過去に干渉し同種タスクを引き寄せる（10%）
            if self.rng.random() < 0.10:
                loop_task = self.spawn_task(task_type=task.task_type)
                self._emit(EventType.CAUSALITY_LOOP, agent_id=agent.agent_id,
                           task_id=task.task_id,
                           data={"loop_task_id": loop_task.task_id,
                                 "task_type": task.task_type.value,
                                 "loop_reward": loop_task.reward})
            agent.assigned_task_id = None
            agent.target_x = None
            agent.target_y = None
            agent.status = AgentStatus.IDLE

    def _charge_agents(self) -> None:
        for agent in self.agents:
            cell = self.world.get_cell(agent.x, agent.y)
            if cell == Cell.CHARGE:
                agent.charge()
                agent.status = AgentStatus.CHARGING
                self._emit(EventType.AGENT_CHARGED, agent_id=agent.agent_id, data={"energy": agent.energy})

    def _emit(self, event_type: EventType, agent_id: Optional[str] = None,
              task_id: Optional[str] = None, data: Optional[Dict] = None) -> None:
        self._seq += 1
        self.event_log.append(Event(
            tick=self.tick,
            sequence_id=self._seq,
            event_type=event_type,
            source="simulator",
            agent_id=agent_id,
            task_id=task_id,
            payload=data or {},
        ))

    def _get_agent(self, agent_id: Optional[str]) -> Optional[Agent]:
        return next((a for a in self.agents if a.agent_id == agent_id), None)

    def _get_task(self, task_id: Optional[str]) -> Optional[Task]:
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def _snapshot(self) -> StateSnapshot:
        active = [t for t in self.tasks
                  if t.status not in (TaskStatus.COMPLETED, TaskStatus.EXPIRED)]
        return StateSnapshot(
            tick=self.tick,
            agents=[AgentSnapshot(
                agent_id=a.agent_id, role=a.role.value, x=a.x, y=a.y,
                energy=round(a.energy, 1), balance=round(a.balance, 1), status=a.status.value
            ) for a in self.agents],
            tasks=[TaskSnapshot(
                task_id=t.task_id, x=t.x, y=t.y,
                reward=t.reward, energy_cost=t.energy_cost,
                status=t.status.value, assigned_to=t.assigned_to,
                task_type=t.task_type.value, expires_at=t.expires_at,
            ) for t in active],
            economy=EconomySnapshot(
                tick=self.tick,
                total_energy=round(sum(a.energy for a in self.agents), 1),
                total_balance=round(sum(a.balance for a in self.agents), 1),
                transactions=self.economy.tx_count,
            ),
            metrics=self._calc_metrics(),
        )

    def _calc_metrics(self) -> Dict:
        completed = [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
        expired   = [t for t in self.tasks if t.status == TaskStatus.EXPIRED]
        total = len(self.tasks)
        balances = [a.balance for a in self.agents]
        mean_b = sum(balances) / len(balances) if balances else 0
        if len(balances) > 1 and mean_b > 0:
            gini = sum(abs(b1 - b2) for b1 in balances for b2 in balances) / (2 * len(balances) ** 2 * mean_b)
        else:
            gini = 0.0
        scores = self.policy.score(self.agents, self.tasks)
        return {
            "task_completion_rate": round(len(completed) / total, 2) if total else 0,
            "task_expired_count": len(expired),
            "open_tasks": len([t for t in self.tasks if t.status == TaskStatus.OPEN]),
            "total_energy": round(sum(a.energy for a in self.agents), 1),
            "mean_balance": round(mean_b, 1),
            "gini": round(gini, 3),
            "policy_efficiency": scores.get("efficiency", 0),
            "policy_equality": scores.get("equality", 0),
            "policy_violations": len(self.policy.violations),
            "tax_pool": round(self.economy.tax_pool, 1),
        }

    def save_log(self, path: str = "logs/events.jsonl") -> None:
        Path(path).parent.mkdir(exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in self.event_log:
                f.write(e.model_dump_json() + "\n")

    def save_replay(self, path: str = "replays/replay.jsonl") -> None:
        Path(path).parent.mkdir(exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"seed": self.seed}) + "\n")
            for s in self.snapshots:
                f.write(s.model_dump_json() + "\n")
