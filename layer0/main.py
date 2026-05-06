import os
import time
from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.renderer.ascii_renderer import render

def main():
    sim = Simulator(seed=42)

    agents = [
        Agent("W1", AgentRole.WORKER,   x=2,  y=2),
        Agent("W2", AgentRole.WORKER,   x=5,  y=5),
        Agent("W3", AgentRole.WORKER,   x=10, y=10),
        Agent("G1", AgentRole.GUARDIAN, x=15, y=3),
        Agent("O1", AgentRole.OBSERVER, x=3,  y=15),
    ]
    for a in agents:
        sim.add_agent(a)

    print("HACS Layer0 シミュレーション開始")
    print("=" * 40)

    for _ in range(50):
        snap = sim.step()
        os.system("cls" if os.name == "nt" else "clear")
        print(render(sim.world, snap))
        time.sleep(0.15)

    sim.save_log("logs/events.jsonl")
    sim.save_replay("replays/replay.jsonl")
    print("\n完了。logs/ と replays/ に保存しました。")

if __name__ == "__main__":
    main()
