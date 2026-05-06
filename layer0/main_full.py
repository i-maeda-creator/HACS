import sys
sys.path.insert(0, ".")

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.core.policy import PolicyEngine
from layer0.renderer.matplotlib_renderer import MatplotlibRenderer
from layer0.renderer.kpi_dashboard import show_dashboard

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

    renderer = MatplotlibRenderer(sim.world, title="HACS Layer0 — Full Simulation")

    print(f"HACS シミュレーション開始: {len(sim.agents)} agents / {TICKS} ticks")
    renderer.animate(sim.step, ticks=TICKS, interval=120)

    sim.save_log("logs/events_full.jsonl")
    sim.save_replay("replays/replay_full.jsonl")

    print("\n--- 最終 Policy スコア ---")
    scores = sim.policy.score(sim.agents, sim.tasks)
    for k, v in scores.items():
        print(f"  {k}: {v}")
    print(f"  violations: {len(sim.policy.violations)}")

    show_dashboard(sim.snapshots, title="HACS KPI Dashboard")


if __name__ == "__main__":
    main()
