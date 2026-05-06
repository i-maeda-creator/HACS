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
        # Worker x 10 — グリッド全体に分散
        ("W01", AgentRole.WORKER,   2,  2), ("W02", AgentRole.WORKER,   6,  2),
        ("W03", AgentRole.WORKER,  11,  2), ("W04", AgentRole.WORKER,  16,  2),
        ("W05", AgentRole.WORKER,   2,  8), ("W06", AgentRole.WORKER,   7,  7),
        ("W07", AgentRole.WORKER,  13,  6), ("W08", AgentRole.WORKER,  17,  8),
        ("W09", AgentRole.WORKER,   4, 14), ("W10", AgentRole.WORKER,  14, 15),
        # Guardian x 3 — 外周パトロール
        ("G1",  AgentRole.GUARDIAN,  3,  3),
        ("G2",  AgentRole.GUARDIAN, 16,  3),
        ("G3",  AgentRole.GUARDIAN,  3, 16),
        # Trader x 3 — 中間エリア
        ("T1",  AgentRole.TRADER,    6,  6),
        ("T2",  AgentRole.TRADER,   13,  6),
        ("T3",  AgentRole.TRADER,    9, 13),
        # Observer x 2 — 対角担当
        ("O1",  AgentRole.OBSERVER,  3, 15),
        ("O2",  AgentRole.OBSERVER, 15,  4),
        # Governor x 2 — 中央 + 第2拠点スタート
        ("V1",  AgentRole.GOVERNOR, 10, 10),
        ("V2",  AgentRole.GOVERNOR,  5,  5),
    ]
    for aid, role, x, y in agents:
        sim.add_agent(Agent(aid, role, x=x, y=y))

    import json
    for tick in range(1, TICKS + 1):
        prev = len(sim.event_log)
        snap = sim.step()
        new_events = sim.event_log[prev:]
        for event in new_events:
            bus.publish_event(event)

        # スナップショット + policy_params を live_viewer へ送信
        snap_dict = json.loads(snap.model_dump_json())
        snap_dict["policy_params"] = dict(sim.policy_params)
        bus._client.publish("hacs/snapshot", json.dumps(snap_dict))

        if tick % 10 == 0:
            scores = sim.policy.score(sim.agents, sim.tasks)
            pp = sim.policy_params
            print(f"  tick {tick:3d} | events={len(sim.event_log):4d} | "
                  f"eff={scores.get('efficiency',0):.2f} | "
                  f"eq={scores.get('equality',0):.2f} | "
                  f"wb={pp['worker_bid_bonus']:.2f} rm={pp['reward_multiplier']:.2f}")

        time.sleep(TICK_INTERVAL)

    print(f"\n完了: {len(sim.event_log)} events published")
    bus.disconnect()


if __name__ == "__main__":
    main()
