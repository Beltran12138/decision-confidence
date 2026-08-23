#!/usr/bin/env python3
"""Live demo, runnable from any shell.

Same two steps as ``tools/demo_okx.sh``, but ``sh`` does not exist in
PowerShell or cmd, and a demo that depends on which terminal happens to be
focused is a demo that fails in the room. This runs anywhere Python does.

    python tools/demo_okx.py

Two commands on purpose: the first is the only thing that touches the network,
the second is the product. Keeping them apart is the point — the calculation
never needs a connection.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "okx-live.jsonl")


def run(*args) -> int:
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    return subprocess.call([sys.executable, *args], cwd=ROOT, env=env)


def main() -> int:
    rc = run(os.path.join("tools", "fetch_okx.py"), "--out", CORPUS)
    if rc != 0:
        print("\n取数这一步失败了——这是唯一联网的一步。"
              "网络不通就照 slide 上的区间讲，不要重试。", file=sys.stderr)
        return rc
    return run(os.path.join("tools", "neff.py"), CORPUS)


if __name__ == "__main__":
    raise SystemExit(main())
