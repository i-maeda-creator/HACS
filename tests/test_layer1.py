"""Layer1 物理シミュレーションのテスト。"""
import sys
sys.path.insert(0, ".")

import pytest
import random

from layer1.mapping.home_map import HomeMap, Terrain
from layer1.physical.battery import Battery
from layer1.physical.sensors import BatterySensor, TemperatureSensor, read_all_sensors
from layer1.physical.robot import PhysicalRobot, FailureMode
from layer1.runtime.edge_runtime import EdgeRuntime
from layer1.bridge import Layer1Bridge
from layer0.core.agent import AgentRole, AgentStatus
from layer0.schemas.command import cmd_move, cmd_charge, cmd_stop


# ── HomeMap ────────────────────────────────────────────────────────────────────

class TestHomeMap:
    def setup_method(self):
        self.m = HomeMap()

    def test_charger_cells_are_chargers(self):
        for (cx, cy) in HomeMap.CHARGERS:
            assert self.m.is_charger(cx, cy)

    def test_obstacle_cells_not_passable(self):
        for (ox, oy) in HomeMap.OBSTACLES:
            assert not self.m.is_passable(ox, oy)

    def test_room_tiles_passable(self):
        # 部屋中央は通行可能
        assert self.m.is_passable(5, 5)   # Living
        assert self.m.is_passable(15, 5)  # Kitchen
        assert self.m.is_passable(5, 15)  # Bedroom
        assert self.m.is_passable(15, 15) # Study

    def test_out_of_bounds_not_passable(self):
        assert not self.m.is_passable(-1, 0)
        assert not self.m.is_passable(0, 20)
        assert not self.m.is_passable(20, 20)

    def test_carpet_move_cost_higher(self):
        # Bedroom (x=5, y=15) はカーペット
        assert self.m.move_cost_factor(5, 15) == 1.4

    def test_tile_move_cost_normal(self):
        assert self.m.move_cost_factor(5, 5) == 1.0

    def test_nearest_charger_returns_closest(self):
        # (1,1) から最寄り充電器は (1,1) 自身
        nearest = self.m.nearest_charger(1, 1)
        assert nearest == (1, 1)

    def test_room_at_correct(self):
        assert self.m.room_at(5, 5) == "Living"
        assert self.m.room_at(15, 5) == "Kitchen"
        assert self.m.room_at(5, 15) == "Bedroom"
        assert self.m.room_at(15, 15) == "Study"

    def test_door_cells_passable(self):
        # ドアセルは通行可能
        assert self.m.is_passable(5, 9)
        assert self.m.is_passable(5, 10)


# ── Battery ────────────────────────────────────────────────────────────────────

class TestBattery:
    def test_drain_reduces_level(self):
        b = Battery()
        b.drain(10.0)
        assert b.level == 90.0

    def test_drain_terrain_factor(self):
        b = Battery(level=100.0)
        b.drain(10.0, terrain_factor=1.4)
        assert abs(b.level - 86.0) < 0.01

    def test_drain_cannot_go_below_zero(self):
        b = Battery(level=5.0)
        b.drain(100.0)
        assert b.level == 0.0

    def test_charge_increases_level(self):
        b = Battery(level=50.0)
        b.charge()
        assert b.level > 50.0

    def test_full_charge_increments_cycles(self):
        b = Battery(level=95.0)
        b.charge(rate=10.0)
        assert b.charge_cycles >= 1

    def test_degradation_on_cycle(self):
        b = Battery(level=95.0)
        for _ in range(100):
            b.charge(rate=10.0)
        assert b.capacity_max < 100.0

    def test_is_low(self):
        b = Battery(level=15.0)
        assert b.is_low(threshold=20.0)

    def test_is_dead(self):
        b = Battery(level=0.0)
        assert b.is_dead()

    def test_health_degrades(self):
        b = Battery()
        for _ in range(200):
            b.charge(rate=10.0)
        assert b.health() < 1.0


# ── Sensors ────────────────────────────────────────────────────────────────────

class TestSensors:
    def setup_method(self):
        self.home_map = HomeMap()
        self.rng = random.Random(42)
        self.robot = PhysicalRobot("r0", AgentRole.WORKER, 5, 5)

    def test_battery_sensor_in_range(self):
        readings_list = [BatterySensor().read(self.robot, 1, self.rng).value for _ in range(50)]
        assert all(0 <= v <= 100 for v in readings_list)

    def test_temperature_sensor_in_range(self):
        s = TemperatureSensor()
        r = s.read(self.robot, self.home_map, 1, self.rng)
        assert 15.0 <= r.value <= 35.0

    def test_read_all_returns_all_keys(self):
        readings = read_all_sensors(self.robot, self.home_map, 1, self.rng)
        assert set(readings.keys()) == {"battery", "temperature", "presence", "collision"}


