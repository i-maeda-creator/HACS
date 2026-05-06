"""MQTT 統合テスト: Mosquitto が動いているか確認 → 10 tick シミュレーションを Pub/Sub."""
from __future__ import annotations
import sys
import os
import time
import subprocess
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer2.event_bus import EventBus
from layer2.simulator_bridge import SimulatorBridge


def start_broker() -> subprocess.Popen:
    """Mosquitto をローカルで起動（既に起動中ならエラーを無視）."""
    mosquitto_path = r"C:\Program Files\mosquitto\mosquitto.exe"
    try:
        proc = subprocess.Popen(
            [mosquitto_path, "-v"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        return proc
    except FileNotFoundError:
        print("[ERROR] mosquitto.exe が見つかりません")
        sys.exit(1)


def main():
    print("=== HACS Layer2 MQTT 統合テスト ===\n")

    # 1. Broker 起動
    print("[1/4] Mosquitto Broker 起動中...")
    broker = start_broker()
    print("      起動完了\n")

    # 2. Publisher 接続
    print("[2/4] Publisher (Simulator Bridge) 接続中...")
    pub_bus = EventBus(client_id="hacs_simulator")
    if not pub_bus.connect(timeout=5.0):
        print("[ERROR] Broker に接続できませんでした")
        broker.terminate()
        sys.exit(1)
    print("      接続完了\n")

    # 3. Subscriber 接続
    print("[3/4] Subscriber (Observer) 接続中...")
    sub_bus = EventBus(client_id="hacs_observer")
    sub_bus.connect(timeout=5.0)

    received: list = []
    def on_event(topic: str, payload: dict):
        received.append((topic, payload.get("event_type", "?")))
        etype = payload.get("event_type", "?")
        agent = payload.get("agent_id", "")
        print(f"      [RCV] {topic:45s} | {etype} {agent}")

    # 全トピックを直接購読（ワイルドカード）
    for w in ["city/#", "agent/#", "energy/#", "safety/#", "network/#"]:
        sub_bus.subscribe(w, on_event)
    time.sleep(0.5)  # subscription が broker に届くまで待つ
    print()

    # 4. シミュレーション実行 → Publish
    print("[4/4] 10 tick シミュレーション実行 → MQTT Publish...")
    sim = Simulator(seed=42)
    sim.add_agent(Agent("W1", AgentRole.WORKER,   x=2, y=2))
    sim.add_agent(Agent("W2", AgentRole.WORKER,   x=5, y=5))
    sim.add_agent(Agent("G1", AgentRole.GUARDIAN, x=8, y=8))
    sim.add_agent(Agent("T1", AgentRole.TRADER,   x=10, y=10))

    bridge = SimulatorBridge(sim, pub_bus)
    bridge.run(10)
    time.sleep(1.0)  # メッセージ到着を待つ

    # 結果
    print(f"\n=== 結果 ===")
    print(f"  Published : {pub_bus.stats()['published']}")
    print(f"  Received  : {len(received)}")
    print(f"  Event Log : {len(sim.event_log)} events total")

    if len(received) > 0:
        print("\n  成功: Layer0 -> MQTT -> Layer2 の疎通確認完了!")
    else:
        print("\n  [WARN] メッセージを受信できませんでした（Broker確認を）")

    pub_bus.disconnect()
    sub_bus.disconnect()
    broker.terminate()
    print("\nテスト完了")


if __name__ == "__main__":
    main()
