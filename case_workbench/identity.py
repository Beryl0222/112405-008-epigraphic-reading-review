"""同名人合并/分开的纯逻辑。

身份规则是“有条件的”：例如“仅当 G-6 残字读作‘周’时，E12 所见名讳
与谱系人物‘周伯’为同一人”。本模块不访问持久化，只依据调用方给出的
当前读法状态做合并/拆分推演，因此研究用户可以传入“若读作舟/周”的
假设读法，而不会改动编目结论。
"""

from __future__ import annotations

from typing import Any, Callable

ReadingState = dict[str, Any]
ReadingResolver = Callable[[str], ReadingState]


class UnionFind:
    def __init__(self, nodes: list[str] | None = None):
        self.parent: dict[str, str] = {}
        for node in nodes or []:
            self.add(node)

    def add(self, node: str) -> None:
        self.parent.setdefault(node, node)

    def find(self, node: str) -> str:
        self.add(node)
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != root:
            self.parent[node], node = root, self.parent[node]
        return root

    def union(self, a: str, b: str) -> str:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra
        return ra

    def connected(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)


def _decision(rule: dict[str, Any], decision: str, reason: str,
              reading: ReadingState | None) -> dict[str, Any]:
    return {
        "rule_id": rule["id"],
        "mention_id": rule.get("mention_id"),
        "person_id": rule.get("person_id"),
        "other_endpoint": rule.get("other_endpoint"),
        "glyph_id": rule.get("glyph_id"),
        "if_reading": rule.get("if_reading"),
        "decision": decision,  # merged | split | pending | unconditional
        "reason": reason,
        "reading": _public_reading(reading),
        "basis": rule.get("basis", []),
    }


def _public_reading(reading: ReadingState | None) -> dict[str, Any] | None:
    if not reading:
        return None
    return {
        "state": reading.get("state"),
        "candidate": reading.get("candidate"),
        "opinion_id": reading.get("opinion_id"),
        "adoption_id": reading.get("adoption_id"),
        "hypothetical": bool(reading.get("hypothetical")),
        "reason": reading.get("reason"),
    }


def resolve_persons(
    *,
    mentions: list[dict[str, Any]],
    persons: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    reading_state: ReadingResolver,
) -> dict[str, Any]:
    """根据条件身份规则计算人物簇。

    返回：
    - ``decisions``：每条规则在当前读法下的判定（合并/分开/待复核）；
    - ``clusters``：并查集得到的人物/称谓簇；
    - ``pending``：是否存在因读法未定而无法判定的规则；
    - ``conflicts``：强制分开与既有合并冲突的规则。
    """

    nodes: list[str] = []
    labels: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for mention in mentions:
        mid = mention["id"]
        nodes.append(mid)
        kinds[mid] = "mention"
        labels[mid] = mention.get("label") or mid
    for person in persons:
        pid = person["id"]
        nodes.append(pid)
        kinds[pid] = "person"
        labels[pid] = person.get("name") or pid

    uf = UnionFind(nodes)
    decisions: list[dict[str, Any]] = []
    split_pairs: list[tuple[str, str, str]] = []

    for rule in rules:
        left = rule.get("mention_id") or rule.get("from_id")
        right = rule.get("person_id") or rule.get("other_endpoint") or rule.get("to_id")
        if left is None or right is None:
            continue
        uf.add(left)
        uf.add(right)
        labels.setdefault(left, left)
        labels.setdefault(right, right)
        kinds.setdefault(left, "unknown")
        kinds.setdefault(right, "unknown")

        glyph_id = rule.get("glyph_id")
        expected = rule.get("if_reading")

        # 无条件同一规则（例如已有清晰铭文或谱系内证）。
        if not glyph_id or not expected:
            uf.union(left, right)
            decisions.append(
                _decision(rule, "unconditional", "规则不依赖残字读法，直接按同一处理。", None)
            )
            continue

        state = reading_state(glyph_id)
        current = (state or {}).get("candidate")
        state_name = (state or {}).get("state", "unknown")

        if state_name in ("active", "hypothetical") and current:
            required_opinion = rule.get("via_opinion_id")
            adopted_opinion = (state or {}).get("opinion_id")
            if current == expected:
                uf.union(left, right)
                reason = f"当前{'假设' if state_name == 'hypothetical' else '编目采纳'}读法为“{current}”，满足同一条件“{expected}”。"
                if required_opinion and adopted_opinion and required_opinion != adopted_opinion:
                    reason += (
                        f"注意：规则原指定依据 {required_opinion}，"
                        f"当前读法来自 {adopted_opinion}，需编目员确认依据等效。"
                    )
                decisions.append(_decision(rule, "merged", reason, state))
            else:
                split_pairs.append((left, right, rule["id"]))
                reason = (
                    f"当前读法为“{current}”，与同一条件要求的“{expected}”不同，"
                    "按分开处理（两个名号不应合并为同一人）。"
                )
                decisions.append(_decision(rule, "split", reason, state))
        else:
            reason = (state or {}).get("reason") or (
                f"字形 {glyph_id} 尚无有效采纳读法（状态：{state_name}），"
                "合并/分开必须挂起为待复核。"
            )
            decisions.append(_decision(rule, "pending", reason, state))

    conflicts: list[dict[str, Any]] = []
    for left, right, rule_id in split_pairs:
        if uf.connected(left, right):
            conflicts.append(
                {
                    "rule_id": rule_id,
                    "between": [left, right],
                    "reason": "其他规则已将这两个端点合并，与本条“分开”结论冲突，需人工审定。",
                }
            )

    groups: dict[str, list[str]] = {}
    for node in uf.parent:
        groups.setdefault(uf.find(node), []).append(node)

    clusters: list[dict[str, Any]] = []
    for root, members in sorted(groups.items(), key=lambda kv: kv[0]):
        member_info = [
            {"id": m, "kind": kinds.get(m, "unknown"), "label": labels.get(m, m)}
            for m in sorted(members)
        ]
        clusters.append(
            {
                "cluster_id": root,
                "members": member_info,
                "labels": [labels.get(m, m) for m in sorted(members)],
            }
        )

    return {
        "clusters": clusters,
        "decisions": decisions,
        "conflicts": conflicts,
        "pending": [d for d in decisions if d["decision"] == "pending"],
        "notice": "人物合并/分开是条件性推演，不代表存在唯一确定的释文或历史结论。",
    }
