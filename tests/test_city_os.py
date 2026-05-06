import pytest
from layer0.core.agent import Agent, AgentRole, AgentStatus
from layer0.schemas.command import cmd_move, cmd_stop, cmd_emergency_stop, cmd_charge, Command, CommandAction
from layer3.city_os import CityOS, CitySnapshot
from layer3.alert_system import AlertSystem, AlertLevel
from layer3.policy_gate import PolicyGate
from layer3.command_dispatcher import CommandDispatcher


# ── fixtures ────────────────────────────────────────────────────

@pytest.fixture
def city():
    c = CityOS(seed=42)
    c.add_agent(Agent("W1", AgentRole.WORKER,   x=2,  y=2))
    c.add_agent(Agent("W2", AgentRole.WORKER,   x=5,  y=5))
    c.add_agent(Agent("T1", AgentRole.TRADER,   x=8,  y=8))
    c.add_agent(Agent("G1", AgentRole.GUARDIAN, x=15, y=3))
    c.add_agent(Agent("O1", AgentRole.OBSERVER, x=3,  y=15))
    c.add_agent(Agent("V1", AgentRole.GOVERNOR, x=10, y=10))
    return c


# ── CityOS 基本 ─────────────────────────────────────────────────

def test_city_tick_returns_snapshot(city):
    snap = city.tick()
    assert isinstance(snap, CitySnapshot)
    assert snap.sim_snap.tick == 1


def test_city_run_returns_list(city):
    snaps = city.run(10)
    assert len(snaps) == 10


def test_emergency_level_starts_zero(city):
    snap = city.tick()
    assert snap.emergency_level == 0


def test_policy_params_present(city):
    snap = city.tick()
    assert "reward_multiplier" in snap.policy_params
    assert "tax_rate" in snap.policy_params
    assert "worker_bid_bonus" in snap.policy_params


def test_city_summary_keys(city):
    city.run(5)
    s = city.summary()
    for key in ("tick", "emergency_level", "agents", "events", "gini", "policy_params"):
        assert key in s


# ── AlertSystem ─────────────────────────────────────────────────

def test_no_alerts_healthy_state(city):
    snap = city.tick()
    assert snap.alerts == []


def test_alert_on_critical_energy(city):
    al = AlertSystem()
    snap = city.sim.step()
    # 低エネルギーエージェントを人工的に作る
    city.sim.agents[0].energy = 3.0
    snap2 = city.sim.step()
    alerts = al.check(snap2)
    critical = [a for a in alerts if a.level == AlertLevel.CRITICAL and a.category == "ENERGY"]
    assert len(critical) >= 1


def test_alert_summary_structure(city):
    city.run(10)
    summary = city.alerts.summary()
    assert "total" in summary
    assert "by_category" in summary
    assert "by_level" in summary


def test_emergency_level_rises_with_criticals(city):
    al = AlertSystem()
    # 複数の CRITICAL を生成
    snap = city.sim.step()
    for a in city.sim.agents:
        a.energy = 2.0
    snap2 = city.sim.step()
    al.check(snap2)
    assert al.emergency_level >= 2


# ── PolicyGate ──────────────────────────────────────────────────

def test_gate_allows_valid_move(city):
    city.tick()
    gate = PolicyGate()
    cmd = cmd_move("W1", 3, 3, tick=1)
    result = gate.validate(cmd, city.sim)
    assert result.allowed


def test_gate_rejects_wall_move(city):
    city.tick()
    gate = PolicyGate()
    cmd = cmd_move("W1", 0, 0, tick=1)  # (0,0) は壁
    result = gate.validate(cmd, city.sim)
    assert not result.allowed


def test_gate_rejects_unknown_agent(city):
    city.tick()
    gate = PolicyGate()
    cmd = cmd_move("GHOST", 5, 5, tick=1)
    result = gate.validate(cmd, city.sim)
    assert not result.allowed


def test_gate_allows_emergency_stop_always(city):
    city.tick()
    city.sim.safety.trigger_emergency_stop(1, "test")
    gate = PolicyGate()
    cmd = cmd_emergency_stop(tick=1)
    result = gate.validate(cmd, city.sim)
    assert result.allowed


# ── CommandDispatcher ────────────────────────────────────────────

def test_dispatch_move_changes_target(city):
    city.tick()
    result = city.issue_command(cmd_move("W1", 7, 7, tick=1))
    assert result.allowed
    agent = city.sim._get_agent("W1")
    assert agent.target_x == 7
    assert agent.target_y == 7
    assert agent.status == AgentStatus.MOVING


def test_dispatch_stop_idles_agent(city):
    city.tick()
    city.issue_command(cmd_move("W1", 7, 7, tick=1))
    city.issue_command(cmd_stop("W1", tick=1))
    agent = city.sim._get_agent("W1")
    assert agent.status == AgentStatus.IDLE
    assert agent.target_x is None


def test_dispatch_emergency_stop_freezes_all(city):
    city.tick()
    city.issue_command(cmd_emergency_stop(tick=1))
    for a in city.sim.agents:
        assert a.status == AgentStatus.IDLE


def test_rejected_command_tracked(city):
    city.tick()
    city.issue_command(cmd_move("GHOST", 5, 5, tick=1))
    assert city.dispatcher.stats()["rejected"] >= 1


def test_dispatcher_stats(city):
    city.run(5)
    city.issue_command(cmd_move("W1", 4, 4, tick=5))
    stats = city.dispatcher.stats()
    assert stats["dispatched"] >= 1


# ── StateManager ────────────────────────────────────────────────

def test_state_get_agent(city):
    city.tick()
    a = city.state.get_agent("W1")
    assert a is not None
    assert a.agent_id == "W1"


def test_state_open_tasks(city):
    city.run(10)
    tasks = city.state.open_tasks()
    assert isinstance(tasks, list)


def test_state_policy_params(city):
    city.tick()
    params = city.state.policy_params()
    assert params["reward_multiplier"] >= 1.0


def test_state_worker_idle_ratio_range(city):
    city.run(20)
    ratio = city.state.worker_idle_ratio()
    assert 0.0 <= ratio <= 1.0


def test_state_recent_events(city):
    city.run(5)
    evts = city.state.recent_events(10)
    assert len(evts) <= 10
