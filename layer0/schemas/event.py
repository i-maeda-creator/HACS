from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class EventType(str, Enum):
    TASK_CREATED          = "TaskCreated"
    BID_SUBMITTED         = "BidSubmitted"
    TASK_ASSIGNED         = "TaskAssigned"
    TASK_COMPLETED        = "TaskCompleted"
    AGENT_MOVED           = "AgentMoved"
    ENERGY_SPENT          = "EnergySpent"
    TRANSACTION_RECORDED  = "TransactionRecorded"
    POLICY_CHANGED        = "PolicyChanged"
    INCIDENT_DETECTED     = "IncidentDetected"
    AGENT_CHARGED         = "AgentCharged"
    COMMAND_ISSUED        = "CommandIssued"
    SAFETY_TRIGGERED      = "SafetyTriggered"
    NETWORK_EVENT         = "NetworkEvent"
    VOTE_SUBMITTED        = "VoteSubmitted"   # Governor が投票を提出
    VOTE_PASSED           = "VotePassed"      # 過半数合意 → 政策発動
    MARKET_EVENT          = "MarketEvent"     # 市場Boom/Crash
    UPKEEP_PAID           = "UpkeepPaid"      # 維持費支払い
    HEALING_DONE          = "HealingDone"     # Medic 治療完了
    SAFETY_NET_PAID       = "SafetyNetPaid"   # セーフティネット補助
    GOVERNANCE_REWARD     = "GovernanceReward"# Governor 統治報酬
    PATROL_SALARY         = "PatrolSalary"    # Guardian/Observer 巡回給与
    BUILDING_INCOME       = "BuildingIncome"  # Architect 建物不労所得
    BASIC_INCOME_PAID     = "BasicIncomePaid" # 全員への基本所得分配
    MEMORY_TRADE          = "MemoryTrade"     # Trader による記憶売買
    TEMPORAL_LOAN         = "TemporalLoan"    # 未来の自分からEC借入
    TEMPORAL_REPAYMENT    = "TemporalRepayment" # ローン返済
    PARADOX_COLLAPSE      = "ParadoxCollapse" # 返済不能→時空崩壊
    CAUSALITY_LOOP        = "CausalityLoop"   # タスク完了が過去に干渉し同種タスク召喚
    CHRONO_ARRIVAL        = "ChronoArrival"   # 未来エージェントが時間軸に出現
    CHRONO_DEPARTURE      = "ChronoDeparture" # 未来エージェントが消滅
    TEMPORAL_EXPOSURE     = "TemporalExposure"# 正体発覚 → 知識爆発・大規模パラドックス
    # ── 闇市 / 公安 ──────────────────────────────────────────────────
    ILLEGAL_TASK_CREATED  = "IllegalTaskCreated"  # 闇市タスクがスポーン
    ILLEGAL_TASK_COMPLETED = "IllegalTaskCompleted" # 違法タスク完了（無税）
    KOAN_DEPLOYED         = "KoanDeployed"    # 公安がWorkerとして潜入配置
    KOAN_ARREST           = "KoanArrest"      # 逮捕執行 — 残高没収・活動停止
    INFORMANT_TIP         = "InformantTip"    # Observer が公安に密告
    # ── 感情・暴動 ──────────────────────────────────────────────────────
    EMOTION_RIOT          = "EmotionRiot"      # 怒りが35%超 → 暴動発生
    # ── 死と転生 ───────────────────────────────────────────────────────
    AGENT_DIED            = "AgentDied"        # エネルギー枯渇で死亡
    AGENT_REBORN          = "AgentReborn"      # 転生（新個体として復活）
    # ── カルト ─────────────────────────────────────────────────────────
    CULT_JOINED           = "CultJoined"       # カルト加入
    CULT_BUSTED           = "CultBusted"       # カルト解散
    # ── 影の市場 ───────────────────────────────────────────────────────
    SHADOW_DEAL           = "ShadowDeal"       # 賄賂で入札を降ろす
    # ── 特性進化 ───────────────────────────────────────────────────────
    TRAIT_EVOLVED         = "TraitEvolved"     # 特性が別の特性へ進化
    # ── 銀行 ───────────────────────────────────────────────────────────
    BANK_DEPOSIT          = "BankDeposit"      # 預金
    BANK_INTEREST         = "BankInterest"     # 預金利息
    BANK_WITHDRAW         = "BankWithdraw"     # 引き出し
    BANK_LOAN             = "BankLoan"         # 融資
    BANK_REPAYMENT        = "BankRepayment"    # 融資返済
    BANK_DEFAULT          = "BankDefault"      # 融資デフォルト
    # ── 株式市場 ───────────────────────────────────────────────────────
    STOCK_BOUGHT          = "StockBought"      # 株購入
    STOCK_SOLD            = "StockSold"        # 株売却
    STOCK_DIVIDEND        = "StockDividend"    # 配当
    MARKET_CRASH          = "MarketCrash"      # 株式市場クラッシュ
    # ── 弾劾・クーデター ───────────────────────────────────────────────
    IMPEACHMENT_PRESSURE  = "ImpeachmentPressure"  # Worker不満が蓄積 → 弾劾圧力
    GOVERNOR_IMPEACHED    = "GovernorImpeached"    # Governor弾劾成立
    COUP_DECLARED         = "CoupDeclared"         # クーデター宣言
    COUP_SUCCEEDED        = "CoupSucceeded"        # クーデター成功 → 反乱政府樹立
    COUP_FAILED           = "CoupFailed"           # クーデター失敗 → 主導者逮捕
    REBEL_RESIGNED        = "RebelResigned"        # 反乱政府の任期終了 → Worker復帰


