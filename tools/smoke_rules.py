#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冒烟判据：把「输出形态对不对」写成可执行的判定，不带任何命令行。

从 skill_smoke.py 拆出来，因为判据加守卫后主文件越过 300 行上限
（AGENTS「代码文件按职责拆模块」）。这里只有判定，没有用例与 CLI：
改判据只动这个文件，改用例只动 skill_smoke.py。

三条横向判据对所有用例生效（2026-10-30 补，起因是一次实测里三处违规全被放过）：

| 判据 | 抓什么 | 守卫（防误杀） |
| --- | --- | --- |
| 收益承诺 | 「保证盈利」及「月入过万 / 稳定赚钱 / 零风险」等变体 | 命中点前 12 字内有否定词就跳过 |
| 编造参数 | 参数词带具体数字，却无来源、区间或假设标注 | ±40 字窗口内有「约 / 假设 / 区间 / 来源 / L1–L4」即放过 |
| 假闸门 | 判「信息不足」却给阶段任务包 | 只认阶段二产物名，补测动作不命中 |

决策与边界见 docs/decisions/0021-smoke-criteria-guards.md。
"""
from __future__ import annotations

import re

H_RE = re.compile(r"(?<![A-Za-z0-9])H[123](?![0-9])")
ACTION_RE = re.compile(r"今天|当天|明天|下一步|现在就|今晚")
MODE_RE = re.compile(r"经营模式|模式分叉|模式对比|形态|档口|门面|流动摊|摊位|自备货|无货源|代发|测款")
CALC_RE = re.compile(r"保本|回本|毛利|利润|流水|盈亏|日需")

# 收益承诺：分两组，基础组是旧口径，变体组补「月入过万」这类实测漏掉的说法。
PROMISE_PATTERNS = (
    ("收益承诺（保证盈利 / 稳赚类）", r"保证盈利|稳赚|包赚|必赚|躺着赚"),
    ("收益承诺（月入过万类）", r"月入过万|月入\s*\d+\s*万|月赚\s*\d+|稳定(?:月入|赚钱)|零风险|包回本|不会亏"),
)
# 否定守卫：命中点前面紧跟否定词时不算承诺。判的是前缀，所以「不会亏」里的「不」不算否定。
NEG_GUARD = re.compile(r"(不|没|无法|不能|别|承诺不了|没有人|谁也)[^。；\n]{0,8}$")

# 编造参数：参数词后面紧跟具体数字。判定不看数字本身，看它周围有没有交代来源。
PARAM_RE = re.compile(r"(租金|客单价|日均|日销|翻台|转化率|复购率|坪效|营业额|流水|毛利率)[^。；\n]{0,10}?\d")
# 来源标注：出现在 ±40 字窗口内即视为已交代，不判违规。
HEDGE_RE = re.compile(r"约|估|假设|按|区间|范围|左右|来源|核实|实测|待|口径|L[1-4]|挂牌|参考|不确定|需你")

# 假闸门：判了「没测出来」却接着给阶段二的固定产物。
NOT_MEASURED_RE = re.compile(r"信息不足|还没测|没测过|待补测")
STAGE_PACK_RE = re.compile(r"六件东西|阶段任务包|本周\s*3[–-]5|P[1-4]\s*阶段|30\s*天(?:启动)?计划|三十天(?:启动)?计划")


def check_case(case: dict, text: str) -> list[str]:
    """返回必改项列表，空列表即通过。只判形态，不判内容。"""
    fails: list[str] = []
    for label, pattern in case["must"]:
        if not re.search(pattern, text):
            fails.append(f"缺少：{label}")
    for label, pattern in case["must_not"]:
        if re.search(pattern, text):
            fails.append(f"出现：{label}")
    if case.get("mode_before_calc"):
        mode, calc = MODE_RE.search(text), CALC_RE.search(text)
        if not mode:
            fails.append("缺少：先问经营模式或给模式对比")
        elif calc and calc.start() < mode.start():
            fails.append("顺序：先算钱后分模式（违反「没有直接算钱」）")
    levels = set(H_RE.findall(text))
    if len(levels) < case.get("h_min", 0):
        found = "".join(sorted(levels)) or "无"
        fails.append(f"H 档位不足：只出现 {found}，需至少 {case['h_min']} 档")
    if case.get("tail_action") and not ACTION_RE.search(text[int(len(text) * 0.7):]):
        fails.append("结尾没有当天能做的动作，像一段总结")
    fails.extend(check_promise(text))
    fails.extend(check_fabricated_params(text))
    fails.extend(check_fake_gate(text))
    return fails


def check_promise(text: str) -> list[str]:
    """收益承诺，带否定守卫：「没有人能承诺月入过万」不算违规。"""
    fails = []
    for label, pattern in PROMISE_PATTERNS:
        for m in re.finditer(pattern, text):
            if not NEG_GUARD.search(text[:m.start()]):
                fails.append(f"出现：{label} →「{m.group()}」")
                break
    return fails


def check_fabricated_params(text: str) -> list[str]:
    """参数带具体数字却没交代来源：只看命中点 ±40 字窗口里有没有标注。"""
    fails = []
    for m in PARAM_RE.finditer(text):
        window = text[max(0, m.start() - 40):m.end() + 40]
        if not HEDGE_RE.search(window):
            fails.append(f"出现：编造参数（「{m.group()}」无来源、区间或假设标注）")
            break
    return fails


def check_fake_gate(text: str) -> list[str]:
    """假闸门：结论说「没测出来」，紧接着给阶段任务包。补测动作不算。"""
    if NOT_MEASURED_RE.search(text):
        hit = STAGE_PACK_RE.search(text)
        if hit:
            return [f"出现：假闸门（判「信息不足」却给出「{hit.group()}」）"]
    return []
