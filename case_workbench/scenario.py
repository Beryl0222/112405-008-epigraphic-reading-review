"""端到端脚本化场景：演示每一条业务要求如何被系统承接。

``python3 -m case_workbench demo`` 与仓库根目录的 ``verify.py`` 都调用这里，
保证“文档里演示的流程”和“验证通过的流程”是同一份代码。
"""

from __future__ import annotations

from typing import Any, Callable

from .models import ACTIVE, PENDING_REVIEW, WITHDRAWN
from .seed import build_workbench
from .workbench import Workbench


def run_lifecycle(wb: Workbench) -> dict[str, Any]:
    """在已播种的工作台上执行完整生命周期，返回每一步的关键观测。"""

    observations: dict[str, Any] = {}

    # 1) 研究用户的两种“若读作”推演（不改编目结论）
    observations["resolve_zhou"] = wb.resolve_persons({"G-6": "周"})
    observations["resolve_zhou_hypothesis"] = wb.resolve_persons({"G-6": "舟"})
    observations["resolve_current"] = wb.resolve_persons()

    # 2) 新增照片：只能增加字形证据，事件状态保持 unverified
    event_before = wb.get("EV-SAC")["occurrence_status"]
    wb.add_photo(
        "EVD-PH2", "E12多光谱补照（合成新照片）", glyph_id="G-6",
        observed_traits=["进一步确认右侧残笔层次", "仍未发现可定谳的关键笔画"],
        added_at="2026-11-20",
    )
    event_after_photo = wb.get("EV-SAC")["occurrence_status"]
    observations["photo_keeps_event_unverified"] = (
        event_before == "unverified" and event_after_photo == "unverified"
    )

    photo_rejected = False
    try:
        wb.corroborate_event("EV-SAC", "EVD-PH2", by="U-GUI")
    except Exception:
        photo_rejected = True
    observations["photo_corroboration_rejected"] = photo_rejected

    wb.add_evidence(
        "EVD-ARCH-INDEP", "archaeological-context",
        "北岸相关祭祀坑共存遗迹（合成独立考古证据）", independent=True,
    )
    wb.corroborate_event(
        "EV-SAC", "EVD-ARCH-INDEP", by="U-REN",
        note="仅为合成演练：独立考古背景可佐证祭祀活动，但仍不自动证明铭文具体事件。",
    )
    observations["event_with_independent_evidence"] = wb.get("EV-SAC")["occurrence_status"]

    # 3) 专家撤回 OP-3 -> 级联待复核
    observations["withdraw_report"] = wb.withdraw_opinion(
        "OP-3", by="U-YI", reason="重新核对旧拓与层位后，认为‘周’读字形依据表述过强，撤回该意见。",
        at="2026-11-21",
    )

    # 4) 编目改采 OP-4（照片后仍保留的另一条有效意见）
    wb.adopt_reading(
        "ADP-2", "CAT-1", "G-6", "OP-4", by="U-REN", at="2026-11-22",
        note="改采仍有效的 OP-4；OP-1/OP-2/已撤回 OP-3 全部保留。",
    )
    for rid in ("REL-LIN", "REL-ID", "REL-KIN", "REL-DATE"):
        wb.reconfirm(
            rid, by="U-REN", at="2026-11-23", new_adoption_id="ADP-2",
            note="核对新采纳与全部候选后维持原关系，把握程度仍为 probable。",
        )
    # 事件联想关系：只解除依赖问题，学术待核问题不能被顺手关掉。
    wb.reconfirm(
        "REL-EVENT", by="U-GUI", at="2026-11-23", new_adoption_id="ADP-2",
        note="字形依赖已更新；EP-3 的独立证据问题继续保留。",
    )

    observations["statuses_after_remediation"] = {
        "ADP-1": wb.get("ADP-1")["status"],
        "ADP-2": wb.get("ADP-2")["status"],
        "REL-LIN": wb.get("REL-LIN")["status"],
        "REL-ID": wb.get("REL-ID")["status"],
        "REL-KIN": wb.get("REL-KIN")["status"],
        "REL-DATE": wb.get("REL-DATE")["status"],
        "REL-EVENT": wb.get("REL-EVENT")["status"],
        "REL-SITE": wb.get("REL-SITE")["status"],
        "CITE-1": wb.get("CITE-1")["status"],
        "CITE-2": wb.get("CITE-2")["status"],
        "CITE-3": wb.get("CITE-3")["status"],
        "OP-3": wb.get("OP-3")["status"],
    }
    return observations


