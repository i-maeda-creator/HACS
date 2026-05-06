from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer0.schemas.command import Command
from layer0.schemas.state import StateSnapshot
from layer3.alert_system import AlertSystem, Alert
from layer3.state_manager import StateManager
from layer3.command_dispatcher import CommandDispatcher
from layer3.policy_gate import PolicyGate


@dataclass
class CitySnapshot:
    """1 tick 分の City OS 統合スナップショット。"""
    sim_snap:        StateSnapshot
    alerts:          List[Alert]
    emergency_level: int
    policy_params:   dict
    dispatcher_stats: dict


class CityOS:
    """
    Layer3 City OS — HACS 中央オーケストレーター。

    Simulator (Layer0) の上に乗り、
    AlertSystem / CommandDispatcher / PolicyGate を統合して
    安全優先の都市運営を実現する。

    優先順位: Safety > Stability > Economy > Efficiency
    """

    def __init__(self, seed: int = 42):
        self.sim         = Simulator(seed=seed)
        self.alerts      = AlertSystem()
        self.state       = StateManager(self.sim)
        self.dispatcher  = CommandDispatcher(self.sim)
        self.gate        = PolicyGate()
        self._city_tick  = 0

    # ── エージェント追加 ────────────────────────────────────────
    def add_agent(self, agent: Agent) -> None:
        self.sim.add_agent(agent)

    # ── tick 実行 ───────────────────────────────────────────────
    def tick(self) -> CitySnapshot:
        self._city_tick += 1
        sim_snap = self.sim.step()
        new_alerts = self.alerts.check(sim_snap)

        # 緊急レベル 3 なら自動 EMERGENCY_STOP
        if self.alerts.emergency_level >= 3 and not self.sim.safety.is_emergency_active():
            from layer0.schemas.command import cmd_emergency_stop
            self.dispatcher.dispatch(
                cmd_emergency_stop(requested_by="city_os", tick=self._city_tick))

        return CitySnapshot(
            sim_snap=sim_snap,
            alerts=new_alerts,
            emergency_level=self.alerts.emergency_level,
            policy_params=self.state.policy_params(),
            dispatcher_stats=self.dispatcher.stats(),
        )

    def run(self, ticks: int) -> List[CitySnapshot]:
        return [self.tick() for _ in range(ticks)]

    # ── コマンド発行 ────────────────────────────────────────────
    def issue_command(self, command: Command):
        return self.dispatcher.dispatch(command)

    # ── ユーティリティ ──────────────────────────────────────────
    def summary(self) -> dict:
        metrics = self.state.get_metrics()
        alert_sum = self.alerts.summary()
        return {
            "tick":              self._city_tick,
            "emergency_level":   self.alerts.emergency_level,
            "agents":            len(self.sim.agents),
            "events":            len(self.sim.event_log),
            "efficiency":        metrics.get("policy_efficiency", 0),
            "equality":          metrics.get("policy_equality", 0),
            "gini":              metrics.get("gini", 0),
            "worker_idle_ratio": self.state.worker_idle_ratio(),
            "policy_params":     self.state.policy_params(),
            "alerts":            alert_sum,
            "commands":          self.dispatcher.stats(),
        }
