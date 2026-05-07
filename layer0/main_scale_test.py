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
    """20×20グリッドに60体を分散配置。"""
    agents = []

    # Worker x 36（6×6 グリッド均等配置）
    worker_spots = [
        (2,1),(5,1),(8,1),(11,1),(14,1),(17,1),
        (2,4),(5,4),(8,4),(11,4),(14,4),(17,4),
        (2,8),(5,8),(8,8),(11,8),(14,8),(17,8),
        (2,11),(5,11),(8,11),(11,11),(14,11),(17,11),
        (2,15),(5,15),(8,15),(11,15),(14,15),(17,15),
        (2,18),(5,18),(8,18),(11,18),(14,18),(17,18),
    ]
    for i, (x, y) in enumerate(worker_spots):
        agents.append(Agent(f"W{i+1:02d}", AgentRole.WORKER, x=x, y=y))

    # Guardian x 8（外周8点）
    guardian_spots = [
        (2,2),(10,2),(17,2),
        (2,10),(17,10),
        (2,17),(10,17),(17,17),
    ]
    for i, (x, y) in enumerate(guardian_spots):
        agents.append(Agent(f"G{i+1}", AgentRole.GUARDIAN, x=x, y=y))

    # Trader x 7
    trader_spots = [(5,5),(14,5),(5,14),(14,14),(9,9),(5,9),(14,9)]
    for i, (x, y) in enumerate(trader_spots):
        agents.append(Agent(f"T{i+1}", AgentRole.TRADER, x=x, y=y))

    # Observer x 6（4象限 + 南北中央）
    observer_spots = [(3,3),(16,3),(3,16),(16,16),(9,2),(9,17)]
    for i, (x, y) in enumerate(observer_spots):
        agents.append(Agent(f"O{i+1}", AgentRole.OBSERVER, x=x, y=y))

    # Governor x 3
    governor_spots = [(10,10),(4,4),(15,15)]
    for i, (x, y) in enumerate(governor_spots):
        agents.append(Agent(f"V{i+1}", AgentRole.GOVERNOR, x=x, y=y))

    # Medic x 4（各象限に1体）
    medic_spots = [(5,5),(14,5),(5,14),(14,14)]
    for i, (x, y) in enumerate(medic_spots):
        agents.append(Agent(f"M{i+1}", AgentRole.MEDIC, x=x, y=y))

    return agents  # 36+8+7+6+3+4 = 64


