#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""startup-guide MCP 服务端（stdio，零依赖）。

这一层只负责「说」：JSON-RPC 分发、resources、prompts。工具实现全在
同目录的 mcp_tools.py，那里只做确定性计算、不含判断。

为什么手写 JSON-RPC 而不装 mcp SDK：官方 SDK 要 pip install，而本仓库
对外的承诺是「克隆即用、零环境依赖」。stdio 传输就是按行分隔的 JSON-RPC，
标准库足够，也不引入版本漂移。

用法：
    python tools/mcp_server.py              # 由 MCP 宿主以 stdio 启动
    python tools/mcp_server.py --selftest   # 不对管道跑一遍工具，看返回
    python tools/mcp_server.py --list       # 列出暴露的 tools/resources/prompts
"""
from __future__ import annotations

import argparse
import json
import sys

# 不写字节码缓存。这个脚本常从安装目录（dist/startup-guide/tools/）直接启动，
# 默认行为会在同级生成 __pycache__，把安装产物弄脏，skill_check 会判「多出文件」。
sys.dont_write_bytecode = True

from mcp_tools import (
    PARAMS_PATH,
    ROOT,
    TOOLS,
    load_params,
    tool_capital_band,
    tool_h2_check,
    tool_search_budget,
    tool_source_grade,
    tool_taxonomy_lookup,
)

SERVER_NAME = "startup-guide"
SERVER_VERSION = "0.4.0"
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
FALLBACK_PROTOCOL = "2025-06-18"


# ---------------------------------------------------------------- 资源与提示

def resource_files() -> list:
    """只暴露运行时真正有用的文件，不暴露 tools/ 与维护者资料。"""
    files = [ROOT / "SKILL.md", ROOT / "INSTALL.md", PARAMS_PATH]
    for pattern in ("references/*.md", "data/**/*.md", "examples/*.md", "hosts/*.md"):
        files += sorted(ROOT.glob(pattern))
    return [p for p in files if p.is_file()]


def to_uri(path) -> str:
    return "skill://" + path.relative_to(ROOT).as_posix()


def list_resources() -> list:
    return [
        {
            "uri": to_uri(p),
            "name": p.relative_to(ROOT).as_posix(),
            "mimeType": "application/json" if p.suffix == ".json" else "text/markdown",
        }
        for p in resource_files()
    ]


def read_resource(uri: str) -> dict:
    rel = uri[len("skill://"):] if uri.startswith("skill://") else uri
    target = (ROOT / rel).resolve()
    if ROOT.resolve() not in target.parents and target != ROOT.resolve():
        raise ValueError(f"资源越界：{uri}")
    if not target.is_file():
        raise ValueError(f"资源不存在：{uri}")
    return {"contents": [{
        "uri": uri,
        "mimeType": "application/json" if target.suffix == ".json" else "text/markdown",
        "text": target.read_text(encoding="utf-8"),
    }]}


PROMPT_TEXT = """请按 startup-guide 的流程评估下面这个方向，**不要跳过闸门，不要一上来给完整计划**。

方向：{direction}
预算：{budget}
{extra}
执行顺序（每一步都要落到输出里）：
1. 先定资金带与生意原型，再谈数字；模式有分叉就先给结构对比，不问「你想做哪种」
2. 按原型发起定向检索，只查必查项，预算 = 必查项 × 2，上限 12
3. 过三道硬门槛 H1 客户可达 / H2 现金流断点 / H3 合规前置，四条软约束只排序不求和
4. 给四档判断之一：放行 / 有条件放行 / 信息不足 / 不建议启动
5. 以一个当天能做的动作结尾，并说明这个动作产出哪道门槛的输入

