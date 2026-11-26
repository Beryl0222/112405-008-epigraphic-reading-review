"""领域常量与无模式记录的辅助函数。

为了让 JSON 持久化和人工核对尽可能简单，工作台内部统一使用
“带固定字段的普通 dict”表示记录，而不是复杂的对象图。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

# ---- 审定/复核状态 ---------------------------------------------------------

ACTIVE = "active"
"""现行有效。"""

PENDING_REVIEW = "pending_review"
"""待复核：依赖的释读意见被撤回/改采，或资料本身自陈待核。"""

WITHDRAWN = "withdrawn"
"""专家已撤回（记录与历史仍保留）。"""

SUPERSEDED = "superseded"
"""被更新的正式采纳取代（旧采纳记录保留）。"""

MERGED_DUPLICATE = "merged_duplicate"
"""该器物编号是误建的重复器物，已并入 canonical 记录（不删除）。"""

RETRACTED = "retracted"
"""记录被明确作废（保留历史）。"""

# ---- 学术把握程度（与行政复核状态分开） -----------------------------------

CONFIRMED = "confirmed"
PROBABLE = "probable"
TENTATIVE = "tentative"

# ---- 铭文所述事件的真实性状态（与字形证据分开） ---------------------------

EVENT_UNVERIFIED = "unverified"
EVENT_CORROBORATED = "corroborated"
EVENT_DISPUTED = "disputed"

# 只有这些类别的证据可以独立支持“铭文所述事件确实发生”。
# 照片、拓片、释读意见都只是铭文/字形层面的证据，不在其中。
INDEPENDENT_EVENT_EVIDENCE_KINDS = frozenset(
    {
        "archaeological-context",  # 考古共存现象/地层/遗迹
        "independent-text",         # 独立的同时期或传世文本互证
        "material-dating",           # 独立的材质/年代检测
    }
)

DATA_NOTICE = (
    "库内全部资料均为合成样本，不对应真实人员、机构、地点或业务决定；"
    "第6行残字没有唯一确定释文，‘舟’‘周’均为保留中的候选读法。"
)

# 持久化 JSON 中的全部集合（顺序也用于稳定输出）。
COLLECTIONS: list[str] = [
    "sources",
    "people",
    "glyphs",
    "opinions",
    "evidence",
    "artifacts",
    "rubbings",
    "sites",
    "lineages",
    "persons",
    "mentions",
    "identity_rules",
    "catalogs",
    "adoptions",
    "date_claims",
    "events",
    "relations",
    "citations",
]

RELATION_KINDS = {
    "unearthed_at": "器物—出土地关系",
    "found_at": "器物—采集地点关系",
    "assigned_to_lineage": "器物—家族谱系归属",
    "same_identity": "名号称谓—谱系人物同一关系",
    "kinship": "人物—人物亲属关系",
    "dated_to": "器物—年代说法",
    "alludes_to_event": "铭文—所述事件关联",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_db(case_id: str = "epigraphy-1") -> dict[str, Any]:
    db: dict[str, Any] = {name: [] for name in COLLECTIONS}
    db["case_id"] = case_id
    db["data_notice"] = DATA_NOTICE
    db["audit"] = []
    return db


def compact_basis(items: None | str | dict | Iterable[dict | str]) -> list[dict[str, Any]]:
    """把灵活输入的依据统一成 ``[{"kind": ..., "detail": ...}]``。"""

    if items is None:
        return []
    if isinstance(items, str):
        return [{"kind": "unspecified", "detail": items}]
    if isinstance(items, dict):
        return [dict(items)]
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            out.append({"kind": "unspecified", "detail": item})
        elif isinstance(item, dict):
            entry = dict(item)
            entry.setdefault("kind", "unspecified")
            if "detail" not in entry:
                raise ValueError(f"依据条目缺少 detail：{entry!r}")
            out.append(entry)
        else:  # pragma: no cover - 防御性分支
            raise TypeError(f"无法识别的依据条目：{item!r}")
    return out
