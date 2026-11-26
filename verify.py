#!/usr/bin/env python3
"""仓库级端到端验证脚本：运行合成场景中的全部核验点。

用法：
    python3 verify.py
退出码 0 表示全部通过，1 表示存在失败项。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from case_workbench.scenario import evaluate  # noqa: E402


def main() -> int:
    checks = evaluate()
    width = max(len(name) for name, _, _ in checks)
    failed = 0
    for name, ok, _detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name.ljust(width)}")
        if not ok:
            failed += 1
    print(f"\n{len(checks) - failed}/{len(checks)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
