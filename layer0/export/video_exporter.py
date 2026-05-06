from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# Windows 日本語フォントを設定
for fname in ["Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]:
    if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        matplotlib.rcParams["font.family"] = fname
        break
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
from typing import List
from layer0.core.world import World, Cell
from layer0.schemas.state import StateSnapshot

CELL_COLOR = {Cell.EMPTY: [0.08, 0.08, 0.14], Cell.WALL: [0.15, 0.15, 0.25],
              Cell.CHARGE: [0.1, 0.55, 0.3], Cell.DANGER: [0.6, 0.1, 0.1]}
ROLE_COLOR = {"Worker": "#2196F3", "Guardian": "#F44336", "Trader": "#FF9800",
              "Observer": "#9C27B0", "Governor": "#795548"}
ROLE_JP    = {"Worker": "作業員", "Guardian": "警備", "Trader": "商人",
              "Observer": "観察者", "Governor": "統治者"}
STATUS_JP  = {"idle": "待機", "moving": "移動中", "working": "作業中", "charging": "充電中"}


def _build_bg(world: World) -> np.ndarray:
    img = np.zeros((world.height, world.width, 3))
    for y in range(world.height):
        for x in range(world.width):
            img[y, x] = CELL_COLOR[world.get_cell(x, y)]
    return img


def export_gif(world: World, snapshots: List[StateSnapshot],
               path: str = "web/hacs_demo.gif",
               every: int = 2, fps: int = 8) -> None:

    from matplotlib.animation import FuncAnimation, PillowWriter

    bg = _build_bg(world)
    selected = snapshots[::every]

    fig = plt.figure(figsize=(14, 7), facecolor="#0a0a1a")
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.05, width_ratios=[1, 0.55])
    ax_world = fig.add_subplot(gs[0])
    ax_info  = fig.add_subplot(gs[1])
    ax_world.set_facecolor("#0a0a1a")
    ax_info.set_facecolor("#0a0a1a")
    ax_info.axis("off")

    # KPI 履歴
    all_ticks  = [s.tick for s in snapshots]
    all_comp   = [s.metrics.get("task_completion_rate", 0) for s in snapshots]
    all_gini   = [s.metrics.get("gini", 0) for s in snapshots]
    all_energy = [s.economy.total_energy for s in snapshots]

    def draw(snap: StateSnapshot) -> None:
        ax_world.clear()
        ax_info.clear()
        ax_world.set_facecolor("#0a0a1a")
        ax_info.set_facecolor("#0a0a1a")
        ax_info.axis("off")

        # ── ワールド ──────────────────────────────
        ax_world.imshow(bg, origin="upper", interpolation="nearest")
        ax_world.set_xticks([]); ax_world.set_yticks([])
        ax_world.set_title(f"HACS Layer0  tick={snap.tick}",
                           color="white", fontsize=11, pad=8)

        for t in snap.tasks:
            c = "#FFD700" if t.status == "open" else "#FF6600"
            ax_world.plot(t.x, t.y, "*", color=c, markersize=11, zorder=3)

        for a in snap.agents:
            c = ROLE_COLOR.get(a.role, "#fff")
            ax_world.plot(a.x, a.y, "o", color=c, markersize=9, zorder=4,
                          markeredgewidth=1.5, markeredgecolor="white")
            ax_world.annotate(a.agent_id, (a.x, a.y),
                              xytext=(3, 3), textcoords="offset points",
                              fontsize=6, color="white", zorder=5)

        legend_items = [mpatches.Patch(color=c, label=f"{r}（{ROLE_JP[r]}）")
                        for r, c in ROLE_COLOR.items()]
        legend_items += [mpatches.Patch(color="#FFD700", label="タスク（未着手）"),
                         mpatches.Patch(color="#FF6600", label="タスク（担当中）")]
        ax_world.legend(handles=legend_items, loc="lower left", fontsize=7,
                        facecolor="#11112a", labelcolor="white", framealpha=0.85)

        # ── 右パネル ──────────────────────────────
        m = snap.metrics
        e = snap.economy

        # タイトル
        ax_info.text(0.5, 0.97, "HACS — 自律文明シミュレーター", ha="center", va="top",
                     color="#88aaff", fontsize=12, fontweight="bold",
                     transform=ax_info.transAxes)

        # 説明テキスト
        desc = (
            "ロボット（エージェント）が自律的にタスクへ\n"
            "入札し、エネルギーコインで報酬を受け取る。\n"
            "税・ルール・格差指標（Gini）で都市を運営。"
        )
        ax_info.text(0.05, 0.90, desc, ha="left", va="top",
                     color="#aaaacc", fontsize=8, linespacing=1.7,
                     transform=ax_info.transAxes)

        # KPI テーブル
        kpi_lines = [
            ("タスク成立率",  f"{m.get('task_completion_rate', 0)*100:.0f}%"),
            ("格差 (Gini)",   f"{m.get('gini', 0):.3f}"),
            ("オープンタスク",f"{m.get('open_tasks', 0)}"),
            ("総エネルギー",  f"{e.total_energy} EC"),
            ("総残高",        f"{e.total_balance} EC"),
            ("取引数",        f"{e.transactions}"),
            ("効率スコア",    f"{m.get('policy_efficiency', 0)*100:.0f}%" if m.get('policy_efficiency') is not None else "—"),
            ("平等スコア",    f"{m.get('policy_equality', 0)*100:.0f}%"  if m.get('policy_equality')  is not None else "—"),
        ]
        y0 = 0.72
        for label, val in kpi_lines:
            ax_info.text(0.06, y0, label, color="#8888aa", fontsize=9, transform=ax_info.transAxes)
            ax_info.text(0.94, y0, val,   color="#ffffff", fontsize=9, fontweight="bold",
                         ha="right", transform=ax_info.transAxes)
            y0 -= 0.065

        # ミニグラフ（KPI 推移）
        cur_idx = snap.tick - 1 if snap.tick <= len(all_ticks) else len(all_ticks) - 1
        sub_ax = ax_info.inset_axes([0.05, 0.05, 0.9, 0.22])
        sub_ax.set_facecolor("#0f0f23")
        sub_ax.plot(all_ticks[:cur_idx+1], all_comp[:cur_idx+1],  color="#2196F3", lw=1.2, label="成立率")
        sub_ax.plot(all_ticks[:cur_idx+1], all_gini[:cur_idx+1],  color="#F44336", lw=1.2, label="Gini")
        sub_ax.set_xlim(0, max(all_ticks))
        sub_ax.set_ylim(0, 1.05)
        sub_ax.tick_params(colors="white", labelsize=6)
        sub_ax.spines["bottom"].set_color("#334"); sub_ax.spines["left"].set_color("#334")
        sub_ax.spines["top"].set_visible(False);   sub_ax.spines["right"].set_visible(False)
        sub_ax.legend(fontsize=6, facecolor="#111", labelcolor="white", framealpha=0.7, loc="upper left")
        sub_ax.set_title("KPI 推移", color="#8888aa", fontsize=7)

        # エージェント状態バー（上位5体）
        y_bar = 0.285
        ax_info.text(0.06, y_bar + 0.015, "エージェント状態（エネルギー）",
                     color="#8888aa", fontsize=7, transform=ax_info.transAxes)
        for a in snap.agents[:8]:
            c = ROLE_COLOR.get(a.role, "#fff")
            bar_w = a.energy / 100 * 0.85
            ax_info.add_patch(mpatches.FancyBboxPatch(
                (0.06, y_bar - 0.035), bar_w, 0.028,
                boxstyle="round,pad=0.002", color=c, alpha=0.7,
                transform=ax_info.transAxes, zorder=3))
            ax_info.text(0.06 + bar_w + 0.01, y_bar - 0.022,
                         f"{a.agent_id} {STATUS_JP.get(a.status, a.status)}",
                         color="white", fontsize=6, va="center",
                         transform=ax_info.transAxes)
            y_bar -= 0.038

    def update(i: int):
        draw(selected[i])

    ani = FuncAnimation(fig, update, frames=len(selected), repeat=False)
    writer = PillowWriter(fps=fps)
    ani.save(path, writer=writer, dpi=90)
    plt.close(fig)
    print(f"GIF saved → {path}  ({len(selected)} frames)")
