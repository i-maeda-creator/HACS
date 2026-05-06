"""Layer0 シミュレーターをリアルタイムで MQTT Publish するランナー."""
from __future__ import annotations
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer2.event_bus import EventBus

TICK_INTERVAL = 0.2   # 1tick = 0.2秒（5 tick/sec）
TICKS         = 200


def main():
    print("=== HACS Live Simulation ===")
    print(f"  {TICKS} ticks / {TICK_INTERVAL}s per tick")
    print(f"  ブラウザ: http://localhost:8080/live_dashboard.html\n")

    bus = EventBus(client_id="hacs_live_runner")
    if not bus.connect(timeout=5.0):
        print("[ERROR] Mosquitto に接続できません。サービスを確認してください。")
        sys.exit(1)
    print("  MQTT 接続完了\n")

    sim = Simulator(seed=42)
    agents = [
        ("W1",  AgentRole.WORKER,    2,  2),
        ("W2",  AgentRole.WORKER,    5,  5),
        ("W3",  AgentRole.WORKER,   10,  3),
        ("W4",  AgentRole.WORKER,   14,  8),
        ("W5",  AgentRole.WORKER,    7, 14),
        ("G1",  AgentRole.GUARDIAN, 15,  3),
        ("G2",  AgentRole.GUARDIAN,  3, 16),
        ("T1",  AgentRole.TRADER,    8,  8),
        ("O1",  AgentRole.OBSERVER,  3, 15),
        ("V1",  AgentRole.GOVERNOR, 10, 10),
    ]
    for aid, role, x, y in agents:
        sim.add_agent(Agent(aid, role, x=x, y=y))

    for tick in range(1, TICKS + 1):
        prev = len(sim.event_log)
        sim.step()
        new_events = sim.event_log[prev:]
        for event in new_events:
            bus.publish_event(event)

        if tick % 10 == 0:
            scores = sim.policy.score(sim.agents, sim.tasks)
            print(f"  tick {tick:3d} | events={len(sim.event_log):4d} | "
                  f"eff={scores.get('efficiency',0):.2f} | "
                  f"eq={scores.get('equality',0):.2f}")

        time.sleep(TICK_INTERVAL)

    print(f"\n完了: {len(sim.event_log)} events published")
    bus.disconnect()


if __name__ == "__main__":
    main()
