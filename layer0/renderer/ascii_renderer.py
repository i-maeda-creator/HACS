from __future__ import annotations
from layer0.core.world import World, Cell
from layer0.schemas.state import StateSnapshot


CELL_CHAR = {
    Cell.EMPTY: ".",
    Cell.WALL: "#",
    Cell.CHARGE: "C",
    Cell.DANGER: "!",
}


def render(world: World, snap: StateSnapshot) -> str:
    grid = [[CELL_CHAR[world.get_cell(x, y)] for x in range(world.width)] for y in range(world.height)]

    for task in snap.tasks:
        if 0 <= task.y < world.height and 0 <= task.x < world.width:
            grid[task.y][task.x] = "T"

    for agent in snap.agents:
        if 0 <= agent.y < world.height and 0 <= agent.x < world.width:
            symbol = agent.role[0].upper()
            grid[agent.y][agent.x] = symbol

    lines = ["".join(row) for row in grid]
    lines.append(f"tick={snap.tick}  agents={len(snap.agents)}  tasks(open)={snap.metrics.get('open_tasks', '?')}")
    lines.append(f"energy={snap.economy.total_energy}  balance={snap.economy.total_balance}  tx={snap.economy.transactions}")
    lines.append(f"completion={snap.metrics.get('task_completion_rate', '?')}  gini={snap.metrics.get('gini', '?')}")
    return "\n".join(lines)
