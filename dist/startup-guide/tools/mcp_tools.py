#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 工具层：五个只读工具，只做确定性计算，不下判断。

与协议层（mcp_server.py）分开的理由只有一个：单文件会越过本仓库的代码
行数上限 400 行，而放宽上限会让这个约束失效。边界也正好落在这里——
本文件是「算」，协议层是「说」。

阈值全部读 data/params.json，不硬编码。params.json 与文档的一致性由
tools/skill_check.py 校验。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = ROOT / "data" / "params.json"


def load_params() -> dict:
    return json.loads(PARAMS_PATH.read_text(encoding="utf-8"))


def band_for(amount: float, params: dict) -> dict | None:
    """左闭右开：3000 落 B2，不是 B1。区间语义以文档表格为准。"""
    for band in params["capital_bands"]:
        if band["lo"] <= amount < band["hi"]:
            return band
    return None


def parse_taxonomy(rows_from: Path | None = None) -> list[dict]:
    """从文档表格解析门类，不另存一份清单。

    单一真相在这里是硬要求：门类只有 20 个，手工抄一遍就会各自漂移。
    """
    path = rows_from or (ROOT / "data" / "industry-taxonomy.md")
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not re.fullmatch(r"[A-T]", cells[0]):
            continue
        rows.append({
            "code": cells[0],
            "name": cells[1],
            "reachability": cells[2],
            "archetypes": [x for x in re.split(r"[、,，]", cells[3]) if x and x != "—"],
            "examples": [x for x in re.split(r"[、,，]", cells[4]) if x and x != "—"],
        })
    return rows


def grade_for(url: str, params: dict) -> tuple[str, str]:
    """返回 (来源级, 判定依据)。识别不到时按默认级处理并说明是推定。"""
    cfg = params["source_grades"]
    raw = url.strip()
    host = urlparse(raw if "//" in raw else "//" + raw).hostname or raw
    host = host.lower().lstrip(".")

    for site, grade in cfg["known_sites"].items():
        if host == site or host.endswith("." + site):
            return grade, f"已知站点 {site}"

    for rule in cfg["domain_rules"]:
        value, kind = rule["value"], rule["match"]
        hit = (
            (kind == "endswith" and host.endswith(value))
            or (kind == "contains" and value in host)
            or (kind == "prefix" and host.startswith(value))
        )
        if hit:
            return rule["grade"], f"域名规则 {kind} {value}"

    return cfg["default_grade"], "未识别来源，按默认级别推定"


def tool_capital_band(args: dict, params: dict) -> dict:
    amount = args.get("amount_cny")
    if not isinstance(amount, (int, float)) or amount < 0:
        return {"error": "amount_cny 必须是非负数字（人民币元）"}
    band = band_for(amount, params)
    if band is None:
        notes = params["band_notes"]
        if amount > notes["ceiling"]:
            return {"band": None, "out_of_scope": True, "message": notes["beyond"]}
        return {"band": None, "message": "金额未落入任何资金带，检查输入"}
    return {
        "band": band["id"],
        "label": band["label"],
        "input_cny": amount,
        "reachable_archetypes": band["reachable"],
        "blocked_archetypes": band["blocked"],
        "fatal_constraint": band["fatal"],
        "must_ask_next": params["band_notes"]["must_ask"],
        "reminder": "档位只决定问哪几个问题，不替代三个数；用户说「我是 2 万档」不等于算过账",
    }


def tool_h2_check(args: dict, params: dict) -> dict:
    cfg = params["h2"]
    case = str(args.get("case", "")).upper()
    items = args.get("fixed_cost_items")
    buffer_m = cfg["buffer_months"]

    if case not in ("A", "B"):
        return {"error": "case 必须是 A 或 B：首笔收入在首月内用 B，否则用 A"}
    if not isinstance(items, int) or items < 0:
        return {"error": "fixed_cost_items 必填：月度固定支出已覆盖几项（店租、人工、生活开支、其他，共 4 项）"}

    out: dict = {"case": case, "rule": cfg["rule_a"] if case == "A" else cfg["rule_b"]}

    if case == "A":
        fund, fixed = args.get("available_fund"), args.get("monthly_fixed")
        months_in = args.get("months_to_first_income")
        if not all(isinstance(v, (int, float)) for v in (fund, fixed, months_in)):
            return {"error": "情形 A 需要 available_fund、monthly_fixed、months_to_first_income 三个数字"}
        if fixed <= 0:
            return {"verdict": "信息不足", "reason": "月度固定支出为 0 或缺失，无法算可撑月数"}
        runway = fund / fixed
        need = months_in + buffer_m
        out.update({
            "runway_months": round(runway, 1),
            "required_months": need,
            "formula": f"{fund} ÷ {fixed} = {runway:.1f} 个月；需 ≥ {months_in} + {buffer_m} = {need}",
        })
    else:
        capital, outflow = args.get("working_capital"), args.get("monthly_net_outflow")
        ramp = args.get("ramp_months")
        if not all(isinstance(v, (int, float)) for v in (capital, outflow)):
            return {"error": "情形 B 需要 working_capital、monthly_net_outflow（爬坡期可缺省，缺省取 6）"}
        if outflow <= 0:
            out.update({"verdict": "通过", "reason": "月净流出 ≤ 0（净利大于支出），情形 B 直接通过"})
        else:
            if not isinstance(ramp, (int, float)):
                ramp, out["ramp_assumed"] = cfg["default_ramp_months"], True
            runway = capital / outflow
            need = ramp + buffer_m
            out.update({
                "runway_months": round(runway, 1),
                "required_months": need,
                "formula": f"{capital} ÷ {outflow} = {runway:.1f} 个月；需 ≥ {ramp} + {buffer_m} = {need}",
            })

    if "verdict" not in out:
        if items < cfg["fixed_cost_min_items"]:
            out.update({
                "verdict": "信息不足",
                "reason": f"月度固定支出只覆盖 {items} 项，需 {cfg['fixed_cost_min_items']} 项（店租、人工、生活开支、其他）"
                          "；缺项时不许用行业常规值填分母",
            })
        else:
            out["verdict"] = "通过" if out["runway_months"] >= out["required_months"] else "不通过"
    return out


