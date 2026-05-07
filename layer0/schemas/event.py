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
