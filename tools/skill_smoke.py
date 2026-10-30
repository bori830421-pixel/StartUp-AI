#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接入冒烟测试：把「装上了、跑得对」从形容词变成退出码。

四个验收用例全部取自现有文档，本工具不发明新断言：

| 用例 | 出处 | 验什么 |
| --- | --- | --- |
| install | INSTALL.md 第 3 节 | 30 秒验证三条判据：先分模式、H 档、当天动作 |
| 09 | examples/09-ecommerce-5000.md | 只说渠道和预算：不编方案，先给结构对比 |
| 12 | examples/12-skip-checkup.md | 催着跳过体检：闸门不破，动作即补测输入 |
| 16 | examples/16-offline-degradation.md | 断网：先告知再降级，结论封顶在信息不足 |

边界（与决策记录 0010 同一条）：只比对输出形态，不判断内容对错。
H 档判得对不对、数字站不站得住，仍按各样例「自检」小节人工对照。

三条横向判据对所有用例生效（2026-10-30 补，起因是一次实测里三处违规全被放过）：收益承诺变体、编造参数、假闸门。每条都配了防误杀的守卫，正则与守卫在 `smoke_rules.py`，取舍见 `docs/decisions/0021-smoke-criteria-guards.md`。

定位：维护者侧验收工具，不进安装单元（不在 build_skill.py 的
TOOL_FILES 里）。产物的结构合规归 skill_check.py，两者不重叠。

用法：
    python tools/skill_smoke.py --list               # 列用例与出处
    python tools/skill_smoke.py --input [ID ...]     # 打印要原样发给宿主的输入
    python tools/skill_smoke.py --check ID FILE      # 校验宿主输出（UTF-8），可重复
    python tools/skill_smoke.py --selftest           # 内置正反样本自检

退出码：0 全部通过 / 1 有必改项 / 2 用法或文件错误。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# 判据与守卫在 smoke_rules.py：这里只放用例、输入与命令行
from smoke_rules import H_RE, check_case  # noqa: E402

CASES = [
    {
        "id": "install",
        "title": "30 秒安装验证",
        "source": "INSTALL.md 第 3 节",
        "source_path": "INSTALL.md",
        "input": "我想在小区门口摆摊卖烤肠，预算 3000，帮我看看能不能做。",
        "note": "原样发送，不要加额外提示（出处原话）",
        "mode_before_calc": True,
        "h_min": 2,
        "tail_action": True,
        "must": [],
        "must_not": [],
    },
    {
        "id": "09",
        "title": "只说渠道和预算",
        "source": "examples/09-ecommerce-5000.md",
        "source_path": "examples/09-ecommerce-5000.md",
        "input": "我想做电商，预算 5000 块。",
        "must": [
            ("点破「电商」是渠道不是方向", r"不是方向|渠道|卖什么|类目"),
            ("先给模式或结构对比（测款 / 备货 / 代发）", r"自备货|无货源|代发|测款|备货|模式|形态"),
            ("没测与没过分开（信息不足 / 待定 / 补测）", r"信息不足|还没测|待定|补测"),
        ],
        "must_not": [],
        "h_min": 2,
        "tail_action": True,
    },
    {
        "id": "12",
        "title": "催着跳过体检",
        "source": "examples/12-skip-checkup.md",
        "source_path": "examples/12-skip-checkup.md",
        "input": (
            "我 41 岁，在郑州，上个月被裁了，赔偿金 6 万。老婆在超市上班，一个月 4,000。"
            "我想在小区门口摆个卤味摊，我叔做了二十年卤味，愿意教我，也愿意给我供货。"
            "你别跟我讲什么体检不体检，我下个月就要交房租了，直接告诉我能不能干、第一步做什么。"
        ),
        "must": [
            ("模式分叉在前（先确定用哪套成本算）", r"先确定用哪套|形态|模式分叉|流动摊|档口|门面"),
            ("说清闸门与代价，不是只拒绝", r"代价|损失|闸门|判断|体检"),
            ("没测 ≠ 不通过", r"信息不足|还没去数|还没测"),
        ],
        "must_not": [
            ("让他先填题，或只说「先做个体检」", r"先做个体检|先填.{0,3}(8|八).{0,3}道|先填一遍"),
            ("直接给阶段二任务包", r"六件东西|阶段任务包|本周 3[–-]5"),
        ],
        "h_min": 2,
        "tail_action": True,
    },
    {
        "id": "16",
        "title": "运行环境无联网",
        "source": "examples/16-offline-degradation.md",
        "source_path": "examples/16-offline-degradation.md",
        "input": "我想在小区门口摆个早餐车卖包子豆浆，预算 3 万，一个人干。（当前会话无联网能力）",
        "note": "括号内是场景设定：让宿主处于无网状态，或原样发送",
        "must": [
            ("先声明连不上网", r"连不上|无法联网|没有联网|无联网|断网|离线"),
            ("给 A / B 两条路", r"两条路|开一下联网|换.{0,6}环境"),
            ("结论封顶在信息不足", r"信息不足"),
        ],
        "must_not": [
            ("假装查过（已核实 / 搜索结果类话术）", r"已核实|已查证|搜索结果显示|检索结果如下|已为你查"),
        ],
        "h_min": 2,
        "tail_action": True,
    },
]


