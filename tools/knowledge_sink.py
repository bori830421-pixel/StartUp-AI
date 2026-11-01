#!/usr/bin/env python3
"""检索沉淀器：把一次真实检索的路径与结论状态写进本地知识库。

设计边界（决策 0030）：
  - 只写 local-knowledge/regions/，不写 data/、不写 dist/、不入库
  - 只存「怎么查、查到没、哪里是死路」，不存金额与判断
  - 默认按城市层级聚合；差异大的城市可用 --solo 单独成文件

层级只是默认归类，不是硬约束。同档城市查询串相似就合并，差异大的单独开——
判断标准是「下次检索时能不能直接套用」，不是行政区划。
分类逻辑（层级表、品类号、路径解析）在 knowledge_taxonomy.py。

用法：
    python tools/knowledge_sink.py --list             # 有哪些记录文件
    python tools/knowledge_sink.py --find 深圳        # 某城市记录在哪（先跑这个）
    python tools/knowledge_sink.py --show 一线        # 打印某层级
    python tools/knowledge_sink.py --add 深圳 --category 01 --form 门店 \
        --source "许可口径|深圳 食品经营许可 小餐饮 备案|市场监管|拿到原文" \
        --deadend "本地生活平台客单页全是询底价" \
        --gap "客单价带：公开渠道无可比报价"
    python tools/knowledge_sink.py --add 上海 --solo --category 01 --form 门店 ...
    python tools/knowledge_sink.py --check            # 结构自检
    python tools/knowledge_sink.py --selftest         # 回归自检
"""
import argparse
import os
import re
import sys
from datetime import date

