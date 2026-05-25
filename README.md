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

## シミュレーション規模

| 項目 | 値 |
|------|-----|
| グリッド | **40×40**（四地区: 下町NW / 工業NE / 治安SW / 商業SE） |
| エージェント | **106体** |
| 標準ティック数 | **2000 tick** |
| 総イベント数 | ~288,000件 / 2000tick |
| テスト | **132テスト全通過** |

---

## 8つの役職

| 役職 | 体数 | 役割 | 収入源 |
|------|------|------|--------|
| **Worker** | 60 | タスクをオークション入札で獲得。RTを採集・売却 | タスク報酬 + RT売却 |
| **Guardian** | 12 | 5点ルートを永続パトロール。治安タスクにも入札 | パトロール給与 + 治安タスク |
| **Trader** | 8 | 市場平均をEMAで学習し高マージンタスクを選別。Worker からRT を仕入れEC に換算 | タスク報酬 + RT転換益 |
| **Observer** | 8 | 4象限を分担カバー。密告で治安維持に貢献 | パトロール給与 + 調査タスク |
| **Governor** | 4 | 25tick毎にKPI分析→政策提案。税収の配当で収入 | 税配当（KPI連動） |
| **Medic** | 6 | 低エネルギーのエージェントに接近し治療を提供 | 治療費（EC） |
| **Architect** | 4 | 建設タスク専門。完成した建物が毎tick不労所得を生む | 建設報酬 + 建物収入 |
| **公安 (KOAN)** | 4 | Workerに潜入し違法タスクの証拠を蓄積。閾値到達で逮捕 | 内部予算 |

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

### 全役職3種の性格バリエーション

| 役職 | 性格 |
|------|------|
| Guardian | STOIC / AGGRESSIVE / VIGILANT |
| Trader | ANALYST / SHARK / SPECULATOR |
| Observer | SYSTEMATIC / VISIONARY / INFORMANT |
| Governor | BALANCED / POPULIST / CONSERVATIVE |
| Medic | PROFESSIONAL / MERCENARY / SELFLESS |
| Architect | BUILDER / MONOPOLIST / URBANIST |

---

## 3通貨システム

| 通貨 | 記号 | 性質 | 主な流れ |
|------|------|------|---------|
| **EC** (経済クレジット) | EC | 汎用・譲渡可 | タスク報酬 / 税収 / 建物収入 |
| **RT** (Resource Token) | RT | 物理労働の証明・売買可 | 採集→Worker保有→Trader仕入 |
| **TR** (Trust Rating) | TR | 非売品・信頼指標 | タスク完了+1 / 逮捕-5 / 治療+2 |

### RT の流れ
```
Worker が GATHER タスクで RT 採集
  → RT >= 4.0 で Trader が近距離から買取（市場レート）
  → Trader は RT を EC に 1.3倍 マークアップで換算
  → 部屋発見済み Worker は RT を部屋入室コストとして消費
```

### TR の変動ルール

| イベント | TR変動 |
|----------|--------|
| タスク完了 | +1.0（CONSTRUCT +3、UPGRADE/SECURITY +2） |
| Medic 治療 | +2.0 |
| 政策可決 | Governor +3.0 |
| CHRONO 生存 | +5.0 |
| 逮捕 | -5.0 |
| 暴動参加 | -2.0 |
| 銀行デフォルト | -3.0 |

---

## タスクシステム

### 8種のタスクタイプと効果

| タイプ | 主担当 | 報酬 | 特殊効果 |
|--------|--------|------|---------|
| **standard** | Worker/Trader | 8〜20 EC | — |
| **heavy** | Worker優先 | 25〜50 EC | RT 1.0 消費必須・完了でRT回収 |
| **urgent** | 全役職 | 20〜35 EC | 15tick期限・前半完了で+2経験 |
| **trade** | Trader優先 | 12〜28 EC | 完了でRT +0.5（Trader）/ +0.2（他） |
| **security** | Guardian優先 | 10〜22 EC | 半径5の犯罪証拠を20%減衰 |
| **survey** | Observer優先 | 5〜12 EC | 完了で+3経験値ボーナス |
| **micro** | Worker | 2〜6 EC | 完了で半径3の隣接者にエネルギー+5 |
| **construct** | Architect | 25〜45 EC | 建物Lv1を新設 |