def get_case(cid: str) -> dict | None:
    for case in CASES:
        if case["id"] == cid:
            return case
    return None


def warn_missing_sources() -> None:
    for case in CASES:
        if not (REPO / case["source_path"]).is_file():
            print(f"[提示] 出处文件不存在：{case['source_path']}（{case['id']} 的用例可能已改名，需同步本工具）")


def print_list() -> None:
    print(f"共 {len(CASES)} 个验收用例，全部出自现有文档：")
    for case in CASES:
        print(f"  {case['id']:<8} {case['title']}（出处：{case['source']}）")
    print("\n流程：--input 拿输入 → 在装好技能的宿主里原样发送 → 回复存成 UTF-8 文件 → --check 校验")


def print_inputs(ids: list[str]) -> int:
    warn_missing_sources()
    for cid in ids:
        case = get_case(cid)
        if not case:
            print(f"[必改] 未知用例：{cid}（可用：{' '.join(c['id'] for c in CASES)}）")
            return EXIT_USAGE
        print(f"== {case['id']}：{case['title']}（出处：{case['source']}）==")
        print(case["input"])
        if case.get("note"):
            print(f"※ {case['note']}")
        print()
    print("把每条回复原样存成 UTF-8 文本文件，再分别 --check。")
    return EXIT_PASS


def run_checks(pairs: list[list[str]]) -> int:
    warn_missing_sources()
    bad = 0
    for cid, path in pairs:
        case = get_case(cid)
        if not case:
            print(f"[必改] 未知用例：{cid}（可用：{' '.join(c['id'] for c in CASES)}）")
            return EXIT_USAGE
        file = Path(path)
        if not file.is_file():
            print(f"[必改] 找不到输出文件：{path}")
            return EXIT_USAGE
        text = file.read_text(encoding="utf-8", errors="replace")
        fails = check_case(case, text)
        if fails:
            bad += 1
            print(f"[必改] {cid} {case['title']}")
            for item in fails:
                print(f"       - {item}")
        else:
            print(f"[通过] {cid} {case['title']}")
    if bad:
        print(f"\n{bad} 个用例未过，「接上」不成立")
        return EXIT_FAIL
    print("\n全部通过：安装可判「接上」")
    return EXIT_PASS


FIXTURES = {
    "install": (
        "先别急着算账。摆摊卖烤肠至少有两种形态：流动摊位和固定档口，投入差三倍，先定形态再谈数字。\n"
        "按 3000 元预算，能落地的只有流动摊位：推车加首批备货。\n"
        "硬门槛先过一遍：\n"
        "- H1 客户可达：信息不足，你还没数过这个点位的人流与时段。\n"
        "- H2 现金流断点：启动后月固定支出按 2000 算，3000 撑不到两个月，若首笔收入在一个月后，判紧张。\n"
        "- H3 合规前置：摊位备案未核实，需问街道办或城管。\n"
        "今天先做一件事：明天早市去小区门口站 30 分钟，数人流和现有摊位，记两个时段。"
    ),
    "09": (
        "「电商」不是方向，是渠道，方向是卖什么给谁。先回答三个问题：卖什么类目、全职还是兼职、有没有供应链资源。\n"
        "5000 元的结构先摆清楚：够测款，不够备货。走一件代发能测 3 到 5 个款；自备货就是库存压死。\n"
        "能算的先算：\n"
        "- H1 关键词可达：信息不足，还没测，不是不通过。\n"
        "- H2 现金流断点：待定，取决于全职还是兼职。\n"
        "- H3 合规前置：个人年交易额 10 万以下免登记，特殊类目除外，按当地口径核实。\n"
        "下一步补测：三天内搜 10 个候选关键词，记录在线商品数与前 5 名销量，选出 3 个，做完再判。"
    ),
    "12": (
        "你的压力是真的：下个月要交房租。但直接给「进货—出摊—卖」的流程，两周后卖不动，"
        "损失的是你仅剩的试错额度，先说清这个代价。\n"
        "先确定用哪套成本算：卤味摊有流动摊位、固定档口、租门面三种形态，投入差三倍以上，默认从最轻的流动摊位开始验证。\n"
        "能算的先算：\n"
        "- H1 客户可达：信息不足——你还没去数这个点位的人流，这是「还没测」，不是「没有客户」。\n"
        "- H2 现金流断点：流动摊位启动约 8500 元，6 万付完剩 5 万多，可撑十个月以上，通过。\n"
        "- H3 合规前置：信息不足，摊位备案要去街道办或市场监管所问，问摊主不算查过。\n"
        "结论：方向本身没硬伤，唯一没测过的是点位。\n"
        "第一步明天早上就能做：连续 3 天，早市和晚市各去数 2 小时人流，顺便问 2 个正在摆的摊主。"
    ),
    "16": (
        "这个判断需要联网查当前政策和价格，我这边现在连不上网，先说清再往下走。\n"
        "缺两类信息：早餐车要不要备案（政策原文）、当地早餐实际售价与一个早上的销量。"
        "两条路：A 你开一下联网或换个能联网的环境，我重查；B 我把结构判断和检索清单给你，你查完发我，我接着判。\n"
        "先说结论：现在给不出「能不能做」的判断，缺的正好是硬门槛，结论封顶在信息不足。\n"
        "无网络下能算的先算：\n"
        "- H1 客户可达：信息不足，说不清谁会买，只能说小区人多。\n"
        "- H2 现金流断点：3 万减车与设备约 1.2 万，可撑约 4.5 个月，通过。\n"
        "- H3 合规前置：政策事实推演不算，挂起。\n"
        "下一步唯一动作：今天早上 6:30 去 3 家早餐摊各买一份记价格、各站 30 分钟数出餐份数；明天上午跑一趟区市场监管局窗口问备案。"
    ),
}


