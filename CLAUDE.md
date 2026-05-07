# HACS — Claude Code Instructions

## プロジェクト概要
Home Autonomous Civilization System — Pythonマルチエージェント都市シミュレーション

- Layer0: `C:\Users\kyomi\Desktop\hacs\layer0\` — コアシミュレーション
- Tests: `C:\Users\kyomi\Desktop\hacs\tests\` — pytest
- Obsidian Vault: `C:\Users\kyomi\Desktop\mybrain\MyBrain\wiki\HACS\`

## 必須ルール

### 1. Obsidian を常に更新する
実装・修正・実験を行ったセッションの終わりに、必ず以下を更新すること：

**対象ファイル:** `C:\Users\kyomi\Desktop\mybrain\MyBrain\wiki\HACS\HACS_進捗ログ.md`

**書くべき内容（日付セクション単位で追記）:**
- 実装・変更した機能
- 修正したバグ（原因と解法）
- スケールテスト結果（tick時間・効率性・平等性・役職別残高）
- 次の検討候補（新しいアイデア・TODOを含む）

**更新後は必ずコミット&プッシュ:**
```
cd C:/Users/kyomi/Desktop/mybrain
git add MyBrain/wiki/HACS/HACS_進捗ログ.md
git commit -m "HACS: YYYY-MM-DD <作業概要>"
git push origin main
```

### 2. テストを必ず通す
コード変更後は必ず `python -m pytest tests/ -x -q` を実行。132テスト全通過が基準。

### 3. パフォーマンス基準
最大 tick 時間 < 50ms を維持する。

## 主要ファイル構成
```
layer0/
├── core/
│   ├── agent.py       — Agent / AgentRole / AgentStatus
│   ├── ai.py          — WorkerAI / GuardianAI / TraderAI / ObserverAI / GovernorAI / MedicAI / ArchitectAI
│   ├── economy.py     — Economy（税プール・報酬・安全網）
│   ├── event_sourcing.py — EventReplayer（イベントログから状態再構築）
│   ├── task.py        — Task / TaskType / Quantum Auction
│   └── world.py       — World / Cell
├── engine/
│   └── simulator.py   — Simulator（メインループ）
├── schemas/
│   ├── event.py       — EventType / Event（Pydantic v2）
│   └── ...
└── main_scale_test.py — 67エージェント / 200tick スケールテスト
```

## 現在の実装状態（2026-05-07時点）
- 役職: Worker / Guardian / Trader / Observer / Governor / Medic / Architect（7種）
- タスク: standard / heavy / urgent / trade / security / survey / micro / construct（8種）
- Worker特性: HUSTLER / SAVER / SPECIALIST / EXPLORER / OPPORTUNIST
- メカニクス: Quantum Auction / Memory Market / 累進資本課税 / 建物減価償却
- テスト: 132件全通過