def evaluate() -> list[tuple[str, bool, str]]:
    """供 ``verify.py`` 与测试复用的一组端到端断言。"""

    wb = build_workbench()
    obs = run_lifecycle(wb)
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    glyph = wb.get("G-6")
    check("字形位置与舟/周候选同时保留",
          glyph["line"] == 6 and glyph["candidates"] == ["舟", "周"],
          str(glyph["candidates"]))

    check("历次释读意见数量为4且无删除",
          len(wb.db["opinions"]) == 4 and all(wb.has(o["id"]) for o in wb.db["opinions"]))

    zhou = obs["resolve_zhou"]
    zhou_ir1 = next(d for d in zhou["decisions"] if d["rule_id"] == "IR-1")
    check("按‘周’读：E12名讳与周伯合并", zhou_ir1["decision"] == "merged")

    zhou_boat = obs["resolve_zhou_hypothesis"]
    boat_ir1 = next(d for d in zhou_boat["decisions"] if d["rule_id"] == "IR-1")
    check("假设‘舟’读：同一规则改为分开", boat_ir1["decision"] == "split")
    boat_cluster_ids = [set(c["members"][i]["id"] for i in range(len(c["members"])))
                        for c in zhou_boat["clusters"]]
    check("分开时 MN-1 与 P-ZB 不在同一人物簇",
          not any("MN-1" in ids and "P-ZB" in ids for ids in boat_cluster_ids))

    check("新照片不自动改变事件真实性", obs["photo_keeps_event_unverified"])
    check("照片被拒绝作为事件证实依据", obs["photo_corroboration_rejected"])
    check("独立考古证据可走显式佐证流程",
          obs["event_with_independent_evidence"] == "corroborated")

    newly = obs["withdraw_report"]["newly_pending"]
    check("撤回OP-3：采纳ADP-1进入待复核", "ADP-1" in newly["adoptions"])
    for rid in ("REL-LIN", "REL-ID", "REL-KIN", "REL-DATE"):
        check(f"撤回OP-3：{rid}进入待复核", rid in newly["relations"])
    check("撤回OP-3：CITE-1进入待复核", "CITE-1" in newly["citations"])
    check("不依赖释读的REL-SITE仍有效", wb.get("REL-SITE")["status"] == ACTIVE)
    check("不依赖释读的CITE-2仍有效", wb.get("CITE-2")["status"] == ACTIVE)

    statuses = obs["statuses_after_remediation"]
    check("改采OP-4并复核后四条关系恢复有效",
          all(statuses[r] == ACTIVE for r in ("REL-LIN", "REL-ID", "REL-KIN", "REL-DATE")))
    check("CITE-1随下游恢复有效", statuses["CITE-1"] == ACTIVE)
    check("EP-3学术存疑使REL-EVENT继续待复核", statuses["REL-EVENT"] == PENDING_REVIEW)
    check("CITE-3继续待复核", statuses["CITE-3"] == PENDING_REVIEW)
    check("OP-3保留为withdrawn而非删除", statuses["OP-3"] == WITHDRAWN)
    check("ADP-1保留待复核历史", statuses["ADP-1"] == PENDING_REVIEW)

    art999 = wb.get("ART-E999")
    check("误建器物保留为merged_duplicate并指向ART-E12",
          art999["status"] == "merged_duplicate" and art999["duplicate_of"] == "ART-E12")
    check("旧号E-12与新号E12均可解析到同一器物",
          wb.resolve_artifact_id("E-12") == wb.resolve_artifact_id("E12") == "ART-E12")
    check("后拓本RB-2已改挂ART-E12且留有改指历史",
          wb.get("RB-2")["artifact_id"] == "ART-E12"
          and any(h["action"] == "artifact_repointed" for h in wb.get("RB-2")["history"]))

    report = wb.research_report()
    lin_view = next(r for r in report["relations"] if r["id"] == "REL-LIN")
    check("研究视图为关系展示所采用读法与可信依据",
          bool(lin_view["reading"]) and lin_view["reading"]["candidate"] == "周"
          and len(lin_view["reading"]["basis"]) >= 1)
    check("研究视图带合成资料与无定论声明", "合成样本" in report["data_notice"])
    check("审计轨迹记录了撤回/合并/照片边界等动作",
          any(e["action"] == "opinion_withdrawn" for e in wb.db["audit"])
          and any(e["action"] == "artifact_merged" for e in wb.db["audit"])
          and any(e["action"] == "photo_evidence_only" for e in wb.db["audit"]))
    return checks