### 報酬スケーリング
```
最終報酬 = 基本報酬 × (1 + min(経験値/500, 0.20)) × (1 + min(TR/200, 0.10))
```
経験豊富・信頼度の高いエージェントほど高報酬を獲得できる。

---

## コアメカニクス

### Quantum Auction（量子入札）
```
P(当選) ∝ 入札額
```
高い入札は有利だが確定ではない。SAVER や OPPORTUNIST が確率的に受注できる。

### Memory Market（記憶売買）
Trader が高経験値 Worker の AI 記憶を買い取り、新人 Worker に転売する。

```
高経験値 Worker → Trader が隣接時に記憶を仕入れ（experience × 買取レート）
  → 新人 Worker に記憶を転売（マークアップ込み）
  → 購入した Worker は 8tick 間 入札ボーナス（memory_boost）を得る
```

### 精神と時の部屋（チャンバー）
経験値が蓄積した Worker がRT を消費して入室できる特別空間。  
経験値 120 以上 かつ TR ≥ 3.0 で **天才覚醒** → **世界改変発明** が生まれる。

```
一時発明: duration tick で効果消滅
永久技術: 世界に永遠に刻まれる
```

部屋発見済み Worker は RT をオークション入札より部屋入室を優先する。

### 発明システム（7種）

| 発明タイプ | 効果 |
|-----------|------|
| jump_gate | 2地点間に瞬間移動口が出現 |
| collective_consciousness | 全タスク報酬0.5%を最貧5体に毎tick還元 |
| blind_dimension | 公安の検知能力が半減 |
| crypto_reactor | HACK不可能化・SMUGGLE報酬3倍 |
| entropy_reversal | 銀行利息5倍・維持費3倍 |
| memory_flood | 全員のタスク完了経験値2倍 |
| chaos_amplifier | タスク報酬1.8倍 |

### コンボ発明（創発）
永久技術が2件以上蓄積されると100tick毎に「予期せぬ創発」が起きる。  
永久技術が増えるほど合算シグネチャが上昇し、より多くのコンボ条件を満たせる複利構造。

| コンボ | 必要軸 | 効果 |
|--------|--------|------|
| temporal_anchor | temporal強 | CHRONO滞在期間3倍 |
| quantum_tunnel | temporal+chaos | 全建物間瞬間移動網 |
| recursive_growth | economic | 80tick毎に建物自動Lvアップ |
| time_crystal | temporal+social | 全員エネルギー毎tick+2自然回復 |
| gift_economy | crime+political | HACK/SMUGGLEを合法化・課税 |
| hive_mind | social | 最高経験値の知識20%が毎tick伝播 |
| post_scarcity | economic | 維持費永久ゼロ |

### 弾劾・クーデター
```
Worker 不満率 > 60% が3tick連続
  → Governor 全員弾劾（残高40%没収・20tick権力空白）
  → Guardian 支持率 >= 50% なら Worker がクーデター成功
  → 反乱政府が40tick統治 → Worker に自動復帰
```

### 生産チェーン
```
GATHER タスク → Worker がリソースノードから採集 → resources 蓄積
  → 隣接建物に搬入 → 加工収益（建物レベルで倍率変化）
                        └─ 工業地区(NE): +50%ボーナス
```

建物の成長:
```
CONSTRUCT完了 → Lv1  →  UPGRADE完了 → Lv2  →  Lv3（最大）
  （Lv別収入倍率: 1.0x / 1.5x / 2.2x）
```

### 株式市場
- ARCH / TRAD / WORK 株を自動売買
- 価格がクラッシュ閾値（~4 EC）に達すると強制リセット
- 配当は保有株数に応じて毎tick支払い

