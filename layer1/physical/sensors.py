"""
Layer1 Sensors — センサー読み取りシミュレーション（ノイズあり）。
"""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from layer1.physical.robot import PhysicalRobot
    from layer1.mapping.home_map import HomeMap


@dataclass
class SensorReading:
    sensor_id: str
    value: float
    unit: str
    noise_sigma: float
    tick: int


class BatterySensor:
    """バッテリー残量センサー（±2% ノイズ）。"""
    NOISE_SIGMA = 2.0

    def read(self, robot: "PhysicalRobot", tick: int, rng: random.Random) -> SensorReading:
        true_val = robot.battery.percentage
        noisy = true_val + rng.gauss(0, self.NOISE_SIGMA)
        noisy = max(0.0, min(100.0, noisy))
        return SensorReading(f"{robot.robot_id}/battery", round(noisy, 1), "%", self.NOISE_SIGMA, tick)


class TemperatureSensor:
    """室温センサー（±0.5°C ノイズ）。部屋別ベース温度。"""
    NOISE_SIGMA = 0.5
    ROOM_BASE: Dict[str, float] = {
        "Living": 22.0,
        "Kitchen": 24.0,
        "Bedroom": 21.0,
        "Study": 23.0,
    }

    def read(self, robot: "PhysicalRobot", home_map: "HomeMap",
             tick: int, rng: random.Random) -> SensorReading:
        room = home_map.room_at(robot.x, robot.y)
        base = self.ROOM_BASE.get(room, 22.0) if room else 22.0
        noisy = base + rng.gauss(0, self.NOISE_SIGMA)
        return SensorReading(f"{robot.robot_id}/temperature", round(noisy, 1), "°C", self.NOISE_SIGMA, tick)


class PresenceSensor:
    """人感センサー（5% 誤検知・見落とし率）。"""
    ERROR_RATE = 0.05

    def read(self, human_present: bool, robot_id: str,
             tick: int, rng: random.Random) -> SensorReading:
        detected = human_present
        if rng.random() < self.ERROR_RATE:
            detected = not detected
        return SensorReading(f"{robot_id}/presence", float(detected), "bool", self.ERROR_RATE, tick)


class CollisionSensor:
    """衝突予測センサー（前方1マス）。"""

    def read(self, robot: "PhysicalRobot", home_map: "HomeMap",
             tick: int) -> SensorReading:
        tx = robot.x + (1 if robot.target_x is not None and robot.target_x > robot.x else
                        -1 if robot.target_x is not None and robot.target_x < robot.x else 0)
        ty = robot.y + (1 if robot.target_y is not None and robot.target_y > robot.y else
                        -1 if robot.target_y is not None and robot.target_y < robot.y else 0)
        collision_risk = not home_map.is_passable(tx, ty)
        return SensorReading(f"{robot.robot_id}/collision", float(collision_risk), "bool", 0.0, tick)


def read_all_sensors(robot: "PhysicalRobot", home_map: "HomeMap",
                     tick: int, rng: random.Random,
                     human_present: bool = False) -> Dict[str, SensorReading]:
    """全センサーを一括読み取り。"""
    readings: Dict[str, SensorReading] = {}
    batt = BatterySensor().read(robot, tick, rng)
    readings["battery"] = batt
    temp = TemperatureSensor().read(robot, home_map, tick, rng)
    readings["temperature"] = temp
    presence = PresenceSensor().read(human_present, robot.robot_id, tick, rng)
    readings["presence"] = presence
    collision = CollisionSensor().read(robot, home_map, tick)
    readings["collision"] = collision
    return readings
