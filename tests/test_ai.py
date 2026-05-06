import random
import pytest
from layer0.core.agent import Agent, AgentRole, AgentStatus
from layer0.core.world import World
from layer0.core.task import make_task
from layer0.core.ai import WorkerAI, GuardianAI, TraderAI, ObserverAI, GovernorAI, make_ai


@pytest.fixture
def world():
    return World.default_layout()


@pytest.fixture
def rng():
    return random.Random(42)


def idle_agent(agent_id, role, x=5, y=5, energy=80.0, balance=50.0):
    a = Agent(agent_id, role, x=x, y=y, energy=energy, balance=balance)
    a.status = AgentStatus.IDLE
    return a


# ── Worker ──────────────────────────────────────────────────────
def test_worker_bids_on_task(rng):
    w = idle_agent("W1", AgentRole.WORKER)
    task = make_task(8, 8, reward=12.0, energy_cost=3.0)
    bid = WorkerAI().get_bid(task, w, rng)
    assert bid is not None
    assert bid >= task.energy_cost


def test_worker_no_bid_low_energy(rng):
    w = idle_agent("W1", AgentRole.WORKER, energy=10.0)
    task = make_task(8, 8, reward=12.0, energy_cost=3.0)
    bid = WorkerAI().get_bid(task, w, rng)
    assert bid is None


def test_worker_charges_when_low(world, rng):
    w = idle_agent("W1", AgentRole.WORKER, energy=20.0)
    ai = WorkerAI()
    ai.decide(w, world, [], [], tick=10, rng=rng)
    assert w.status == AgentStatus.MOVING
    assert w.target_x is not None


# ── Guardian ────────────────────────────────────────────────────
def test_guardian_never_bids(rng):
    g = idle_agent("G1", AgentRole.GUARDIAN)
    task = make_task(8, 8, reward=20.0, energy_cost=2.0)
    bid = GuardianAI().get_bid(task, g, rng)
    assert bid is None


def test_guardian_patrols_when_idle(world, rng):
    g = idle_agent("G1", AgentRole.GUARDIAN, x=2, y=2, energy=80.0)
    ai = GuardianAI()
    ai.decide(g, world, [], [], tick=10, rng=rng)
    assert g.status == AgentStatus.MOVING


def test_guardian_charges_low_energy(world, rng):
    g = idle_agent("G1", AgentRole.GUARDIAN, energy=30.0)
    ai = GuardianAI()
    ai.decide(g, world, [], [], tick=10, rng=rng)
    # 充電スポットへ向かう
    assert g.status == AgentStatus.MOVING
    charger = world.nearest_charger(g.x, g.y)
    assert (g.target_x, g.target_y) == charger


# ── Trader ──────────────────────────────────────────────────────
def test_trader_skips_low_reward(rng):
    t = idle_agent("T1", AgentRole.TRADER)
    task = make_task(5, 5, reward=8.0, energy_cost=3.0)  # 報酬 < MIN_REWARD(10)
    bid = TraderAI().get_bid(task, t, rng)
    assert bid is None


def test_trader_bids_high_reward(rng):
    t = idle_agent("T1", AgentRole.TRADER)
    task = make_task(5, 5, reward=15.0, energy_cost=3.0)
    bid = TraderAI().get_bid(task, t, rng)
    assert bid is not None
    assert bid >= task.energy_cost


def test_trader_skips_thin_margin(rng):
    t = idle_agent("T1", AgentRole.TRADER)
    # reward=11, cost=9 → margin=2 < MIN_MARGIN(3)
    task = make_task(5, 5, reward=11.0, energy_cost=9.0)
    bid = TraderAI().get_bid(task, t, rng)
    assert bid is None


# ── Observer ────────────────────────────────────────────────────
def test_observer_never_bids(rng):
    o = idle_agent("O1", AgentRole.OBSERVER)
    task = make_task(5, 5, reward=20.0, energy_cost=1.0)
    bid = ObserverAI().get_bid(task, o, rng)
    assert bid is None


def test_observer_moves_in_quadrant(world, rng):
    o = idle_agent("O1", AgentRole.OBSERVER, x=5, y=5)
    ai = ObserverAI(quadrant=0)  # Q0: x1-9, y1-9
    ai.decide(o, world, [], [], tick=1, rng=rng)
    assert o.status == AgentStatus.MOVING
    assert 1 <= o.target_x <= 9
    assert 1 <= o.target_y <= 9


# ── Governor ────────────────────────────────────────────────────
def test_governor_never_bids(rng):
    v = idle_agent("V1", AgentRole.GOVERNOR)
    task = make_task(5, 5, reward=20.0, energy_cost=1.0)
    bid = GovernorAI().get_bid(task, v, rng)
    assert bid is None


def test_governor_moves_to_center(world, rng):
    v = idle_agent("V1", AgentRole.GOVERNOR, x=2, y=2)
    ai = GovernorAI()
    ai.decide(v, world, [], [], tick=1, rng=rng)
    assert v.status == AgentStatus.MOVING
    assert (v.target_x, v.target_y) == GovernorAI.CENTER


def test_governor_proposes_on_high_gini():
    ai = GovernorAI()
    proposal = ai.policy_proposal(tick=25, gini=0.4, completion_rate=0.9)
    assert proposal is not None
    assert proposal["action"] == "tax_increase"


def test_governor_proposes_on_low_completion():
    ai = GovernorAI()
    proposal = ai.policy_proposal(tick=25, gini=0.1, completion_rate=0.4)
    assert proposal is not None
    assert proposal["action"] == "reward_boost"


def test_governor_no_proposal_off_interval():
    ai = GovernorAI()
    proposal = ai.policy_proposal(tick=12, gini=0.5, completion_rate=0.3)
    assert proposal is None


# ── make_ai factory ──────────────────────────────────────────────
def test_make_ai_returns_correct_type():
    assert isinstance(make_ai(AgentRole.WORKER),   WorkerAI)
    assert isinstance(make_ai(AgentRole.GUARDIAN), GuardianAI)
    assert isinstance(make_ai(AgentRole.TRADER),   TraderAI)
    assert isinstance(make_ai(AgentRole.OBSERVER), ObserverAI)
    assert isinstance(make_ai(AgentRole.GOVERNOR), GovernorAI)