def run_demo(out: Callable[[str], None] = print) -> Workbench:
    out("=" * 78)
    out("古文字释读异文与馆藏关系审定 · 合成案例演示")
    out("=" * 78)
    wb = build_workbench()
    report = wb.research_report()
    out(report["data_notice"])
    out("")
    out(f"[初始库] 原始记录 {report['counts']['sources']} 条，"
        f"字形 {report['counts']['glyphs']} 处，意见 {report['counts']['opinions']} 条，"
        f"关系 {report['counts']['relations']} 条，引用 {report['counts']['citations']} 条。")

    out("\n-- 字形位置与候选读法 --")
    g = wb.get("G-6")
    out(f"{g['label']}（line={g['line']}, coords={g['coordinates']}）候选：{g['candidates']}")
    for op in wb.db["opinions"]:
        out(f"  {op['id']} {op['expressed_at']} {op['expert_name']} "
            f"读‘{op['reading']}’ 把握={op['confidence']} 状态={op['status']}")

    out("\n-- 当前编目采纳下的人物簇 --")
    ident = wb.resolve_persons()
    for d in ident["decisions"]:
        out(f"  {d['rule_id']}: {d['decision']} — {d['reason']}")

    out("\n-- 研究视图：每条关系采用的读法与依据 --")
    for rv in report["relations"]:
        reading = rv["reading"]
        rtext = ("不依赖残字读法" if not reading else
                 f"采‘{reading.get('candidate')}’ via {reading.get('opinion_id')}"
                 f"/{reading.get('adoption_id') or '无采纳'}，把握 {reading.get('confidence')}")
        out(f"  [{rv['status']}/{rv['certainty']}] {rv['id']} "
            f"{rv['from']['label']} --{rv['kind_label']}--> {rv['to']['label']}")
        out(f"      读法依据：{rtext}")
        for issue in rv["open_issues"]:
            out(f"      ⚠ 待复核({issue['kind']}/{issue['code']})：{issue['reason']}")

    out("\n-- 执行完整生命周期（新照片 / 撤回 / 改采 / 复核）--")
    obs = run_lifecycle(wb)
    wr = obs["withdraw_report"]["newly_pending"]
    out(f"撤回 OP-3 后新进入待复核：{wr}")
    out(f"照片不证实事件：{obs['photo_keeps_event_unverified']}；"
        f"照片佐证被拒：{obs['photo_corroboration_rejected']}；"
        f"独立证据后事件状态：{obs['event_with_independent_evidence']}")
    out(f"复核后状态：{obs['statuses_after_remediation']}")

    out("\n-- 端到端核验 --")
    checks = evaluate()
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        out(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"（{detail}）" if detail and not ok else ""))
    out(f"\n{passed}/{len(checks)} 项核验通过。")
    if passed != len(checks):
        raise SystemExit(1)
    return wb
