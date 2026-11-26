"""命令行入口：初始化库、查看研究报告、做“若读作X”推演、运行演示核验。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .models import PENDING_REVIEW
from .seed import DEFAULT_DB_PATH, build_workbench
from .workbench import Workbench


def _stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _load_or_seed(db_path: Path) -> tuple[Workbench, bool]:
    if db_path.exists():
        return Workbench.load(db_path), False
    return build_workbench(), True


def _print_report(wb: Workbench, what_if: str | None) -> None:
    overrides: dict[str, Any] | None = {"G-6": what_if} if what_if else None
    report = wb.research_report(overrides)
    print(report["data_notice"])
    if what_if:
        print(f"\n【假设推演】G-6 若读作“{what_if}”——此推演不改变编目数据。")

    print("\n== 原始记录（data/case.json 稳定编号，原文保留）==")
    for s in report["sources"]:
        if str(s["id"]).startswith("EP"):
            print(f"  {s['id']} [{s.get('kind')}] {s['text']}")

    print("\n== 字形位置 / 候选读法 / 历次意见 ==")
    for g in report["glyphs"]:
        print(f"  {g['id']} {g['label']} line={g.get('line')} 候选={g['candidates']}")
    for o in report["opinions"]:
        print(f"    {o['id']} {o['expressed_at']} {o['expert_name']} 读“{o['reading']}” "
              f"把握={o['confidence']} 状态={o['status']}")

    print("\n== 关系与每条关系采用的释读/依据 ==")
    for rv in report["relations"]:
        reading = rv["reading"]
        if reading:
            basis_n = len(reading.get("basis", []))
            rtext = (f"采‘{reading.get('candidate')}’({reading.get('opinion_id')}, "
                     f"把握={reading.get('confidence')}, 依据{basis_n}项)")
            live = reading.get("opinion_current_status")
            if live and live != "active":
                rtext += f" [意见实时状态={live}]"
        else:
            rtext = "不依赖残字释读"
        print(f"[{rv['status']:>14}/{rv['certainty']:<11}] {rv['id']:<15} "
              f"{rv['from']['label']} -> {rv['to']['label']}")
        print(f"    类型：{rv['kind_label']}｜释读：{rtext}")
        for issue in rv["open_issues"]:
            print(f"    ⚠ 待复核[{issue['kind']}]：{issue['reason']}")
        for cite in rv["citations"]:
            print(f"    ↳ 引用 {cite['id']}《{cite['work']}》状态={cite['status']}")

    print("\n== 人物合并/分开 ==")
    ident = report["identity"]
    for d in ident["decisions"]:
        tag = {"merged": "合并", "split": "分开", "pending": "待定",
               "unconditional": "无条件同一"}.get(d["decision"], d["decision"])
        print(f"  {d['rule_id']} [{tag}] {d['reason']}")
    if ident["conflicts"]:
        print("  冲突：")
        for c in ident["conflicts"]:
            print(f"   ! {c}")

    print("\n== 铭文所述事件（区别于字形证据）==")
    for ev in report["events"]:
        print(f"  {ev['id']} {ev['label']}：真实性状态={ev['occurrence_status']}")
        print(f"    {ev['interpretation_boundary']}")

    print("\n== 研究引用及其所涉关系当前读法/状态 ==")
    for cite in report["citations"]:
        print(f"  [{cite['status']}] {cite['id']} {cite['researcher']}《{cite['work']}》")
        print(f"      原引表述（历史原文，不改写）：{cite['statement']}")
        for t in cite["targets"]:
            r = t.get("reading") or {}
            cand = r.get("candidate")
            if cand:
                rtext = f"，当前读法“{cand}”({r.get('opinion_id')})"
            elif t.get("type") == "relation":
                rtext = "，不依赖残字读法"
            else:
                rtext = ""
            print(f"      -> {t['id']} [{t.get('status')}] {t.get('label')}{rtext}")
        for issue in cite["open_issues"]:
            print(f"      ⚠ {issue['reason']}")

    print("\n== 待复核清单 ==")
    if not report["pending_review"]:
        print("  无")
    for item in report["pending_review"]:
        codes = "; ".join(f"{i['code']}:{i['reason']}" for i in item["open_issues"])
        print(f"  [{item['type']}] {item['id']} — {codes}")

    print(f"\n统计：{json.dumps(report['counts'], ensure_ascii=False)}")


def main(argv: list[str] | None = None) -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(
        prog="case_workbench",
        description="古文字释读异文与馆藏关系审定工作台（全部为合成样本）",
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="JSON 库路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="构造合成案例库并保存为 JSON")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在的库文件")

    p_demo = sub.add_parser("demo", help="在内存中运行端到端演示与核验")

    p_query = sub.add_parser("query", help="输出研究报告（关系溯源/人物/事件/待复核）")
    p_query.add_argument("--what-if", choices=["舟", "周"], help="假设 G-6 读作某字进行推演")
    p_query.add_argument("--json", action="store_true", help="输出完整 JSON 报告")

    p_persons = sub.add_parser("persons", help="只输出人物合并/分开结果")
    p_persons.add_argument("--what-if", choices=["舟", "周"])
    p_persons.add_argument("--json", action="store_true")

    p_verify = sub.add_parser("verify", help="运行端到端核验并以退出码表示结果")

    p_serve = sub.add_parser("serve", help="启动只读 HTTP 查询服务（标准库）")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)
    db_path = Path(args.db)

    if args.command == "init":
        if db_path.exists() and not args.force:
            print(f"库已存在：{db_path}（使用 --force 覆盖）")
            return 1
        wb = build_workbench()
        wb.save(db_path)
        print(f"已写入合成案例库：{db_path}")
        print("提示：运行 python3 -m case_workbench query 查看研究视图")
        return 0

    if args.command == "demo":
        from .scenario import run_demo
        run_demo()
        return 0

    if args.command == "verify":
        from .scenario import evaluate
        checks = evaluate()
        failed = [(n, d) for n, ok, d in checks if not ok]
        for name, ok, _ in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        print(f"\n{len(checks) - len(failed)}/{len(checks)} 通过")
        return 1 if failed else 0

    if args.command == "serve":
        from .server import main as server_main
        return server_main(["--db", str(db_path), "--host", args.host, "--port", str(args.port)])

    wb, in_memory = _load_or_seed(db_path)
    if in_memory:
        print(f"（未找到 {db_path}，以下使用内存合成种子；运行 init 可持久化）\n")

    if args.command == "query":
        if args.json:
            overrides = {"G-6": args.what_if} if args.what_if else None
            print(json.dumps(wb.research_report(overrides), ensure_ascii=False, indent=2))
        else:
            _print_report(wb, args.what_if)
        return 0

    if args.command == "persons":
        result = wb.resolve_persons({"G-6": args.what_if} if args.what_if else None)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for d in result["decisions"]:
                print(f"{d['rule_id']}: {d['decision']} — {d['reason']}")
            for c in result["clusters"]:
                print("簇：", " | ".join(m["label"] for m in c["members"]))
        return 0

    parser.error(f"未知命令：{args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
