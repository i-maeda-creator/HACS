# HACS — Home Autonomous Civilization System

自律型エージェントが経済・安全・統治を自己管理する都市シミュレーション。

> **Safety > Stability > Economy > Efficiency** — 設計優先順位

---

## アーキテクチャ

```
Layer3  City OS        ← AlertSystem / CommandDispatcher / PolicyGate
   ↑
Layer2  MQTT Event Bus ← Mosquitto broker / paho-mqtt / WebSocket
   ↑
Layer1  Physical       ← (Raspberry Pi / ESP32 — 未実装)
   ↑
Layer0  Simulator      ← World / Agent / Task / Economy / Policy / Safety / AI
```

すべてのデータはイベントとして流れる **Event-Driven Architecture**。  
Layer0 が生成したイベントを MQTT が中継し、Layer3 が監視・制御する。

---

## 7つの役職

| 役職 | 色 | 役割 | 収入源 |
|------|----|------|--------|
| **Worker** | 🟢 緑 | タスクをオークション入札で獲得。5種の性格特性が戦略を決定 | タスク報酬 |
| **Guardian** | 🔴 赤 | 5点ルートを永続パトロール。治安タスクにも入札 | パトロール給与 + 治安タスク |
| **Trader** | 🟠 橙 | 市場平均をEMAで学習し高マージンタスクを選別。記憶売買の仲介も担う | タスク報酬 + 記憶マージン |
| **Observer** | 🔵 青 | 4象限を分担カバー。調査タスクに入札 | パトロール給与 + 調査タスク |
| **Governor** | 🟣 紫 | 25tick毎にKPI分析→政策提案。税収の配当で収入を得る | 税配当（KPI連動） |
| **Medic** | ⚪ 白 | 低エネルギーのエージェントに接近し治療サービスを提供 | 治療費（EC） |
| **Architect** | 🟡 黄 | 建設タスク専門。完成した建物が毎tick不労所得を生む | 建設報酬 + 建物収入 |

### Worker 11種の性格特性

| 特性 | 戦略 |
|------|------|
| **HUSTLER** | 高熱意・距離を気にせず何でも入札 |
| **SAVER** | 近場・MICROタスク専門。エネルギー温存重視 |
| **SPECIALIST** | HEAVYタスクに超積極的、それ以外は消極的 |
| **EXPLORER** | 距離ペナルティほぼゼロ。広域をカバー |
| **OPPORTUNIST** | 競合の少ないセクターを狙い撃ち |
| **GAMBLER** | 博打師：120〜180%の大博打入札 |
| **NIHILIST** | 虚無主義者：15%確率で意図的入札拒否 |
| **CONFORMIST** | 同調者：直前の推定落札額に追随 |
| **REBEL** | 反逆者：報酬20EC超を「搾取」として拒否 |
| **DRIFTER** | 漂流者：どこでもそこそこ、専門なし |
| **CHRONO** | 🕰️ 時間旅行者：未来から来た存在。完璧な入札で登場・期限付き消滅 |

### 全役職に3種の性格

| 役職 | 性格バリエーション |
|------|-----------------|
| Guardian | STOIC / AGGRESSIVE / VIGILANT |
| Trader | ANALYST / SHARK / SPECULATOR |
| Observer | SYSTEMATIC / VISIONARY / INFORMANT |
| Governor | BALANCED / POPULIST / CONSERVATIVE |
| Medic | PROFESSIONAL / MERCENARY / SELFLESS |
| Architect | BUILDER / MONOPOLIST / URBANIST |

---

## ロボット固有メカニクス

### Quantum Auction（量子入札）
通常の「最高入札者が確実に勝つ」オークションとは異なる。

```
P(当選) ∝ 入札額
```

高い入札は有利だが確定ではない。低い入札の SAVER や OPPORTUNIST が確率的に受注できる。**不確実性が戦略に組み込まれる。**

### Memory Market（記憶売買）
ロボットだけが持つ「経験の外部化」メカニクス。

```
高経験 Worker → Trader 買取 → 新人 Worker へ転売
```

- 高経験 Worker の `experience` 値を 0.4 EC/点 で Trader が買い取る
- Trader は 1.6倍 のマージンで新人 Worker へ転売
- 記憶を買った Worker は **8tick 間、入札に +1.5 EC ボーナス**

### 累進資本課税
Architect が建物を増やすほど課税率が上昇。資本の独占を抑制する。

| 建物数 | 追加税率 |
|--------|---------|
| 1棟目 | 0% |
| 2棟目 | +15% |
| 3棟目 | +30% |
| 4棟目以降 | +45%（上限）|

