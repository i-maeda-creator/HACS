import pytest
from layer0.core.world import World, Cell


@pytest.fixture
def world():
    return World.default_layout()


def test_wall_boundaries(world):
    assert not world.is_passable(0, 0)
    assert not world.is_passable(19, 19)
    assert not world.is_passable(0, 10)


def test_inner_passable(world):
    assert world.is_passable(5, 5)
    assert world.is_passable(10, 10)


def test_out_of_bounds(world):
    assert not world.is_passable(-1, 5)
    assert not world.is_passable(5, 20)
    assert not world.is_passable(25, 5)


def test_charge_cells_exist(world):
    chargers = world.charger_positions()
    assert len(chargers) >= 1


def test_charge_cell_type(world):
    chargers = world.charger_positions()
    for cx, cy in chargers:
        assert world.get_cell(cx, cy) == Cell.CHARGE


def test_nearest_charger_returns_position(world):
    result = world.nearest_charger(10, 10)
    assert result is not None
    cx, cy = result
    assert world.get_cell(cx, cy) == Cell.CHARGE


def test_nearest_charger_is_closest(world):
    chargers = world.charger_positions()
    x, y = 2, 2
    best = world.nearest_charger(x, y)
    best_d = abs(best[0]-x) + abs(best[1]-y)
    for cx, cy in chargers:
        d = abs(cx-x) + abs(cy-y)
        assert d >= best_d


def test_set_and_get_cell(world):
    world.set_cell(5, 5, Cell.DANGER)
    assert world.get_cell(5, 5) == Cell.DANGER


def test_in_bounds(world):
    assert world.in_bounds(0, 0)
    assert world.in_bounds(19, 19)
    assert not world.in_bounds(20, 0)
    assert not world.in_bounds(0, -1)
