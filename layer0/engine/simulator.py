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
from layer0.core.ai import RoleAI, make_ai, GovernorAI, MedicAI
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
        self._market_event: Optional[Dict] = None   # 発動中のイベント
        self._market_event_end: int = 0
        self._next_market_event: int = self.rng.randint(30, 60)

    def add_agent(self, agent: Agent) -> None:
        idx = self._role_counts.get(agent.role, 0)
        self._role_counts[agent.role] = idx + 1
        self._ai[agent.agent_id] = make_ai(agent.role, index=idx)
        self.agents.append(agent)

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
        # 40% の確率でスポーン（うち MICRO はエージェント近傍）
        if self.rng.random() < 0.40:
            self.spawn_task()
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
        self._run_auctions()
        self._move_agents()
        self._work_agents()
        self._charge_agents()
        # Medic 治療サービス
        self._heal_agents()
        snap = self._snapshot()
        self.snapshots.append(snap)
        return snap

    def run(self, ticks: int) -> List[StateSnapshot]:
        return [self.step() for _ in range(ticks)]

    def _run_ai(self) -> None:
        for agent in self.agents:
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
            proposal = ai.policy_proposal(self.tick, gini, completion, worker_idle_ratio)
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
        for agent in self.agents:
            cost = Economy.UPKEEP_COST
            agent.balance = max(0.0, agent.balance - cost)
            self.economy.pay_upkeep(agent.agent_id, self.tick)
            self._emit(EventType.UPKEEP_PAID, agent_id=agent.agent_id,
                       data={"amount": cost, "balance": round(agent.balance, 2)})

    def _apply_safety_net(self) -> None:
        for agent in self.agents:
            if agent.balance < Economy.SAFETY_NET_THRESHOLD:
                if self.economy.pay_safety_net(agent.agent_id, self.tick):
                    agent.balance += Economy.SAFETY_NET_AMOUNT
                    self._emit(EventType.SAFETY_NET_PAID, agent_id=agent.agent_id,
                               data={"amount": Economy.SAFETY_NET_AMOUNT,
                                     "balance": round(agent.balance, 1),
                                     "tax_pool": round(self.economy.tax_pool, 1)})

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
        open_tasks = [t for t in self.tasks if t.status == TaskStatus.OPEN]
        for task in open_tasks:
            task.bids.clear()
            for agent in self.agents:
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
                    bid = round(bid_amount, 1)
                    task.submit_bid(agent.agent_id, bid)
                    self._emit(EventType.BID_SUBMITTED, agent_id=agent.agent_id, task_id=task.task_id,
                               data={"bid": bid, "task_type": task.task_type.value})
            winner_id = task.resolve_auction()
            if winner_id:
                winner = self._get_agent(winner_id)
                if winner:
                    winner.assigned_task_id = task.task_id
                    winner.status = AgentStatus.MOVING
                    winner.target_x = task.x
                    winner.target_y = task.y
                    winning_bid = next((b.amount for b in task.bids if b.agent_id == winner_id), 0)
                    self._emit(EventType.TASK_ASSIGNED, agent_id=winner_id, task_id=task.task_id,
                               data={"target_x": task.x, "target_y": task.y, "bid": winning_bid})

    def _move_agents(self) -> None:
        for agent in self.agents:
            if agent.status != AgentStatus.MOVING or agent.target_x is None:
                continue
            nx, ny = agent.move_toward(agent.target_x, agent.target_y)
            if self.world.is_passable(nx, ny):
                agent.x, agent.y = nx, ny
                agent.spend_energy(Agent.MOVE_COST)
                self._emit(EventType.AGENT_MOVED, agent_id=agent.agent_id,
                           data={"x": nx, "y": ny, "energy": round(agent.energy, 1)})
            if agent.x == agent.target_x and agent.y == agent.target_y:
                agent.status = AgentStatus.WORKING

    def _work_agents(self) -> None:
        for agent in self.agents:
            if agent.status != AgentStatus.WORKING:
                continue
            task = self._get_task(agent.assigned_task_id)
            if task is None:
                agent.status = AgentStatus.IDLE
                continue
            agent.spend_energy(Agent.WORK_COST)
            net = task.reward * (1 - self.policy_params["tax_rate"])
            agent.balance += net
            task.status = TaskStatus.COMPLETED
            task.completed_tick = self.tick
            self.economy.pay_reward(agent.agent_id, task.reward, task.task_id, self.tick)
            self._emit(EventType.TASK_COMPLETED, agent_id=agent.agent_id, task_id=task.task_id,
                       data={"reward": net, "energy": round(agent.energy, 1), "balance": round(agent.balance, 1)})
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