def main():
    agents = generate_agents()
    print(f"=== HACS Scale Test ===")
    print(f"  Agents : {len(agents)} (Worker x36 / Guardian x8 / Trader x7 / Observer x6 / Governor x3 / Medic x4)")
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
    print(f"  税プール : {sim.economy.tax_pool:.1f} EC")

    # 役職別サマリー
    print(f"\n  役職別残高（平均）:")
    from collections import defaultdict
    by_role = defaultdict(list)
    for a in sim.agents:
        by_role[a.role.value].append(a.balance)
    for role, balances in sorted(by_role.items()):
        avg = sum(balances)/len(balances)
        print(f"    {role:10s}: avg={avg:6.1f} EC  n={len(balances)}")

    # Governor 投票・可決
    from layer0.schemas.event import EventType
    votes      = [e for e in sim.event_log if e.event_type == EventType.VOTE_SUBMITTED]
    passed     = [e for e in sim.event_log if e.event_type == EventType.VOTE_PASSED]
    market_evs = [e for e in sim.event_log if e.event_type == EventType.MARKET_EVENT]
    print(f"\n  Governor 投票提出: {len(votes)}件  可決: {len(passed)}件")
    for p in passed[:5]:
        cf = p.payload.get("consensus_factor", 1.0)
        print(f"    tick={p.tick:3d}  {p.payload.get('action','?'):16s}  "
              f"voters={p.payload.get('voters')}  factor={cf:.1f}x")
    print(f"  市場イベント: {len(market_evs)}件")
    for m in market_evs[:6]:
        print(f"    tick={m.tick:3d}  {m.payload.get('event','?')}"
              f"  multiplier={m.payload.get('reward_multiplier','')}")

    # ── オークション詳細 ────────────────────────────────────────
    print(f"\n=== オークション詳細 ===")
    bid_events      = [e for e in sim.event_log if e.event_type == EventType.BID_SUBMITTED]
    assigned_events = [e for e in sim.event_log if e.event_type == EventType.TASK_ASSIGNED]
    done_events     = [e for e in sim.event_log if e.event_type == EventType.TASK_COMPLETED]

    created_events = [e for e in sim.event_log
                      if e.event_type == EventType.TASK_CREATED
                      and e.payload.get("event") != "expired"]
    expired_count = sum(1 for t in sim.tasks if t.status.value == "expired")
    n_tasks = len(created_events)
    avg_bidders = len(bid_events) / n_tasks if n_tasks else 0
    print(f"  タスク数: {n_tasks}  総入札数: {len(bid_events)}  競争率: {avg_bidders:.1f}x  期限切れ: {expired_count}")

    # タスクタイプ別集計
    from collections import Counter
    type_counts   = Counter(e.payload.get("task_type", "?") for e in created_events)
    type_done     = Counter(t.task_type.value for t in sim.tasks if t.status.value == "completed")
    type_expired  = Counter(t.task_type.value for t in sim.tasks if t.status.value == "expired")
    print(f"\n  タスクタイプ別:")
    print(f"  {'Type':10s}  {'生成':>5}  {'完了':>5}  {'期限切':>5}  完了率")
    print(f"  {'-'*42}")
    for ttype in ["standard","heavy","urgent","trade","security","survey"]:
        n   = type_counts.get(ttype, 0)
        d   = type_done.get(ttype, 0)
        ex  = type_expired.get(ttype, 0)
        rate = f"{d/n*100:.0f}%" if n > 0 else "-"
        print(f"  {ttype:10s}  {n:5d}  {d:5d}  {ex:5d}  {rate}")

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

    # Worker 特性別サマリー
    from layer0.core.ai import get_worker_trait, TRAIT_LABELS
    trait_bids  = defaultdict(list)
    trait_wins  = defaultdict(int)
    trait_earn  = defaultdict(float)
    for a in workers:
        ai_obj = sim._ai.get(a.agent_id)
        trait  = get_worker_trait(ai_obj) if ai_obj else None
        label  = TRAIT_LABELS.get(trait, "?") if trait else "?"
        bids_a = [e for e in bid_events if e.agent_id == a.agent_id]
        trait_bids[label].extend(bids_a)
        trait_wins[label] += wins_by_agent.get(a.agent_id, 0)
        trait_earn[label] += earn_by_agent.get(a.agent_id, 0.0)

    print(f"\n  Worker 特性別  体数  入札  勝利  勝率   avg獲得EC")
    print(f"  {'-'*52}")
    trait_counts = defaultdict(int)
    for a in workers:
        ai_obj = sim._ai.get(a.agent_id)
        trait  = get_worker_trait(ai_obj) if ai_obj else None
        label  = TRAIT_LABELS.get(trait, "?") if trait else "?"
        trait_counts[label] += 1
    for label in sorted(trait_counts):
        n     = trait_counts[label]
        bids_ = trait_bids[label]
        wins_ = trait_wins[label]
        earn_ = trait_earn[label]
        rate  = wins_ / len(bids_) * 100 if bids_ else 0
        avg_e = earn_ / n
        print(f"  {label:10s}  {n:4d}  {len(bids_):4d}  {wins_:4d}  {rate:5.1f}%  {avg_e:8.1f} EC")

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

    # ── 消費・補助統計 ─────────────────────────────────────────────
    from layer0.schemas.event import EventType as ET
    heal_events   = [e for e in sim.event_log if e.event_type == ET.HEALING_DONE]
    safety_events = [e for e in sim.event_log if e.event_type == ET.SAFETY_NET_PAID]
    upkeep_events = [e for e in sim.event_log if e.event_type == ET.UPKEEP_PAID]
    gov_rewards   = [e for e in sim.event_log if e.event_type == ET.GOVERNANCE_REWARD]
    print(f"\n=== 経済循環 ===")
    total_upkeep = len(upkeep_events) * 0.20
    total_heal   = sum(e.payload.get("cost", 0) for e in heal_events)
    total_safety = len(safety_events) * 5.0
    total_gov_r  = sum(e.payload.get("reward", 0) for e in gov_rewards)
    print(f"  維持費総額   : {total_upkeep:.1f} EC ({len(upkeep_events)}件)")
    print(f"  Medic治療費  : {total_heal:.1f} EC ({len(heal_events)}件)")
    print(f"  セーフティNet: {total_safety:.1f} EC ({len(safety_events)}件)")
    print(f"  Governor報酬 : {total_gov_r:.1f} EC ({len(gov_rewards)}件)")
    medics = [a for a in sim.agents if a.role.value == "Medic"]
    if medics:
        print(f"\n  Medic 収支:")
        for m in medics:
            heals = [e for e in heal_events if e.agent_id == m.agent_id]
            earned = sum(e.payload.get("cost", 0) for e in heals)
            print(f"    {m.agent_id}: 治療{len(heals)}件  獲得{earned:.1f} EC  残高{m.balance:.1f} EC")

    sim.save_log("logs/scale_test_events.jsonl")
    print(f"\nログ保存: logs/scale_test_events.jsonl")


if __name__ == "__main__":
    main()
