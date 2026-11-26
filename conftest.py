"""让 pytest 从仓库根导入 case_workbench（unittest discover 不依赖此文件）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
