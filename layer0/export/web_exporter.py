from __future__ import annotations
import json
from typing import List
from layer0.core.world import World, Cell
from layer0.schemas.state import StateSnapshot


CELL_TYPE = {Cell.EMPTY: 0, Cell.WALL: 1, Cell.CHARGE: 2, Cell.DANGER: 3}


def export_for_web(world: World, snapshots: List[StateSnapshot], path: str = "web/replay.json") -> None:
    grid = []
    for y in range(world.height):
        for x in range(world.width):
            ct = CELL_TYPE[world.get_cell(x, y)]
            if ct != 0:
                grid.append({"x": x, "y": y, "type": ct})

    frames = []
    for snap in snapshots:
        frames.append({
            "tick": snap.tick,
            "agents": [
                {
                    "id":      a.agent_id,
                    "role":    a.role,
                    "x":       a.x,
                    "y":       a.y,
                    "energy":  a.energy,
                    "balance": a.balance,
                    "status":  a.status,
                }
                for a in snap.agents
            ],
            "tasks": [
                {
                    "id":     t.task_id,
                    "x":      t.x,
                    "y":      t.y,
                    "reward": t.reward,
                    "status": t.status,
                }
                for t in snap.tasks
            ],
            "metrics": snap.metrics,
            "economy": {
                "total_energy":  snap.economy.total_energy,
                "total_balance": snap.economy.total_balance,
                "transactions":  snap.economy.transactions,
            },
        })

    payload = {
        "world":  {"width": world.width, "height": world.height, "cells": grid},
        "frames": frames,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Web replay saved → {path}  ({len(frames)} frames)")
