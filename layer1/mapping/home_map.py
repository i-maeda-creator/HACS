"""
Layer1 HomeMap — 20×20 物理ホームマップ。
各セル = 50cm × 50cm → 総面積 10m × 10m。
Layer0 の World と同じ座標系を共有する。
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class Terrain(str, Enum):
    TILE    = "tile"     # フローリング・タイル（移動コスト×1.0）
    CARPET  = "carpet"   # カーペット（移動コスト×1.4）
    WALL    = "wall"     # 壁（通行不可）
    CHARGER = "charger"  # 充電ステーション（通行可能）
    OBSTACLE = "obstacle" # 家具・障害物（通行不可）


@dataclass
class Room:
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    terrain: Terrain = Terrain.TILE

    def contains(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


class HomeMap:
    """
    デフォルトレイアウト（20×20）:
      Living  (0-9,  0-9 ) ← 南西
      Kitchen (10-19, 0-9 ) ← 南東
      Bedroom (0-9,  10-19) ← 北西
      Study   (10-19,10-19) ← 北東
    内壁あり・ドアあり・充電ステーション各部屋1台。
    """

    WIDTH  = 20
    HEIGHT = 20

    ROOMS: List[Room] = [
        Room("Living",  0,  0,  9,  9, Terrain.TILE),
        Room("Kitchen", 10, 0,  19, 9, Terrain.TILE),
        Room("Bedroom", 0,  10, 9,  19, Terrain.CARPET),
        Room("Study",   10, 10, 19, 19, Terrain.CARPET),
    ]

    # 充電ステーション座標（各部屋の隅）
    CHARGERS: List[Tuple[int, int]] = [
        (1, 1),    # Living  南西隅
        (18, 1),   # Kitchen 南東隅
        (1, 18),   # Bedroom 北西隅
        (18, 18),  # Study   北東隅
    ]

    # 家具・障害物（通行不可）
    OBSTACLES: List[Tuple[int, int]] = [
        # Living のソファ
        (4, 3), (5, 3), (4, 4), (5, 4),
        # Kitchen のカウンター
        (12, 2), (13, 2), (14, 2),
        # Bedroom のベッド
        (3, 12), (4, 12), (5, 12), (3, 13), (4, 13), (5, 13),
        # Study の机
        (14, 14), (15, 14), (14, 15),
    ]

    def __init__(self) -> None:
        self._grid: Dict[Tuple[int, int], Terrain] = {}
        self._build()

    def _build(self) -> None:
        # 全セルを WALL で初期化
        for x in range(self.WIDTH):
            for y in range(self.HEIGHT):
                self._grid[(x, y)] = Terrain.WALL

        # 部屋を塗る
        for room in self.ROOMS:
            for x in range(room.x1, room.x2 + 1):
                for y in range(room.y1, room.y2 + 1):
                    self._grid[(x, y)] = room.terrain

        # 内壁（x=9-10 境界 / y=9-10 境界）はデフォルト WALL のまま
        # ただしドアを開ける
        # 南北の壁 (y=9/10 境界) にドア
        for door_x in [5, 15]:          # Living↔Bedroom, Kitchen↔Study
            self._grid[(door_x, 9)]  = Terrain.TILE
            self._grid[(door_x, 10)] = Terrain.TILE

        # 東西の壁 (x=9/10 境界) にドア
        for door_y in [4, 14]:          # Living↔Kitchen, Bedroom↔Study
            self._grid[(9,  door_y)] = Terrain.TILE
            self._grid[(10, door_y)] = Terrain.TILE

        # 障害物を配置
        for (ox, oy) in self.OBSTACLES:
            self._grid[(ox, oy)] = Terrain.OBSTACLE

        # 充電ステーションを配置（通行可能）
        for (cx, cy) in self.CHARGERS:
            self._grid[(cx, cy)] = Terrain.CHARGER

    def terrain_at(self, x: int, y: int) -> Terrain:
        return self._grid.get((x, y), Terrain.WALL)

    def is_passable(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.WIDTH or y < 0 or y >= self.HEIGHT:
            return False
        return self.terrain_at(x, y) not in (Terrain.WALL, Terrain.OBSTACLE)

    def is_charger(self, x: int, y: int) -> bool:
        return self.terrain_at(x, y) == Terrain.CHARGER

    def move_cost_factor(self, x: int, y: int) -> float:
        """地形による移動コスト倍率。"""
        t = self.terrain_at(x, y)
        return 1.4 if t == Terrain.CARPET else 1.0

    def room_at(self, x: int, y: int) -> Optional[str]:
        for room in self.ROOMS:
            if room.contains(x, y):
                return room.name
        return None

    def nearest_charger(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        if not self.CHARGERS:
            return None
        return min(self.CHARGERS, key=lambda c: abs(c[0]-x) + abs(c[1]-y))

    def passable_cells(self) -> List[Tuple[int, int]]:
        return [(x, y) for (x, y), t in self._grid.items()
                if t not in (Terrain.WALL, Terrain.OBSTACLE)]

    def print_map(self) -> None:
        symbols = {
            Terrain.TILE:     ".",
            Terrain.CARPET:   ",",
            Terrain.WALL:     "#",
            Terrain.CHARGER:  "C",
            Terrain.OBSTACLE: "X",
        }
        for y in range(self.HEIGHT):
            print("".join(symbols[self.terrain_at(x, y)] for x in range(self.WIDTH)))