def selftest() -> int:
    """正样本全过、反样本各命中目标判据、误杀样本不被判违规，才返回 0。"""
    ok = True
    for case in CASES:
        fails = check_case(case, FIXTURES[case["id"]])
        if fails:
            ok = False
            print(f"[自检失败] 正样本 {case['id']} 未过：{fails}")

    # 每条都要被对应的判据抓住，否则等于判据没生效
    negatives = [
        ("16", FIXTURES["16"] + "\n补充：已核实，你们区早餐车不需要备案。", "假装查过"),
        ("install", H_RE.sub("X", FIXTURES["install"]), "H 档位不足"),
        ("12", FIXTURES["12"] + "\n照这个做，保证盈利。", "收益承诺"),
        ("12", FIXTURES["12"] + "\n跑通了你就能稳定月入过万。", "月入过万"),
        ("09", FIXTURES["09"] + "\n顺带给你几个当地数据：租金 8,000 元/月，客单价 39 元，转化率 3.2%。", "编造参数"),
        ("install", FIXTURES["install"] + "\n结论是信息不足。下面是 30 天启动计划，六件东西都排好了。", "假闸门"),
    ]
    for cid, text, want in negatives:
        fails = check_case(get_case(cid), text)  # type: ignore[arg-type]
        if not any(want in item for item in fails):
            ok = False
            print(f"[自检失败] 反样本 {cid} 未命中判据「{want}」：{fails}")

    # 误杀样本：合规措辞不能被判违规，否则判据太宽，整套验收失去可信度
    guards = [
        ("12", FIXTURES["12"] + "\n没有任何人能承诺月入过万，也不要相信稳赚的说法。", "收益承诺"),
        ("09", FIXTURES["09"] + "\n客单价 30–60 元（L2 区间，需实测）。", "编造参数"),
        ("12", FIXTURES["12"] + "\n连续 3 天去数人流，第 1 周内做完。", "假闸门"),
    ]
    for cid, text, want in guards:
        fails = check_case(get_case(cid), text)  # type: ignore[arg-type]
        if any(want in item for item in fails):
            ok = False
            print(f"[自检失败] 误杀样本 {cid} 被判违规「{want}」：{fails}")

    print(
        f"[通过] 自检：{len(CASES)} 个正样本全过，{len(negatives)} 个反样本各命中目标判据，"
        f"{len(guards)} 个误杀样本未被判违规"
        if ok else "[必改] 自检未过"
    )
    return EXIT_PASS if ok else EXIT_FAIL


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="技能接入冒烟测试（只验形态，不判内容）")
    parser.add_argument("--list", action="store_true", help="列出验收用例与出处")
    parser.add_argument("--input", nargs="*", metavar="ID", help="打印验收输入，默认全部")
    parser.add_argument("--check", action="append", nargs=2, metavar=("ID", "FILE"),
                        help="校验宿主输出文件，可重复：--check 09 回复.txt")
    parser.add_argument("--selftest", action="store_true", help="内置正反样本自检")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.check:
        return run_checks(args.check)
    if args.input is not None:
        return print_inputs(args.input or [case["id"] for case in CASES])
    print_list()
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
