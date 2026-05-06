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
    for p in proposals[:5]:
        prop = p.payload.get("proposal", {})
        print(f"    tick={p.tick:3d}  {prop.get('action','?'):16s}  {prop.get('reason','')}")

    # ── オークション詳細 ────────────────────────────────────────
    print(f"\n=== オークション詳細 ===")
    bid_events      = [e for e in sim.event_log if e.event_type == EventType.BID_SUBMITTED]
    assigned_events = [e for e in sim.event_log if e.event_type == EventType.TASK_ASSIGNED]
    done_events     = [e for e in sim.event_log if e.event_type == EventType.TASK_COMPLETED]

    n_tasks = len([e for e in sim.event_log if e.event_type == EventType.TASK_CREATED])
    avg_bidders = len(bid_events) / n_tasks if n_tasks else 0
    print(f"  タスク数: {n_tasks}  総入札数: {len(bid_events)}  競争率: {avg_bidders:.1f}x")

    role_map = {a.agent_id: a.role.value for a in sim.agents}
    by_role_bids = defaultdict(list)
    for e in bid_events:
        by_role_bids[role_map.get(e.agent_id, "?")].append(e.payload.get("bid", 0))

    wins_by_agent = defaultdict(int)
    for e in assigned_events:
        wins_by_agent[e.agent_id] += 1

    by_role_wins = defaultdict(int)
    for aid, cnt in wins_by_agent.items():
        by_role_wins[role_map.get(aid, "?")] += cnt

    earn_by_agent = defaultdict(float)
    for e in done_events:
        earn_by_agent[e.agent_id] += e.payload.get("reward", 0)

    print(f"\n  役職別  入札数  勝利  勝率   avg入札額  avg獲得報酬")
    print(f"  {'-'*58}")
    for role in sorted(by_role_bids):
        bids   = by_role_bids[role]
        wins   = by_role_wins[role]
        rate   = wins / len(bids) * 100 if bids else 0
        avg_b  = sum(bids) / len(bids) if bids else 0
        earners= [a for a in sim.agents if role_map[a.agent_id] == role and earn_by_agent[a.agent_id] > 0]
        avg_e  = sum(earn_by_agent[a.agent_id] for a in earners) / len(earners) if earners else 0
        print(f"  {role:10s}  {len(bids):5d}  {wins:4d}  {rate:5.1f}%  {avg_b:7.2f} EC  {avg_e:6.1f} EC")

    print(f"\n  上位5エージェント（勝利数）:")
    top5 = sorted(wins_by_agent.items(), key=lambda x: -x[1])[:5]
    for i, (aid, w) in enumerate(top5, 1):
        role   = role_map.get(aid, "?")
        earned = earn_by_agent[aid]
        bids   = len([e for e in bid_events if e.agent_id == aid])
        print(f"    {i}. {aid:5s} [{role:8s}]  勝利 {w:2d}件  入札 {bids:3d}回  獲得 {earned:6.1f} EC")

    workers = [a for a in sim.agents if a.role.value == "Worker"]
    w_with_job = sum(1 for w in workers if earn_by_agent[w.agent_id] > 0)
    print(f"\n  Worker 受注状況: {w_with_job}/{len(workers)} 体が受注 "
          f"({w_with_job/len(workers)*100:.0f}%)")

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
