"""工作台核心：承接原始记录、释读意见、编目与关系，并维护审定轨迹。

设计要点（对应任务要求）：

1. 残字按“字形位置”登记，候选读法（舟/周）与历次意见全部保留；
2. 编目采纳必须指向具体释读意见或显式依据，并快照其可信依据，
   不允许把不确定释读静默改写成定论；
3. 器物有别名/误建重复器物时做“合并指向”，旧编号与历史不删除；
4. 每条关系（出土地、谱系、身份、年代、事件）都携带所采用的读法与依据；
5. 专家撤回意见会沿 “意见 -> 采纳 -> 关系 -> 引用” 的依赖链
   把有效记录置为 ``pending_review``，只追加历史、不删除记录；
6. 照片只增加可见字形证据，不存在任何由照片自动证实事件的路径。
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Iterable

from .errors import (
    DuplicateIdError,
    NotFoundError,
    OpinionUnavailableError,
    ValidationError,
)
from .identity import resolve_persons as _resolve_persons
from .models import (
    ACTIVE,
    CONFIRMED,
    DATA_NOTICE,
    EVENT_UNVERIFIED,
    INDEPENDENT_EVENT_EVIDENCE_KINDS,
    MERGED_DUPLICATE,
    PENDING_REVIEW,
    RETRACTED,
    SUPERSEDED,
    WITHDRAWN,
    COLLECTIONS,
    compact_basis,
    new_db,
    utc_now,
)


class Workbench:
    def __init__(self, data: dict[str, Any] | None = None, clock: Callable[[], str] | None = None):
        self.db: dict[str, Any] = data if data is not None else new_db()
        for name in COLLECTIONS:
            self.db.setdefault(name, [])
        self.db.setdefault("audit", [])
        self.db.setdefault("case_id", "epigraphy-1")
        self.db.setdefault("data_notice", DATA_NOTICE)
        self._clock = clock or utc_now
        self._index: dict[str, tuple[str, dict[str, Any]]] = {}
        for collection in COLLECTIONS:
            for record in self.db[collection]:
                self._index_record(collection, record)

    # ------------------------------------------------------------------ utils

    def now(self, at: str | None = None) -> str:
        return at or self._clock()

    def _index_record(self, collection: str, record: dict[str, Any]) -> None:
        rid = record.get("id")
        if rid is not None:
            self._index[rid] = (collection, record)

    def _put(self, collection: str, record: dict[str, Any], rtype: str | None = None) -> dict[str, Any]:
        rid = record.get("id")
        if not rid:
            raise ValidationError("所有记录必须包含非空 id")
        if rid in self._index:
            raise DuplicateIdError(rid)
        record.setdefault("type", rtype or collection.rstrip("s"))
        record.setdefault("status", ACTIVE)
        record.setdefault("created_at", self.now())
        record.setdefault("history", [])
        self.db[collection].append(record)
        self._index_record(collection, record)
        return record

    def get(self, record_id: str) -> dict[str, Any]:
        if record_id not in self._index:
            raise NotFoundError(record_id)
        return self._index[record_id][1]

    def collection_of(self, record_id: str) -> str:
        return self._index[record_id][0]

    def has(self, record_id: str) -> bool:
        return record_id in self._index

    def all(self, collection: str) -> list[dict[str, Any]]:
        return self.db[collection]

    def label_of(self, record_id: str) -> str:
        if record_id is None:
            return "—"
        if record_id not in self._index:
            return record_id
        rec = self.get(record_id)
        for key in ("name", "label", "title", "work"):
            value = rec.get(key)
            if value:
                return str(value)
        if rec.get("type") == "relation":
            return f"{rec.get('kind_label', rec.get('kind'))}（{rec['from_id']}→{rec['to_id']}）"
        text = rec.get("text")
        if text:
            return text if len(text) <= 24 else text[:23] + "…"
        return record_id

    def _audit(self, action: str, detail: str, *, by: str | None = None,
               at: str | None = None, **extra: Any) -> None:
        entry = {
            "seq": len(self.db["audit"]) + 1,
            "at": self.now(at),
            "action": action,
            "detail": detail,
            "by": by,
        }
        entry.update(extra)
        self.db["audit"].append(entry)

    def _history(self, record: dict[str, Any], action: str, detail: str,
                 *, at: str | None = None, by: str | None = None) -> None:
        record.setdefault("history", []).append(
            {"at": self.now(at), "action": action, "detail": detail, "by": by}
        )

    def next_id(self, prefix: str) -> str:
        max_n = 0
        for rid in self._index:
            if rid.startswith(prefix + "-"):
                tail = rid[len(prefix) + 1:]
                if tail.isdigit():
                    max_n = max(max_n, int(tail))
        return f"{prefix}-{max_n + 1}"

    # ------------------------------------------------------------ persistence

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.db)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.db, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workbench":
        return cls(data=deepcopy(data))

    @classmethod
    def load(cls, path: str | Path) -> "Workbench":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data=data)

    # ---------------------------------------------------------- source records

    def add_source(self, source_id: str, text: str, *, kind: str | None = None,
                   source: str | None = None, **extra: Any) -> dict[str, Any]:
        if not text or not text.strip():
            raise ValidationError(f"原始记录 {source_id} 的 text 不能为空")
        record = {"id": source_id, "text": text, "kind": kind, "source": source}
        record.update(extra)
        return self._put("sources", record, "source")

    def load_case_json(self, path: str | Path) -> list[dict[str, Any]]:
        """读取 ``data/case.json`` 中的稳定原始记录；重复执行不重复导入。"""

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.db["case_id"] = payload.get("case_id", self.db["case_id"])
        imported: list[dict[str, Any]] = []
        for raw in payload.get("records", []):
            rid = raw["id"]
            if self.has(rid):
                continue
            imported.append(
                self.add_source(
                    rid,
                    raw["text"],
                    kind=raw.get("kind"),
                    source=raw.get("source"),
                )
            )
        self._audit("load_case_json", f"从 {path} 导入 {len(imported)} 条原始记录")
        return imported

    # ---------------------------------------------------------------- people

    def add_person(self, person_id: str, name: str, *, role: str = "paleographer",
                   note: str | None = None) -> dict[str, Any]:
        return self._put(
            "people",
            {"id": person_id, "name": name, "role": role, "note": note},
            "person_record",
        )

    # ----------------------------------------------------------- glyph & co

    def add_glyph(self, glyph_id: str, label: str, *,
                  artifact_id: str | None = None, rubbing_id: str | None = None,
                  line: int | None = None, column: int | None = None,
                  coordinates: dict[str, Any] | None = None,
                  note: str = "", candidates: Iterable[str] | None = None) -> dict[str, Any]:
        candidate_list: list[str] = []
        for c in candidates or []:
            if c not in candidate_list:
                candidate_list.append(c)
        record = {
            "id": glyph_id,
            "label": label,
            "artifact_id": artifact_id,
            "rubbing_id": rubbing_id,
            "line": line,
            "column": column,
            "coordinates": coordinates,
            "note": note,
            "candidates": candidate_list,
        }
        return self._put("glyphs", record, "glyph_position")

    def add_candidate_reading(self, glyph_id: str, candidate: str, *,
                              note: str | None = None) -> dict[str, Any]:
        glyph = self.get(glyph_id)
        if candidate not in glyph["candidates"]:
            glyph["candidates"].append(candidate)
            self._history(glyph, "add_candidate", f"新增候选读法“{candidate}”：{note or ''}")
        return glyph

    def add_opinion(self, opinion_id: str, glyph_id: str, reading: str, *,
                    expert_id: str, confidence: str = "low",
                    basis: Iterable[dict[str, Any] | str] | None = None,
                    expressed_at: str | None = None,
                    source_record_id: str | None = None,
                    note: str | None = None) -> dict[str, Any]:
        glyph = self.get(glyph_id)
        expert = self.get(expert_id)
        if reading not in glyph["candidates"]:
            # 新意见可以提出新候选，但候选序列必须显式保留它。
            glyph["candidates"].append(reading)
            self._history(glyph, "add_candidate", f"意见 {opinion_id} 提出新候选“{reading}”")
        record = {
            "id": opinion_id,
            "glyph_id": glyph_id,
            "reading": reading,
            "expert_id": expert_id,
            "expert_name": expert.get("name", expert_id),
            "confidence": confidence,
            "basis": compact_basis(basis),
            "expressed_at": self.now(expressed_at),
            "source_record_id": source_record_id,
            "note": note,
            "status": ACTIVE,
        }
        return self._put("opinions", record, "opinion")

    def add_evidence(self, evidence_id: str, kind: str, label: str, *,
                     glyph_id: str | None = None,
                     observed_traits: Iterable[str] | None = None,
                     source_ref: str | None = None,
                     independent: bool = False,
                     added_at: str | None = None,
                     note: str | None = None) -> dict[str, Any]:
        if glyph_id is not None:
            self.get(glyph_id)
        record = {
            "id": evidence_id,
            "kind": kind,  # rubbing | photo | inspection | archaeological-context | ...
            "label": label,
            "glyph_id": glyph_id,
            "observed_traits": list(observed_traits or []),
            "source_ref": source_ref,
            "independent": independent or kind in INDEPENDENT_EVENT_EVIDENCE_KINDS,
            "added_at": self.now(added_at),
            "note": note,
        }
        rec = self._put("evidence", record, "evidence")
        if glyph_id:
            glyph = self.get(glyph_id)
            self._history(
                glyph,
                "evidence_added",
                f"新增{kind}证据 {evidence_id}：{label}（只改变可见字形证据）",
                at=added_at,
            )
        self._audit("evidence_added", f"{evidence_id}({kind}) -> {glyph_id}")
        return rec

    def add_photo(self, evidence_id: str, label: str, *, glyph_id: str | None = None,
                  observed_traits: Iterable[str] | None = None,
                  source_ref: str | None = None,
                  added_at: str | None = None) -> dict[str, Any]:
        """新增照片。注意：本方法只登记可见字形证据，不触碰任何事件真实性状态。"""

        photo = self.add_evidence(
            evidence_id,
            "photo",
            label,
            glyph_id=glyph_id,
            observed_traits=observed_traits,
            source_ref=source_ref,
            added_at=added_at,
        )
        # 显式审计：照片入库不会自动改写 event_claims。
        self._audit(
            "photo_evidence_only",
            f"照片 {evidence_id} 仅更新可见字形证据；不会自动证实铭文所述事件。",
            at=added_at,
        )
        return photo

    # ------------------------------------------------------- artifacts etc.

    def add_artifact(self, artifact_id: str, name: str, *,
                     registration_no: str | None = None,
                     aliases: Iterable[str] | None = None,
                     note: str | None = None) -> dict[str, Any]:
        alias_list = list(dict.fromkeys(aliases or []))
        if registration_no and registration_no not in alias_list:
            alias_list.append(registration_no)
        return self._put(
            "artifacts",
            {
                "id": artifact_id,
                "name": name,
                "registration_no": registration_no,
                "aliases": alias_list,
                "note": note,
            },
            "artifact",
        )

    def find_artifact(self, identifier: str) -> dict[str, Any] | None:
        """按主 id 或旧/新登记号等别名定位器物；优先返回有效（未合并）记录。"""

        direct: dict[str, Any] | None = None
        if self.has(identifier):
            rec = self.get(identifier)
            if rec.get("type") == "artifact":
                direct = rec
        matches: list[dict[str, Any]] = []
        for art in self.db["artifacts"]:
            if identifier == art["id"] or identifier in art.get("aliases", []):
                matches.append(art)
            elif identifier == art.get("registration_no"):
                matches.append(art)
        if direct is not None and direct not in matches:
            matches.insert(0, direct)
        if not matches:
            return None
        for art in matches:
            if art.get("status") != MERGED_DUPLICATE:
                return art
        return matches[0]

    def resolve_artifact_id(self, identifier: str) -> str:
        art = self.find_artifact(identifier)
        if art is None:
            raise NotFoundError(identifier)
        if art.get("status") == MERGED_DUPLICATE and art.get("duplicate_of"):
            return art["duplicate_of"]
        return art["id"]

    def register_alias(self, artifact_id: str, alias: str, *,
                       by: str | None = None, at: str | None = None) -> dict[str, Any]:
        art = self.get(artifact_id)
        if alias not in art.setdefault("aliases", []):
            art["aliases"].append(alias)
            self._history(art, "alias_added", f"登记别名/旧新编号 {alias}", by=by, at=at)
            self._audit("alias_added", f"{alias} -> {artifact_id}", by=by, at=at)
        return art

    def merge_artifacts(self, mistaken_id: str, canonical_id: str, *,
                        by: str | None = None, reason: str = "后到拓片被误建为新器物",
                        at: str | None = None) -> dict[str, Any]:
        """把误建器物 ``mistaken_id`` 并入 ``canonical_id``。

        不删除任何记录：误建器物保留为 ``merged_duplicate``，拓片、编目卡、
        关系端点被重新指向 canonical，并各自留下改指历史。
        """

        mistaken = self.get(mistaken_id)
        canonical = self.get(canonical_id)
        if mistaken_id == canonical_id:
            raise ValidationError("不能把器物并入自身")
        if mistaken.get("type") != "artifact" or canonical.get("type") != "artifact":
            raise ValidationError("merge_artifacts 仅接受器物记录")

        ts = self.now(at)
        mistaken["status"] = MERGED_DUPLICATE
        mistaken["duplicate_of"] = canonical_id
        mistaken["merged_at"] = ts
        mistaken["merged_by"] = by
        mistaken["merge_reason"] = reason
        self._history(mistaken, "merged_duplicate", f"并入 {canonical_id}：{reason}", at=ts, by=by)

        for alias in [mistaken_id, *mistaken.get("aliases", [])]:
            self.register_alias(canonical_id, alias, by=by, at=ts)

        repointed: dict[str, list[str]] = {"rubbings": [], "catalogs": [], "relations": []}
        for rubbing in self.db["rubbings"]:
            if rubbing.get("artifact_id") == mistaken_id:
                rubbing["artifact_id"] = canonical_id
                repointed["rubbings"].append(rubbing["id"])
                self._history(rubbing, "artifact_repointed",
                              f"误建器物 {mistaken_id} 已并入 {canonical_id}，拓片改挂 canonical", at=ts, by=by)
        for catalog in self.db["catalogs"]:
            if catalog.get("artifact_id") == mistaken_id:
                catalog["artifact_id"] = canonical_id
                repointed["catalogs"].append(catalog["id"])
                self._history(catalog, "artifact_repointed", "编目卡随器物合并改指", at=ts, by=by)
        for relation in self.db["relations"]:
            changed = False
            for endpoint in ("from_id", "to_id"):
                if relation.get(endpoint) == mistaken_id:
                    relation[endpoint] = canonical_id
                    changed = True
            if changed:
                repointed["relations"].append(relation["id"])
                self._history(relation, "endpoint_repointed",
                              f"关系端点因器物合并由 {mistaken_id} 改指 {canonical_id}；原结论需编目员留意",
                              at=ts, by=by)
                # 身份合并可能影响既有关系的把握程度：置为待复核而不是静默保留。
                self._ensure_issue(
                    relation,
                    code=f"artifact-merge:{mistaken_id}",
                    kind="dependency",
                    reason=f"关系端点来自被纠正的误建器物 {mistaken_id}，需确认改指后结论仍成立。",
                    at=ts, by=by,
                )
                self._recompute_status(relation, at=ts, by=by)

        self._audit(
            "artifact_merged",
            f"{mistaken_id} -> {canonical_id}；改指 {repointed}",
            by=by, at=ts, repointed=repointed, reason=reason,
        )
        # 关系可能已因合并被置待复核；向上同步引用状态。
        self.reconcile_review_state(at=ts, by=by)
        return {"mistaken_id": mistaken_id, "canonical_id": canonical_id, "repointed": repointed}

    def add_rubbing(self, rubbing_id: str, label: str, *,
                    artifact_id: str | None = None,
                    description: str = "",
                    source_record_id: str | None = None,
                    later_rubbing: bool = False) -> dict[str, Any]:
        if artifact_id is not None:
            self.get(artifact_id)
        return self._put(
            "rubbings",
            {
                "id": rubbing_id,
                "label": label,
                "artifact_id": artifact_id,
                "description": description,
                "source_record_id": source_record_id,
                "later_rubbing": later_rubbing,
            },
            "rubbing",
        )

    def add_site(self, site_id: str, name: str, *, note: str = "") -> dict[str, Any]:
        return self._put("sites", {"id": site_id, "name": name, "note": note}, "site")

    def add_lineage(self, lineage_id: str, name: str, *, note: str = "") -> dict[str, Any]:
        return self._put("lineages", {"id": lineage_id, "name": name, "note": note}, "lineage")

    def add_person_entity(self, person_id: str, name: str, *,
                          lineage_id: str | None = None, note: str = "") -> dict[str, Any]:
        if lineage_id:
            self.get(lineage_id)
        return self._put(
            "persons",
            {"id": person_id, "name": name, "lineage_id": lineage_id, "note": note},
            "genealogy_person",
        )

    def add_mention(self, mention_id: str, label: str, *,
                    artifact_id: str | None = None,
                    glyph_id: str | None = None,
                    note: str = "") -> dict[str, Any]:
        if glyph_id:
            self.get(glyph_id)
        return self._put(
            "mentions",
            {"id": mention_id, "label": label, "artifact_id": artifact_id,
             "glyph_id": glyph_id, "note": note},
            "name_mention",
        )

    def add_identity_rule(self, rule_id: str, mention_id: str, person_id: str, *,
                          glyph_id: str | None = None, if_reading: str | None = None,
                          via_opinion_id: str | None = None,
                          basis: Iterable[dict[str, Any] | str] | None = None) -> dict[str, Any]:
        self.get(mention_id)
        self.get(person_id)
        if glyph_id:
            self.get(glyph_id)
        if via_opinion_id:
            self.get(via_opinion_id)
        return self._put(
            "identity_rules",
            {
                "id": rule_id,
                "mention_id": mention_id,
                "person_id": person_id,
                "glyph_id": glyph_id,
                "if_reading": if_reading,
                "via_opinion_id": via_opinion_id,
                "basis": compact_basis(basis),
            },
            "identity_rule",
        )

    def add_catalog(self, catalog_id: str, artifact_id: str, title: str, *,
                    cataloger_id: str | None = None,
                    fields: dict[str, Any] | None = None) -> dict[str, Any]:
        self.get(artifact_id)
        return self._put(
            "catalogs",
            {
                "id": catalog_id,
                "artifact_id": artifact_id,
                "title": title,
                "cataloger_id": cataloger_id,
                "fields": fields or {},
            },
            "catalog",
        )

    def add_date_claim(self, date_id: str, label: str, *, artifact_id: str | None = None,
                       basis: Iterable[dict[str, Any] | str] | None = None) -> dict[str, Any]:
        return self._put(
            "date_claims",
            {"id": date_id, "label": label, "artifact_id": artifact_id, "basis": compact_basis(basis)},
            "date_claim",
        )

    def add_event_claim(self, event_id: str, label: str, *,
                        source_record_id: str | None = None,
                        note: str = "") -> dict[str, Any]:
        return self._put(
            "events",
            {
                "id": event_id,
                "label": label,
                "occurrence_status": EVENT_UNVERIFIED,
                "evidence_ids": [],
                "source_record_id": source_record_id,
                "note": note,
            },
            "event_claim",
        )

    def corroborate_event(self, event_id: str, evidence_id: str, *,
                          by: str | None = None, at: str | None = None,
                          note: str | None = None) -> dict[str, Any]:
        """用*独立于铭文/照片*的证据支持事件真实性。

        照片、拓片、释读意见一律被拒绝：它们只能改变字形层面的判断。
        """

        event = self.get(event_id)
        evidence = self.get(evidence_id)
        kind = evidence.get("kind")
        if kind not in INDEPENDENT_EVENT_EVIDENCE_KINDS and not evidence.get("independent"):
            raise ValidationError(
                f"证据 {evidence_id} 类型为 {kind}，属于字形/铭文层面材料；"
                "新照片不能自动证明铭文所述事件真实发生，需要考古或独立文本等独立证据。"
            )
        if evidence_id not in event["evidence_ids"]:
            event["evidence_ids"].append(evidence_id)
        event["occurrence_status"] = "corroborated"
        self._history(event, "corroborated",
                      f"依据独立证据 {evidence_id}（{kind}）标记为可佐证：{note or ''}",
                      by=by, at=at)
        self._audit("event_corroborated", f"{event_id} by {evidence_id}", by=by, at=at)
        return event

    # ------------------------------------------------------------- adoption

    def _reading_snapshot_from_opinion(self, opinion: dict[str, Any]) -> dict[str, Any]:
        expert = None
        if self.has(opinion["expert_id"]):
            expert = self.get(opinion["expert_id"])
        return {
            "glyph_id": opinion["glyph_id"],
            "candidate": opinion["reading"],
            "opinion_id": opinion["id"],
            "expert_id": opinion["expert_id"],
            "expert_name": (expert or {}).get("name", opinion.get("expert_name")),
            "expressed_at": opinion.get("expressed_at"),
            "confidence": opinion.get("confidence"),
            "basis": deepcopy(opinion.get("basis", [])),
            "opinion_status": opinion.get("status", ACTIVE),
        }

    def adopt_reading(self, adoption_id: str, catalog_id: str, glyph_id: str,
                      opinion_id: str, *, by: str | None = None,
                      at: str | None = None, note: str | None = None) -> dict[str, Any]:
        """编目卡正式采纳某条释读意见（必须指向仍有效的意见）。"""

        catalog = self.get(catalog_id)
        glyph = self.get(glyph_id)
        opinion = self.get(opinion_id)
        if opinion.get("type") != "opinion":
            raise ValidationError(f"{opinion_id} 不是释读意见")
        if opinion["glyph_id"] != glyph_id:
            raise ValidationError("释读意见与字形位置不匹配")
        if opinion["status"] == WITHDRAWN:
            raise OpinionUnavailableError(
                f"释读意见 {opinion_id} 已撤回，不能被采纳为定论；请依据新的有效意见重新审定。"
            )
        if opinion["status"] == SUPERSEDED:
            raise OpinionUnavailableError(f"释读意见 {opinion_id} 已被更新意见取代，不能直接采纳。")

        ts = self.now(at)
        # 同一编目卡+字形只允许一个现行采纳；旧采纳保留为 superseded，
        # 依赖它的关系不会被静默改写，而是进入待复核。
        for old in self.db["adoptions"]:
            if (old.get("catalog_id") == catalog_id and old.get("glyph_id") == glyph_id
                    and old["status"] == ACTIVE and old["id"] != adoption_id):
                old["status"] = SUPERSEDED
                old["superseded_by"] = adoption_id
                self._history(old, "superseded", f"被新的采纳 {adoption_id} 取代", at=ts, by=by)

        snapshot = self._reading_snapshot_from_opinion(opinion)
        adoption = {
            "id": adoption_id,
            "catalog_id": catalog_id,
            "catalog_title": catalog.get("title"),
            "glyph_id": glyph_id,
            "glyph_label": glyph.get("label"),
            "opinion_id": opinion_id,
            "reading": opinion["reading"],
            "reading_snapshot": snapshot,
            "adopted_by": by,
            "adopted_at": ts,
            "note": note,
            "review_issues": [],
        }
        rec = self._put("adoptions", adoption, "reading_adoption")
        self._history(rec, "adopted", f"采纳 {opinion_id} 的“{opinion['reading']}”读", at=ts, by=by)
        self._audit("reading_adopted",
                    f"{catalog_id}/{glyph_id} -> {opinion_id}（{opinion['reading']}）", by=by, at=ts)
        self.reconcile_review_state(at=ts, by=by)
        return rec

    # ------------------------------------------------------------ relations

    def add_relation(self, relation_id: str, kind: str, from_id: str, to_id: str, *,
                     adoption_id: str | None = None,
                     opinion_id: str | None = None,
                     glyph_id: str | None = None,
                     candidate: str | None = None,
                     certainty: str = "probable",
                     basis: Iterable[dict[str, Any] | str] | None = None,
                     source_record_ids: Iterable[str] | None = None,
                     scope: str | None = None,
                     status: str = ACTIVE,
                     review_issues: Iterable[dict[str, Any]] | None = None,
                     by: str | None = None,
                     at: str | None = None) -> dict[str, Any]:
        if not self.has(from_id):
            raise NotFoundError(from_id)
        if not self.has(to_id):
            raise NotFoundError(to_id)

        reading_block: dict[str, Any] | None = None
        final_adoption_id = adoption_id
        final_opinion_id = opinion_id
        final_glyph_id = glyph_id

        if adoption_id:
            adoption = self.get(adoption_id)
            if adoption.get("type") != "reading_adoption":
                raise ValidationError(f"{adoption_id} 不是释读采纳记录")
            snap = deepcopy(adoption["reading_snapshot"])
            snap["adoption_id"] = adoption_id
            snap["adoption_status"] = adoption["status"]
            snap["adopted_by"] = adoption.get("adopted_by")
            snap["adopted_at"] = adoption.get("adopted_at")
            reading_block = snap
            final_opinion_id = adoption["opinion_id"]
            final_glyph_id = adoption["glyph_id"]
        elif opinion_id:
            opinion = self.get(opinion_id)
            if opinion["status"] == WITHDRAWN:
                raise OpinionUnavailableError(f"不能依据已撤回意见 {opinion_id} 新建有效关系")
            reading_block = self._reading_snapshot_from_opinion(opinion)
            final_glyph_id = opinion["glyph_id"]
        elif candidate is not None:
            if not glyph_id:
                raise ValidationError("直接指定候选读法时必须给出 glyph_id（字形位置）")
            glyph = self.get(glyph_id)
            if candidate not in glyph.get("candidates", []):
                raise ValidationError(
                    f"候选“{candidate}”不在字形 {glyph_id} 的保留候选 {glyph.get('candidates')} 中；"
                    "不允许凭空写入定论。"
                )
            extra_basis = compact_basis(basis)
            if not extra_basis:
                raise ValidationError(
                    "关系直接采用候选读法但没有指向释读意见时，必须给出显式可信依据；"
                    "禁止把不确定释读静默替换成定论。"
                )
            reading_block = {
                "glyph_id": glyph_id,
                "candidate": candidate,
                "opinion_id": None,
                "adoption_id": None,
                "hypothesis_only": True,
                "basis": extra_basis,
                "note": "未经编目正式采纳的直接写法，候选分歧仍保留，查询时必须显式展示。",
            }
        # else: 不依赖释读的关系（如出土地），reading_block 为 None。

        record = {
            "id": relation_id,
            "kind": kind,
            "kind_label": self._relation_kind_label(kind),
            "from_id": from_id,
            "to_id": to_id,
            "reading": reading_block,
            "adoption_id": final_adoption_id,
            "opinion_id": final_opinion_id,
            "glyph_id": final_glyph_id,
            "certainty": certainty,
            "basis": compact_basis(basis),
            "source_record_ids": list(source_record_ids or []),
            "scope": scope,
            "review_issues": [],
        }
        rec = self._put("relations", record, "relation")
        if status == PENDING_REVIEW:
            rec["status"] = PENDING_REVIEW
        for issue in review_issues or []:
            issue = dict(issue)
            issue.setdefault("open", True)
            issue.setdefault("at", self.now(at))
            issue.setdefault("kind", "scholarly")
            rec["review_issues"].append(issue)
        if rec["review_issues"]:
            rec["status"] = PENDING_REVIEW
        self._history(rec, "created", f"建立关系 {kind}: {from_id} -> {to_id}", by=by, at=at)
        return rec

    @staticmethod
    def _relation_kind_label(kind: str) -> str:
        from .models import RELATION_KINDS
        return RELATION_KINDS.get(kind, kind)

    # ------------------------------------------------------------ citations

    def add_citation(self, citation_id: str, researcher: str, work: str,
                     target_ids: Iterable[str], *, statement: str = "",
                     at: str | None = None) -> dict[str, Any]:
        targets = list(target_ids)
        if not targets:
            raise ValidationError("引用至少要指向一条关系或采纳记录")
        for tid in targets:
            if not self.has(tid):
                raise NotFoundError(tid)
        citation = {
            "id": citation_id,
            "researcher": researcher,
            "work": work,
            "target_ids": targets,
            "statement": statement,
            "cited_at": self.now(at),
            "review_issues": [],
        }
        rec = self._put("citations", citation, "citation")
        self._history(rec, "created", f"建立引用，指向 {targets}", at=at)
        self.reconcile_review_state()
        return rec

    # ------------------------------------------------- review issue machinery

    def _ensure_issue(self, record: dict[str, Any], *, code: str, kind: str,
                      reason: str, at: str | None = None, by: str | None = None) -> bool:
        for issue in record.setdefault("review_issues", []):
            if issue.get("code") == code and issue.get("open", True):
                return False
        issue = {
            "code": code,
            "kind": kind,  # dependency | scholarly
            "reason": reason,
            "at": self.now(at),
            "by": by,
            "open": True,
        }
        record["review_issues"].append(issue)
        self._history(record, "review_issue_raised", f"[{code}] {reason}", at=at, by=by)
        return True

    def _close_issues(self, record: dict[str, Any], *, prefixes: tuple[str, ...] = (),
                      codes: Iterable[str] = (), kind: str | None = None,
                      by: str | None = None,
                      at: str | None = None, note: str = "复核关闭") -> list[str]:
        code_set = set(codes)
        closed: list[str] = []
        for issue in record.get("review_issues", []):
            if not issue.get("open", True):
                continue
            if kind is not None and issue.get("kind") != kind:
                continue
            code = issue.get("code", "")
            if code_set or prefixes:
                if code not in code_set and not any(code.startswith(p) for p in prefixes):
                    continue
            # 若既未给 codes 也未给 prefixes，则配合 kind 过滤关闭该类全部问题。
            issue["open"] = False
            issue["closed_at"] = self.now(at)
            issue["closed_by"] = by
            issue["closure_note"] = note
            closed.append(code)
        if closed:
            self._history(record, "review_issue_closed",
                          f"关闭问题 {closed}：{note}", at=at, by=by)
        return closed

    def _has_open_issues(self, record: dict[str, Any]) -> bool:
        return any(i.get("open", True) for i in record.get("review_issues", []))

    def _recompute_status(self, record: dict[str, Any], *, at: str | None = None,
                          by: str | None = None) -> str:
        if record.get("type") not in ("reading_adoption", "relation", "citation"):
            return record.get("status", ACTIVE)
        current = record.get("status", ACTIVE)
        # 生命周期终态/替代态不允许被“无待办问题”的对账自动冲掉。
        if current in (SUPERSEDED, WITHDRAWN, RETRACTED, MERGED_DUPLICATE):
            return current
        new_status = PENDING_REVIEW if self._has_open_issues(record) else ACTIVE
        if current != new_status:
            record["status"] = new_status
            self._history(
                record,
                "status_changed",
                f"{current} -> {new_status}",
                at=at, by=by,
            )
        return new_status

    def reconcile_review_state(self, *, at: str | None = None,
                               by: str | None = None) -> dict[str, list[str]]:
        """按 当前意见/采纳/目标 的状态，对依赖问题做一次全量对账。

        只自动维护 ``dependency`` 类问题；``scholarly`` 类问题（如资料自陈
        “待核”）必须由人明确确认才能关闭。
        """

        transitions: dict[str, list[str]] = {"adoptions": [], "relations": [], "citations": []}

        # 1) 采纳 <- 意见撤回
        for adp in self.db["adoptions"]:
            op = self.get(adp["opinion_id"]) if self.has(adp["opinion_id"]) else None
            code = f"opinion-withdrawn:{adp['opinion_id']}"
            if op is not None and op.get("status") == WITHDRAWN:
                self._ensure_issue(
                    adp, code=code, kind="dependency",
                    reason=f"所采纳的释读意见 {op['id']} 已被撤回：{op.get('withdraw_reason', '')}",
                    at=at, by=by,
                )
            else:
                self._close_issues(adp, codes=[code], by=by, at=at,
                                   note="意见恢复有效或已改采其他意见")
            before = adp.get("status")
            self._recompute_status(adp, at=at, by=by)
            if before != adp["status"]:
                transitions["adoptions"].append(adp["id"])

        # 2) 关系 <- 意见撤回 / 采纳待复核
        for rel in self.db["relations"]:
            if rel.get("opinion_id") and self.has(rel["opinion_id"]):
                op = self.get(rel["opinion_id"])
                code = f"opinion-withdrawn:{op['id']}"
                if op.get("status") == WITHDRAWN:
                    self._ensure_issue(
                        rel, code=code, kind="dependency",
                        reason=f"关系直接依据的释读意见 {op['id']} 已撤回。", at=at, by=by,
                    )
                else:
                    self._close_issues(rel, codes=[code], by=by, at=at)
            if rel.get("adoption_id") and self.has(rel["adoption_id"]):
                adp = self.get(rel["adoption_id"])
                pending_code = f"adoption-pending:{adp['id']}"
                superseded_code = f"adoption-superseded:{adp['id']}"
                if adp.get("status") == PENDING_REVIEW:
                    reasons = [i["reason"] for i in adp.get("review_issues", []) if i.get("open")]
                    self._ensure_issue(
                        rel, code=pending_code, kind="dependency",
                        reason="所采用的编目释读结论待复核" + (f"：{'；'.join(reasons)}" if reasons else ""),
                        at=at, by=by,
                    )
                    self._close_issues(rel, codes=[superseded_code], by=by, at=at)
                elif adp.get("status") == SUPERSEDED:
                    self._ensure_issue(
                        rel, code=superseded_code, kind="dependency",
                        reason=f"关系所依据的采纳 {adp['id']} 已被新的编目采纳取代，需确认关系是否改依新读法。",
                        at=at, by=by,
                    )
                    self._close_issues(rel, codes=[pending_code], by=by, at=at)
                else:
                    self._close_issues(rel, codes=[pending_code, superseded_code], by=by, at=at)
            before = rel.get("status")
            self._recompute_status(rel, at=at, by=by)
            if before != rel["status"]:
                transitions["relations"].append(rel["id"])

        # 3) 引用 <- 目标记录待复核
        reviewable = {"reading_adoption", "relation"}
        for cite in self.db["citations"]:
            live_codes: set[str] = set()
            for tid in cite.get("target_ids", []):
                if not self.has(tid):
                    code = f"target-missing:{tid}"
                    self._ensure_issue(cite, code=code, kind="dependency",
                                       reason=f"引用目标 {tid} 已不存在", at=at, by=by)
                    live_codes.add(code)
                    continue
                target = self.get(tid)
                if target.get("type") in reviewable and target.get("status") == PENDING_REVIEW:
                    code = f"target-pending:{tid}"
                    open_reasons = [i["reason"] for i in target.get("review_issues", []) if i.get("open")]
                    self._ensure_issue(
                        cite, code=code, kind="dependency",
                        reason=f"被引用的 {tid} 处于待复核" + (f"：{'；'.join(open_reasons[:2])}" if open_reasons else ""),
                        at=at, by=by,
                    )
                    live_codes.add(code)
                else:
                    self._close_issues(cite, codes=[f"target-pending:{tid}"], by=by, at=at,
                                       note="被引用记录已完成复核")
            before = cite.get("status")
            self._recompute_status(cite, at=at, by=by)
            if before != cite["status"]:
                transitions["citations"].append(cite["id"])

        return transitions

    def withdraw_opinion(self, opinion_id: str, *, by: str | None = None,
                         reason: str = "专家撤回该意见",
                         at: str | None = None) -> dict[str, Any]:
        opinion = self.get(opinion_id)
        if opinion.get("type") != "opinion":
            raise ValidationError(f"{opinion_id} 不是释读意见")
        ts = self.now(at)

        before = {
            "adoptions": {a["id"]: a["status"] for a in self.db["adoptions"]},
            "relations": {r["id"]: r["status"] for r in self.db["relations"]},
            "citations": {c["id"]: c["status"] for c in self.db["citations"]},
        }

        if opinion["status"] != WITHDRAWN:
            opinion["status"] = WITHDRAWN
            opinion["withdrawn_at"] = ts
            opinion["withdrawn_by"] = by
            opinion["withdraw_reason"] = reason
            self._history(opinion, "withdraw", reason, at=ts, by=by)
            self._audit("opinion_withdrawn", f"{opinion_id}：{reason}", by=by, at=ts)

        transitions = self.reconcile_review_state(at=ts, by=by)

        after = {
            "adoptions": {a["id"]: a["status"] for a in self.db["adoptions"]},
            "relations": {r["id"]: r["status"] for r in self.db["relations"]},
            "citations": {c["id"]: c["status"] for c in self.db["citations"]},
        }
        newly_pending = {
            kind: [rid for rid in ids if before[kind].get(rid) != PENDING_REVIEW
                   and after[kind].get(rid) == PENDING_REVIEW]
            for kind, ids in after.items()
        }
        report = {
            "opinion_id": opinion_id,
            "opinion_status": WITHDRAWN,
            "newly_pending": newly_pending,
            "transitions": transitions,
            "notice": "意见与全部历史均保留；受影响记录进入待复核而非被删除。",
        }
        self._audit("withdrawal_cascade",
                    f"{opinion_id} 新置待复核：{newly_pending}", by=by, at=ts)
        return report

    def reconfirm(self, record_id: str, *, by: str | None = None,
                  at: str | None = None, note: str | None = None,
                  new_opinion_id: str | None = None,
                  new_adoption_id: str | None = None,
                  acknowledge_scholarly: bool = False) -> dict[str, Any]:
        """编目/研究人员完成复核。

        - 可改采新的意见或采纳（更新快照，保留旧记录与历史）；
        - 依赖类问题在依赖恢复有效后关闭；
        - ``scholarly`` 类问题（例如“待独立证据”）默认不会被关闭，
          除非显式 ``acknowledge_scholarly=True`` 并给出实质性 ``note``。
        """

        record = self.get(record_id)
        rtype = record.get("type")
        ts = self.now(at)
        display_note = note or "复核后确认"

        if rtype == "reading_adoption":
            if new_opinion_id:
                op = self.get(new_opinion_id)
                if op.get("status") != ACTIVE:
                    raise OpinionUnavailableError(f"新意见 {new_opinion_id} 不是有效状态")
                record["opinion_id"] = new_opinion_id
                record["reading"] = op["reading"]
                record["reading_snapshot"] = self._reading_snapshot_from_opinion(op)
                self._history(record, "readopted", f"复核改采 {new_opinion_id}", at=ts, by=by)
            if self.has(record["opinion_id"]) and self.get(record["opinion_id"]).get("status") == ACTIVE:
                self._close_issues(record, prefixes=("opinion-withdrawn:",), by=by, at=ts,
                                   note=display_note)

        elif rtype == "relation":
            if new_adoption_id:
                adp = self.get(new_adoption_id)
                if adp.get("type") != "reading_adoption" or adp.get("status") != ACTIVE:
                    raise ValidationError(f"新采纳 {new_adoption_id} 不存在或仍待复核")
                record["adoption_id"] = new_adoption_id
                record["opinion_id"] = adp["opinion_id"]
                record["glyph_id"] = adp["glyph_id"]
                record["reading"] = deepcopy(adp["reading_snapshot"])
                record["reading"]["adoption_id"] = new_adoption_id
                record["reading"]["adoption_status"] = ACTIVE
                self._history(record, "readopted", f"复核改依采纳 {new_adoption_id}", at=ts, by=by)
            if new_opinion_id:
                op = self.get(new_opinion_id)
                if op.get("status") != ACTIVE:
                    raise OpinionUnavailableError(f"新意见 {new_opinion_id} 不是有效状态")
                record["opinion_id"] = new_opinion_id
                record["reading"] = self._reading_snapshot_from_opinion(op)
                self._history(record, "readopted", f"复核改依意见 {new_opinion_id}", at=ts, by=by)
            # 复核人明确承担责任：先关闭依赖类问题，随后 reconcile 会按当前依赖重新判定。
            self._close_issues(
                record,
                prefixes=("opinion-withdrawn:", "adoption-pending:",
                          "adoption-superseded:", "artifact-merge:"),
                by=by, at=ts, note=display_note,
            )
            if acknowledge_scholarly:
                if not (note and note.strip()):
                    raise ValidationError("确认学术存疑问题时必须通过 note 给出实质性说明依据")
                self._close_issues(record, kind="scholarly", by=by, at=ts,
                                   note=f"复核人明确知悉并保留/承担：{note}")

        elif rtype == "citation":
            # 引用只有在全部目标不再待复核时才能真正恢复有效。
            blocking = [tid for tid in record.get("target_ids", [])
                        if self.has(tid) and self.get(tid).get("status") == PENDING_REVIEW]
            if blocking:
                raise ValidationError(
                    f"引用 {record_id} 的目标 {blocking} 仍待复核，不能提前恢复；请先完成下游关系复核。"
                )
            self._close_issues(record, prefixes=("target-pending:", "target-missing:"),
                               by=by, at=ts, note=display_note)
        else:
            raise ValidationError(f"记录 {record_id}（{rtype}）不支持 reconfirm")

        self._history(record, "reconfirm", display_note, at=ts, by=by)
        self.reconcile_review_state(at=ts, by=by)
        return self.get(record_id)

    # -------------------------------------------------------- identity states

    def reading_states(self, overrides: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        """计算每个字形位置当前的有效读法；overrides 可做“若读作X”推演。"""

        overrides = overrides or {}
        states: dict[str, dict[str, Any]] = {}

        def _norm_override(value: Any) -> dict[str, Any]:
            return {"candidate": value} if isinstance(value, str) else dict(value or {})

        for glyph in self.db["glyphs"]:
            gid = glyph["id"]
            if gid in overrides:
                ov = _norm_override(overrides[gid])
                candidate = ov.get("candidate") or ov.get("reading")
                opinion_id = ov.get("opinion_id")
                state: dict[str, Any] = {
                    "state": "hypothetical",
                    "hypothetical": True,
                    "candidate": candidate,
                    "opinion_id": opinion_id,
                    "adoption_id": ov.get("adoption_id"),
                }
                if opinion_id and self.has(opinion_id):
                    op = self.get(opinion_id)
                    state["candidate"] = op["reading"]
                    state["opinion_status"] = op["status"]
                    state["basis"] = op.get("basis", [])
                    state["confidence"] = op.get("confidence")
                if candidate and candidate not in glyph.get("candidates", []):
                    state["warning"] = f"假设读法“{candidate}”不在保留候选中"
                states[gid] = state
                continue

            active_adps = [a for a in self.db["adoptions"]
                           if a["glyph_id"] == gid and a.get("status") == ACTIVE]
            if active_adps:
                adp = active_adps[-1]
                snap = adp["reading_snapshot"]
                live_op = self.get(adp["opinion_id"]) if self.has(adp["opinion_id"]) else {}
                states[gid] = {
                    "state": "active",
                    "hypothetical": False,
                    "candidate": adp["reading"],
                    "opinion_id": adp["opinion_id"],
                    "adoption_id": adp["id"],
                    "confidence": snap.get("confidence"),
                    "basis": snap.get("basis", []),
                    "expert_name": snap.get("expert_name"),
                    "opinion_status": live_op.get("status", snap.get("opinion_status")),
                }
                continue

            pending_adps = [a for a in self.db["adoptions"] if a["glyph_id"] == gid]
            if pending_adps:
                states[gid] = {
                    "state": PENDING_REVIEW,
                    "candidate": None,
                    "reason": "该字形的编目采纳记录待复核，当前没有有效定论。",
                    "adoption_ids": [a["id"] for a in pending_adps],
                }
            else:
                states[gid] = {
                    "state": "unadopted",
                    "candidate": None,
                    "reason": "该字形只有候选读法与专家意见，编目尚未正式采纳任何一种。",
                    "candidates": glyph.get("candidates", []),
                }
        return states

    def resolve_persons(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        states = self.reading_states(overrides)
        return _resolve_persons(
            mentions=self.db["mentions"],
            persons=self.db["persons"],
            rules=self.db["identity_rules"],
            reading_state=lambda gid: states.get(gid, {"state": "unknown", "candidate": None}),
        )

    # --------------------------------------------------------------- queries

    def citations_for(self, target_id: str) -> list[dict[str, Any]]:
        return [c for c in self.db["citations"] if target_id in c.get("target_ids", [])]

    def relation_view(self, relation: dict[str, Any]) -> dict[str, Any]:
        rid = relation["id"]
        reading = deepcopy(relation.get("reading"))
        # 用意见/采纳的实时状态补充快照，确保撤回后查询能亮警示。
        if reading and reading.get("opinion_id") and self.has(reading["opinion_id"]):
            op = self.get(reading["opinion_id"])
            reading["opinion_current_status"] = op.get("status")
            if op.get("status") == WITHDRAWN:
                reading["withdraw_reason"] = op.get("withdraw_reason")
        if relation.get("adoption_id") and self.has(relation["adoption_id"]):
            reading = reading or {}
            reading["adoption_current_status"] = self.get(relation["adoption_id"]).get("status")

        return {
            "id": rid,
            "kind": relation["kind"],
            "kind_label": relation.get("kind_label"),
            "from": {"id": relation["from_id"], "label": self.label_of(relation["from_id"])},
            "to": {"id": relation["to_id"], "label": self.label_of(relation["to_id"])},
            "status": relation.get("status", ACTIVE),
            "certainty": relation.get("certainty"),
            "scope": relation.get("scope"),
            "reading": reading,
            "basis": deepcopy(relation.get("basis", [])),
            "source_record_ids": list(relation.get("source_record_ids", [])),
            "open_issues": [i for i in relation.get("review_issues", []) if i.get("open", True)],
            "citations": [
                {
                    "id": c["id"],
                    "researcher": c.get("researcher"),
                    "work": c.get("work"),
                    "status": c.get("status"),
                    "statement": c.get("statement"),
                    "open_issues": [i for i in c.get("review_issues", []) if i.get("open")],
                }
                for c in self.citations_for(rid)
            ],
        }

    def citation_view(self, citation: dict[str, Any]) -> dict[str, Any]:
        targets = []
        for tid in citation.get("target_ids", []):
            if not self.has(tid):
                targets.append({"id": tid, "exists": False})
                continue
            target = self.get(tid)
            reading = None
            if target.get("type") == "relation":
                r = target.get("reading") or {}
                reading = {
                    "candidate": r.get("candidate"),
                    "opinion_id": r.get("opinion_id"),
                    "adoption_id": r.get("adoption_id"),
                }
            targets.append({
                "id": tid,
                "exists": True,
                "type": target.get("type"),
                "label": self.label_of(tid),
                "status": target.get("status"),
                "kind": target.get("kind"),
                "reading": reading,
            })
        return {
            "id": citation["id"],
            "researcher": citation.get("researcher"),
            "work": citation.get("work"),
            "statement": citation.get("statement"),
            "cited_at": citation.get("cited_at"),
            "status": citation.get("status", ACTIVE),
            "targets": targets,
            "open_issues": [i for i in citation.get("review_issues", []) if i.get("open", True)],
        }

    def research_report(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        relations = [self.relation_view(r) for r in sorted(self.db["relations"], key=lambda r: r["id"])]
        citations = [self.citation_view(c) for c in sorted(self.db["citations"], key=lambda c: c["id"])]
        identity = self.resolve_persons(overrides)

        pending_items: list[dict[str, Any]] = []
        for collection, rtype in (("adoptions", "adoption"), ("relations", "relation"),
                                   ("citations", "citation")):
            for rec in self.db[collection]:
                if rec.get("status") == PENDING_REVIEW:
                    pending_items.append({
                        "type": rtype,
                        "id": rec["id"],
                        "open_issues": [
                            {"code": i["code"], "kind": i.get("kind"), "reason": i["reason"]}
                            for i in rec.get("review_issues", []) if i.get("open")
                        ],
                    })

        events = []
        for ev in self.db["events"]:
            events.append({
                "id": ev["id"],
                "label": ev["label"],
                "occurrence_status": ev["occurrence_status"],
                "evidence_ids": list(ev.get("evidence_ids", [])),
                "source_record_id": ev.get("source_record_id"),
                "note": ev.get("note"),
                "interpretation_boundary": (
                    "照片/拓片/释读意见只决定字形证据；事件是否真实发生取决于独立证据，"
                    "新增照片不会自动改变本状态。"
                ),
            })

        return {
            "case_id": self.db["case_id"],
            "data_notice": self.db["data_notice"],
            "hypothetical_overrides": overrides or {},
            "sources": deepcopy(self.db["sources"]),
            "glyphs": deepcopy(self.db["glyphs"]),
            "opinions": [
                {
                    "id": o["id"], "glyph_id": o["glyph_id"], "reading": o["reading"],
                    "expert_name": o.get("expert_name"), "confidence": o.get("confidence"),
                    "expressed_at": o.get("expressed_at"), "status": o.get("status"),
                    "basis": o.get("basis", []), "source_record_id": o.get("source_record_id"),
                    "withdraw_reason": o.get("withdraw_reason"),
                }
                for o in self.db["opinions"]
            ],
            "counts": {
                "sources": len(self.db["sources"]),
                "glyphs": len(self.db["glyphs"]),
                "opinions": len(self.db["opinions"]),
                "evidence": len(self.db["evidence"]),
                "artifacts": len(self.db["artifacts"]),
                "rubbings": len(self.db["rubbings"]),
                "catalogs": len(self.db["catalogs"]),
                "adoptions": len(self.db["adoptions"]),
                "relations": len(self.db["relations"]),
                "citations": len(self.db["citations"]),
                "pending_review": len(pending_items),
            },
            "reading_states": self.reading_states(overrides),
            "relations": relations,
            "citations": citations,
            "identity": identity,
            "events": events,
            "pending_review": pending_items,
        }
