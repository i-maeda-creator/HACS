"""
Layer1 EdgeRuntime — Raspberry Pi / ESP32 相当のエッジデバイスシミュレーター。
1台の PhysicalRobot を管理し、物理 tick を進める。
"""
from __future__ import annotations
import random
from typing import Dict, List, Optional

from layer0.core.agent import AgentStatus
from layer0.schemas.command import Command, CommandAction
from layer0.schemas.event import Event, EventType
from layer1.mapping.home_map import HomeMap
from layer1.physical.battery import Battery
from layer1.physical.robot import PhysicalRobot, FailureMode
from layer1.physical.sensors import read_all_sensors


class EdgeRuntime:
    """
    1台のロボットの物理ループを担当する。
    - コマンドを受け取りキューに積む
    - tick() で物理状態を進め、イベントを発火する
    """

    def __init__(self, robot: PhysicalRobot, home_map: HomeMap,
                 rng: random.Random) -> None:
        self.robot = robot
        self.home_map = home_map
        self.rng = rng
        self.event_log: List[Event] = []
        self._tick = 0
        self._seq = 0
        self._human_present = False   # 人感センサー用（外部から設定可能）

    def receive_command(self, cmd: Command) -> None:
        self.robot.receive_command(cmd, self._tick)

    def tick(self) -> List[Event]:
        """1 tick 分の物理シミュレーションを実行。発火したイベントを返す。"""
        self._tick += 1
        tick_events: List[Event] = []

        robot = self.robot

        # ① ランダム障害チェック
        failure = robot.check_failure(self.rng)
        if failure not in (FailureMode.NONE, FailureMode.SENSOR_FAULT):
            tick_events.append(self._emit(
                EventType.SAFETY_TRIGGERED, robot_id=robot.robot_id,
                payload={"failure_mode": failure.value, "battery_pct": robot.battery.percentage}
            ))

        # ② コマンドキューから実行可能なコマンドを取り出す
        cmd = robot.process_commands(self._tick)
        if cmd:
            self._execute_command(cmd, tick_events)

        # ③ 移動ステップ（target へ1歩近づく）
        if robot.status == AgentStatus.MOVING and robot.target_x is not None:
            nx, ny = robot.move_toward(robot.target_x, robot.target_y, self.home_map, self.rng)
            if (nx, ny) != (robot.x, robot.y):
                robot.x, robot.y = nx, ny
                tick_events.append(self._emit(
                    EventType.AGENT_MOVED, robot_id=robot.robot_id,
                    payload={"x": nx, "y": ny,
                             "battery_pct": robot.battery.percentage,
                             "room": self.home_map.room_at(nx, ny)}
                ))
            # 目標到達
            if robot.x == robot.target_x and robot.y == robot.target_y:
                robot.status = AgentStatus.WORKING if robot.assigned_task_id else AgentStatus.IDLE

        # ④ 充電スポット上なら充電
        if self.home_map.is_charger(robot.x, robot.y):
            charged = robot.try_charge(self.home_map)
            if charged:
                tick_events.append(self._emit(
                    EventType.AGENT_CHARGED, robot_id=robot.robot_id,
                    payload={"battery_pct": robot.battery.percentage,
                             "cycles": robot.battery.charge_cycles,
                             "health": robot.battery.health()}
                ))

        # ⑤ 低バッテリー警告
        if robot.battery.is_low() and robot.status != AgentStatus.CHARGING:
            tick_events.append(self._emit(
                EventType.ENERGY_SPENT, robot_id=robot.robot_id,
                payload={"battery_pct": robot.battery.percentage,
                         "warning": "low_battery",
                         "failure_mode": robot.failure_mode.value}
            ))

        # ⑥ センサー読み取り（10 tick ごと）
        if self._tick % 10 == 0:
            readings = read_all_sensors(robot, self.home_map, self._tick,
                                        self.rng, self._human_present)
            tick_events.append(self._emit(
                EventType.NETWORK_EVENT, robot_id=robot.robot_id,
                payload={k: {"value": v.value, "unit": v.unit}
                         for k, v in readings.items()}
            ))

        self.event_log.extend(tick_events)
        return tick_events

    def _execute_command(self, cmd: Command, events: List[Event]) -> None:
        robot = self.robot
        action = cmd.action

        if action == CommandAction.MOVE:
            robot.target_x = cmd.parameters.get("x", robot.x)
            robot.target_y = cmd.parameters.get("y", robot.y)
            robot.status = AgentStatus.MOVING
        elif action == CommandAction.WORK:
            robot.assigned_task_id = cmd.parameters.get("task_id")
            robot.work()
            events.append(self._emit(
                EventType.TASK_COMPLETED, robot_id=robot.robot_id,
                payload={"task_id": robot.assigned_task_id,
                         "battery_pct": robot.battery.percentage}
            ))
            robot.assigned_task_id = None
            robot.status = AgentStatus.IDLE
        elif action == CommandAction.CHARGE:
            charger = self.home_map.nearest_charger(robot.x, robot.y)
            if charger:
                robot.target_x, robot.target_y = charger
                robot.status = AgentStatus.MOVING
        elif action in (CommandAction.STOP, CommandAction.EMERGENCY_STOP):
            robot.status = AgentStatus.IDLE
            robot.target_x = None
            robot.target_y = None

        events.append(self._emit(
            EventType.COMMAND_ISSUED, robot_id=robot.robot_id,
            payload={"action": action.value, "command_id": cmd.command_id}
        ))

    def _emit(self, event_type: EventType, robot_id: str,
              payload: Optional[dict] = None) -> Event:
        self._seq += 1
        return Event(
            tick=self._tick,
            sequence_id=self._seq,
            event_type=event_type,
            source=robot_id,
            agent_id=robot_id,
            payload=payload or {},
        )

    def telemetry(self) -> dict:
        """現在のロボット状態サマリ。"""
        return {
            "tick": self._tick,
            **self.robot.snapshot(),
            "room": self.home_map.room_at(self.robot.x, self.robot.y),
        }
