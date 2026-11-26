"""只读查询 HTTP 服务（仅标准库）。

目的：让研究用户/外部脚本可以通过 HTTP 获得
``research_report`` 与人物合并/分开结果。服务不提供任何写操作，
所有登记/撤回/复核仍通过 Python API 或 CLI 完成，避免绕过审计。

路由：

- ``GET /health``                         -> {"ok": true}
- ``GET /api/report`` 或 ``/api/report?what_if=舟`` -> 完整研究报告 JSON
- ``GET /api/persons`` 或 ``?what_if=周``           -> 人物簇与条件判定 JSON
- ``GET /``                               -> 简短中文索引页
"""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .seed import build_workbench
from .workbench import Workbench

_INDEX_HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>释读异文审定工作台（合成样本）</title>
<body style="font-family:sans-serif;max-width:760px;margin:2rem auto;line-height:1.7">
<h1>古文字释读异文与馆藏关系审定</h1>
<p>全部资料均为合成样本；第6行残字没有唯一确定释文。</p>
<ul>
<li><a href="/api/report">/api/report</a> 完整研究报告</li>
<li><a href="/api/report?what_if=%E8%88%9F">/api/report?what_if=舟</a> 假设读作“舟”</li>
<li><a href="/api/report?what_if=%E5%91%A8">/api/report?what_if=周</a> 假设读作“周”</li>
<li><a href="/api/persons">/api/persons</a> 人物合并/分开结果</li>
<li><a href="/health">/health</a> 健康检查</li>
</ul></body></html>"""


def _load(db_path: str | Path | None) -> Workbench:
    if db_path and Path(db_path).exists():
        return Workbench.load(db_path)
    return build_workbench()


def make_handler(wb: Workbench) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "CaseWorkbench/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # 保持测试输出安静
            return

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (stdlib 命名)
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            what_if = (query.get("what_if") or [None])[0]
            if what_if is not None and what_if not in ("舟", "周"):
                self._send_json({"error": "what_if 仅支持 ‘舟’ 或 ‘周’"}, status=400)
                return

            if parsed.path == "/health":
                self._send_json({"ok": True, "synthetic": True})
            elif parsed.path == "/":
                body = _INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/report":
                overrides = {"G-6": what_if} if what_if else None
                self._send_json(wb.research_report(overrides))
            elif parsed.path == "/api/persons":
                overrides = {"G-6": what_if} if what_if else None
                self._send_json(wb.resolve_persons(overrides))
            else:
                self._send_json({"error": f"未知路径：{parsed.path}"}, status=404)

    return Handler


def make_server(db_path: str | Path | None = None, host: str = "127.0.0.1",
                port: int = 8765) -> ThreadingHTTPServer:
    wb = _load(db_path)
    return ThreadingHTTPServer((host, port), make_handler(wb))


def serve_in_background(db_path: str | Path | None = None, host: str = "127.0.0.1",
                        port: int = 0) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """供测试使用：在后台线程启动，port=0 时由系统分配端口。"""

    httpd = make_server(db_path, host, port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="启动只读研究查询 HTTP 服务")
    parser.add_argument("--db", default=None, help="JSON 库路径（不存在则用合成种子）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    httpd = make_server(args.db, args.host, args.port)
    print(f"查询服务已启动：http://{args.host}:{args.port}/  （Ctrl+C 停止；只读）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n停止服务。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
