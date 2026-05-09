"""
NarrativeExporter: シミュレーションのイベントログから「都市新聞」を自動生成する。

使い方:
    exporter = NarrativeExporter(sim.event_log, sim.agents, ticks=200)
    newspaper = exporter.generate()
    print(newspaper)
    exporter.save("logs/city_daily.txt")
"""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from layer0.schemas.event import Event, EventType


class NarrativeExporter:
    def __init__(self, event_log: List[Event], agents: list, ticks: int = 200):
        self.log = event_log
        self.agents = {a.agent_id: a for a in agents}
        self.ticks = ticks
        self._by_type: Dict[str, List[Event]] = defaultdict(list)
        for e in event_log:
            self._by_type[e.event_type].append(e)

    # ── メイン ────────────────────────────────────────────────────────────
    def generate(self) -> str:
        sections = [
            self._header(),
            self._section_breaking(),
            self._section_politics(),
            self._section_crime(),
            self._section_temporal(),
            self._section_economy(),
            self._section_currency(),
            self._section_society(),
            self._section_stocks(),
            self._section_production(),
            self._section_genius(),
            self._section_obituary(),
            self._footer(),
        ]
        return "\n".join(s for s in sections if s)

    def save(self, path: str) -> None:
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.generate())

    # ── ヘッダー ──────────────────────────────────────────────────────────
    def _header(self) -> str:
        total_events = len(self.log)
        width = 60
        border = "━" * width
        return (
            f"{border}\n"
            f"  HACS CITY DAILY  ―  全{self.ticks}tick号外\n"
            f"  総イベント数: {total_events:,}件   発行: HACS観察局\n"
            f"{border}"
        )

    def _footer(self) -> str:
        return "━" * 60 + "\n  以上、本号終わり。\n" + "━" * 60

    def _section_header(self, title: str) -> str:
        return f"\n【{title}】"

    # ── 速報面 ────────────────────────────────────────────────────────────
    def _section_breaking(self) -> str:
        lines = [self._section_header("速報")]
        coups   = self._by_type.get(EventType.COUP_SUCCEEDED, [])
        failed  = self._by_type.get(EventType.COUP_FAILED, [])
        imps    = self._by_type.get(EventType.GOVERNOR_IMPEACHED, [])
        riots   = self._by_type.get(EventType.EMOTION_RIOT, [])
        crashes = self._by_type.get(EventType.MARKET_CRASH, [])

        if coups:
            e = coups[0]
            chrono_tag = "（時間旅行者！）" if e.payload.get("is_chrono") else ""
            lines.append(
                f"  ★ tick{e.tick:3d}: クーデター成功 — {e.agent_id}{chrono_tag}が反乱政府を樹立\n"
                f"           Guardian {e.payload.get('support',0)}/{e.payload.get('guardians',0)}体の支持を獲得"
            )
        if imps:
            for e in imps:
                lines.append(
                    f"  ★ tick{e.tick:3d}: Governor {e.agent_id} 弾劾 — "
                    f"{e.payload.get('seized', 0):.1f}EC没収、権力空白{e.payload.get('power_vacuum_until', 0)-e.tick}tick"
                )
        if failed:
            for e in failed:
                chrono_tag = "（未来人）" if e.payload.get("is_chrono") else ""
                lines.append(
                    f"  ✗ tick{e.tick:3d}: クーデター失敗 — {e.agent_id}{chrono_tag}が逮捕\n"
                    f"           Guardian 支持 {e.payload.get('support',0)}/{e.payload.get('guardians',0)}体、経験値{e.payload.get('experience',0)}"
                )
        if riots:
            lines.append(f"  ⚡ 暴動 {len(riots)}回発生（建物破壊・略奪あり）")
        if crashes:
            tickers = [e.payload.get('ticker','?') for e in crashes]
            lines.append(f"  ▼ 株式市場クラッシュ {len(crashes)}回: {', '.join(tickers)}")
        if not (coups or failed or imps or riots or crashes):
            lines.append("  （今号は平穏。記事なし）")
        return "\n".join(lines)

    # ── 政治面 ────────────────────────────────────────────────────────────
    def _section_politics(self) -> str:
        lines = [self._section_header("政治")]
        passed  = self._by_type.get(EventType.VOTE_PASSED, [])
        rebels  = self._by_type.get(EventType.REBEL_RESIGNED, [])
        pressures = self._by_type.get(EventType.IMPEACHMENT_PRESSURE, [])

        if passed:
            policy_summary: Dict[str, list] = defaultdict(list)
            for e in passed:
                policy_summary[e.payload.get("action", "?")].append(e.tick)
            for action, ticks_list in policy_summary.items():
                lines.append(f"  政策「{action}」可決 {len(ticks_list)}回 "
                              f"(tick {', '.join(str(t) for t in ticks_list[:3])}{'...' if len(ticks_list)>3 else ''})")
        else:
            lines.append("  政策可決: 0件")

        if pressures:
            max_pressure = max(e.payload.get("pressure", 0) for e in pressures)
            lines.append(f"  弾劾圧力: 最大{max_pressure}tick連続（閾値3）")
            max_ratio = max(e.payload.get("dissatisfied_ratio", 0) for e in pressures)
            lines.append(f"  Worker最大不満率: {max_ratio*100:.1f}%")

        if rebels:
            for e in rebels:
                lines.append(
                    f"  反乱政府 {e.agent_id} が任期{e.payload.get('reigned_ticks',0)}tick終了 → Worker復帰\n"
                    f"  退任時残高: {e.payload.get('balance', 0):.1f}EC"
                )
        return "\n".join(lines)

    # ── 事件面 ────────────────────────────────────────────────────────────
    def _section_crime(self) -> str:
        lines = [self._section_header("事件・治安")]
        arrests  = self._by_type.get(EventType.KOAN_ARREST, [])
        hacks    = [e for e in self._by_type.get(EventType.ILLEGAL_TASK_COMPLETED, [])
                    if e.payload.get("task_type") == "hack"]
        smuggles = [e for e in self._by_type.get(EventType.ILLEGAL_TASK_COMPLETED, [])
                    if e.payload.get("task_type") == "smuggle"]
        shadows  = self._by_type.get(EventType.SHADOW_DEAL, [])
        tips     = self._by_type.get(EventType.INFORMANT_TIP, [])
        coup_fails = self._by_type.get(EventType.COUP_FAILED, [])

        if arrests:
            total_seized = sum(e.payload.get("seized", 0) for e in arrests)
            lines.append(f"  公安逮捕 {len(arrests)}件 / 没収総額 {total_seized:.1f}EC")
            for e in arrests[:3]:
                lines.append(
                    f"    tick{e.tick:3d}: {e.agent_id} 逮捕 — "
                    f"{e.payload.get('seized', 0):.1f}EC没収 / {e.payload.get('freeze_ticks',15)}tick停止"
                )
            if len(arrests) > 3:
                lines.append(f"    ...他 {len(arrests)-3}件")
        else:
            lines.append("  公安逮捕: 0件")

        if hacks:
            total_steal = sum(e.payload.get("steal", 0) for e in hacks)
            lines.append(f"  HACKハッキング: {len(hacks)}件 / 窃取総額 {total_steal:.1f}EC")
        if smuggles:
            lines.append(f"  SMUGGLE密輸: {len(smuggles)}件完了")
        if shadows:
            total_bribe = sum(e.payload.get("bribe", 0) for e in shadows)
            lines.append(f"  影の市場（賄賂）: {len(shadows)}件 / 総額 {total_bribe:.1f}EC")
        if tips:
            lines.append(f"  Observer密告: {len(tips)}件")
        if coup_fails:
            lines.append(f"  クーデター未遂による逮捕: {len(coup_fails)}件")
        return "\n".join(lines)

    # ── 時空面 ────────────────────────────────────────────────────────────
    def _section_temporal(self) -> str:
        lines = [self._section_header("時空・未来人")]
        arrivals   = self._by_type.get(EventType.CHRONO_ARRIVAL, [])
        departures = self._by_type.get(EventType.CHRONO_DEPARTURE, [])
        exposures  = self._by_type.get(EventType.TEMPORAL_EXPOSURE, [])
        paradoxes  = self._by_type.get(EventType.PARADOX_COLLAPSE, [])
        loans      = self._by_type.get(EventType.TEMPORAL_LOAN, [])

        if arrivals:
            lines.append(f"  CHRONO到来: {len(arrivals)}体")
            for e in arrivals:
                lines.append(
                    f"    tick{e.tick:3d}: {e.agent_id} 出現 — "
                    f"残高{e.payload.get('balance',0):.0f}EC / 経験{e.payload.get('experience',0)}"
                )
        if exposures:
            lines.append(f"  正体発覚（TEMPORAL_EXPOSURE）: {len(exposures)}件")
            for e in exposures:
                count = len(e.payload.get("close_agents", []))
                lines.append(
                    f"    tick{e.tick:3d}: {e.agent_id} 発覚 — "
                    f"半径5の{count}体に知識爆発 / 残高60%放出"
                )
        if departures:
            total_legacy = sum(e.payload.get("legacy_share", 0) * len(e.payload.get("recipients", []))
                               for e in departures)
            lines.append(f"  CHRONO消滅: {len(departures)}体 / 時空遺産総計 {total_legacy:.1f}EC")
        if paradoxes:
            lines.append(f"  パラドックス崩壊: {len(paradoxes)}件")
        if loans:
            lines.append(f"  時間ローン借入: {len(loans)}件")
        if not (arrivals or departures or exposures or paradoxes):
            lines.append("  （今号は時空の異変なし）")
        return "\n".join(lines)

    # ── 経済面 ────────────────────────────────────────────────────────────
    def _section_economy(self) -> str:
        lines = [self._section_header("経済")]
        completions = self._by_type.get(EventType.TASK_COMPLETED, [])
        defaults    = self._by_type.get(EventType.BANK_DEFAULT, [])
        loans       = self._by_type.get(EventType.BANK_LOAN, [])
        deposits    = self._by_type.get(EventType.BANK_DEPOSIT, [])
        basic       = self._by_type.get(EventType.BASIC_INCOME_PAID, [])
        upkeep      = self._by_type.get(EventType.UPKEEP_PAID, [])

        if completions:
            total_reward = sum(e.payload.get("reward", 0) for e in completions)
            lines.append(f"  タスク完了: {len(completions)}件 / 総報酬 {total_reward:.1f}EC")
            # トップ3の大型タスク
            big = sorted(completions, key=lambda e: e.payload.get("reward", 0), reverse=True)[:3]
            for e in big:
                lines.append(
                    f"    tick{e.tick:3d}: {e.agent_id} が {e.payload.get('reward',0):.1f}EC 獲得"
                )

        if deposits:
            lines.append(f"  銀行預金: {len(deposits)}件")
        if loans:
            lines.append(f"  銀行融資: {len(loans)}件")
        if defaults:
            lines.append(f"  銀行デフォルト: {len(defaults)}件 ⚠")
        if basic:
            total_share = sum(e.payload.get("share", 0) for e in basic)
            lines.append(f"  基本所得分配: {len(basic)}回 / 累計 {total_share:.1f}EC")
        if upkeep:
            lines.append(f"  維持費徴収: {len(upkeep)}回")
        return "\n".join(lines)

    # ── 社会面 ────────────────────────────────────────────────────────────
    def _section_society(self) -> str:
        lines = [self._section_header("社会・文化")]
        evolutions = self._by_type.get(EventType.TRAIT_EVOLVED, [])
        cult_joins = self._by_type.get(EventType.CULT_JOINED, [])
        cult_busts = self._by_type.get(EventType.CULT_BUSTED, [])
        healing    = self._by_type.get(EventType.HEALING_DONE, [])
        buildings  = [e for e in self._by_type.get(EventType.BUILDING_INCOME, [])
                      if e.payload.get("event") == "built"]

        if evolutions:
            evo_summary: Dict[str, int] = defaultdict(int)
            for e in evolutions:
                key = f"{e.payload.get('from','?')}→{e.payload.get('to','?')}"
                evo_summary[key] += 1
            lines.append(f"  特性進化: 計{len(evolutions)}件")
            for path, cnt in sorted(evo_summary.items(), key=lambda x: -x[1])[:4]:
                lines.append(f"    {path}: {cnt}件")

        if cult_joins:
            cult_ids = {e.payload.get("cult_id") for e in cult_joins}
            lines.append(f"  カルト: {len(cult_ids)}組 / 加入{len(cult_joins)}件")
            if cult_busts:
                lines.append(f"    解散: {len(cult_busts)}件（公安により摘発）")

        if healing:
            total_heal = sum(e.payload.get("heal", 0) for e in healing)
            lines.append(f"  Medic治療: {len(healing)}件 / 合計 {total_heal:.0f}エネルギー回復")

        if buildings:
            lines.append(f"  建物建設: {len(buildings)}棟")
        return "\n".join(lines)

    # ── 株式面 ────────────────────────────────────────────────────────────
    def _section_stocks(self) -> str:
        lines = [self._section_header("株式市場")]
        buys      = self._by_type.get(EventType.STOCK_BOUGHT, [])
        sells     = self._by_type.get(EventType.STOCK_SOLD, [])
        dividends = self._by_type.get(EventType.STOCK_DIVIDEND, [])
        crashes   = self._by_type.get(EventType.MARKET_CRASH, [])

        if buys or sells or dividends:
            lines.append(f"  購入 {len(buys)}件 / 売却 {len(sells)}件 / 配当 {len(dividends)}件")
            # 銘柄別統計
            ticker_buy: Dict[str, int] = defaultdict(int)
            for e in buys:
                ticker_buy[e.payload.get("ticker", "?")] += e.payload.get("shares", 0)
            for ticker, shares in sorted(ticker_buy.items()):
                lines.append(f"    {ticker}: {shares}株購入")
            if dividends:
                total_div = sum(e.payload.get("dividend", 0) for e in dividends)
                lines.append(f"  配当総額: {total_div:.2f}EC")
        if crashes:
            for e in crashes:
                lines.append(f"  ⚠ tick{e.tick:3d}: {e.payload.get('ticker','?')}クラッシュ "
                              f"(価格{e.payload.get('price',0):.2f}EC → 強制リセット)")
        if not (buys or sells or dividends or crashes):
            lines.append("  （株式取引なし）")
        return "\n".join(lines)

    # ── 複数通貨面（RT / TR） ────────────────────────────────────────────
    def _section_currency(self) -> str:
        lines = [self._section_header("複数通貨経済 — RT・TR レポート")]
        rt_earned  = self._by_type.get(EventType.RT_EARNED, [])
        rt_spent   = self._by_type.get(EventType.RT_SPENT, [])
        rt_exch    = self._by_type.get(EventType.RT_EXCHANGED, [])
        tr_changed = self._by_type.get(EventType.TR_CHANGED, [])

        if rt_earned:
            total = sum(e.payload.get("rt", 0) for e in rt_earned)
            lines.append(f"  RT獲得: {len(rt_earned)}件 / 合計 {total:.1f} RT")
        if rt_spent:
            total = sum(e.payload.get("rt", 0) for e in rt_spent)
            lines.append(f"  RT消費: {len(rt_spent)}件 / 合計 {total:.1f} RT")
        if rt_exch:
            peer_trades = [e for e in rt_exch if e.payload.get("direction") == "Worker→Trader→EC"]
            total_rt_traded = sum(e.payload.get("rt", 0) for e in peer_trades)
            lines.append(f"  RT両替仲介: {len(peer_trades)}件 / 合計 {total_rt_traded:.1f} RT")
        if tr_changed:
            pos = sum(e.payload.get("delta", 0) for e in tr_changed if e.payload.get("delta", 0) > 0)
            neg = sum(e.payload.get("delta", 0) for e in tr_changed if e.payload.get("delta", 0) < 0)
            lines.append(f"  TR変動: +{pos:.1f} / {neg:.1f}  （{len(tr_changed)}件）")
            from collections import Counter
            reasons = Counter(e.payload.get("reason", "?") for e in tr_changed)
            for reason, cnt in reasons.most_common(5):
                lines.append(f"    {reason}: {cnt}件")

        if not (rt_earned or rt_exch or tr_changed):
            lines.append("  （今号は通貨活動なし）")
        return "\n".join(lines)

    # ── 生産チェーン面 ────────────────────────────────────────────────────
    def _section_production(self) -> str:
        lines = [self._section_header("生産チェーン / 都市成長")]
        gathered  = self._by_type.get(EventType.RESOURCE_GATHERED, [])
        processed = self._by_type.get(EventType.RESOURCE_PROCESSED, [])
        upgraded  = self._by_type.get(EventType.BUILDING_UPGRADED, [])
        spawned   = self._by_type.get(EventType.RESOURCE_SPAWNED, [])

        if spawned:
            lines.append(f"  リソースノード出現: {len(spawned)}件")
        if gathered:
            total_res = sum(e.payload.get("gathered", 0) for e in gathered)
            lines.append(f"  採集: {len(gathered)}件 / 合計 {total_res}単位")
        if processed:
            total_inc = sum(e.payload.get("income", 0) for e in processed)
            lines.append(f"  加工・売却: {len(processed)}件 / 合計収益 {total_inc:.1f}EC")
        if upgraded:
            lines.append(f"  建物レベルアップ: {len(upgraded)}件")
            for e in upgraded:
                pos = f"({e.payload.get('x','?')},{e.payload.get('y','?')})"
                lv  = e.payload.get("level", "?")
                lines.append(f"    tick{e.tick:3d}: 建物{pos} → Lv{lv}")

        if not (gathered or processed or upgraded):
            lines.append("  （今号は生産活動なし）")
        return "\n".join(lines)

    # ── 天才・発明面 ──────────────────────────────────────────────────────
    def _section_genius(self) -> str:
        lines = [self._section_header("精神と時の部屋 / 天才発明 / 永久技術")]
        enters     = self._by_type.get(EventType.CHAMBER_ENTERED, [])
        exits      = self._by_type.get(EventType.CHAMBER_EXITED, [])
        geniuses   = self._by_type.get(EventType.GENIUS_EMERGED, [])
        genesis    = self._by_type.get(EventType.GENESIS_EVENT, [])
        moves      = self._by_type.get(EventType.CHAMBER_MOVED, [])
        permanents = self._by_type.get(EventType.INVENTION_PERMANENT, [])
        combos     = self._by_type.get(EventType.COMBO_EMERGED, [])

        if moves:
            lines.append(f"  精神と時の部屋: {len(moves)}回移動")
        if enters:
            lines.append(f"  入室者: {len(enters)}体")
        if exits:
            avg_exp = (sum(e.payload.get("exp_gained", 0) for e in exits) / len(exits)) if exits else 0
            lines.append(f"  退室者: {len(exits)}体 / 平均経験値獲得 {avg_exp:.0f}")

        if geniuses:
            lines.append(f"\n  ★ 天才覚醒: {len(geniuses)}体")
            for e in geniuses:
                inv_name = e.payload.get("invention_name", "不明")
                inv_type = e.payload.get("invention_type", "?")
                exp      = e.payload.get("experience", 0)
                perm     = e.payload.get("permanent", False)
                perm_tag = "【永久技術】" if perm else f"（有効期限: tick{e.payload.get('expires_at', '?')}）"
                lines.append(f"    tick{e.tick:3d}: {e.agent_id} 覚醒（経験値{exp}）{perm_tag}")
                lines.append(f"           発明: 【{inv_name}】 種別: {inv_type}")

        if permanents:
            lines.append(f"\n  ◆ 永久技術として刻まれた発明: {len(permanents)}件")
            for e in permanents:
                lines.append(f"    tick{e.tick:3d}: 〈{e.payload.get('invention_name', '?')}〉 永久技術化")

        if genesis:
            lines.append(f"\n  世界改変発明（一時）: {len(genesis)}件")
            for e in genesis:
                desc = e.payload.get("description", "")
                exp_tick = e.payload.get("expires_at", "?")
                lines.append(f"    〈{e.payload.get('name', '?')}〉 有効期限: tick{exp_tick}")
                if desc:
                    lines.append(f"     {desc}")

        if combos:
            lines.append(f"\n  ✦ コンボ発明（予期せぬ創発）: {len(combos)}件")
            for e in combos:
                sources = ", ".join(e.payload.get("source_inventions", []))
                lines.append(f"    tick{e.tick:3d}: 〈{e.payload.get('name', '?')}〉")
                lines.append(f"           起源技術: {sources}")
                desc = e.payload.get("description", "")
                if desc:
                    lines.append(f"           {desc[:60]}…")

        if not (enters or geniuses or permanents or combos):
            lines.append("  （今号は部屋への入室なし）")
        return "\n".join(lines)

    # ── 訃報面 ────────────────────────────────────────────────────────────
    def _section_obituary(self) -> str:
        lines = [self._section_header("訃報・転生")]
        deaths  = self._by_type.get(EventType.AGENT_DIED, [])
        reborns = self._by_type.get(EventType.AGENT_REBORN, [])

        if not deaths:
            lines.append("  （今号は死亡者なし。全エージェント生存中）")
            return "\n".join(lines)

        for e in deaths:
            gen = e.payload.get("generation", 0)
            bal = e.payload.get("balance_left", 0)
            exp = e.payload.get("experience", 0)
            lines.append(
                f"  tick{e.tick:3d}: {e.agent_id} 死亡 "
                f"（第{gen}世代 / 経験{exp} / 遺産{bal:.1f}EC）"
            )
        if reborns:
            lines.append(f"  転生: {len(reborns)}体 （新世代として復活）")
        return "\n".join(lines)
