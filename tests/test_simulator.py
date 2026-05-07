import pytest
from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole, AgentStatus


@pytest.fixture
def sim():
    s = Simulator(seed=42)
    s.add_agent(Agent("W1", AgentRole.WORKER,   x=2, y=2))
    s.add_agent(Agent("W2", AgentRole.WORKER,   x=5, y=5))
    s.add_agent(Agent("G1", AgentRole.GUARDIAN, x=15, y=3))
    s.add_agent(Agent("T1", AgentRole.TRADER,   x=8, y=8))
    s.add_agent(Agent("O1", AgentRole.OBSERVER, x=3, y=15))
    s.add_agent(Agent("V1", AgentRole.GOVERNOR, x=10, y=10))
    return s


def test_step_increments_tick(sim):
    sim.step()
    assert sim.tick == 1


def test_run_returns_snapshots(sim):
    snaps = sim.run(10)
    assert len(snaps) == 10


def test_event_log_grows(sim):
    sim.run(10)
    assert len(sim.event_log) > 0


def test_tasks_spawned(sim):
    sim.run(50)
    from layer0.schemas.event import EventType
    task_events = [e for e in sim.event_log
                   if e.event_type == EventType.TASK_CREATED
                   and e.payload.get("event") != "expired"]
    # 40% 確率スポーン → 50 tick で概ね 5〜40 件
    assert 5 <= len(task_events) <= 50


def test_sequence_ids_unique(sim):
    sim.run(20)
    seq_ids = [e.sequence_id for e in sim.event_log]
    assert len(seq_ids) == len(set(seq_ids))


def test_sequence_ids_monotone(sim):
    sim.run(20)
    seq_ids = [e.sequence_id for e in sim.event_log]
    assert seq_ids == sorted(seq_ids)


def test_guardian_bids_on_security_only(sim):
    sim.run(100)
    from layer0.schemas.event import EventType
    from layer0.core.task import TaskType
    guardian_bids = [
        e for e in sim.event_log
        if e.event_type == EventType.BID_SUBMITTED and e.agent_id == "G1"
    ]
    task_map = {t.task_id: t for t in sim.tasks}
    for e in guardian_bids:
        tid = e.payload.get("task_id")
        if tid and tid in task_map:
            assert task_map[tid].task_type in (TaskType.SECURITY, TaskType.URGENT)


def test_observer_bids_on_survey_only(sim):
    sim.run(100)
    from layer0.schemas.event import EventType
    from layer0.core.task import TaskType
    obs_bids = [
        e for e in sim.event_log
        if e.event_type == EventType.BID_SUBMITTED and e.agent_id == "O1"
    ]
    # Observer may bid on SURVEY/URGENT tasks; bids on other types must not exist
    task_map = {t.task_id: t for t in sim.tasks}
    for e in obs_bids:
        tid = e.payload.get("task_id")
        if tid and tid in task_map:
            assert task_map[tid].task_type in (TaskType.SURVEY, TaskType.URGENT)


def test_worker_earns_balance(sim):
    initial = {a.agent_id: a.balance for a in sim.agents}
    sim.run(100)
    workers = [a for a in sim.agents if a.role == AgentRole.WORKER]
    earned = sum(a.balance - initial[a.agent_id] for a in workers)
    assert earned > 0


def test_snapshot_tick_matches(sim):
    snaps = sim.run(5)
    for i, snap in enumerate(snaps, 1):
        assert snap.tick == i


def test_ai_registered_for_all_agents(sim):
    for a in sim.agents:
        assert a.agent_id in sim._ai


def test_reproducible_with_same_seed():
    def run():
        s = Simulator(seed=99)
        s.add_agent(Agent("W1", AgentRole.WORKER, x=3, y=3))
        s.add_agent(Agent("T1", AgentRole.TRADER, x=8, y=8))
        s.run(20)
        return [(a.agent_id, round(a.balance, 1)) for a in s.agents]
    assert run() == run()
