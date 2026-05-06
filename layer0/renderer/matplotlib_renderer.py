from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from typing import List, Callable
from layer0.core.world import World, Cell
from layer0.schemas.state import StateSnapshot

CELL_COLOR = {
    Cell.EMPTY:  [0.95, 0.95, 0.95],
    Cell.WALL:   [0.2,  0.2,  0.2],
    Cell.CHARGE: [0.2,  0.8,  0.4],
    Cell.DANGER: [0.9,  0.2,  0.2],
}

ROLE_COLOR = {
    "Worker":   "#2196F3",
    "Guardian": "#F44336",
    "Trader":   "#FF9800",
    "Observer": "#9C27B0",
    "Governor": "#795548",
}

STATUS_MARKER = {
    "idle":     "o",
    "moving":   "^",
    "working":  "s",
    "charging": "D",
}


def build_bg(world: World) -> np.ndarray:
    img = np.zeros((world.height, world.width, 3))
    for y in range(world.height):
        for x in range(world.width):
            img[y, x] = CELL_COLOR[world.get_cell(x, y)]
    return img


class MatplotlibRenderer:
    def __init__(self, world: World, title: str = "HACS Layer0"):
        self.world = world
        self.bg = build_bg(world)
        self.fig, self.axes = plt.subplots(1, 2, figsize=(14, 7))
        self.fig.patch.set_facecolor("#1a1a2e")
        self.ax = self.axes[0]
        self.ax_kpi = self.axes[1]
        self.ax.set_facecolor("#1a1a2e")
        self.ax_kpi.set_facecolor("#1a1a2e")
        self.fig.suptitle(title, color="white", fontsize=14)
        self._kpi_history: dict = {
            "ticks": [], "completion": [], "gini": [],
            "energy": [], "balance": [], "open_tasks": []
        }

    def draw(self, snap: StateSnapshot) -> None:
        self._update_kpi_history(snap)
        self._draw_world(snap)
        self._draw_kpi(snap)
        plt.tight_layout()

    def _draw_world(self, snap: StateSnapshot) -> None:
        ax = self.ax
        ax.clear()
        ax.imshow(self.bg, origin="upper", interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"tick={snap.tick}", color="white", fontsize=10)

        for task in snap.tasks:
            color = "#FFD700" if task.status == "open" else "#FFA500"
            ax.plot(task.x, task.y, marker="*", color=color, markersize=10, zorder=3)

        for agent in snap.agents:
            color = ROLE_COLOR.get(agent.role, "#ffffff")
            marker = STATUS_MARKER.get(agent.status, "o")
            ax.plot(agent.x, agent.y, marker=marker, color=color, markersize=9, zorder=4)
            ax.annotate(
                agent.agent_id,
                (agent.x, agent.y),
                textcoords="offset points", xytext=(4, 4),
                fontsize=6, color="white", zorder=5,
            )

        legend = [
            mpatches.Patch(color=c, label=r) for r, c in ROLE_COLOR.items()
        ] + [
            mpatches.Patch(color="#FFD700", label="Task(open)"),
            mpatches.Patch(color="#2ecc71", label="Charge"),
        ]
        ax.legend(handles=legend, loc="lower left", fontsize=6,
                  facecolor="#222244", labelcolor="white", framealpha=0.7)

        info = (
            f"energy={snap.economy.total_energy}  "
            f"balance={snap.economy.total_balance}  "
            f"tx={snap.economy.transactions}"
        )
        ax.set_xlabel(info, color="#aaaaaa", fontsize=8)

    def _draw_kpi(self, snap: StateSnapshot) -> None:
        ax = self.ax_kpi
        ax.clear()
        h = self._kpi_history
        ticks = h["ticks"]

        ax.set_facecolor("#1a1a2e")
        ax.set_title("KPI", color="white", fontsize=10)

        if ticks:
            ax.plot(ticks, h["completion"], label="completion", color="#2196F3")
            ax.plot(ticks, h["gini"],       label="gini",       color="#F44336")
            ax2 = ax.twinx()
            ax2.set_facecolor("#1a1a2e")
            ax2.plot(ticks, h["energy"],  label="energy",  color="#4CAF50", linestyle="--")
            ax2.plot(ticks, h["balance"], label="balance", color="#FF9800", linestyle="--")
            ax2.tick_params(colors="white")
            ax2.yaxis.label.set_color("white")
            lines2, labels2 = ax2.get_legend_handles_labels()
        else:
            lines2, labels2 = [], []

        ax.tick_params(colors="white")
        ax.set_xlabel("tick", color="white", fontsize=8)
        lines1, labels1 = ax.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2,
                  loc="upper left", fontsize=7,
                  facecolor="#222244", labelcolor="white", framealpha=0.7)

        m = snap.metrics
        summary = (
            f"completion={m.get('task_completion_rate', 0):.2f}  "
            f"gini={m.get('gini', 0):.3f}\n"
            f"open_tasks={m.get('open_tasks', 0)}  "
            f"mean_balance={m.get('mean_balance', 0)}"
        )
        ax.set_title(f"KPI\n{summary}", color="white", fontsize=8)

    def _update_kpi_history(self, snap: StateSnapshot) -> None:
        m = snap.metrics
        self._kpi_history["ticks"].append(snap.tick)
        self._kpi_history["completion"].append(m.get("task_completion_rate", 0))
        self._kpi_history["gini"].append(m.get("gini", 0))
        self._kpi_history["energy"].append(snap.economy.total_energy)
        self._kpi_history["balance"].append(snap.economy.total_balance)
        self._kpi_history["open_tasks"].append(m.get("open_tasks", 0))

    def animate(self, step_fn: Callable[[], StateSnapshot], ticks: int, interval: int = 150) -> None:
        def update(_frame):
            snap = step_fn()
            self.draw(snap)

        ani = FuncAnimation(self.fig, update, frames=ticks, interval=interval, repeat=False)
        plt.show()
