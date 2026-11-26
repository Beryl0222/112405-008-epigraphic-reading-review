"""工作台的异常类型。"""


class WorkbenchError(Exception):
    """所有工作台错误的基类。"""


class NotFoundError(WorkbenchError, KeyError):
    """引用了不存在的记录编号。"""

    def __init__(self, record_id: str):
        super().__init__(f"记录不存在：{record_id}")
        self.record_id = record_id


class DuplicateIdError(WorkbenchError):
    """同一编号被重复登记。"""

    def __init__(self, record_id: str):
        super().__init__(f"记录编号重复：{record_id}")
        self.record_id = record_id


class ValidationError(WorkbenchError, ValueError):
    """登记内容不满足审定规则。"""


class OpinionUnavailableError(ValidationError):
    """释读意见已撤回或已被取代，不能据此直接定论。"""
