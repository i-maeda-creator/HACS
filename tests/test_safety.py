import pytest
from layer0.core.agent import Agent, AgentRole, AgentStatus
from layer0.core.safety import SafetyGate
from layer0.schemas.event import EventType


@pytest.fixture
def gate():
    return SafetyGate()


@pytest.fixture
def moving_worker():
    a = Agent("W1", AgentRole.WORKER, x=5, y=5)
    a.status = AgentStatus.MOVING
    return a


def test_energy_depleted_stops_agent(gate, moving_worker):
    moving_worker.energy = 0.0
    events = gate.check([moving_worker], tick=1)
    assert moving_worker.status == AgentStatus.IDLE
    assert any(e.event_type == EventType.SAFETY_TRIGGERED for e in events)


def test_alive_agent_not_stopped(gate, moving_worker):
    moving_worker.energy = 50.0
    gate.check([moving_worker], tick=1)
    assert moving_worker.status == AgentStatus.MOVING


def test_night_restriction_stops_guardian(gate):
    guardian = Agent("G1", AgentRole.GUARDIAN, x=5, y=5)
    guardian.status = AgentStatus.MOVING
    # tick % 100 < 5 → 夜間
    events = gate.check([guardian], tick=2)
    assert guardian.status == AgentStatus.IDLE
    assert any(e.event_type == EventType.SAFETY_TRIGGERED for e in events)


def test_night_restriction_not_daytime(gate):
    guardian = Agent("G1", AgentRole.GUARDIAN, x=5, y=5)
    guardian.status = AgentStatus.MOVING
    # tick=10 → 夜間ではない
    gate.check([guardian], tick=10)
    assert guardian.status == AgentStatus.MOVING


def test_worker_not_affected_by_night(gate, moving_worker):
    moving_worker.energy = 50.0
    events = gate.check([moving_worker], tick=2)
    assert moving_worker.status == AgentStatus.MOVING
    assert not any(e.payload.get("rule") == "night_restriction" for e in events)


def test_emergency_stop_triggers(gate):
    events = gate.trigger_emergency_stop(tick=5, reason="test")
    assert gate.is_emergency_active()
    assert any(e.event_type == EventType.SAFETY_TRIGGERED for e in events)
    assert any(e.payload.get("rule") == "emergency_stop" for e in events)


def test_emergency_stop_freezes_all_agents(gate):
    agents = [
        Agent("W1", AgentRole.WORKER,   x=1, y=1),
        Agent("G1", AgentRole.GUARDIAN, x=2, y=2),
    ]
    for a in agents:
        a.status = AgentStatus.MOVING
    gate.trigger_emergency_stop(tick=1)
    gate.check(agents, tick=2)
    for a in agents:
        assert a.status == AgentStatus.IDLE


def test_reset_emergency(gate):
    gate.trigger_emergency_stop(tick=1)
    gate.reset_emergency()
    assert not gate.is_emergency_active()


def test_violation_recorded(gate, moving_worker):
    moving_worker.energy = 0.0
    gate.check([moving_worker], tick=1)
    assert len(gate.violations) >= 1
    assert gate.violations[0].rule == "energy_depleted"
