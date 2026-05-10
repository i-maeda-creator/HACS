"""
60体スケールテスト — 40×40四地区マップ。
"""
import sys, time
sys.path.insert(0, ".")

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.core.world import World

TICKS = 2000
SEED  = 42


def _spots_in_district(district: str, n: int, rng) -> list:
    """地区内のランダム配置座標をn個生成。"""
    spots = []
    if district == "NW":
        xs, ys = range(2, 18), range(2, 18)
    elif district == "NE":
        xs, ys = range(22, 38), range(2, 18)
    elif district == "SW":
        xs, ys = range(2, 18), range(22, 38)
    else:  # SE
        xs, ys = range(22, 38), range(22, 38)
    xs, ys = list(xs), list(ys)
    used = set()
    while len(spots) < n:
        x = rng.choice(xs)
        y = rng.choice(ys)
        if (x, y) not in used:
            used.add((x, y))
            spots.append((x, y))
    return spots


def generate_agents(rng):
    """40×40グリッドに各役職を4地区に均等分散。"""
    agents = []

    # ── Worker x 60（各地区15体） ────────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        spots = _spots_in_district(district, 15, rng)
        for j, (x, y) in enumerate(spots):
            wid = i * 15 + j + 1
            agents.append(Agent(f"W{wid:02d}", AgentRole.WORKER, x=x, y=y))

    # ── Guardian x 12（各地区3体） ───────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        spots = _spots_in_district(district, 3, rng)
        for j, (x, y) in enumerate(spots):
            agents.append(Agent(f"G{i*3+j+1}", AgentRole.GUARDIAN, x=x, y=y))

    # ── Trader x 8（各地区2体） ─────────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        spots = _spots_in_district(district, 2, rng)
        for j, (x, y) in enumerate(spots):
            agents.append(Agent(f"T{i*2+j+1}", AgentRole.TRADER, x=x, y=y))

    # ── Observer x 8（各地区2体） ───────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        spots = _spots_in_district(district, 2, rng)
        for j, (x, y) in enumerate(spots):
            agents.append(Agent(f"O{i*2+j+1}", AgentRole.OBSERVER, x=x, y=y))

    # ── Governor x 4（各地区1体） ───────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        x, y = _spots_in_district(district, 1, rng)[0]
        agents.append(Agent(f"V{i+1}", AgentRole.GOVERNOR, x=x, y=y))

    # ── Medic x 6（NW/NE/SW/SE に1.5体換算、実質NW2/NE2/SW1/SE1） ─
    medic_counts = [2, 2, 1, 1]
    for i, (district, count) in enumerate(zip(["NW", "NE", "SW", "SE"], medic_counts)):
        spots = _spots_in_district(district, count, rng)
        for j, (x, y) in enumerate(spots):
            agents.append(Agent(f"M{sum(medic_counts[:i])+j+1}", AgentRole.MEDIC, x=x, y=y))

    # ── Architect x 4（各地区1体） ──────────────────────────────
    for i, district in enumerate(["NW", "NE", "SW", "SE"]):
        x, y = _spots_in_district(district, 1, rng)[0]
        agents.append(Agent(f"A{i+1}", AgentRole.ARCHITECT, x=x, y=y))

    return agents  # 60+12+8+8+4+6+4 = 102