def tool_taxonomy_lookup(args: dict, params: dict) -> dict:
    keyword = str(args.get("keyword", "")).strip()
    if not keyword:
        return {"error": "keyword 必填：用户说的方向，如「卤味摊」「家政保洁」"}
    rows = parse_taxonomy()
    if not rows:
        return {"error": "读不到 data/industry-taxonomy.md，安装单元可能不完整"}
    hits = [r for r in rows if keyword in r["name"] or any(keyword in e for e in r["examples"])]
    if not hits:
        hits = [r for r in rows if any(keyword[:2] in e for e in r["examples"])]
    archetypes = sorted({a for h in hits for a in h["archetypes"]})
    return {
        "keyword": keyword,
        "matched": bool(hits),
        "categories": hits,
        "archetype_candidates": archetypes,
        "note": ("门类不决定原型；可及度为「否」的门类不必继续评估" if hits
                 else "未命中门类。先问清具体做什么，再按「用途→场所→客户」落到门类，不要猜"),
        "all_categories": [{"code": r["code"], "name": r["name"], "reachability": r["reachability"]} for r in rows],
    }


def tool_source_grade(args: dict, params: dict) -> dict:
    url = str(args.get("url", "")).strip()
    if not url:
        return {"error": "url 必填：要判级的链接或域名"}
    grade, why = grade_for(url, params)
    cfg = params["source_grades"]
    return {
        "url": url,
        "grade": grade,
        "grade_name": cfg["levels"][grade],
        "basis": why,
        "usage": cfg["usage"][grade],
        "combo_rule": cfg["combo"],
        "reminder": "L4 不进判断；L3 不能替代用户自己查；单来源 L2 按 L4 处理",
    }


def tool_search_budget(args: dict, params: dict) -> dict:
    required = args.get("required_online")
    if not isinstance(required, int) or required < 0:
        return {"error": "required_online 必填：必查项数量（整数）"}
    cfg = params["search"]
    budget = min(required * cfg["multiplier"], cfg["cap"])
    return {
        "required_online": required,
        "budget": budget,
        "capped": required * cfg["multiplier"] > cfg["cap"],
        "rule": cfg["rule"],
        "offline": "线下必查项不占预算，转成用户动作",
    }


TOOLS = {
    "capital_band": (
        tool_capital_band,
        "按预算定资金带（B1–B6），返回这一档能碰与碰不了的原型、致命约束、接着必问的三个数。"
        "只做分档，不判断能不能做。左闭右开：3000 落 B2。",
        {
            "type": "object",
            "properties": {"amount_cny": {"type": "number", "description": "用户打算投的钱，人民币元"}},
            "required": ["amount_cny"],
        },
    ),
    "h2_check": (
        tool_h2_check,
        "算 H2 现金流断点：情形 A 看可撑月数 ≥ 首笔收入月数 +1，情形 B 看流动资金 ÷ 月净流出 ≥ 爬坡期 +1。"
        "首笔收入在首月内用 B，否则用 A。只算数给判定，不给建议。固定支出覆盖不足 3 项时判信息不足。",
        {
            "type": "object",
            "properties": {
                "case": {"type": "string", "enum": ["A", "B"], "description": "A 先投入后收钱；B 开业即有收入但净流出"},
                "available_fund": {"type": "number", "description": "情形 A：可用资金"},
                "monthly_fixed": {"type": "number", "description": "情形 A：月度固定支出（含生活开支）"},
                "months_to_first_income": {"type": "number", "description": "情形 A：预计首笔收入月数，取保守值"},
                "working_capital": {"type": "number", "description": "情形 B：流动资金 = 可用资金 − 开店投入"},
                "monthly_net_outflow": {"type": "number", "description": "情形 B：月净流出 = 月度固定支出 − 月净利"},
                "ramp_months": {"type": "number", "description": "情形 B：爬坡期，未知时省略，按 6 个月算"},
                "fixed_cost_items": {"type": "integer", "description": "月度固定支出已覆盖几项（店租、人工、生活开支、其他）"},
            },
            "required": ["case", "fixed_cost_items"],
        },
    ),
    "taxonomy_lookup": (
        tool_taxonomy_lookup,
        "把用户说的方向落到国标 20 门类之一，返回可及度与原型候选。只做定位，不判断可行性，也不提供成本数据。",
        {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "用户口中的方向，如「卤味摊」「家政保洁」"}},
            "required": ["keyword"],
        },
    ),
    "source_grade": (
        tool_source_grade,
        "给链接或域名定来源级（A 官方 / B 行业组织 / C 主流媒体 / D 利益相关方 / E 用户生成），"
        "并给出该级的用法限制与数据级别组合规则。识别不到时按 E 推定并说明依据。",
        {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "链接或域名"}},
            "required": ["url"],
        },
    ),
    "search_budget": (
        tool_search_budget,
        "按必查项数量算检索预算：线上必查项 × 2，上限 12。线下必查项不占预算，转成用户动作。",
        {
            "type": "object",
            "properties": {"required_online": {"type": "integer", "description": "线上必查项数量"}},
            "required": ["required_online"],
        },
    ),
}