余剰税は `tax_pool` に還元 → Governor が `basic_income` で全員に再分配。

### 建物減価償却
建物は **50tick で自然崩壊**。Architect は新しい建設タスクを取り続けないと収入が途絶える。建物セルを通過したエージェントはエネルギーを +0.3 回収（インフラ恩恵）。

### 時空歪曲メカニクス

| メカニクス | 説明 |
|-----------|------|
| **Temporal Loan** | 残高低下時に +15 EC 借入。15tick 後に 22 EC 返済義務 |
| **Paradox Collapse** | 返済不能 → 残高ランダムリセット + 半径3の全員に ±6 EC ゆらぎ |
| **Causality Loop** | タスク完了の10%確率で同種タスクが「過去から召喚」される |
| **CHRONO Arrival** | 40〜80tick 毎に時間旅行者が登場。高経験値・高残高で出現 |
| **CHRONO Departure** | 期限切れで消滅。残高40%を近隣3体に「時空遺産」として残す |

### CHRONO 正体発覚システム

時間旅行者は**正体を悟られてはならない**。疑惑度が 15 を超えると正体発覚。

```
疑惑度上昇:
  + 2.5 落札するたびに（完璧すぎる入札が怪しまれる）
  + 2.5/tick AGGRESSIVE/VIGILANT Guardian が半径3以内
  + 0.8/tick 通常Guardian が半径3以内
  - 0.3/tick 自然減衰（目立たなければ疑惑は薄れる）

疑惑 > 8:   カモフラージュ発動 → 入札を意図的に 50〜80% まで下げる
疑惑 ≥ 15:  TEMPORAL_EXPOSURE！
  → 知識爆発（周囲に experience × 0.5 EC を分配）
  → 残高60%を半径5以内に均等配布
  → 大規模パラドックス波（半径3: ±15 EC、半径4-5: ±5 EC）
  → エージェント即時消滅
```

**実際に確認された挙動（67agent / 200tick）:**
- CHR1: tick 47 出現 → tick 63 正体発覚（16tick で捕捉）
- CHR2: tick 123 出現 → tick 138 正体発覚（15tick で捕捉）  
- CHR3: tick 192 出現 → 200tick まで生存（唯一の生還者）

---

## 経済設計

```
タスク報酬
  └─ 5% 税収
       ├─ 30% → Governor（KPIスコア×0.4〜1.3倍で調整）
       └─ 70% → tax_pool
                   ├─ Guardian/Observer パトロール給与
                   ├─ Architect 建物収入
                   ├─ セーフティネット（残高15EC以下に5EC補助）
                   └─ basic_income（Governor提案で全員均等分配）

全エージェント: 維持費 0.2 EC/tick（ECシンク）
```

### Governor の政策提案（25tick毎）

| 条件 | 提案 | 効果 |
|------|------|------|
| 完了率 < 60% | `reward_boost` | タスク報酬倍率 +12% |
| Worker 稼働率 < 50% | `worker_support` | Worker 入札ボーナス +1.5 EC |
| 税プール > 400 EC かつ Gini > 0.15 | `basic_income` | 全員均等分配 |
| Gini > 0.30 かつ KPI > 0.6 | `tax_increase` | 税率 +2% |

全 Governor が同一提案 → コンセンサスボーナス 1.5倍。  
Governor の収入は KPI スコア（効率性 + 平等性）に連動 — **良い統治が自分の収入を増やす。**

---

## セットアップ

```bash
pip install pydantic paho-mqtt pillow edge-tts
```

```bash
# Mosquitto MQTT broker (Windows)
# https://mosquitto.org/download/
```

`mosquitto.conf`:
```
listener 1883
listener 9001
protocol websockets
allow_anonymous true
```

---

## 実行方法

### スケールテスト（67体 / 200tick）
```bash
python layer0/main_scale_test.py
```

### リアルタイムライブビューア
```bash
# ターミナル1: HTTPサーバー
python -m http.server 8080 --directory web

# ターミナル2: シミュレーション起動
python layer2/run_live.py

# ブラウザで開く → http://localhost:8080/live_viewer.html
```

### テスト（132テスト）
```bash
python -m pytest tests/ -v
```

### Event Sourcing — イベントログから状態を再構築
```python
from layer0.core.event_sourcing import EventReplayer

replayer = EventReplayer(agents)
replayer.apply_all(sim.event_log)
state = replayer.state_at(tick=50)   # 任意 tick の状態
final = replayer.final_state()
```

