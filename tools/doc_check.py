#!/usr/bin/env python3
"""文档结构自检：跨平台替代 find/wc 单行命令。

判定四类缺陷（对应 AGENTS.md「文件规模与导航约束」）：
  1. 越过硬上限：Markdown 300 行 / 32 KB，代码文件 400 行
  2. 超过 120 行却没有「## 本文导航」
  3. 导航锚点对不上真实标题
  4. 相对链接失效

退出码：0 干净 / 1 有缺陷。

用法：
    python tools/doc_check.py
    python tools/doc_check.py --root . --verbose
"""
import argparse
import os
import re
import sys

MD_LINE_MAX, MD_BYTE_MAX = 300, 32 * 1024
CODE_LINE_MAX = 400
NAV_REQUIRED_OVER = 120
# .venv 是 setup.bat 装的第三方依赖，不是本项目的代码，必须跳过——
# 否则光 Pillow/pptx 就有上百个文件越过代码行数上限，把真缺陷淹没。
SKIP_DIRS = {"__pycache__", "node_modules", "venv", ".env", "wheels"}
# 工具运行产物：deck_lint / doctor / 预览在项目内建临时目录（%TEMP% 在本机不可写）。
# 异常退出会留下残骸，里面可能带 200+ 行的 text.md；不跳就会把运行残骸报成文档缺陷。
SKIP_PREFIXES = ("decklint-", "ar_pptx_", "doctor-probe-")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def slug(text: str) -> str:
    """GitHub 风格锚点：转小写，去掉标点，空格转连字符；保留中文与连字符。"""
    t = text.strip().lower()
    t = re.sub(r"[`*_~]", "", t)
    t = re.sub(r"[^\w\u4e00-\u9fff\- ]", "", t)
    return t.replace(" ", "-")


def walk(root: str):
    """按体积倒序列出所有待检文件，跳过无关目录。"""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 点开头的一律跳过：.git / .venv / .workbuddy-ai / .backup / .preview 都是
        # 工具或宿主产物，不是本项目的文档
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS
                       and not d.startswith(".")
                       and not d.startswith(SKIP_PREFIXES)]
        for name in filenames:
            if name.endswith((".md", ".py")):
                path = os.path.join(dirpath, name)
                try:
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
                except (UnicodeDecodeError, OSError) as exc:
                    found.append((path, 0, 0, str(exc), ""))
                    continue
                size = os.path.getsize(path)
                found.append((path, text.count("\n") + 1, size, "", text))
    found.sort(key=lambda r: (r[1], r[2]), reverse=True)
    return found


def check_size(rel: str, lines: int, size: int) -> list:
    if rel.endswith(".md"):
        if lines > MD_LINE_MAX or size > MD_BYTE_MAX:
            return [f"{rel}: 越过硬上限（{lines} 行 / {size // 1024} KB，上限 {MD_LINE_MAX} 行 / {MD_BYTE_MAX // 1024} KB）"]
    elif rel.endswith(".py") and lines > CODE_LINE_MAX:
        return [f"{rel}: 代码越过硬上限（{lines} 行，上限 {CODE_LINE_MAX}）"]
    return []


def check_nav(rel: str, lines: int, text: str) -> list:
    """超过 120 行必须有本文导航，且锚点要能对上真实标题。"""
    if not rel.endswith(".md"):
        return []
    has_nav = "## 本文导航" in text
    if lines > NAV_REQUIRED_OVER and not has_nav:
        return [f"{rel}: {lines} 行缺「## 本文导航」"]
    if not has_nav:
        return []

    headings, nav_anchors = set(), []
    for raw in text.splitlines():
        m = HEADING_RE.match(raw)
        if m:
            if m.group(2) != "本文导航":
                headings.add(slug(m.group(2)))
            continue
        if re.match(r"^\s*- \[", raw):
            lm = LINK_RE.search(raw)
            if lm and lm.group(1).startswith("#"):
                nav_anchors.append(lm.group(1)[1:])

    problems = []
    bad = [a for a in nav_anchors if a not in headings]
    if bad:
        problems.append(f"{rel}: 导航锚点对不上标题 → {', '.join(bad)}")
    unlisted = headings - set(nav_anchors)
    top_level = [
        slug(HEADING_RE.match(ln).group(2))
        for ln in text.splitlines()
        if HEADING_RE.match(ln) and len(HEADING_RE.match(ln).group(1)) == 2
        and HEADING_RE.match(ln).group(2) != "本文导航"
    ]
    missing = [h for h in top_level if h in unlisted]
    # 规则文件（如 AGENTS.md）条款多且短，导航只需覆盖主要章节：绝对缺失过半才算缺陷
    if missing and len(missing) * 2 > len(top_level) + 1:
        problems.append(f"{rel}: 导航不完整，缺 {len(missing)}/{len(top_level)} 个二级标题")
    return problems


def check_links(rel: str, text: str, root: str) -> list:
    if not rel.endswith(".md"):
        return []
    base = os.path.dirname(os.path.join(root, rel))
    problems = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#")[0]
        if not path_part:
            continue
        if not os.path.exists(os.path.normpath(os.path.join(base, path_part))):
            problems.append(f"{rel}: 链接失效 → {target}")
    return problems


def main() -> int:
    # Windows 控制台默认非 UTF-8，中文报告会乱码；重定向到管道时也不崩
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="文档结构自检")
    parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    parser.add_argument("--verbose", action="store_true", help="打印体积排行")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    records = walk(root)
    problems, errors = [], []

    for path, lines, size, err, text in records:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if err:
            errors.append(f"{rel}: 读取失败（{err}）")
            continue
        problems += check_size(rel, lines, size)
        problems += check_nav(rel, lines, text)
        problems += check_links(rel, text, root)

    if args.verbose:
        print("体积排行（前 20）")
        for path, lines, size, err, _ in records[:20]:
            flag = "!" if any(p.startswith(os.path.relpath(path, root).replace(os.sep, "/")) for p in problems) else " "
            print(f"  {flag} {lines:>5} 行 {size / 1024:>6.1f} KB  {os.path.relpath(path, root)}")
        print()

    for item in problems + errors:
        print(item)

    md_count = sum(1 for r in records if r[0].endswith(".md"))
    print(f"\n检查 {len(records)} 个文件（Markdown {md_count} 个）：{len(problems)} 项缺陷，{len(errors)} 项读取失败")
    return 1 if (problems or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