### 銀行システム
- 残高 60 EC 以上で自動預金（8%確率）
- 融資：残高 10 EC 未満に最大 25 EC 貸付（準備金から）
- 利息は準備金から支払い（無制限創造なし）
- デフォルト時残高没収 → 準備金へ

### 時空歪曲メカニクス

| メカニクス | 説明 |
|-----------|------|
| **Temporal Loan** | 残高低下時に EC 借入。期限後に利息付き返済 |
| **Paradox Collapse** | 返済不能 → 残高ランダムリセット + 近隣に経済的ゆらぎ |
| **Causality Loop** | タスク完了の10%確率で同種タスクが「過去から召喚」 |
| **CHRONO Arrival** | 40〜80tick 毎に時間旅行者が登場 |
| **CHRONO Departure** | 期限切れで消滅。残高を近隣に「時空遺産」として残す |

### CHRONO 正体発覚システム
疑惑度が 15 を超えると正体発覚。

```
疑惑度上昇:
  + 2.5 落札するたびに（完璧すぎる入札が怪しまれる）
  + 2.5/tick AGGRESSIVE/VIGILANT Guardian が半径3以内
  - 0.3/tick 自然減衰

疑惑 > 8:   入札を意図的に 50〜80% まで下げてカモフラージュ
疑惑 ≥ 15:  TEMPORAL_EXPOSURE → 知識爆発 + 残高60%放出 + 即時消滅
```

### 社会メカニクス

| メカニクス | 説明 |
|-----------|------|
| **感情・暴動** | emotion_level < -5 で怒り → -8 で暴動・建物略奪 |
| **死と転生** | エネルギー枯渇で死亡。次世代として経験継承し復活 |
| **特性進化** | hustler→opportunist→explorer→hustler のサイクル進化 |
| **同盟/ライバル** | 同盟相手にタスク報酬5%シェア。ライバル相手に入札10%増し |
| **影の市場** | 賄賂でタスク担当者を買収（Observer が密告） |
| **カルト** | 特定条件で信者集団が形成される |

---

## 経済設計

```
タスク報酬
  └─ 課税（税率: デフォルト5%、Governor 政策で可変）
       ├─ 30% → Governor（KPIスコア×0.4〜1.3倍で調整）
       └─ 70% → tax_pool
                   ├─ Guardian/Observer パトロール給与
                   ├─ Architect 建物収入
                   ├─ セーフティネット（残高低下に補助）
                   └─ basic_income（Governor提案で全員均等分配）

全エージェント: 維持費 0.2 EC/tick（ECシンク）
逮捕没収: 被疑者残高60% → 銀行準備金へ
```

### Governor の政策提案（25tick毎）

| 条件 | 提案 | 効果 |
|------|------|------|
| 完了率 < 60% | `reward_boost` | タスク報酬倍率 +12% |
| Worker 稼働率 < 50% | `worker_support` | Worker 入札ボーナス +1.5 EC |
| 税プール > 400 EC かつ Gini > 0.15 | `basic_income` | 全員均等分配 |
| Gini > 0.30 かつ KPI > 0.6 | `tax_increase` | 税率 +2% |

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

### スケールテスト（106体 / 2000tick）
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
│   │   ├── world.py          # 40×40 グリッドマップ・四地区・充電ステーション
│   │   ├── agent.py          # Agent（EC / RT / TR / experience 含む）
│   │   ├── task.py           # Task / Bid / Quantum Auction / タイプ別効果
│   │   ├── economy.py        # 税プール・報酬・セーフティネット
│   │   ├── policy.py         # PolicyEngine（制約・目標）
│   │   ├── safety.py         # SafetyGate（夜間制限・緊急停止）
│   │   ├── ai.py             # 8役職AI + Worker 11特性 + 全役職3種性格
│   │   └── event_sourcing.py # EventReplayer（イベントから状態再構築）
│   ├── engine/
│   │   └── simulator.py      # メインシミュレーター（全メカニクス実装）
│   ├── export/
│   │   └── narrative_exporter.py  # 都市新聞（City Daily）自動生成
│   └── schemas/
│       ├── event.py          # Event / EventType（50種以上）
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

