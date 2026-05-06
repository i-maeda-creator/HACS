import sys
sys.path.insert(0, ".")

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.core.policy import PolicyEngine
from layer0.export.web_exporter import export_for_web
from layer0.export.video_exporter import export_gif

AGENTS = [
    ("W1",  AgentRole.WORKER,   2,  2),
    ("W2",  AgentRole.WORKER,   5,  5),
    ("W3",  AgentRole.WORKER,  10,  3),
    ("W4",  AgentRole.WORKER,  14,  8),
    ("W5",  AgentRole.WORKER,   7, 14),
    ("W6",  AgentRole.WORKER,  12, 16),
    ("W7",  AgentRole.WORKER,   3, 10),
    ("W8",  AgentRole.WORKER,  16, 12),
    ("W9",  AgentRole.WORKER,   9,  7),
    ("W10", AgentRole.WORKER,   6, 17),
    ("G1",  AgentRole.GUARDIAN,15,  3),
    ("G2",  AgentRole.GUARDIAN, 3, 16),
    ("T1",  AgentRole.TRADER,   8,  8),
    ("T2",  AgentRole.TRADER,  13,  5),
    ("O1",  AgentRole.OBSERVER, 3, 15),
    ("O2",  AgentRole.OBSERVER,16,  6),
    ("V1",  AgentRole.GOVERNOR,10, 10),
]

TICKS = 100
SEED  = 42


def main():
    sim = Simulator(seed=SEED, policy=PolicyEngine())
    for aid, role, x, y in AGENTS:
        sim.add_agent(Agent(aid, role, x=x, y=y))

    # ── シミュレーションを全 tick 実行（先に全部走らせる）──
    print(f"HACS シミュレーション実行中: {len(sim.agents)} agents / {TICKS} ticks...")
    snapshots = sim.run(TICKS)
    print(f"完了: {len(snapshots)} snapshots 収集")

    sim.save_log("logs/events_full.jsonl")
    sim.save_replay("replays/replay_full.jsonl")

    print("\n--- Safety Gate ---")
    print(f"  violations: {len(sim.safety.violations)}")
    for v in sim.safety.violations[:5]:
        print(f"    tick={v.tick} rule={v.rule} agent={v.agent_id} severity={v.severity}")

    print("\n--- Policy スコア ---")
    scores = sim.policy.score(sim.agents, sim.tasks)
    for k, v in scores.items():
        print(f"  {k}: {v}")
    print(f"  violations: {len(sim.policy.violations)}")

    safety_event_count = sum(1 for e in sim.event_log if e.event_type.value == "SafetyTriggered")
    total_events = len(sim.event_log)
    print(f"\n--- Event Log ---")
    print(f"  total: {total_events}  safety_triggered: {safety_event_count}")

    # ── Web 3D ビューアー用 JSON ──────────────────────────
    print("\nWeb リプレイデータを生成中...")
    export_for_web(sim.world, snapshots, "web/replay.json")

    # ── 解説 GIF ─────────────────────────────────────────
    print("解説 GIF を生成中（30秒ほどかかります）...")
    export_gif(sim.world, snapshots, "web/hacs_demo.gif", every=2, fps=8)

    print("\n完了！")
    print("  3D ビューアー → web/viewer.html をブラウザで開いてください")
    print("  解説 GIF     → web/hacs_demo.gif")

    # ── matplotlib ダッシュボード（インタラクティブ環境のみ）──
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        from layer0.renderer.matplotlib_renderer import MatplotlibRenderer
        from layer0.renderer.kpi_dashboard import show_dashboard

        print("\nKPI ダッシュボードを表示中...")
        show_dashboard(snapshots, title="HACS KPI Dashboard")
    except Exception as e:
        print(f"\n[info] GUI 表示をスキップ: {e}")


if __name__ == "__main__":
    main()