# ── PhysicalRobot ──────────────────────────────────────────────────────────────

class TestPhysicalRobot:
    def setup_method(self):
        self.home_map = HomeMap()
        self.rng = random.Random(42)
        self.robot = PhysicalRobot("r0", AgentRole.WORKER, 5, 5)

    def test_move_toward_changes_position(self):
        nx, ny = self.robot.move_toward(10, 5, self.home_map, self.rng)
        assert (nx, ny) != (5, 5)

    def test_move_drains_battery(self):
        initial = self.robot.battery.level
        self.robot.move_toward(10, 5, self.home_map, self.rng)
        assert self.robot.battery.level < initial

    def test_command_queue_latency(self):
        cmd = cmd_move("r0", 10, 5, tick=0)
        self.robot.receive_command(cmd, current_tick=0)
        # tick=1 ではまだ実行されない（latency=2）
        assert self.robot.process_commands(1) is None
        # tick=2 で実行可能
        assert self.robot.process_commands(2) is not None

    def test_motor_stuck_prevents_movement(self):
        self.robot.failure_mode = FailureMode.MOTOR_STUCK
        nx, ny = self.robot.move_toward(10, 5, self.home_map, self.rng)
        assert (nx, ny) == (5, 5)

    def test_charge_on_charger_cell(self):
        self.robot.x, self.robot.y = 1, 1  # 充電スポット
        self.robot.battery.level = 50.0
        result = self.robot.try_charge(self.home_map)
        assert result
        assert self.robot.battery.level > 50.0

    def test_snapshot_has_required_keys(self):
        snap = self.robot.snapshot()
        for key in ("robot_id", "role", "x", "y", "battery_pct",
                    "battery_health", "status", "failure_mode", "odometer"):
            assert key in snap


# ── EdgeRuntime ────────────────────────────────────────────────────────────────

class TestEdgeRuntime:
    def setup_method(self):
        self.home_map = HomeMap()
        robot = PhysicalRobot("r0", AgentRole.WORKER, 5, 5)
        self.rt = EdgeRuntime(robot, self.home_map, random.Random(42))

    def test_tick_returns_events(self):
        cmd = cmd_move("r0", 8, 5, tick=0)
        self.rt.receive_command(cmd)
        events = []
        for _ in range(10):
            events.extend(self.rt.tick())
        assert len(events) > 0

    def test_move_command_changes_position(self):
        cmd = cmd_move("r0", 8, 5, tick=0)
        self.rt.receive_command(cmd)
        for _ in range(10):
            self.rt.tick()
        robot = self.rt.robot
        # 8 tick 移動したので (5,5) より右に動いているはず
        assert robot.x > 5 or robot.status == AgentStatus.IDLE

    def test_stop_command_idles_robot(self):
        cmd_mv = cmd_move("r0", 15, 15, tick=0)
        self.rt.receive_command(cmd_mv)
        for _ in range(3):
            self.rt.tick()
        cmd_st = cmd_stop("r0", tick=3)
        self.rt.receive_command(cmd_st)
        for _ in range(3):
            self.rt.tick()
        assert self.rt.robot.status == AgentStatus.IDLE


# ── Layer1Bridge ───────────────────────────────────────────────────────────────

class TestLayer1Bridge:
    def test_bridge_runs_without_error(self):
        bridge = Layer1Bridge(seed=42)
        for _ in range(20):
            bridge.step(autonomous=True)
        snap = bridge.get_snapshot()
        assert snap["tick"] == 20
        assert snap["total_events"] > 0

    def test_all_robots_have_moved(self):
        bridge = Layer1Bridge(seed=42)
        for _ in range(30):
            bridge.step(autonomous=True)
        snap = bridge.get_snapshot()
        # motor_stuck 以外のロボットは移動しているはず
        moved = [r for r in snap["robots"]
                 if r["odometer"] > 0 and r["failure_mode"] == "none"]
        assert len(moved) >= 5

    def test_external_command_reaches_robot(self):
        bridge = Layer1Bridge(seed=42)
        first_id = list(bridge.runtimes.keys())[0]
        cmd = cmd_move(first_id, 1, 1, tick=0)
        ok = bridge.send_command(first_id, cmd)
        assert ok
        for _ in range(10):
            bridge.step(autonomous=False)
        robot = bridge.runtimes[first_id].robot
        # コマンド送信後10 tick で (1,1) 方向へ動いているはず
        assert robot.odometer > 0 or robot.x == 1
