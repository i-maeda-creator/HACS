"""
50体スケールテスト — パフォーマンスと安定性の確認。
"""
import sys, time
sys.path.insert(0, ".")

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole

TICKS = 200
SEED  = 42


def generate_agents():
    """20×20グリッドに50体を分散配置。"""
    agents = []
    positions = []

    def pos(x, y):
        positions.append((x, y))
        return x, y

    # Worker x 30（グリッド全体に均等分散）
    worker_spots = [
        (2,2),(5,2),(8,2),(11,2),(14,2),(17,2),
        (2,6),(5,6),(8,6),(11,6),(14,6),(17,6),
        (2,10),(5,10),(8,10),(11,10),(14,10),(17,10),
        (2,14),(5,14),(8,14),(11,14),(14,14),(17,14),
        (2,17),(5,17),(8,17),(11,17),(14,17),(17,17),
    ]
    for i,(x,y) in enumerate(worker_spots):
        agents.append(Agent(f"W{i+1:02d}", AgentRole.WORKER, x=x, y=y))

    # Guardian x 6（外周パトロール開始点）
    guardian_spots = [(3,3),(16,3),(16,16),(3,16),(10,3),(10,16)]
    for i,(x,y) in enumerate(guardian_spots):
        agents.append(Agent(f"G{i+1}", AgentRole.GUARDIAN, x=x, y=y))

    # Trader x 6
    trader_spots = [(6,6),(13,6),(6,13),(13,13),(6,10),(13,10)]
    for i,(x,y) in enumerate(trader_spots):
        agents.append(Agent(f"T{i+1}", AgentRole.TRADER, x=x, y=y))

    # Observer x 5（4象限 + 中央）
    observer_spots = [(3,3),(16,3),(3,16),(16,16),(9,9)]
    for i,(x,y) in enumerate(observer_spots):
        agents.append(Agent(f"O{i+1}", AgentRole.OBSERVER, x=x, y=y))

    # Governor x 3
    governor_spots = [(10,10),(5,5),(15,15)]
    for i,(x,y) in enumerate(governor_spots):
        agents.append(Agent(f"V{i+1}", AgentRole.GOVERNOR, x=x, y=y))

    return agents  # 30+6+6+5+3 = 50


def main():
    agents = generate_agents()
    print(f"=== HACS Scale Test ===")
    print(f"  Agents : {len(agents)}")
    print(f"  Ticks  : {TICKS}")
    print()

    sim = Simulator(seed=SEED)
    for a in agents:
        sim.add_agent(a)

    # ── 実行 & 計測 ──────────────────────────────────────────────
    tick_times = []
    t_total = time.perf_counter()
    for i in range(TICKS):
        t0 = time.perf_counter()
        sim.step()
        tick_times.append(time.perf_counter() - t0)
        if (i+1) % 50 == 0:
            avg_ms = sum(tick_times[-50:]) / 50 * 1000
            print(f"  tick {i+1:4d} | events={len(sim.event_log):5d} | avg {avg_ms:.2f}ms/tick")

    elapsed = time.perf_counter() - t_total

    # ── 結果 ────────────────────────────────────────────────────
    print(f"\n=== 結果 ===")
    print(f"  実行時間       : {elapsed:.2f}s")
    print(f"  平均 tick 速度 : {elapsed/TICKS*1000:.2f}ms/tick")
    print(f"  総イベント数   : {len(sim.event_log)}")
    print(f"  Safety 違反    : {len(sim.safety.violations)}")
    print(f"  Policy 違反    : {len(sim.policy.violations)}")

    scores = sim.policy.score(sim.agents, sim.tasks)
    print(f"\n  効率性   : {scores.get('efficiency',0):.3f}")
    print(f"  平等性   : {scores.get('equality',0):.3f}")

    # 役職別サマリー
    print(f"\n  役職別残高（平均）:")
    from collections import defaultdict
    by_role = defaultdict(list)
    for a in sim.agents:
        by_role[a.role.value].append(a.balance)
    for role, balances in sorted(by_role.items()):
        avg = sum(balances)/len(balances)
        print(f"    {role:10s}: avg={avg:6.1f} EC  n={len(balances)}")

    # Governor 提案
    from layer0.schemas.event import EventType
    proposals = [e for e in sim.event_log
                 if e.event_type == EventType.POLICY_CHANGED
                 and e.payload.get("source") == "governor"]
    print(f"\n  Governor 政策提案: {len(proposals)}件")
    for p in proposals[:3]:
        print(f"    tick={p.tick}  {p.payload.get('proposal',{})}")

    # パフォーマンス診断
    max_ms = max(tick_times) * 1000
    print(f"\n=== パフォーマンス ===")
    print(f"  最大 tick 時間: {max_ms:.2f}ms")
    if max_ms < 10:
        print("  判定: 良好 (< 10ms)")
    elif max_ms < 50:
        print("  判定: 許容範囲 (< 50ms)")
    else:
        print("  判定: 要最適化 (> 50ms)")

    sim.save_log("logs/scale_test_events.jsonl")
    print(f"\nログ保存: logs/scale_test_events.jsonl")


if __name__ == "__main__":
    main()
