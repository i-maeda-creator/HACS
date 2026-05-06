from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layer0.engine.simulator import Simulator
from layer0.core.agent import Agent, AgentRole
from layer2.event_bus import EventBus


class SimulatorBridge:
    """Layer0 Simulator の Event を Layer2 EventBus へ流すブリッジ."""

    def __init__(self, sim: Simulator, bus: EventBus):
        self.sim = sim
        self.bus = bus

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            prev_count = len(self.sim.event_log)
            self.sim.step()
            new_events = self.sim.event_log[prev_count:]
            for event in new_events:
                self.bus.publish_event(event)
