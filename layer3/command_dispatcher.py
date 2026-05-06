from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from layer0.schemas.command import Command, CommandAction
from layer0.core.agent import AgentStatus
from layer3.policy_gate import PolicyGate, ValidationResult

if TYPE_CHECKING:
    from layer0.engine.simulator import Simulator


class CommandDispatcher:
    """Policy Gate を通過したコマンドを Simulator に適用する。"""

    def __init__(self, sim: "Simulator"):
        self._sim = sim
        self._gate = PolicyGate()
        self.rejected: List[dict] = []
        self.dispatched: List[dict] = []

    def dispatch(self, command: Command) -> ValidationResult:
        result = self._gate.validate(command, self._sim)
        if not result.allowed:
            self.rejected.append({"tick": self._sim.tick,
                                  "command": command.action.value,
                                  "agent_id": command.target,
                                  "reason": result.reason})
            return result

        action = command.action

        if action == CommandAction.EMERGENCY_STOP:
            for a in self._sim.agents:
                a.status = AgentStatus.IDLE
                a.target_x = None
                a.target_y = None
            self._sim.safety.trigger_emergency_stop(
                self._sim.tick, reason=command.parameters.get("reason", "manual"))
        else:
            agent = self._sim._get_agent(command.target)
            if agent is None:
                return result  # 既に gate でチェック済みなので到達しないが念のため

            if action == CommandAction.MOVE:
                agent.target_x = int(command.parameters["x"])
                agent.target_y = int(command.parameters["y"])
                agent.status = AgentStatus.MOVING

            elif action == CommandAction.STOP:
                agent.status = AgentStatus.IDLE
                agent.target_x = None
                agent.target_y = None

            elif action == CommandAction.CHARGE:
                charger = self._sim.world.nearest_charger(agent.x, agent.y)
                if charger:
                    agent.target_x, agent.target_y = charger
                    agent.status = AgentStatus.MOVING

        self.dispatched.append({"tick": self._sim.tick,
                                "command": action.value,
                                "agent_id": command.target})
        return result

    def dispatch_all(self, commands: List[Command]) -> List[ValidationResult]:
        return [self.dispatch(c) for c in commands]

    def stats(self) -> dict:
        return {"dispatched": len(self.dispatched), "rejected": len(self.rejected)}
