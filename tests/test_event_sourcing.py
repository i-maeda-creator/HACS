import pytest
from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.core.event_sourcing import EventReplayer


@pytest.fixture
def sim_and_replayer():
    initial_config = [
        ("W1", AgentRole.WORKER,   2,  2),
        ("W2", AgentRole.WORKER,   5,  5),
        ("T1", AgentRole.TRADER,   8,  8),
        ("G1", AgentRole.GUARDIAN, 15, 3),
        ("O1", AgentRole.OBSERVER, 3,  15),
        ("V1", AgentRole.GOVERNOR, 10, 10),
    ]
    sim = Simulator(seed=42)
    for aid, role, x, y in initial_config:
        sim.add_agent(Agent(aid, role, x=x, y=y))
    sim.run(50)
    replayer_agents = [Agent(aid, role, x=x, y=y) for aid, role, x, y in initial_config]
    replayer = EventReplayer(replayer_agents)
    replayer.apply_all(sim.event_log)
    return sim, replayer


def test_replayer_has_all_agents(sim_and_replayer):
    sim, replayer = sim_and_replayer
    state = replayer.final_state()
    for a in sim.agents:
        assert a.agent_id in state.agents


def test_replayer_tasks_recorded(sim_and_replayer):
    sim, replayer = sim_and_replayer
    state = replayer.final_state()
    # TaskCreated イベントが存在すればタスクが記録されているはず
    from layer0.schemas.event import EventType
    created = {e.task_id for e in sim.event_log if e.event_type == EventType.TASK_CREATED}
    assert set(state.tasks.keys()) == created


def test_completed_tasks_marked(sim_and_replayer):
    sim, replayer = sim_and_replayer
    state = replayer.final_state()
    from layer0.schemas.event import EventType
    completed_ids = {e.task_id for e in sim.event_log if e.event_type == EventType.TASK_COMPLETED}
    for tid in completed_ids:
        assert state.tasks[tid].status == "completed"


def test_balance_matches_snapshot(sim_and_replayer):
    sim, replayer = sim_and_replayer
    result = replayer.verify_against_snapshot(sim.snapshots[-1], tolerance=1.0)
    # 残高の差が許容誤差内かチェック
    balance_mismatches = [m for m in result["mismatches"] if "balance" in m]
    assert len(balance_mismatches) == 0, f"Balance mismatches: {balance_mismatches}"


def test_position_matches_snapshot(sim_and_replayer):
    sim, replayer = sim_and_replayer
    result = replayer.verify_against_snapshot(sim.snapshots[-1], tolerance=1.0)
    pos_mismatches = [m for m in result["mismatches"] if "pos" in m]
    assert len(pos_mismatches) == 0, f"Position mismatches: {pos_mismatches}"


def test_state_at_tick(sim_and_replayer):
    sim, replayer = sim_and_replayer
    s0 = replayer.state_at(0)
    assert s0 is not None
    # 初期状態はイベント前なので Worker は初期位置にいるはず
    assert s0.agents["W1"].x == 2
    assert s0.agents["W1"].y == 2


def test_total_balance_nonnegative(sim_and_replayer):
    _, replayer = sim_and_replayer
    state = replayer.final_state()
    assert state.total_balance >= 0


def test_energy_in_range(sim_and_replayer):
    _, replayer = sim_and_replayer
    state = replayer.final_state()
    for a in state.agents.values():
        assert 0.0 <= a.energy <= 100.0, f"{a.agent_id} energy={a.energy}"


def test_reset_restores_initial(sim_and_replayer):
    sim, replayer = sim_and_replayer
    replayer.reset()
    state = replayer.state_at(0)
    assert state.agents["W1"].x == 2
    assert state.agents["W1"].balance == 50.0