没有联网能力时先告知再降级，结论封顶在「信息不足」，不许假装查过。"""


def get_prompt(name: str, args: dict) -> dict:
    if name != "checkup":
        raise ValueError(f"未知提示：{name}")
    direction = str(args.get("direction", "")).strip() or "（用户未说明）"
    budget = str(args.get("budget", "")).strip() or "（用户未说明）"
    notes = str(args.get("notes", "")).strip()
    extra = f"补充情况：{notes}\n" if notes else ""
    return {
        "description": "启动条件体检：把方向与预算装进两阶段流程",
        "messages": [{"role": "user", "content": {
            "type": "text",
            "text": PROMPT_TEXT.format(direction=direction, budget=budget, extra=extra),
        }}],
    }


# ---------------------------------------------------------------- 协议层

def rpc_result(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def rpc_error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(msg: dict, params: dict) -> dict | None:
    method = msg.get("method", "")
    mid = msg.get("id")

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        return rpc_result(mid, {
            "protocolVersion": asked if asked in PROTOCOLS else FALLBACK_PROTOCOL,
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": "创业方向评估技能。工具只做确定性计算（资金带、H2、门类、来源分级、检索预算），"
                            "判断在提示词侧。先读 skill://SKILL.md，方法就齐了。",
        })
    if mid is None:
        return None  # 通知（notifications/initialized 等）不需要回

    if method == "ping":
        return rpc_result(mid, {})
    if method == "tools/list":
        return rpc_result(mid, {"tools": [
            {"name": name, "description": spec[1], "inputSchema": spec[2]}
            for name, spec in TOOLS.items()
        ]})
    if method == "tools/call":
        p = msg.get("params") or {}
        name = p.get("name", "")
        if name not in TOOLS:
            return rpc_error(mid, -32602, f"未知工具：{name}")
        try:
            payload = TOOLS[name][0](p.get("arguments") or {}, params)
        except Exception as exc:  # 工具内异常按错误结果返回，不打断会话
            return rpc_result(mid, {"content": [{"type": "text", "text": f"工具执行失败：{exc}"}], "isError": True})
        return rpc_result(mid, {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": isinstance(payload, dict) and "error" in payload,
        })
    if method == "resources/list":
        return rpc_result(mid, {"resources": list_resources()})
    if method == "resources/read":
        try:
            return rpc_result(mid, read_resource((msg.get("params") or {}).get("uri", "")))
        except ValueError as exc:
            return rpc_error(mid, -32602, str(exc))
    if method == "prompts/list":
        return rpc_result(mid, {"prompts": [{
            "name": "checkup",
            "description": "启动条件体检：把方向与预算装进两阶段流程",
            "arguments": [
                {"name": "direction", "description": "想做的方向", "required": True},
                {"name": "budget", "description": "打算投的钱", "required": True},
                {"name": "notes", "description": "已知情况：城市、人手、资源", "required": False},
            ],
        }]})
    if method == "prompts/get":
        p = msg.get("params") or {}
        try:
            return rpc_result(mid, get_prompt(p.get("name", ""), p.get("arguments") or {}))
        except ValueError as exc:
            return rpc_error(mid, -32602, str(exc))
    return rpc_error(mid, -32601, f"不支持的方法：{method}")


def serve() -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    params = load_params()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps(rpc_error(None, -32700, f"JSON 解析失败：{exc}")), flush=True)
            continue
        reply = handle(msg, params)
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)
    return 0


# ---------------------------------------------------------------- 自检

def selftest() -> int:
    """工具断言。改任何工具或阈值都该在这里加一条，否则回归靠人肉。"""
    params = load_params()
    bad = 0

    def expect(label, cond, detail=""):
        nonlocal bad
        if cond:
            print(f"[通过] {label}")
        else:
            bad += 1
            print(f"[必改] {label} {detail}")

    expect("3000 落 B2（左闭右开）", tool_capital_band({"amount_cny": 3000}, params).get("band") == "B2")
    expect("0 落 B1", tool_capital_band({"amount_cny": 0}, params).get("band") == "B1")
    expect("超上限判 out_of_scope",
           tool_capital_band({"amount_cny": 2_000_000}, params).get("out_of_scope") is True)

    h = tool_h2_check({"case": "A", "available_fund": 3000, "monthly_fixed": 2000,
                       "months_to_first_income": 1, "fixed_cost_items": 3}, params)
    expect("A：1.5 个月 < 1+1 判不通过", h.get("verdict") == "不通过", h)
    h2 = tool_h2_check({"case": "A", "available_fund": 3000, "monthly_fixed": 2000,
                        "months_to_first_income": 1, "fixed_cost_items": 1}, params)
    expect("固定支出只有 1 项判信息不足", h2.get("verdict") == "信息不足", h2)
    h3 = tool_h2_check({"case": "B", "working_capital": 50000, "monthly_net_outflow": 8000,
                        "fixed_cost_items": 3}, params)
    expect("B：缺爬坡期按 6 个月", h3.get("required_months") == 7 and h3.get("ramp_assumed") is True, h3)

    t = tool_taxonomy_lookup({"keyword": "卤味摊"}, params)
    expect("门类解析到 20 个", len(t.get("all_categories", [])) == 20, len(t.get("all_categories", [])))

    expect("gov.cn 判 A", tool_source_grade({"url": "https://www.gov.cn/x"}, params)["grade"] == "A")
    expect("jiameng 域名判 D", tool_source_grade({"url": "https://www.jiameng.com/a"}, params)["grade"] == "D")
    expect("未识别按 E", tool_source_grade({"url": "https://example.com/x"}, params)["grade"] == "E")

    expect("5 个必查项 → 10", tool_search_budget({"required_online": 5}, params).get("budget") == 10)
    expect("9 个必查项封顶 12", tool_search_budget({"required_online": 9}, params).get("budget") == 12)

    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18"}}, params)
    expect("initialize 回协议版本", init["result"]["protocolVersion"] == "2025-06-18")
    expect("resources 可读 SKILL.md",
           handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                   "params": {"uri": "skill://SKILL.md"}}, params)["result"]["contents"][0]["text"].startswith("---"))
    expect("资源越界被拒",
           "error" in handle({"jsonrpc": "2.0", "id": 3, "method": "resources/read",
                              "params": {"uri": "skill://../AGENTS.md"}}, params))

    print("\n自检通过" if not bad else f"\n{bad} 项未过")
    return 0 if not bad else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="startup-guide MCP server（stdio）")
    parser.add_argument("--selftest", action="store_true", help="不跑管道，直接验工具返回")
    parser.add_argument("--list", action="store_true", help="列出暴露的 tools/resources/prompts")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.list:
        print(f"{SERVER_NAME} {SERVER_VERSION}（stdio JSON-RPC，零依赖）\n")
        print("tools：")
        for name, spec in TOOLS.items():
            print(f"  {name:<16} {spec[1].splitlines()[0]}")
        print(f"\nresources：{len(resource_files())} 个（skill:// 前缀，只读）")
        print("prompts：checkup")
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main())