---

## ファイル構成

```
hacs/
├── layer0/
│   ├── core/
│   │   ├── world.py          # 20×20 グリッドマップ・充電ステーション
│   │   ├── agent.py          # Agent（experience / memory_boost 含む）
│   │   ├── task.py           # Task / Bid / Quantum Auction
│   │   ├── economy.py        # 税プール・報酬・セーフティネット
│   │   ├── policy.py         # PolicyEngine（制約・目標）
│   │   ├── safety.py         # SafetyGate（夜間制限・緊急停止）
│   │   ├── ai.py             # 7役職AI + Worker 11特性 + 全役職3種性格
│   │   └── event_sourcing.py # EventReplayer（イベントから状態再構築）
│   ├── engine/
│   │   └── simulator.py      # メインシミュレーター
│   └── schemas/
│       ├── event.py          # Event / EventType（20種以上）
│       ├── command.py        # Command / CommandAction
│       └── state.py          # StateSnapshot
├── layer2/
│   ├── event_bus.py          # MQTT Pub/Sub ラッパー
│   └── run_live.py           # リアルタイム配信（0.2s/tick）
├── layer3/
│   ├── city_os.py            # CityOS 統合エントリポイント
│   ├── alert_system.py       # AlertSystem（INFO/WARNING/CRITICAL）
│   ├── state_manager.py      # StateManager（読み取り専用 API）
│   ├── command_dispatcher.py # CommandDispatcher + PolicyGate
│   └── policy_gate.py        # PolicyGate（壁・緊急時チェック）
├── tests/                    # pytest 132テスト
└── web/
    ├── live_viewer.html       # Canvas 2D リアルタイムビューア
    └── live_dashboard.html    # MQTT KPI ダッシュボード
```

---

## パフォーマンス（67体 / 200tick）

| 指標 | 値 |
|------|-----|
| 平均 tick 速度 | ~9ms/tick |
| 最大 tick 時間 | ~38ms（< 50ms 合格）|
| 総イベント数 | ~11,700件 |
| 効率性スコア | 0.974 |
| 平等性スコア | 0.776 |
| pytest | **132テスト全通過** |

---

## 進捗ログ

<!-- AUTO-UPDATED -->
**最終更新: 2026-05-07**

### 実装済み

**Layer0 コア**
- [x] World / Agent / Task / Economy / Policy / Safety
- [x] 7役職 AI（Worker / Guardian / Trader / Observer / Governor / Medic / Architect）
- [x] Worker 5特性（HUSTLER / SAVER / SPECIALIST / EXPLORER / OPPORTUNIST）
- [x] 8タスクタイプ（standard / heavy / urgent / trade / security / survey / micro / construct）
- [x] Event Sourcing（EventReplayer — イベントログのみから状態完全再構築）
- [x] pytest 132テスト全通過

**ロボット固有メカニクス**
- [x] Quantum Auction — P(当選) ∝ 入札額
- [x] Memory Market — Trader による経験値の売買・入札ボーナス
- [x] 累進資本課税 — 建物棟数に応じて課税率増加
- [x] 建物減価償却 — 50tick で自然崩壊

**経済システム**
- [x] 税プール + KPI連動 Governor 配当
- [x] 維持費（EC シンク）/ セーフティネット / パトロール給与 / 基本所得

**Layer2 / Layer3**
- [x] MQTT Event Bus（Mosquitto + paho-mqtt + WebSocket）
- [x] リアルタイムライブビューア
- [x] City OS（CityOS / AlertSystem / StateManager / CommandDispatcher / PolicyGate）

### 検討中
- [ ] エージェント寿命と相続（死→遺産引き継ぎで再起動）
- [ ] ブラックマーケット（高報酬違法タスク、Guardianに捕捉リスク）
- [ ] Governor 弾劾とクーデター（Worker 集合投票で権力交代）
- [ ] 感染バグとパンデミック（Medic が唯一の治療手段）
- [ ] Layer1: 物理接続（Raspberry Pi / ESP32）
- [ ] デジタルツイン（高品質 3D 可視化）
<!-- /AUTO-UPDATED -->

---

## 技術スタック

- **Python 3.9+** / Pydantic v2 / dataclasses
- **MQTT**: Mosquitto 2.1.2 / paho-mqtt / WebSocket (port 9001)
- **Web**: Vanilla JS / Canvas 2D / MQTT.js
- **動画**: Pillow / edge-tts (ja-JP-NanamiNeural) / ffmpeg
- **テスト**: pytest

---

*Built with Claude Code*
