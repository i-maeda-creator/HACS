"""
Layer1 エントリポイント — 物理シミュレーションのスタンドアロン実行。
"""
import sys
sys.path.insert(0, ".")

from layer1.bridge import Layer1Bridge


def main():
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    bridge = Layer1Bridge(seed=42)
    bridge.run(ticks=ticks, verbose=True)


if __name__ == "__main__":
    main()
