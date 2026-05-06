"""
Event Sourcing: イベントログだけから世界状態を再構築する。

使い方:
    replayer = EventReplayer(agents_config)
    replayer.apply_all(event_log)
    state = replayer.state_at(tick=50)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from layer0.schemas.event import Event, EventType
from layer0.core.agent import AgentRole, AgentStatus, Agent


@dataclass
class AgentState:
    agent_id:   str
    role:       str
    x:          int
    y:          int
    energy:     float
    balance:    float
    status:     str
    last_tick:  int = 0


@dataclass
class TaskState:
    task_id:    str
    x:          int
    y:          int
    reward:     float
    status:     str        # open / assigned / completed
    assigned_to: Optional[str] = None
    completed_tick: int = 0


@dataclass
class WorldSnapshot:
    tick:   int
    agents: Dict[str, AgentState]
    tasks:  Dict[str, TaskState]
    total_balance: float = 0.0
    total_energy:  float = 0.0


class EventReplayer:
    """
    イベントを順番に適用して世界状態を再構築する。

    初期エージェント情報（位置・役割・初期エネルギー）はコンストラクタで渡す。
    イベントには含まれないため。（将来 AgentRegistered イベントを追加すれば不要になる）
    """

    MOVE_COST = 0.5
    WORK_COST = 2.0
    CHARGE_RATE = 5.0

    def __init__(self, agents: List[Agent]):
        self._initial: Dict[str, AgentState] = {
            a.agent_id: AgentState(
                agent_id=a.agent_id, role=a.role.value,
                x=a.x, y=a.y, energy=a.energy, balance=a.balance,
                status=a.status.value,
            )
            for a in agents
        }
        # 現在の状態（可変）
        self._agents: Dict[str, AgentState] = {}
        self._tasks:  Dict[str, TaskState]  = {}
        self._tick_snapshots: Dict[int, WorldSnapshot] = {}
        self._current_tick = 0
        self.reset()

    def reset(self) -> None:
        import copy
        self._agents = copy.deepcopy(self._initial)
        self._tasks  = {}
        self._tick_snapshots = {0: self._snapshot(0)}
        self._current_tick = 0

    # ── メイン ──────────────────────────────────────────────────
    def apply_all(self, events: List[Event]) -> None:
        """イベントリスト全体を適用する。"""
        self.reset()
        prev_tick = 0
        for e in sorted(events, key=lambda x: (x.tick, x.sequence_id)):
            if e.tick != prev_tick:
                # tick が変わったら直前の tick のスナップショットを保存
                self._tick_snapshots[prev_tick] = self._snapshot(prev_tick)
                prev_tick = e.tick
            self._apply(e)
            self._current_tick = e.tick
        self._tick_snapshots[self._current_tick] = self._snapshot(self._current_tick)

    def state_at(self, tick: int) -> Optional[WorldSnapshot]:
        """指定 tick のスナップショットを返す。"""
        # 完全一致
        if tick in self._tick_snapshots:
            return self._tick_snapshots[tick]
        # 直前の tick を探す
        available = sorted(k for k in self._tick_snapshots if k <= tick)
        if available:
            return self._tick_snapshots[available[-1]]
        return None

    def final_state(self) -> WorldSnapshot:
        return self._snapshot(self._current_tick)

    # ── イベント適用 ─────────────────────────────────────────────
    def _apply(self, e: Event) -> None:
        et = e.event_type
        p  = e.payload

        if et == EventType.TASK_CREATED:
            self._tasks[e.task_id] = TaskState(
                task_id=e.task_id, x=p.get("x",0), y=p.get("y",0),
                reward=p.get("reward",0), status="open",
            )

        elif et == EventType.BID_SUBMITTED:
            pass  # 状態変化なし（入札は情報イベント）

        elif et == EventType.TASK_ASSIGNED:
            if e.task_id in self._tasks:
                self._tasks[e.task_id].status      = "assigned"
                self._tasks[e.task_id].assigned_to = e.agent_id
            if e.agent_id in self._agents:
                self._agents[e.agent_id].status   = AgentStatus.MOVING.value
                self._agents[e.agent_id].last_tick = e.tick

        elif et == EventType.AGENT_MOVED:
            if e.agent_id in self._agents:
                a = self._agents[e.agent_id]
                a.x = p.get("x", a.x)
                a.y = p.get("y", a.y)
                # payloadにエネルギーがあれば使う、なければ計算で補完
                if "energy" in p:
                    a.energy = p["energy"]
                else:
                    a.energy = max(0.0, a.energy - self.MOVE_COST)
                a.last_tick = e.tick

        elif et == EventType.TASK_COMPLETED:
            if e.task_id in self._tasks:
                self._tasks[e.task_id].status         = "completed"
                self._tasks[e.task_id].completed_tick = e.tick
            if e.agent_id in self._agents:
                a = self._agents[e.agent_id]
                if "balance" in p:
                    a.balance = p["balance"]
                else:
                    a.balance += p.get("reward", 0)
                if "energy" in p:
                    a.energy = p["energy"]
                else:
                    a.energy = max(0.0, a.energy - self.WORK_COST)
                a.status   = AgentStatus.IDLE.value
                a.last_tick = e.tick

        elif et == EventType.AGENT_CHARGED:
            if e.agent_id in self._agents:
                a = self._agents[e.agent_id]
                a.energy   = p.get("energy", min(100.0, a.energy + self.CHARGE_RATE))
                a.status   = AgentStatus.CHARGING.value
                a.last_tick = e.tick

        elif et == EventType.SAFETY_TRIGGERED:
            if e.agent_id and e.agent_id in self._agents:
                self._agents[e.agent_id].status = AgentStatus.IDLE.value

    # ── スナップショット作成 ─────────────────────────────────────
    def _snapshot(self, tick: int) -> WorldSnapshot:
        import copy
        agents = copy.deepcopy(self._agents)
        tasks  = copy.deepcopy(self._tasks)
        total_balance = sum(a.balance for a in agents.values())
        total_energy  = sum(a.energy  for a in agents.values())
        return WorldSnapshot(tick=tick, agents=agents, tasks=tasks,
                             total_balance=round(total_balance, 1),
                             total_energy=round(total_energy, 1))

    # ── 検証ユーティリティ ───────────────────────────────────────
    def verify_against_snapshot(self, snapshot, tolerance: float = 1.0) -> dict:
        """
        シミュレーターのスナップショットと再構築結果を比較する。
        position と balance の一致を確認。
        """
        result = {"ok": True, "mismatches": []}
        replayed = self._snapshot(self._current_tick)

        for agent_snap in snapshot.agents:
            aid = agent_snap.agent_id
            if aid not in replayed.agents:
                result["mismatches"].append(f"{aid}: not found in replayed state")
                result["ok"] = False
                continue
            ra = replayed.agents[aid]
            # 位置チェック
            if ra.x != agent_snap.x or ra.y != agent_snap.y:
                result["mismatches"].append(
                    f"{aid}: pos replayed=({ra.x},{ra.y}) actual=({agent_snap.x},{agent_snap.y})")
                result["ok"] = False
            # 残高チェック（許容誤差あり）
            if abs(ra.balance - agent_snap.balance) > tolerance:
                result["mismatches"].append(
                    f"{aid}: balance replayed={ra.balance:.1f} actual={agent_snap.balance:.1f}")
                result["ok"] = False

        return result
