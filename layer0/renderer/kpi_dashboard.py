from __future__ import annotations
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from typing import List
from layer0.schemas.state import StateSnapshot


def show_dashboard(snapshots: List[StateSnapshot], title: str = "HACS KPI Dashboard") -> None:
    ticks       = [s.tick for s in snapshots]
    completion  = [s.metrics.get("task_completion_rate", 0) for s in snapshots]
    gini        = [s.metrics.get("gini", 0) for s in snapshots]
    open_tasks  = [s.metrics.get("open_tasks", 0) for s in snapshots]
    energy      = [s.economy.total_energy for s in snapshots]
    balance     = [s.economy.total_balance for s in snapshots]
    transactions= [s.economy.transactions for s in snapshots]
    mean_bal    = [s.metrics.get("mean_balance", 0) for s in snapshots]

    fig = plt.figure(figsize=(16, 10), facecolor="#1a1a2e")
    fig.suptitle(title, color="white", fontsize=15, fontweight="bold")
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    panels = [
        (gs[0, 0], "Task Completion Rate", ticks, completion, "#2196F3", None),
        (gs[0, 1], "Gini Coefficient",     ticks, gini,       "#F44336", None),
        (gs[0, 2], "Open Tasks",           ticks, open_tasks, "#FF9800", None),
        (gs[1, 0], "Total Energy (EC)",    ticks, energy,     "#4CAF50", None),
        (gs[1, 1], "Total Balance (EC)",   ticks, balance,    "#9C27B0", None),
        (gs[1, 2], "Transactions",         ticks, transactions,"#00BCD4", None),
    ]

    for spec, title_p, xs, ys, color, _ in panels:
        ax = fig.add_subplot(spec)
        _style_ax(ax)
        ax.plot(xs, ys, color=color, linewidth=1.5)
        ax.fill_between(xs, ys, alpha=0.15, color=color)
        ax.set_title(title_p, color="white", fontsize=9)
        ax.set_xlabel("tick", color="#aaaaaa", fontsize=7)

    # エージェント別残高の積み上げエリア
    ax_agents = fig.add_subplot(gs[2, :])
    _style_ax(ax_agents)
    if snapshots:
        agent_ids = [a.agent_id for a in snapshots[0].agents]
        colors_ag = plt.cm.tab10.colors
        for i, aid in enumerate(agent_ids):
            bal = [next((a.balance for a in s.agents if a.agent_id == aid), 0) for s in snapshots]
            ax_agents.plot(ticks, bal, label=aid, color=colors_ag[i % 10], linewidth=1.5)
        ax_agents.set_title("Agent Balance History", color="white", fontsize=9)
        ax_agents.set_xlabel("tick", color="#aaaaaa", fontsize=7)
        ax_agents.legend(loc="upper left", fontsize=7, facecolor="#222244",
                         labelcolor="white", framealpha=0.7)

    plt.show()


def _style_ax(ax) -> None:
    ax.set_facecolor("#0f0f23")
    ax.tick_params(colors="white", labelsize=7)
    ax.spines["bottom"].set_color("#444466")
    ax.spines["left"].set_color("#444466")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.label.set_color("white")
