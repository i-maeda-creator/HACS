from __future__ import annotations
import random
import json
from typing import Dict, List, Optional
from pathlib import Path
from layer0.core.world import World, Cell
from layer0.core.agent import Agent, AgentRole, AgentStatus
from layer0.core.task import Task, TaskStatus, make_task
from layer0.core.economy import Economy
from layer0.core.policy import PolicyEngine
from layer0.core.safety import SafetyGate
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
        self.event_log: List[Event] = []
        self.snapshots: List[StateSnapshot] = []

    def add_agent(self, agent: Agent) -> None:
        self.agents.append(agent)

    def spawn_task(self) -> Task:
        while True:
            x = self.rng.randint(1, self.world.width - 2)
            y = self.rng.randint(1, self.world.height - 2)
            if self.world.is_passable(x, y):
                break
        reward = round(self.rng.uniform(8.0, 20.0), 1)
        cost = round(self.rng.uniform(1.0, 5.0), 1)
        t = make_task(x, y, reward=reward, energy_cost=cost, tick=self.tick)
        self.tasks.append(t)
        self._emit(EventType.TASK_CREATED, task_id=t.task_id, data={"x": x, "y": y, "reward": reward})
        return t

    def step(self) -> StateSnapshot:
        self.tick += 1
        if self.tick % 5 == 0:
            self.spawn_task()
        # Safety first — must run before Policy and Economy
        safety_events = self.safety.check(self.agents, self.tick)
        self.event_log.extend(safety_events)
        policy_events = self.policy.apply(self.agents, self.tasks, self.tick)
        self.event_log.extend(policy_events)
        self._run_auctions()
        self._move_agents()
        self._work_agents()
        self._charge_agents()
        snap = self._snapshot()
        self.snapshots.append(snap)
        return snap

    def run(self, ticks: int) -> List[StateSnapshot]:
        return [self.step() for _ in range(ticks)]

    def _run_auctions(self) -> None:
        open_tasks = [t for t in self.tasks if t.status == TaskStatus.OPEN]
        for task in open_tasks:
            task.bids.clear()
            for agent in self.agents:
                if agent.status == AgentStatus.IDLE and agent.energy > task.energy_cost:
                    bid = round(task.energy_cost + self.rng.uniform(0, 2), 1)
                    task.submit_bid(agent.agent_id, bid)
                    self._emit(EventType.BID_SUBMITTED, agent_id=agent.agent_id, task_id=task.task_id, data={"bid": bid})
            winner_id = task.resolve_auction()
            if winner_id:
                winner = self._get_agent(winner_id)
                if winner:
                    winner.assigned_task_id = task.task_id
                    winner.status = AgentStatus.MOVING
                    winner.target_x = task.x
                    winner.target_y = task.y
                    self._emit(EventType.TASK_ASSIGNED, agent_id=winner_id, task_id=task.task_id)

    def _move_agents(self) -> None:
        for agent in self.agents:
            if agent.status != AgentStatus.MOVING or agent.target_x is None:
                continue
            nx, ny = agent.move_toward(agent.target_x, agent.target_y)
            if self.world.is_passable(nx, ny):
                agent.x, agent.y = nx, ny
                agent.spend_energy(Agent.MOVE_COST)
                self._emit(EventType.AGENT_MOVED, agent_id=agent.agent_id, data={"x": nx, "y": ny})
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
            net = task.reward * (1 - Economy.TAX_RATE)
            agent.balance += net
            task.status = TaskStatus.COMPLETED
            task.completed_tick = self.tick
            self.economy.pay_reward(agent.agent_id, task.reward, task.task_id, self.tick)
            self._emit(EventType.TASK_COMPLETED, agent_id=agent.agent_id, task_id=task.task_id, data={"reward": net})
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
        active = [t for t in self.tasks if t.status != TaskStatus.COMPLETED]
        return StateSnapshot(
            tick=self.tick,
            agents=[AgentSnapshot(
                agent_id=a.agent_id, role=a.role.value, x=a.x, y=a.y,
                energy=round(a.energy, 1), balance=round(a.balance, 1), status=a.status.value
            ) for a in self.agents],
            tasks=[TaskSnapshot(
                task_id=t.task_id, x=t.x, y=t.y,
                reward=t.reward, energy_cost=t.energy_cost,
                status=t.status.value, assigned_to=t.assigned_to
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
            "open_tasks": len([t for t in self.tasks if t.status == "open"]),
            "total_energy": round(sum(a.energy for a in self.agents), 1),
            "mean_balance": round(mean_b, 1),
            "gini": round(gini, 3),
            "policy_efficiency": scores.get("efficiency", 0),
            "policy_equality": scores.get("equality", 0),
            "policy_violations": len(self.policy.violations),
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
