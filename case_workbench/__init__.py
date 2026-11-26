"""case_workbench：古文字释读异文与馆藏关系审定工作台。

全部库内资料均为合成样本，不对应真实人员、机构、地点或业务决定；
系统也不提供“唯一确定释文”。
"""

from .errors import (
    WorkbenchError,
    NotFoundError,
    DuplicateIdError,
    ValidationError,
    OpinionUnavailableError,
)
from .workbench import Workbench
from .identity import resolve_persons, UnionFind

__all__ = [
    "Workbench",
    "resolve_persons",
    "UnionFind",
    "WorkbenchError",
    "NotFoundError",
    "DuplicateIdError",
    "ValidationError",
    "OpinionUnavailableError",
]

__version__ = "0.1.0"
