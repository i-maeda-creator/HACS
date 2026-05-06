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
        # Worker x 30 — グリッド全体に均等分散
        ("W01",AgentRole.WORKER, 2, 2),("W02",AgentRole.WORKER, 5, 2),("W03",AgentRole.WORKER, 8, 2),
        ("W04",AgentRole.WORKER,11, 2),("W05",AgentRole.WORKER,14, 2),("W06",AgentRole.WORKER,17, 2),
        ("W07",AgentRole.WORKER, 2, 6),("W08",AgentRole.WORKER, 5, 6),("W09",AgentRole.WORKER, 8, 6),
        ("W10",AgentRole.WORKER,11, 6),("W11",AgentRole.WORKER,14, 6),("W12",AgentRole.WORKER,17, 6),
        ("W13",AgentRole.WORKER, 2,10),("W14",AgentRole.WORKER, 5,10),("W15",AgentRole.WORKER, 8,10),
        ("W16",AgentRole.WORKER,11,10),("W17",AgentRole.WORKER,14,10),("W18",AgentRole.WORKER,17,10),
        ("W19",AgentRole.WORKER, 2,14),("W20",AgentRole.WORKER, 5,14),("W21",AgentRole.WORKER, 8,14),
        ("W22",AgentRole.WORKER,11,14),("W23",AgentRole.WORKER,14,14),("W24",AgentRole.WORKER,17,14),
        ("W25",AgentRole.WORKER, 2,17),("W26",AgentRole.WORKER, 5,17),("W27",AgentRole.WORKER, 8,17),
        ("W28",AgentRole.WORKER,11,17),("W29",AgentRole.WORKER,14,17),("W30",AgentRole.WORKER,17,17),
        # Guardian x 6 — 外周パトロール
        ("G1",AgentRole.GUARDIAN, 3, 3),("G2",AgentRole.GUARDIAN,16, 3),
        ("G3",AgentRole.GUARDIAN,16,16),("G4",AgentRole.GUARDIAN, 3,16),
        ("G5",AgentRole.GUARDIAN,10, 3),("G6",AgentRole.GUARDIAN,10,16),
        # Trader x 6 — 中間エリア
        ("T1",AgentRole.TRADER, 6, 6),("T2",AgentRole.TRADER,13, 6),
        ("T3",AgentRole.TRADER, 6,13),("T4",AgentRole.TRADER,13,13),
        ("T5",AgentRole.TRADER, 6,10),("T6",AgentRole.TRADER,13,10),
        # Observer x 5 — 4象限 + 中央
        ("O1",AgentRole.OBSERVER, 3, 3),("O2",AgentRole.OBSERVER,16, 3),
        ("O3",AgentRole.OBSERVER, 3,16),("O4",AgentRole.OBSERVER,16,16),
        ("O5",AgentRole.OBSERVER, 9, 9),
        # Governor x 3 — 監視拠点スタート分散
        ("V1",AgentRole.GOVERNOR,10,10),
        ("V2",AgentRole.GOVERNOR, 5, 5),
        ("V3",AgentRole.GOVERNOR,15,15),
    ]  # 30+6+6+5+3 = 50体
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
