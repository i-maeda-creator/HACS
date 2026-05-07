"""
Layer1 Bridge — 複数 EdgeRuntime をまとめて Layer2(MQTT) に接続する橋渡し。
MQTT が不在でもスタンドアロンで動作する。
"""
from __future__ import annotations
import json
import random
from typing import Dict, List, Optional

from layer0.core.agent import AgentRole, AgentStatus
from layer0.schemas.command import Command, cmd_move, cmd_charge
from layer1.mapping.home_map import HomeMap
from layer1.physical.battery import Battery
from layer1.physical.robot import PhysicalRobot
from layer1.runtime.edge_runtime import EdgeRuntime


# ── ロボットのデフォルト配置 ─────────────────────────────────────────────────
DEFAULT_ROBOTS = [
    # (robot_id, role, start_x, start_y)
    ("robot_w1", AgentRole.WORKER,   2,  2),
    ("robot_w2", AgentRole.WORKER,   7,  2),
    ("robot_w3", AgentRole.WORKER,   2,  7),
    ("robot_g1", AgentRole.GUARDIAN, 12, 2),
    ("robot_g2", AgentRole.GUARDIAN, 17, 7),
    ("robot_t1", AgentRole.TRADER,   12, 7),
    ("robot_o1", AgentRole.OBSERVER, 2,  13),
    ("robot_gv", AgentRole.GOVERNOR, 12, 13),
    ("robot_w4", AgentRole.WORKER,   7,  13),
    ("robot_t2", AgentRole.TRADER,   17, 13),
]


class Layer1Bridge:
    """
    全 EdgeRuntime を統括し、Layer2 との MQTT 通信を仲介する。
    MQTT クライアントはオプション — なければスタンドアロン動作。
    """

    def __init__(self, seed: int = 42,
                 robot_specs: Optional[list] = None,
                 mqtt_client=None) -> None:
        self.home_map = HomeMap()
        self.rng = random.Random(seed)
        self.mqtt = mqtt_client
        self.tick = 0
        self.runtimes: Dict[str, EdgeRuntime] = {}
        self._all_events = []

        specs = robot_specs or DEFAULT_ROBOTS
        for (rid, role, sx, sy) in specs:
            robot = PhysicalRobot(
                robot_id=rid,
                role=role,
                x=sx, y=sy,
                battery=Battery(level=self.rng.uniform(60, 100)),
            )
            rt = EdgeRuntime(robot, self.home_map, random.Random(self.rng.randint(0, 9999)))
            self.runtimes[rid] = rt

    # ── シミュレーションループ ────────────────────────────────────────────────

    def step(self, autonomous: bool = True) -> List[dict]:
        """全ロボットを1 tick 進める。発生したテレメトリを返す。"""
        self.tick += 1
        tick_telemetry = []

        # 低バッテリー → 充電コマンド優先
        self._auto_charge_low_robots()

        # 自律モード：アイドル中のロボットにランダム移動目標を与える
        if autonomous:
            self._autonomous_dispatch()

        for rt in self.runtimes.values():
            events = rt.tick()
            for ev in events:
                ev_dict = ev.model_dump()
                self._all_events.append(ev_dict)
                self._publish_mqtt(ev.mqtt_topic, ev_dict)
            tick_telemetry.append(rt.telemetry())

        return tick_telemetry

    def _autonomous_dispatch(self) -> None:
        """命令がないアイドルロボットへランダム移動を発行（Layer3未接続時のテスト用）。"""
        from layer0.schemas.command import cmd_move
        from layer0.core.agent import AgentStatus
        passable = self.home_map.passable_cells()
        for rt in self.runtimes.values():
            robot = rt.robot
            if (robot.status == AgentStatus.IDLE
                    and not robot._cmd_queue
                    and not robot.battery.is_low()):
                tx, ty = self.rng.choice(passable)
                cmd = cmd_move(robot.robot_id, tx, ty, tick=self.tick, requested_by="autonomous")
                rt.receive_command(cmd)

    def run(self, ticks: int, verbose: bool = True) -> None:
        print(f"=== Layer1 Physical Simulation - {len(self.runtimes)} robots / {ticks} ticks ===")
        self.home_map.print_map()
        print()

        for _ in range(ticks):
            telemetry = self.step(autonomous=True)

            if verbose and self.tick % 10 == 0:
                self._print_status(telemetry)

        print()
        self._print_summary()

    def _auto_charge_low_robots(self) -> None:
        """バッテリー15%未満のロボットへ充電コマンドを自動発行。"""
        for rt in self.runtimes.values():
            robot = rt.robot
            if robot.battery.is_low(15.0) and robot.status != AgentStatus.CHARGING:
                cmd = cmd_charge(robot.robot_id, tick=self.tick)
                rt.receive_command(cmd)

    # ── MQTT ─────────────────────────────────────────────────────────────────

    def _publish_mqtt(self, topic: str, payload: dict) -> None:
        if self.mqtt:
            try:
                self.mqtt.publish(topic, json.dumps(payload))
            except Exception:
                pass  # MQTT 不在でも続行

    def send_command(self, robot_id: str, cmd: Command) -> bool:
        """外部からコマンドを特定ロボットへ送信。"""
        rt = self.runtimes.get(robot_id)
        if rt is None:
            return False
        rt.receive_command(cmd)
        return True

    # ── レポート ──────────────────────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        return {
            "tick": self.tick,
            "robots": [rt.telemetry() for rt in self.runtimes.values()],
            "total_events": len(self._all_events),
        }

    def _print_status(self, telemetry: list) -> None:
        print(f"\n[Tick {self.tick:3d}]")
        for t in telemetry:
            bar = "=" * int(t["battery_pct"] / 10) + "-" * (10 - int(t["battery_pct"] / 10))
            failure = f" [FAIL:{t['failure_mode']}]" if t["failure_mode"] != "none" else ""
            print(f"  {t['robot_id']:10s} [{t['role']:8s}] "
                  f"({t['x']:2d},{t['y']:2d}) {bar} {t['battery_pct']:5.1f}%"
                  f"  {t['status']:8s}  {t['room'] or '?':7s}{failure}")

    def _print_summary(self) -> None:
        print("=== Summary ===")
        snap = self.get_snapshot()
        print(f"Total ticks : {snap['tick']}")
        print(f"Total events: {snap['total_events']}")
        print()
        for t in snap["robots"]:
            print(f"  {t['robot_id']:10s}  battery={t['battery_pct']:5.1f}%"
                  f"  health={t['battery_health']:.3f}"
                  f"  cycles={t['charge_cycles']:3d}"
                  f"  odometer={t['odometer']:6.1f} cells"
                  f"  failure={t['failure_mode']}")
