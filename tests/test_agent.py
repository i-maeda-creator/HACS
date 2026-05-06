import pytest
from layer0.core.agent import Agent, AgentRole, AgentStatus


@pytest.fixture
def worker():
    return Agent("W1", AgentRole.WORKER, x=5, y=5)


def test_initial_energy(worker):
    assert worker.energy == 100.0


def test_initial_balance(worker):
    assert worker.balance == 50.0


def test_spend_energy(worker):
    worker.spend_energy(10.0)
    assert worker.energy == 90.0


def test_energy_floor(worker):
    worker.spend_energy(9999.0)
    assert worker.energy == 0.0


def test_charge(worker):
    worker.energy = 80.0
    worker.charge()
    assert worker.energy == 85.0  # CHARGE_RATE = 5.0


def test_charge_cap(worker):
    worker.energy = 98.0
    worker.charge()
    assert worker.energy == 100.0


def test_needs_charge_true(worker):
    worker.energy = 15.0
    assert worker.needs_charge()


def test_needs_charge_false(worker):
    worker.energy = 25.0
    assert not worker.needs_charge()


def test_move_toward_x(worker):
    nx, ny = worker.move_toward(8, 5)
    assert (nx, ny) == (6, 5)


def test_move_toward_y(worker):
    nx, ny = worker.move_toward(5, 9)
    assert (nx, ny) == (5, 6)


def test_move_toward_already_there(worker):
    nx, ny = worker.move_toward(5, 5)
    assert (nx, ny) == (5, 5)


def test_move_toward_diagonal_prefers_x():
    a = Agent("X", AgentRole.WORKER, x=0, y=0)
    nx, ny = a.move_toward(3, 3)
    assert nx == 1 and ny == 0  # |dx|==|dy| → x優先


def test_is_alive(worker):
    assert worker.is_alive()
    worker.energy = 0.0
    assert not worker.is_alive()