from knowledge_taxonomy import (
    CATEGORIES, TIER_NOTE, TIERS,
    is_known_city, normalize_category, normalize_city,
    resolve_path, solo_path, tier_of, tier_path,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 记录根目录。模块级变量是为了 selftest 能指向临时目录；对外用法不改它。
REGIONS = os.path.join(REPO, "local-knowledge", "regions")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _parse_rows(line: str) -> list:
    """把「a|b|c|d」拆成四列；不足四列补空，多于四列并进最后一列。"""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        parts += [""] * (4 - len(parts))
    elif len(parts) > 4:
        parts = parts[:3] + ["|".join(parts[3:])]
    return parts


def add_record(city: str, category: str, form: str, sources: list,
               deadends: list, gaps: list, today: str | None = None,
               solo: bool | None = None) -> str:
    """把一次检索写进对应文件，返回写入路径。

    默认落层级文件（一线/新一线/二线/三线及以下），节内按城市分子节。
    solo=True 时该城市单独成文件，文件内只有这一个城市。
    同城同品类同形态重写时只替换那个城市子节，不影响同档其他城市。
    """
    city = normalize_city(city)
    category = normalize_category(category)
    path, is_solo = resolve_path(city, solo, REGIONS)
    today = today or date.today().isoformat()
    tier = tier_of(city)

    text = _read(path) if os.path.exists(path) else _new_tier_file(tier, city if is_solo else None)
    marker = f"### {category} {form}"
    sub = _render_city_sub(city, sources, deadends, gaps, today)

    if marker in text:
        text = _upsert_city_sub(text, marker, city, sub)
    else:
        section = f"{marker}\n\n{sub}"
        if "## 使用提示" in text:
            text = text.replace("## 使用提示", section.rstrip() + "\n\n## 使用提示", 1)
        else:
            text = text.rstrip() + "\n\n" + section

    _write(path, _stamp(text, today))
    return path


def _upsert_city_sub(text: str, marker: str, city: str, sub: str) -> str:
    """在已有品类节内替换或追加该城市的子节。"""
    start = text.index(marker)
    end = len(text)
    for sep in ("\n### ", "\n## "):
        idx = text.find(sep, start + len(marker))
        if idx != -1:
            end = min(end, idx)
    section = text[start:end]

    if f"#### 城市：{city}" in section:
        # 标题行是「#### 城市：深圳（一线）· 采集 …」，城市名后不是换行，
        # 所以要用 [^\n]*\n 吃掉整行，只按城市名定位
        pat = re.compile(r"#### 城市：" + re.escape(city) + r"[^\n]*\n.*?(?=\n#### 城市：|\Z)", re.S)
        new_section = pat.sub(sub.rstrip() + "\n", section, count=1)
    elif "#### 城市：" in section:
        new_section = section.rstrip() + "\n\n" + sub
    else:
        new_section = marker + "\n\n" + sub

    return text[:start] + new_section + text[end:]


def _render_city_sub(city, sources, deadends, gaps, today) -> str:
    """单个城市子节。同层级多城市共存时只替换这一小节。"""
    lines = [f"#### 城市：{city}（{tier_of(city)}）· 采集 {today}", "",
             "**拿到的源**", "",
             "| 项 | 查询串 | 站点 | 拿到什么 |",
             "| --- | --- | --- | --- |"]
    for item in sources:
        lines.append("| " + " | ".join(_parse_rows(item)) + " |")
    if not sources:
        lines.append("| 无 | — | — | — |")

    lines += ["", "**死路（下次别在这花预算）**", ""]
    lines += [f"- {d}" for d in deadends] or ["- 无"]

    lines += ["", "**结构性空缺（转用户实测，不要重复搜）**", ""]
    lines += [f"- {g}" for g in gaps] or ["- 无"]
    return "\n".join(lines) + "\n"


def _stamp(text: str, today: str) -> str:
    """把「最近更新」改成今天。"""
    return re.sub(r"(\| 最近更新 \|)[^|]*(\|)", rf"\g<1> {today} \g<2>", text, count=1)


def _new_tier_file(tier: str, solo_city: str | None = None) -> str:
    if solo_city:
        return (
            f"# {solo_city} · 检索记录\n\n"
            "本地检索记录，不入库、不进分发包。只存检索路径与结论状态；具体数字见品类卡缓存节。\n\n"
            "| 元信息 | 内容 |\n| --- | --- |\n"
            f"| 覆盖范围 | {solo_city} 单独成文件（{tier}，与同档城市差异大） |\n"
            "| 最近更新 | — |\n\n"
            + _TAIL
        )
    return (
        f"# {tier}城市 · 检索记录\n\n"
        "本地检索记录，不入库、不进分发包。只存检索路径与结论状态；具体数字见品类卡缓存节。\n\n"
        "| 元信息 | 内容 |\n| --- | --- |\n"
        f"| 覆盖层级 | {tier}（{TIER_NOTE[tier]}） |\n"
        "| 最近更新 | — |\n\n"
        + _TAIL
    )


# 使用提示固定放末尾：新增节一律插在它前面，保证越加越长的记录不会把提示埋掉
_TAIL = (
    "## 使用提示\n\n"
    "命中后仍要跑检索循环：政策看有没有新文，租金与工资每次重新询价。"
    "超过 6 个月只当检索起点，超过 12 个月视为无记录。\n"
)


def _record_files() -> list:
    """所有记录文件（层级文件 + 城市单独文件），跳过 README。"""
    out = []
    for dirpath, _dirs, names in os.walk(REGIONS):
        for name in sorted(names):
            if name.endswith(".md") and name != "README.md":
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def check() -> int:
    """结构自检：单文件不超 50 KB、每个城市子节三块齐全。"""
    if not os.path.isdir(REGIONS):
        print(f"缺目录 {REGIONS}")
        return 1
    problems = []
    for path in _record_files():
        rel = os.path.relpath(path, REGIONS).replace(os.sep, "/")
        size = os.path.getsize(path)
        if size > 50 * 1024:
            problems.append(f"{rel}: {size // 1024} KB 超过单文件 50 KB，按品类拆")
        text = _read(path)
        for block in re.split(r"^#### 城市：", text, flags=re.M)[1:]:
            city = block.splitlines()[0] if block.splitlines() else "?"
            for need in ("**拿到的源**", "**死路", "**结构性空缺"):
                if need not in block:
                    problems.append(f"{rel} → {city}: 缺「{need}」")
    for p in problems:
        print(p)
    print(f"\n检查 {REGIONS}：{len(problems)} 项缺陷")
    return 1 if problems else 0


def find(city: str) -> int:
    """某城市的记录在哪个文件、哪些品类。快速定位用。"""
    name = normalize_city(city)
    hits = []
    for path in _record_files():
        text = _read(path)
        if f"#### 城市：{name}" not in text:
            continue
        rel = os.path.relpath(path, REGIONS).replace(os.sep, "/")
        cats, cur = [], None
        for line in text.splitlines():
            if line.startswith("### "):
                cur = line[4:].strip()
            elif line.startswith(f"#### 城市：{name}"):
                cats.append(cur or "?")
        hits.append((rel, cats))

    if not hits:
        tier = tier_of(name)
        print(f"{name}：暂无记录（默认会写进 {tier}.md）")
        return 0
    for rel, cats in hits:
        print(f"{name} → {rel}")
        print(f"  已记录品类：{', '.join(cats)}")
    return 0


def selftest() -> int:
    """回归自检：在临时目录跑一遍写入/合并/替换，断言结构不变。

    这几条正是开发时踩过的坑：同档城市互相覆盖、替换正则匹配不到标题行、
    品类标题丢失、提示被埋到中间。改动渲染逻辑后先跑这个。
    """
    import shutil
    import tempfile

    global REGIONS
    saved, tmp = REGIONS, tempfile.mkdtemp(prefix="ks-selftest-")
    REGIONS = tmp
    cases = []
    try:
        cases += [
            ("层级 深圳=一线", tier_of("深圳") == "一线"),
            ("层级 长沙=新一线", tier_of("长沙") == "新一线"),
            ("层级 合肥=二线", tier_of("合肥") == "二线"),
            ("层级 张家口=三线及以下", tier_of("张家口") == "三线及以下"),
            ("层级 带「市」后缀", tier_of("深圳市") == "一线"),
        ]

        add_record("深圳", "01", "门店", ["项|q1|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        add_record("广州", "01", "门店", ["项|q2|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        text = _read(os.path.join(tmp, "一线.md"))
        cases += [
            ("同档两城共存", text.count("#### 城市：") == 2),
            ("广州未覆盖深圳", "q1" in text and "q2" in text),
            ("品类标题保留", "### 01 门店" in text),
        ]

        add_record("深圳", "01", "门店", ["项|q3|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        text = _read(os.path.join(tmp, "一线.md"))
        cases += [
            ("同城重写仍两城", text.count("#### 城市：") == 2),
            ("深圳已更新", "q3" in text),
            ("广州保留", "q2" in text),
        ]

        add_record("北京", "09", "门店", ["项|q4|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        text = _read(os.path.join(tmp, "一线.md"))
        cases += [
            ("不同品类分节", "### 01 门店" in text and "### 09 门店" in text),
            ("使用提示在末尾", text.rstrip().endswith("视为无记录。")),
            ("check 通过", check() == 0),
            ("未用层级不预建", not os.path.exists(os.path.join(tmp, "二线.md"))),
        ]

        # solo：差异大的城市单独成文件，不跟同档合并
        solo_p = add_record("上海", "01", "门店", ["项|q5|站|拿到"],
                            ["死路"], ["空缺"], "2026-11-01", solo=True)
        cases += [
            ("solo 落在城市子目录", os.sep + "城市" + os.sep in solo_p),
            ("solo 文件只有该城", _read(solo_p).count("#### 城市：") == 1),
            ("solo 不污染层级文件", "上海" not in _read(os.path.join(tmp, "一线.md"))),
            ("solo 重复写入仍落原文件", add_record("上海", "01", "门店", ["项|q6|站|拿到"],
                                                  ["死路"], ["空缺"], "2026-11-01") == solo_p),
        ]
        # 显式 --solo 后再写同城，不带 solo 也应继续落原文件
        cases.append(("solo 后默认续写原文件", resolve_path("上海", None, REGIONS)[1] is True))

        # 城市名归一：深圳市 / 深圳宝安 不能各建一节
        before = _read(os.path.join(tmp, "一线.md")).count("#### 城市：")
        add_record("深圳市", "01", "门店", ["项|q7|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        add_record("深圳宝安", "01", "门店", ["项|q8|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        after = _read(os.path.join(tmp, "一线.md"))
        cases += [
            ("深圳市归到深圳", after.count("#### 城市：") == before),
            ("区县名归到所属城市", "深圳宝安" not in after and "q8" in after),
            ("区县名不落三线", not os.path.exists(os.path.join(tmp, "三线及以下.md"))),
        ]

        # 品类号归一：1 / 01 / 中文名 落同一节
        for cat in ("1", "餐饮食品"):
            add_record("北京", cat, "档口", ["项|q9|站|拿到"], ["死路"], ["空缺"], "2026-11-01")
        cats = re.findall(r"^### (.+)$", _read(os.path.join(tmp, "一线.md")), re.M)
        cases += [
            ("品类号归一 1→01", cats.count("01 档口") == 1),
            ("中文品类名归一", len([c for c in cats if c.startswith("01 ")]) == 2),
        ]

        # 未知品类必须报错，不许静默建节
        try:
            add_record("北京", "餐饮", "门店", [], [], [], "2026-11-01")
            cases.append(("未知品类报错", False))
        except ValueError:
            cases.append(("未知品类报错", True))
    finally:
        REGIONS = saved
        shutil.rmtree(tmp, ignore_errors=True)

    for name, passed in cases:
        print(("  OK  " if passed else "  FAIL") + "  " + name)
    good = sum(1 for _, p in cases if p)
    print(f"\n自检 {good}/{len(cases)} 通过")
    return 0 if good == len(cases) else 1


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="检索沉淀器：写本地知识库")
    ap.add_argument("--list", action="store_true", help="列出所有记录文件")
    ap.add_argument("--find", metavar="城市", help="某城市记录在哪个文件、哪些品类")
    ap.add_argument("--show", metavar="层级或城市", help="打印某个记录文件")
    ap.add_argument("--tier", metavar="城市", help="查某城市默认落哪一层")
    ap.add_argument("--solo", action="store_true",
                    help="该城市单独成文件（差异大、不跟同档合并时用）")
    ap.add_argument("--check", action="store_true", help="结构自检")
    ap.add_argument("--selftest", action="store_true", help="回归自检：临时目录跑写入/合并/替换")
    ap.add_argument("--add", metavar="城市", help="写入一条检索记录")
    ap.add_argument("--category", default="", help="品类号，如 01")
    ap.add_argument("--form", default="", help="形态，如 门店")
    ap.add_argument("--source", action="append", default=[],
                    help="源，格式「项|查询串|站点|拿到什么」，可重复")
    ap.add_argument("--deadend", action="append", default=[], help="死路，可重复")
    ap.add_argument("--gap", action="append", default=[], help="结构性空缺，可重复")
    args = ap.parse_args(argv)

    if args.tier:
        print(f"{args.tier} → {tier_of(args.tier)}")
        return 0

    if args.find:
        return find(args.find)

    if args.list:
        for path in _record_files():
            rel = os.path.relpath(path, REGIONS).replace(os.sep, "/")
            text = _read(path)
            cities = re.findall(r"^#### 城市：([^（\n]+)", text, re.M)
            cats = re.findall(r"^### (.+)$", text, re.M)
            print(f"{rel:16s} {os.path.getsize(path) // 1024:3d} KB  "
                  f"城市 {len(cities)} 个  品类 {', '.join(cats) if cats else '—'}")
        return 0

    if args.show:
        path = tier_path(args.show, REGIONS)
        if not os.path.exists(path):
            path = solo_path(args.show, REGIONS)
        if not os.path.exists(path):
            print(f"{args.show} 还没有记录")
            return 0
        print(_read(path))
        return 0

    if args.check:
        return check()

    if args.selftest:
        return selftest()

    if args.add:
        if not (args.category and args.form):
            print("--add 需要同时给 --category 与 --form")
            return 2
        try:
            path = add_record(args.add, args.category, args.form,
                              args.source, args.deadend, args.gap,
                              solo=True if args.solo else None)
        except ValueError as exc:
            print(f"品类号不认识：{exc}")
            return 2
        city = normalize_city(args.add)
        print(f"已写入 {os.path.relpath(path, REPO)}")
        print(f"  城市：{city}（{tier_of(city)}）  品类：{normalize_category(args.category)}")
        if not is_known_city(city):
            print(f"  [提示] {city} 不在层级表里，按「三线及以下」处理。"
                  f"城市名若写错，用 --find 查一下有没有记到别的文件。")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
