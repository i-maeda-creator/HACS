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

## 5つの役職

| 役職 | 数 | 色 | 役割 |
|------|----|----|------|
| **Worker** | 30 | 🟢 緑 | タスクをオークション入札で獲得。近いタスクほど強く入札。sector学習で最適化 |
| **Guardian** | 6 | 🔴 赤 | 5点パトロールルートを永続巡回。タスクに入札しない守護者 |
| **Trader** | 6 | 🟠 橙 | 市場平均をEMAで学習し、高マージンタスクのみ選別入札 |
| **Observer** | 5 | 🔵 青 | 4象限を分担カバー。情報収集専門でタスク入札なし |
| **Governor** | 3 | 🟣 紫 | 25tick毎にKPI分析→政策提案。提案は世界に即時反映 |

### Governor の政策提案

| 条件 | 提案 | 効果 |
|------|------|------|
| Worker稼働率 < 50% | `worker_support` | Worker入札ボーナス +1.5 EC |
| Gini > 0.25 | `tax_increase` | 税率 +2% |
| 完了率 < 60% | `reward_boost` | タスク報酬倍率 +12% |

効果は毎tick自然減衰し、状況が改善されなければ再提案される。

---

## Layer3 City OS

```python
from layer3.city_os import CityOS
from layer0.core.agent import Agent, AgentRole

city = CityOS(seed=42)
city.add_agent(Agent("W1", AgentRole.WORKER, x=2, y=2))
city.run(100)

print(city.summary())
# {'tick': 100, 'emergency_level': 0, 'gini': 0.12, ...}
```

| モジュール | 役割 |
|-----------|------|
| `CityOS` | 統合エントリポイント。緊急Lv3で自動EMERGENCY_STOP |
| `AlertSystem` | ENERGY/ECONOMY/TASK/SAFETY を INFO/WARNING/CRITICAL 判定 |
| `StateManager` | Simulator状態の読み取り専用API |
| `CommandDispatcher` | PolicyGate検証後にコマンドを適用 |
| `PolicyGate` | 壁チェック / 緊急時制限 / エージェント存在確認 |

---

## セットアップ

```bash
pip install pydantic paho-mqtt pillow edge-tts
# Mosquitto MQTT broker (Windows)
# https://mosquitto.org/download/
```

`mosquitto.conf` に WebSocket 設定が必要:
```
listener 1883
listener 9001
protocol websockets
allow_anonymous true
```

---

## 実行方法

### スケールテスト (50体 / 200tick)
```bash
python layer0/main_scale_test.py
```

### リアルタイムライブビューア
```bash
# ターミナル1: HTTPサーバー
python -m http.server 8080 --directory web

# ターミナル2: シミュレーション起動
python layer2/run_live.py

# ブラウザで開く
# http://localhost:8080/live_viewer.html
```

### テスト (92テスト)
```bash
python -m pytest tests/ -v
```

### Event Sourcing — イベントログから状態を再構築
```python
from layer0.core.event_sourcing import EventReplayer
replayer = EventReplayer(agents)
replayer.apply_all(sim.event_log)
state = replayer.final_state()
```

---

## ファイル構成

```
hacs/
├── layer0/
│   ├── core/
│   │   ├── world.py          # 20x20 グリッドマップ
│   │   ├── agent.py          # Agent dataclass
│   │   ├── task.py           # Task / Bid / オークション
│   │   ├── economy.py        # 税・台帳
│   │   ├── policy.py         # PolicyEngine (制約・目標)
│   │   ├── safety.py         # SafetyGate (夜間制限・緊急停止)
│   │   ├── ai.py             # 役職固有AI (Worker/Guardian/Trader/Observer/Governor)
│   │   └── event_sourcing.py # EventReplayer
│   ├── engine/
│   │   └── simulator.py      # メインシミュレーター
│   └── schemas/
│       ├── event.py          # Event / EventType / MQTT topic
│       ├── command.py        # Command / CommandAction
│       └── state.py          # StateSnapshot
├── layer2/
│   ├── event_bus.py          # MQTT Pub/Sub ラッパー
│   └── run_live.py           # 50体リアルタイム配信 (0.2s/tick)
├── layer3/
│   ├── city_os.py            # CityOS 統合エントリポイント
│   ├── alert_system.py       # AlertSystem
│   ├── state_manager.py      # StateManager
│   ├── command_dispatcher.py # CommandDispatcher
│   └── policy_gate.py        # PolicyGate
├── tests/                    # pytest 92テスト
└── web/
    ├── live_viewer.html       # Canvas 2D リアルタイムビューア
    └── live_dashboard.html    # MQTT KPIダッシュボード
```

---

## パフォーマンス (50体 / 200tick)

| 指標 | 値 |
|------|-----|
| 平均 tick 速度 | ~2ms/tick |
| 最大 tick 時間 | ~22ms (< 50ms 合格) |
| 総イベント数 | ~4,500件 |
| Worker 受注率 | ~60% |
| 効率性スコア | ~0.95 |
| 平等性スコア | ~0.88 |

---

## 進捗ログ

<!-- AUTO-UPDATED -->
**最終更新: 2026-05-06**

### 実装済み
- [x] Layer0: World / Agent / Task / Economy / Policy / Safety
- [x] Layer0: 役職固有AI — Worker(sector学習) / Guardian(パトロール) / Trader(市場学習) / Observer(象限カバー) / Governor(政策提案)
- [x] Layer0: Event Sourcing (EventReplayer)
- [x] Layer0: pytest 92テスト全通過
- [x] Layer0: 50体スケールテスト (2ms/tick)
- [x] Layer2: MQTT Event Bus (Mosquitto + paho-mqtt)
- [x] Layer2: リアルタイムライブビューア (50体 / 0.2s/tick)
- [x] Layer3: City OS (CityOS / AlertSystem / StateManager / CommandDispatcher / PolicyGate)
- [x] Governor 政策実効化 (提案が実際に世界を変える)

### 未実装
- [ ] Layer1: 物理接続 (Raspberry Pi / ESP32)
- [ ] Governance 強化 (投票・多数決・拒否権)
- [ ] デジタルツイン (高品質 3D 可視化)
- [ ] AWS クラウド移行
<!-- /AUTO-UPDATED -->

---

## 技術スタック

- **Python 3.9** / Pydantic v2 / dataclasses
- **MQTT**: Mosquitto 2.1.2 / paho-mqtt / WebSocket (port 9001)
- **Web**: Vanilla JS / Canvas 2D / MQTT.js
- **動画**: Pillow / edge-tts (ja-JP-NanamiNeural) / ffmpeg
- **テスト**: pytest

---

*Built with Claude Code*