# EventType → MQTT トピックのマッピング
MQTT_TOPIC: Dict[str, str] = {
    EventType.TASK_CREATED:         "city/task/new",
    EventType.BID_SUBMITTED:        "city/task/bid",
    EventType.TASK_ASSIGNED:        "city/task/assigned",
    EventType.TASK_COMPLETED:       "city/task/completed",
    EventType.AGENT_MOVED:          "agent/{source}/event",
    EventType.ENERGY_SPENT:         "energy/usage",
    EventType.TRANSACTION_RECORDED: "economy/ledger",
    EventType.POLICY_CHANGED:       "city/policy/update",
    EventType.INCIDENT_DETECTED:    "security/incident",
    EventType.AGENT_CHARGED:        "energy/charge",
    EventType.COMMAND_ISSUED:       "city/command",
    EventType.SAFETY_TRIGGERED:     "safety/alert",
    EventType.NETWORK_EVENT:        "network/health",
    EventType.VOTE_SUBMITTED:       "city/governance/vote",
    EventType.VOTE_PASSED:          "city/governance/policy",
    EventType.MARKET_EVENT:         "city/market/event",
}


class Event(BaseModel):
    # ── 識別 ──────────────────────────────────────────────────
    event_id:       str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    sequence_id:    int = 0                # 全イベント通しの順序番号（Simulator が採番）
    correlation_id: Optional[str] = None  # 因果追跡：親イベントのevent_id

    # ── 時空間 ────────────────────────────────────────────────
    tick:      int
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── 内容 ──────────────────────────────────────────────────
    event_type: EventType
    source:     str = "simulator"          # Layer1 では robot_id / sensor_id になる
    agent_id:   Optional[str] = None
    task_id:    Optional[str] = None
    payload:    Dict[str, Any] = Field(default_factory=dict)

    # ── ルーティング ──────────────────────────────────────────
    @property
    def mqtt_topic(self) -> str:
        topic = MQTT_TOPIC.get(self.event_type, "city/event/unknown")
        return topic.replace("{source}", self.source)

    # 後方互換：旧コードが data を参照している箇所のため
    @property
    def data(self) -> Dict[str, Any]:
        return self.payload