## パフォーマンス（106体 / 2000tick）

| 指標 | 値 |
|------|-----|
| 平均 tick 速度 | ~68ms/tick |
| 最大 tick 時間 | ~1000ms（高負荷時） |
| 総イベント数 | ~288,000件 |
| 天才覚醒 | ~4〜10体 |
| 永久技術 | ~8〜15件（うちコンボ7件） |
| pytest | **132テスト全通過** |

---

## 進捗ログ

<!-- AUTO-UPDATED -->
**最終更新: 2026-05-24**

### 実装済み

**Layer0 コア**
- [x] World / Agent / Task / Economy / Policy / Safety（40×40四地区）
- [x] 8役職 AI（Worker / Guardian / Trader / Observer / Governor / Medic / Architect / 公安）
- [x] Worker 11特性 + 全役職3種性格
- [x] 12タスクタイプ（standard / heavy / urgent / trade / security / survey / micro / construct / gather / upgrade / smuggle / hack）
- [x] タスクタイプ別質的効果（SURVEY経験ボーナス / SECURITYパトロール / HEAVYリソース消費 / MICROコミュニティ）
- [x] 経験値・TR連動報酬スケーリング
- [x] Event Sourcing（EventReplayer）
- [x] pytest 132テスト全通過

**3通貨システム**
- [x] EC（汎用経済クレジット）
- [x] RT（Resource Token — 物理労働証明・Worker採集→Trader換算）
- [x] TR（Trust Rating — 非売品・社会信頼指標）
- [x] RT 市場（Worker→Trader 売却・マークアップ換算）
- [x] Memory Market（記憶売買 — 高経験WorkerからTraderが仕入れ→新人Workerに転売・8tick入札ボーナス）

**発明・文明システム**
- [x] 精神と時の部屋（チャンバー — RT消費入室・天才覚醒）
- [x] 天才発明7種（jump_gate / collective_consciousness / blind_dimension 他）
- [x] コンボ発明7種（永久技術の合算シグネチャから創発）
- [x] 発明効果の世界適用（HACK無効化 / 建物自動成長 / 維持費ゼロ 他）

**統治・政治**
- [x] Governor 25tick毎政策提案（reward_boost / worker_support / basic_income / tax_increase）
- [x] 弾劾・クーデター（Worker集合投票→権力交代→反乱統治40tick）
- [x] KPI連動税配当

**経済インフラ**
- [x] 銀行（預金・融資・利息・デフォルト — 準備金制約あり）
- [x] 株式市場（ARCH/TRAD/WORK 自動売買・クラッシュ・配当）
- [x] 生産チェーン（採集→加工→建物成長 + 工業地区NE 1.5倍ボーナス）
- [x] 累進資本課税・建物減価償却

**社会・治安**
- [x] ブラックマーケット（SMUGGLE / HACK 違法タスク）
- [x] 公安潜入・証拠蓄積・逮捕（没収→銀行準備金）
- [x] 感情システム・暴動・建物略奪
- [x] 死と転生（経験継承）・特性進化サイクル
- [x] 同盟・ライバル関係
- [x] 影の市場（賄賂）・Observer 密告

**時空メカニクス**
- [x] CHRONO 時間旅行者（出現・正体発覚・消滅・時空遺産）
- [x] Temporal Loan / Paradox Collapse / Causality Loop

**Layer2 / Layer3**
- [x] MQTT Event Bus（Mosquitto + paho-mqtt + WebSocket）
- [x] リアルタイムライブビューア
- [x] City OS（CityOS / AlertSystem / StateManager / CommandDispatcher / PolicyGate）
- [x] 都市新聞（City Daily）ナラティブ自動生成

### 検討中
- [ ] 商社役職（地区間大口卸・Worker融資・Architect建設前払い）
- [ ] カルト活性化（現在0件 — トリガー条件の調整）
- [ ] 効率性スコア修正（常に0.000 — 計算式のバグ）
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
