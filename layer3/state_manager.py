from __future__ import annotations
from typing import Dict, List, Optional, TYPE_CHECKING
from layer0.schemas.state import StateSnapshot, AgentSnapshot, TaskSnapshot

if TYPE_CHECKING:
    from layer0.engine.simulator import Simulator


class StateManager:
    """Simulator の状態に対する読み取り専用 API を提供する。"""

    def __init__(self, sim: "Simulator"):
        self._sim = sim

    # ── エージェント ────────────────────────────────────────────
    def get_agent(self, agent_id: str) -> Optional[AgentSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return None
        return next((a for a in snap.agents if a.agent_id == agent_id), None)

    def agents_by_role(self, role: str) -> List[AgentSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return []
        return [a for a in snap.agents if a.role == role]

    def idle_agents(self) -> List[AgentSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return []
        return [a for a in snap.agents if a.status == "idle"]

    def low_energy_agents(self, threshold: float = 20.0) -> List[AgentSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return []
        return [a for a in snap.agents if a.energy <= threshold]

    # ── タスク ──────────────────────────────────────────────────
    def open_tasks(self) -> List[TaskSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return []
        return [t for t in snap.tasks if t.status == "open"]

    def get_task(self, task_id: str) -> Optional[TaskSnapshot]:
        snap = self._latest_snap()
        if snap is None:
            return None
        return next((t for t in snap.tasks if t.task_id == task_id), None)

    # ── メトリクス ──────────────────────────────────────────────
    def get_metrics(self) -> Dict:
        snap = self._latest_snap()
        return snap.metrics if snap else {}

    def policy_params(self) -> Dict[str, float]:
        return dict(self._sim.policy_params)

    def worker_idle_ratio(self) -> float:
        from layer0.core.agent import AgentRole
        from layer0.schemas.event import EventType
        workers = [a for a in self._sim.agents if a.role == AgentRole.WORKER]
        if not workers:
            return 0.0
        earned = {e.agent_id for e in self._sim.event_log
                  if e.event_type == EventType.TASK_COMPLETED and e.agent_id}
        return 1.0 - sum(1 for w in workers if w.agent_id in earned) / len(workers)

    # ── イベント履歴 ────────────────────────────────────────────
    def recent_events(self, last_n: int = 20) -> list:
        return self._sim.event_log[-last_n:]

    def events_for_agent(self, agent_id: str, last_n: int = 20) -> list:
        matching = [e for e in self._sim.event_log if e.agent_id == agent_id]
        return matching[-last_n:]

    # ── 内部 ────────────────────────────────────────────────────
    def _latest_snap(self) -> Optional[StateSnapshot]:
        return self._sim.snapshots[-1] if self._sim.snapshots else None
