#!/usr/bin/env python3
"""仓库根入口，等价于 ``python3 -m case_workbench``。

示例：
    python3 main.py verify
    python3 main.py init
    python3 main.py query
    python3 main.py query --what-if 舟
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from case_workbench.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