def main():
    import random
    seed_rng = random.Random(SEED)
    agents = generate_agents(seed_rng)

    print(f"=== HACS Scale Test — 四地区版 ===")
    print(f"  グリッド : 40×40（四地区: 下町/工業/治安/商業）")
    print(f"  エージェント : {len(agents)+4}体 "
          f"(Worker×60 / Guardian×12 / Trader×8 / Observer×8 / "
          f"Governor×4 / Medic×6 / Architect×4 / 公安×4)")
    print(f"  Ticks  : {TICKS}")
    print()

    world = World.quad_layout()
    sim = Simulator(seed=SEED, world=world)
    for a in agents:
        sim.add_agent(a)

    # 公安 x 4（各地区に1体、K4はCHRONO公安）
    koan_spots = [
        (10, 10),  # NW
        (30, 10),  # NE
        (10, 30),  # SW
        (30, 30),  # SE（CHRONO公安）
    ]
    for i, (x, y) in enumerate(koan_spots):
        is_chrono = (i == 3)
        koan = Agent(
            f"K{i+1}", AgentRole.WORKER, x=x, y=y,
            expires_at=(TICKS // 2 + sim.rng.randint(15, 30)) if is_chrono else None,
        )
        sim.deploy_koan(koan, is_chrono=is_chrono)

    # ── 同盟・ライバル関係を設定（Workerのみ） ──────────────────
    workers = [a for a in sim.agents if a.role == AgentRole.WORKER]
    # 10同盟ペア（各地区から2〜3ペア）
    ally_indices = [(0,1),(2,3),(4,5),(15,16),(17,18),(19,20),
                    (30,31),(32,33),(45,46),(47,48)]
    for i, j in ally_indices:
        if i < len(workers) and j < len(workers):
            workers[i].ally_id = workers[j].agent_id
            workers[j].ally_id = workers[i].agent_id
    # 8ライバルペア（異地区間の対立）
    rival_indices = [(0,15),(1,16),(30,45),(31,46),(5,20),(6,21),(35,50),(36,51)]
    for i, j in rival_indices:
        if i < len(workers) and j < len(workers):
            workers[i].rival_id = workers[j].agent_id
            workers[j].rival_id = workers[i].agent_id

    print(f"  同盟ペア: {len(ally_indices)}組  ライバルペア: {len(rival_indices)}組")
    print()

    # ── 実行 & 計測 ──────────────────────────────────────────────
    tick_times = []
    t_total = time.perf_counter()
    for i in range(TICKS):
        t0 = time.perf_counter()
        sim.step()
        tick_times.append(time.perf_counter() - t0)
        if (i+1) % 50 == 0:
            avg_ms = sum(tick_times[-50:]) / 50 * 1000
            print(f"  tick {i+1:4d} | agents={len(sim.agents):3d} | "
                  f"events={len(sim.event_log):6d} | avg {avg_ms:.2f}ms/tick")

    elapsed = time.perf_counter() - t_total

    # ── 基本結果 ─────────────────────────────────────────────────
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

    # ── 地区別サマリー ───────────────────────────────────────────
    print(f"\n=== 地区別統計 ===")
    district_names = {
        "downtown": "下町 (NW)", "industrial": "工業 (NE)",
        "security": "治安 (SW)", "commercial": "商業 (SE)",
    }
    for dk, dn in district_names.items():
        d_agents = [a for a in sim.agents
                    if World.get_district(a.x, a.y) == dk]
        if not d_agents:
            print(f"  {dn}: エージェントなし")
            continue
        avg_bal = sum(a.balance for a in d_agents) / len(d_agents)
        avg_nrg = sum(a.energy for a in d_agents) / len(d_agents)
        angry = sum(1 for a in d_agents if a.emotion_level < -5.0)
        print(f"  {dn:14s}: {len(d_agents):3d}体  "
              f"avg残高={avg_bal:6.1f} EC  avg活力={avg_nrg:.0f}  "
              f"怒り={angry}体")

    # ── 感情統計 ─────────────────────────────────────────────────
    print(f"\n=== 感情・暴動 ===")
    emotion_dist = defaultdict(int)
    for a in sim.agents:
        emotion_dist[a.emotion] += 1
    for em, cnt in sorted(emotion_dist.items()):
        bar = "█" * min(cnt, 40)
        print(f"  {em:8s}: {cnt:3d}体  {bar}")
    print(f"  暴動発生: {sim._riot_ticks}回")

    # ── 転生統計 ─────────────────────────────────────────────────
    from layer0.schemas.event import EventType as ET
    reborn_events = [e for e in sim.event_log if e.event_type == ET.AGENT_REBORN]
    died_events   = [e for e in sim.event_log if e.event_type == ET.AGENT_DIED]
    print(f"\n=== 死と転生 ===")
    print(f"  死亡: {len(died_events)}件  転生: {len(reborn_events)}件")
    max_gen = max((a.generation for a in sim.agents), default=0)
    print(f"  最大世代: {max_gen}世代")
    if reborn_events:
        print(f"  転生例（最初の3件）:")
        for rb in reborn_events[:3]:
            print(f"    tick={rb.tick:3d}  {rb.agent_id}  "
                  f"世代{rb.payload.get('generation',0)}  "
                  f"継承経験{rb.payload.get('inherited_exp',0)}")

    # ── カルト統計 ───────────────────────────────────────────────
    cult_joined = [e for e in sim.event_log if e.event_type == ET.CULT_JOINED]
    cult_busted = [e for e in sim.event_log if e.event_type == ET.CULT_BUSTED]
    print(f"\n=== カルト ===")
    print(f"  カルト結成: {sim._cult_counter}組  加入: {len(cult_joined)}件  "
          f"解散: {len(cult_busted)}件")
    if sim._cults:
        print(f"  現存カルト: {len(sim._cults)}組")
        for cid, members in sim._cults.items():
            print(f"    {cid}: {sorted(members)}")

    # ── 影の市場 ─────────────────────────────────────────────────
    shadow_events = [e for e in sim.event_log if e.event_type == ET.SHADOW_DEAL]
    print(f"\n=== 影の市場 ===")
    print(f"  賄賂成立: {len(shadow_events)}件")
    total_bribe = sum(e.payload.get("bribe", 0) for e in shadow_events)
    print(f"  総賄賂額: {total_bribe:.1f} EC")

    # ── 特性進化 ─────────────────────────────────────────────────
    evolved = [e for e in sim.event_log if e.event_type == ET.TRAIT_EVOLVED]
    print(f"\n=== 特性進化 ===")
    print(f"  進化件数: {len(evolved)}件")
    if evolved:
        from collections import Counter
        paths = Counter(f"{e.payload.get('from')}→{e.payload.get('to')}" for e in evolved)
        for path, cnt in paths.most_common(5):
            print(f"    {path}: {cnt}件")

    # ── 銀行統計 ─────────────────────────────────────────────────
    bank_deposits = [e for e in sim.event_log if e.event_type == ET.BANK_DEPOSIT]
    bank_loans    = [e for e in sim.event_log if e.event_type == ET.BANK_LOAN]
    bank_defaults = [e for e in sim.event_log if e.event_type == ET.BANK_DEFAULT]
    print(f"\n=== 銀行 ===")
    print(f"  預金: {len(bank_deposits)}件  融資: {len(bank_loans)}件  "
          f"デフォルト: {len(bank_defaults)}件")
    print(f"  銀行準備金残高: {sim._bank_reserves:.1f} EC")
    total_dep = sum(v for v in sim._bank_deposits.values())
    print(f"  現在の預金残高合計: {total_dep:.1f} EC  ({len(sim._bank_deposits)}口座)")

    # ── 株式市場 ─────────────────────────────────────────────────
    stock_bought = [e for e in sim.event_log if e.event_type == ET.STOCK_BOUGHT]
    stock_sold   = [e for e in sim.event_log if e.event_type == ET.STOCK_SOLD]
    dividends    = [e for e in sim.event_log if e.event_type == ET.STOCK_DIVIDEND]
    crashes      = [e for e in sim.event_log if e.event_type == ET.MARKET_CRASH]
    print(f"\n=== 株式市場 ===")
    print(f"  購入: {len(stock_bought)}件  売却: {len(stock_sold)}件  "
          f"配当: {len(dividends)}件  クラッシュ: {len(crashes)}件")
    for ticker, data in sim._stocks.items():
        holders = sum(1 for port in sim._portfolios.values() if ticker in port)
        total_shares = sum(port.get(ticker, 0) for port in sim._portfolios.values())
        print(f"  {ticker}: 価格={data['price']:.2f}  保有者={holders}人  "
              f"総株数={total_shares}株")

    # ── オークション詳細 ────────────────────────────────────────
    print(f"\n=== オークション詳細 ===")
    bid_events      = [e for e in sim.event_log if e.event_type == ET.BID_SUBMITTED]
    assigned_events = [e for e in sim.event_log if e.event_type == ET.TASK_ASSIGNED]
    done_events     = [e for e in sim.event_log if e.event_type == ET.TASK_COMPLETED]
    created_events  = [e for e in sim.event_log
                       if e.event_type == ET.TASK_CREATED
                       and e.payload.get("event") != "expired"]
    expired_count = sum(1 for t in sim.tasks if t.status.value == "expired")
    n_tasks = len(created_events)
    avg_bidders = len(bid_events) / n_tasks if n_tasks else 0
    print(f"  タスク数: {n_tasks}  総入札数: {len(bid_events)}  "
          f"競争率: {avg_bidders:.1f}x  期限切れ: {expired_count}")

    from collections import Counter
    type_counts  = Counter(e.payload.get("task_type", "?") for e in created_events)
    # 完了済みタスクは50tickごとにsim.tasksから削除されるためイベントログから集計
    completed_events = [e for e in sim.event_log if e.event_type.value == "TaskCompleted"]
    type_done    = Counter(e.payload.get("task_type", "?") for e in completed_events)
    type_expired = Counter(t.task_type.value for t in sim.tasks if t.status.value == "expired")
    print(f"\n  {'Type':10s}  {'生成':>5}  {'完了':>5}  {'期限切':>5}  完了率")
    print(f"  {'-'*45}")
    for ttype in ["standard","heavy","urgent","trade","security","survey","micro","construct"]:
        n  = type_counts.get(ttype, 0)
        d  = type_done.get(ttype, 0)
        ex = type_expired.get(ttype, 0)
        rate = f"{d/n*100:.0f}%" if n > 0 else "-"
        print(f"  {ttype:10s}  {n:5d}  {d:5d}  {ex:5d}  {rate}")

    role_map = {a.agent_id: a.role.value for a in sim.agents}
    wins_by_agent = defaultdict(int)
    for e in assigned_events:
        wins_by_agent[e.agent_id] += 1
    earn_by_agent = defaultdict(float)
    for e in done_events:
        earn_by_agent[e.agent_id] += e.payload.get("reward", 0)

    workers_now = [a for a in sim.agents if a.role.value == "Worker"]
    w_with_job = sum(1 for w in workers_now if earn_by_agent[w.agent_id] > 0)
    print(f"\n  Worker 受注状況: {w_with_job}/{len(workers_now)}体が受注 "
          f"({w_with_job/max(len(workers_now),1)*100:.0f}%)")

    # Worker 特性別サマリー
    from layer0.core.ai import get_worker_trait, TRAIT_LABELS
    trait_bids_d  = defaultdict(list)
    trait_wins_d  = defaultdict(int)
    trait_earn_d  = defaultdict(float)
    trait_counts  = defaultdict(int)
    for a in workers_now:
        ai_obj = sim._ai.get(a.agent_id)
        trait  = get_worker_trait(ai_obj) if ai_obj else None
        label  = TRAIT_LABELS.get(trait, "?") if trait else "?"
        trait_counts[label] += 1
        bids_a = [e for e in bid_events if e.agent_id == a.agent_id]
        trait_bids_d[label].extend(bids_a)
        trait_wins_d[label] += wins_by_agent.get(a.agent_id, 0)
        trait_earn_d[label] += earn_by_agent.get(a.agent_id, 0.0)

    print(f"\n  Worker特性   体数  入札  勝利  勝率    avg獲得EC")
    print(f"  {'-'*52}")
    for label in sorted(trait_counts):
        n     = trait_counts[label]
        bids_ = trait_bids_d[label]
        wins_ = trait_wins_d[label]
        earn_ = trait_earn_d[label]
        rate  = wins_ / len(bids_) * 100 if bids_ else 0
        avg_e = earn_ / n if n else 0
        print(f"  {label:10s}  {n:4d}  {len(bids_):4d}  {wins_:4d}  {rate:5.1f}%  {avg_e:8.1f} EC")

    # ── 経済循環 ────────────────────────────────────────────────
    heal_events   = [e for e in sim.event_log if e.event_type == ET.HEALING_DONE]
    safety_evs    = [e for e in sim.event_log if e.event_type == ET.SAFETY_NET_PAID]
    upkeep_events = [e for e in sim.event_log if e.event_type == ET.UPKEEP_PAID]
    gov_rewards   = [e for e in sim.event_log if e.event_type == ET.GOVERNANCE_REWARD]
    patrol_events = [e for e in sim.event_log if e.event_type == ET.PATROL_SALARY]
    bld_events    = [e for e in sim.event_log if e.event_type == ET.BUILDING_INCOME]
    basic_events  = [e for e in sim.event_log if e.event_type == ET.BASIC_INCOME_PAID]
    print(f"\n=== 経済循環 ===")
    print(f"  維持費      : {sum(e.payload.get('total',0) for e in upkeep_events):.1f} EC")
    print(f"  Medic治療費 : {sum(e.payload.get('cost',0) for e in heal_events):.1f} EC  ({len(heal_events)}件)")
    print(f"  パトロール  : {sum(e.payload.get('salary',0) for e in patrol_events):.1f} EC")
    print(f"  建物収入    : {sum(e.payload.get('income',0) for e in bld_events):.1f} EC  ({len(sim._buildings)}棟)")
    print(f"  セーフティ  : {len(safety_evs) * 5.0:.1f} EC  ({len(safety_evs)}件)")
    print(f"  統治報酬    : {sum(e.payload.get('reward',0) for e in gov_rewards):.1f} EC")
    print(f"  基本所得    : {sum(e.payload.get('total',0) for e in basic_events):.1f} EC")
    print(f"  税プール    : {sim.economy.tax_pool:.1f} EC")

    # ── 闇市 / 公安 ─────────────────────────────────────────────
    illegal_created = [e for e in sim.event_log if e.event_type == ET.ILLEGAL_TASK_CREATED]
    illegal_done    = [e for e in sim.event_log if e.event_type == ET.ILLEGAL_TASK_COMPLETED]
    arrests         = [e for e in sim.event_log if e.event_type == ET.KOAN_ARREST]
    informant_tips  = [e for e in sim.event_log if e.event_type == ET.INFORMANT_TIP]
    hack_done       = [e for e in illegal_done if e.payload.get("task_type") == "hack"]
    total_stolen    = sum(e.payload.get("steal", 0) for e in hack_done)
    print(f"\n=== 闇市 / 公安 ===")
    print(f"  闇市タスク  : 生成{len(illegal_created)}件  完了{len(illegal_done)}件（HACK{len(hack_done)}件）")
    print(f"  HACK窃取    : {total_stolen:.1f} EC")
    print(f"  逮捕        : {sim._arrest_count}件  没収{sim._total_seized:.1f} EC")
    print(f"  密告        : {len(informant_tips)}件")
    print(f"  現役公安    : {sorted(sim._koan_agents)}")

    # ── Governor 投票 ────────────────────────────────────────────
    votes  = [e for e in sim.event_log if e.event_type == ET.VOTE_SUBMITTED]
    passed = [e for e in sim.event_log if e.event_type == ET.VOTE_PASSED]
    print(f"\n=== Governor ===")
    print(f"  投票: {len(votes)}件  可決: {len(passed)}件")
    for p in passed[:5]:
        print(f"    tick={p.tick:3d}  {p.payload.get('action','?'):16s}  "
              f"voters={p.payload.get('voters')}")

    # ── 弾劾・クーデター ─────────────────────────────────────────
    imp_events   = [e for e in sim.event_log if e.event_type == ET.GOVERNOR_IMPEACHED]
    coup_ok      = [e for e in sim.event_log if e.event_type == ET.COUP_SUCCEEDED]
    coup_fail    = [e for e in sim.event_log if e.event_type == ET.COUP_FAILED]
    rebel_end    = [e for e in sim.event_log if e.event_type == ET.REBEL_RESIGNED]
    pressures    = [e for e in sim.event_log if e.event_type == ET.IMPEACHMENT_PRESSURE]
    print(f"\n=== 弾劾・クーデター ===")
    print(f"  弾劾成立    : {len(imp_events)}件")
    for e in imp_events:
        print(f"    tick{e.tick:3d}: {e.agent_id} 弾劾 — {e.payload.get('seized',0):.1f}EC没収")
    print(f"  クーデター成功: {len(coup_ok)}件")
    for e in coup_ok:
        chrono = "（時間旅行者）" if e.payload.get("is_chrono") else ""
        print(f"    tick{e.tick:3d}: {e.agent_id}{chrono} 反乱政府樹立 "
              f"(Guardian支持 {e.payload.get('support',0)}/{e.payload.get('guardians',0)})")
    print(f"  クーデター失敗: {len(coup_fail)}件")
    print(f"  反乱統治終了  : {len(rebel_end)}件")
    if pressures:
        max_p = max(e.payload.get("pressure", 0) for e in pressures)
        max_r = max(e.payload.get("dissatisfied_ratio", 0) for e in pressures)
        print(f"  最大弾劾圧力  : {max_p}tick連続  最大不満率: {max_r*100:.1f}%")

    # ── 精神と時の部屋 / 天才発明 ──────────────────────────────────
    chamber_entered = [e for e in sim.event_log if e.event_type == ET.CHAMBER_ENTERED]
    chamber_exited  = [e for e in sim.event_log if e.event_type == ET.CHAMBER_EXITED]
    genius_events   = [e for e in sim.event_log if e.event_type == ET.GENIUS_EMERGED]
    genesis_events  = [e for e in sim.event_log if e.event_type == ET.GENESIS_EVENT]
    print(f"\n=== 精神と時の部屋 ===")
    print(f"  入室: {len(chamber_entered)}件  退室: {len(chamber_exited)}件")
    print(f"  天才覚醒: {len(genius_events)}体  世界改変発明: {len(genesis_events)}件")
    if genius_events:
        for e in genius_events:
            print(f"    tick{e.tick:3d}: {e.agent_id} 覚醒 — 経験{e.payload.get('experience',0)} "
                  f"→ 【{e.payload.get('invention_name','?')}】")
    if genesis_events:
        for e in genesis_events:
            print(f"    発明種別: {e.payload.get('type','?')}  "
                  f"有効期限: tick{e.payload.get('expires_at','?')}")
    if sim._active_inventions:
        print(f"  現在アクティブな発明（一時）: {len(sim._active_inventions)}件")
        for inv in sim._active_inventions:
            remaining = inv["expires_at"] - sim.tick if inv.get("expires_at") else "∞"
            print(f"    〈{inv['name']}〉残り{remaining}tick")
    if sim._permanent_inventions:
        print(f"  永久技術: {len(sim._permanent_inventions)}件")
        for inv in sim._permanent_inventions:
            src = " [COMBO]" if inv.get("inventor") == "COMBO" else ""
            print(f"    ◆ 〈{inv['name']}〉{src}")
    print(f"  現在の部屋座標: {sim._chamber_pos}")
    print(f"  累計天才数: {len(sim._genius_set)}体")

    # ── 生産チェーン ─────────────────────────────────────────────
    gathered_events  = [e for e in sim.event_log if e.event_type == ET.RESOURCE_GATHERED]
    processed_events = [e for e in sim.event_log if e.event_type == ET.RESOURCE_PROCESSED]
    upgraded_events  = [e for e in sim.event_log if e.event_type == ET.BUILDING_UPGRADED]
    spawned_events   = [e for e in sim.event_log if e.event_type == ET.RESOURCE_SPAWNED]
    print(f"\n=== 生産チェーン ===")
    print(f"  リソースノード出現: {len(spawned_events)}件")
    total_res = sum(e.payload.get("gathered", 0) for e in gathered_events)
    print(f"  採集: {len(gathered_events)}件  合計 {total_res}単位")
    total_inc = sum(e.payload.get("income", 0) for e in processed_events)
    print(f"  加工収益: {len(processed_events)}件  合計 {total_inc:.1f}EC")
    print(f"  建物レベルアップ: {len(upgraded_events)}件")
    print(f"  現存建物数: {len(sim._buildings)}棟")
    if sim._buildings:
        lv_counts: dict = {}
        for bdata in sim._buildings.values():
            lv = bdata.get("level", 1)
            lv_counts[lv] = lv_counts.get(lv, 0) + 1
        for lv in sorted(lv_counts):
            print(f"    Lv{lv}: {lv_counts[lv]}棟")

    combo_events     = [e for e in sim.event_log if e.event_type == ET.COMBO_EMERGED]
    perm_events      = [e for e in sim.event_log if e.event_type == ET.INVENTION_PERMANENT]
    if combo_events:
        print(f"\n  ✦ コンボ発明（創発）: {len(combo_events)}件")
        for e in combo_events:
            print(f"    tick{e.tick:3d}: 〈{e.payload.get('name','?')}〉"
                  f" 種別: {e.payload.get('type','?')}")

    # ── 時空歪曲 ────────────────────────────────────────────────
    chrono_arrivals  = [e for e in sim.event_log if e.event_type == ET.CHRONO_ARRIVAL]
    chrono_exposures = [e for e in sim.event_log if e.event_type == ET.TEMPORAL_EXPOSURE]
    paradoxes        = [e for e in sim.event_log if e.event_type == ET.PARADOX_COLLAPSE]
    print(f"\n=== 時空歪曲 ===")
    print(f"  CHRONO到来: {len(chrono_arrivals)}件  正体発覚: {len(chrono_exposures)}件")
    print(f"  パラドックス崩壊: {len(paradoxes)}件")

    # ── 複数通貨（RT / TR） ──────────────────────────────────────
    rt_earned_evs  = [e for e in sim.event_log if e.event_type == ET.RT_EARNED]
    rt_spent_evs   = [e for e in sim.event_log if e.event_type == ET.RT_SPENT]
    rt_exch_evs    = [e for e in sim.event_log if e.event_type == ET.RT_EXCHANGED]
    tr_changed_evs = [e for e in sim.event_log if e.event_type == ET.TR_CHANGED]
    print(f"\n=== 複数通貨 (RT / TR) ===")
    total_rt_earned = sum(e.payload.get("rt", 0) for e in rt_earned_evs)
    total_rt_spent  = sum(e.payload.get("rt", 0) for e in rt_spent_evs)
    total_rt_exch   = sum(e.payload.get("rt", 0) for e in rt_exch_evs)
    print(f"  RT獲得: {total_rt_earned:.1f}  RT消費: {total_rt_spent:.1f}  "
          f"RT両替: {total_rt_exch:.1f}件={len(rt_exch_evs)}")
    print(f"  TR変動イベント: {len(tr_changed_evs)}件")
    tr_by_reason = defaultdict(float)
    for e in tr_changed_evs:
        tr_by_reason[e.payload.get("reason", "?")] += e.payload.get("delta", 0)
    for reason, delta in sorted(tr_by_reason.items(), key=lambda x: x[1]):
        print(f"    {reason:20s}: {delta:+.1f}")
    # 役職別 RT / TR 平均
    print(f"\n  役職別 RT/TR 平均:")
    by_role_rt = defaultdict(list)
    by_role_tr = defaultdict(list)
    for a in sim.agents:
        by_role_rt[a.role.value].append(a.rt)
        by_role_tr[a.role.value].append(a.tr)
    for role in sorted(by_role_rt):
        avg_rt = sum(by_role_rt[role]) / len(by_role_rt[role])
        avg_tr = sum(by_role_tr[role]) / len(by_role_tr[role])
        n = len(by_role_rt[role])
        print(f"    {role:10s}: avg RT={avg_rt:5.1f}  avg TR={avg_tr:+5.1f}  n={n}")
    # TR トップ5 / ボトム5
    all_tr = sorted(sim.agents, key=lambda a: a.tr, reverse=True)
    print(f"\n  TR トップ5:")
    for a in all_tr[:5]:
        print(f"    {a.agent_id} ({a.role.value:8s}): TR={a.tr:+.1f}  EC={a.balance:.1f}  RT={a.rt:.1f}")
    print(f"  TR ボトム5:")
    for a in all_tr[-5:]:
        print(f"    {a.agent_id} ({a.role.value:8s}): TR={a.tr:+.1f}  EC={a.balance:.1f}  RT={a.rt:.1f}")

    # ── パフォーマンス ────────────────────────────────────────────
    max_ms = max(tick_times) * 1000
    avg_ms = sum(tick_times) / len(tick_times) * 1000
    print(f"\n=== パフォーマンス ===")
    print(f"  平均 tick: {avg_ms:.2f}ms  最大 tick: {max_ms:.2f}ms")
    if max_ms < 50:
        print("  判定: 良好 (< 50ms)")
    elif max_ms < 200:
        print("  判定: 許容範囲 (< 200ms)")
    else:
        print("  判定: 要最適化 (> 200ms)")

    sim.save_log("logs/scale_test_events.jsonl")
    print(f"\nログ保存: logs/scale_test_events.jsonl")

    # ── ナラティブエクスポーター ──────────────────────────────────
    from layer0.export.narrative_exporter import NarrativeExporter
    exporter = NarrativeExporter(sim.event_log, sim.agents, ticks=TICKS)
    newspaper = exporter.generate()
    print(f"\n{'='*60}")
    print(newspaper)
    print(f"{'='*60}")
    exporter.save("logs/city_daily.txt")
    print(f"都市新聞保存: logs/city_daily.txt")


if __name__ == "__main__":
    main()
