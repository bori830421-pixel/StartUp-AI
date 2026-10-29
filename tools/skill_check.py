#!/usr/bin/env python3
"""校验 dist/startup-guide/ 是否符合 Agent Skills 规范与分发约束。

退出码 0 通过 / 1 有必改项（含产物过期，需重建）。
用法：python tools/skill_check.py [--path dist/startup-guide]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

from build_skill import REPO, SKILL_NAME, collect_files
from doc_check import check_links, walk

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 400
FORBIDDEN = (".venv", ".git", "__pycache__", "wheels", ".workbuddy-ai", ".pyc")


def parse_frontmatter(text: str) -> dict[str, str]:
    """解析 SKILL.md 的 YAML frontmatter，只认一层缩进，够用且不引依赖。"""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    data: dict[str, str] = {}
    parent = ""
    for raw in text[3:end].splitlines():
        if not raw.strip():
            continue
        if raw.startswith(("  ", "\t")) and parent:
            key, _, value = raw.strip().partition(":")
            data[f"{parent}.{key.strip()}"] = value.strip().strip('"')
            continue
        key, _, value = raw.partition(":")
        parent = key.strip()
        data[parent] = value.strip().strip('"')
    return data


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frontmatter(skill_md: Path, dirname: str) -> list[str]:
    """规范字段、目录名一致性，以及宿主在发现阶段能看到的环境声明。"""
    meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    if not meta:
        return ["SKILL.md 缺少 YAML frontmatter"]

    errors: list[str] = []
    name = meta.get("name", "")
    if not name:
        errors.append("frontmatter 缺 name")
    elif not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"name 不合规：{name!r}（只能小写字母、数字、连字符，≤64 字符）")
    elif name != dirname:
        errors.append(f"name 与安装目录名不一致：{name!r} != {dirname!r}")

    desc = meta.get("description", "")
    if not 0 < len(desc) <= 1024:
        errors.append(f"description 长度须在 1–1024，当前 {len(desc)}")

    comp = meta.get("compatibility", "")
    if not comp:
        errors.append("缺 compatibility：宿主发现阶段只读 name/description，环境需求只能写这里")
    elif len(comp) > 500:
        errors.append(f"compatibility 超 500 字符，当前 {len(comp)}")

    for field in ("license", "metadata.version"):
        if not meta.get(field):
            errors.append(f"缺 {field}")
    return errors


def check_layout(root: Path) -> list[str]:
    """体积、文件数、禁止入库的内容。"""
    files = [p for p in root.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    errors: list[str] = []
    if total > MAX_BYTES:
        errors.append(f"体积 {total / 1024 / 1024:.1f} MB 超上限 5 MB")
    if len(files) > MAX_FILES:
        errors.append(f"文件数 {len(files)} 超上限 {MAX_FILES}")
    for p in files:
        rel = p.relative_to(root).as_posix()
        if any(word in rel for word in FORBIDDEN):
            errors.append(f"不该进安装单元：{rel}")
    return errors


def check_fresh(root: Path) -> list[str]:
    """产物是否与源文件一致：缺文件、内容不同、多出文件都算过期。"""
    expected = {rel.as_posix(): src for src, rel in collect_files()}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    errors: list[str] = []
    for rel, src in expected.items():
        target = root / rel
        if not target.is_file():
            errors.append(f"产物缺文件：{rel}（需重建）")
        elif sha(target) != sha(src):
            errors.append(f"产物已过期：{rel}（源文件改过，需重建）")
    for rel in sorted(actual - set(expected)):
        errors.append(f"产物多出文件：{rel}（移除或加进 build_skill 清单）")
    return errors


def check_dead_links(root: Path) -> list[str]:
    """装上去之后打不开的链接：正文链接了维护者文件就会在这里暴露。"""
    errors: list[str] = []
    for path, _lines, _size, err, text in walk(str(root)):
        if err:
            errors.append(f"读取失败：{path}")
            continue
        rel = os.path.relpath(path, str(root)).replace(os.sep, "/")
        errors += check_links(rel, text, str(root))
    return errors


def cny_label(amount: int) -> str:
    """把金额写成文档里的中文写法：3000 → 3 千，30000 → 3 万。"""
    if amount == 0:
        return "0"
    if amount % 10000 == 0:
        return f"{amount // 10000} 万"
    if amount % 1000 == 0:
        return f"{amount // 1000} 千"
    return str(amount)


def check_params(root: Path) -> list[str]:
    """params.json 与文档一致，否则就是两套真相。

    MCP 与脚本读 json，人读 md。两边各自漂移时，用户拿到的判断和文档写的
    规则会对不上，而且没人会发现。这里把「一致」变成可执行的断言。
    """
    import json

    path = root / "data" / "params.json"
    if not path.is_file():
        return ["缺 data/params.json：MCP 与工具都从它读阈值"]
    try:
        params = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"data/params.json 不是合法 JSON：{exc}"]

    errors: list[str] = []
    bands = params.get("capital_bands", [])
    if len(bands) != 6:
        errors.append(f"资金带应为 6 档，params.json 有 {len(bands)} 档")
    cursor = 0
    for band in bands:
        if band["lo"] != cursor:
            errors.append(f"{band['id']} 下界 {band['lo']} 与前档上界 {cursor} 不相接")
        cursor = band["hi"]

    bands_doc = root / "references" / "capital-bands.md"
    if bands_doc.is_file():
        text = bands_doc.read_text(encoding="utf-8")
        for band in bands[1:]:
            label = cny_label(band["lo"])
            if label not in text:
                errors.append(f"文档切点与 params 不一致：{band['id']} 起点 {label} 未出现在 capital-bands.md")
        if "30 万" not in text:
            errors.append("capital-bands.md 缺 30 万切点，与 params 的 B5/B6 边界对不上")
    else:
        errors.append("缺 references/capital-bands.md")

    scorecard = root / "references" / "checkup-scorecard.md"
    h2 = params.get("h2", {})
    if scorecard.is_file():
        text = scorecard.read_text(encoding="utf-8")
        if f"+ {h2.get('buffer_months', 1)}" not in text:
            errors.append(f"checkup-scorecard.md 缺 H2 缓冲项 + {h2.get('buffer_months')}")
        if f"**{h2.get('default_ramp_months', 6)} 个月**" not in text:
            errors.append(f"checkup-scorecard.md 缺爬坡期默认 {h2.get('default_ramp_months')} 个月")
        if "三项构成" not in text:
            errors.append("checkup-scorecard.md 缺「月度固定支出必须由三项构成」")
    else:
        errors.append("缺 references/checkup-scorecard.md")

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
    search = params.get("search", {})
    if f"× {search.get('multiplier')}" not in skill_text:
        errors.append(f"SKILL.md 缺检索预算倍数 × {search.get('multiplier')}")
    if str(search.get("cap")) not in skill_text:
        errors.append(f"SKILL.md 缺检索预算上限 {search.get('cap')}")
    for arch in params.get("archetypes", []):
        if arch["name"] not in skill_text:
            errors.append(f"SKILL.md 缺原型「{arch['name']}」，与 params.json 不一致")
    if len(params.get("archetypes", [])) != 7:
        errors.append(f"原型应为 7 种，params.json 有 {len(params.get('archetypes', []))} 种")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验技能安装产物")
    parser.add_argument("--path", help=f"安装目录，默认 dist/{SKILL_NAME}")
    args = parser.parse_args()

    root = Path(args.path).resolve() if args.path else REPO / "dist" / SKILL_NAME
    if not root.is_dir():
        print(f"[必改] 找不到 {root}，先跑 python tools/build_skill.py")
        return 1
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        print("[必改] 安装单元缺 SKILL.md")
        return 1

    errors = check_frontmatter(skill_md, root.name)
    errors += check_layout(root)
    errors += check_fresh(root)
    errors += check_params(root)
    errors += check_dead_links(root)
    head = "\n".join(skill_md.read_text(encoding="utf-8").splitlines()[:20])
    if "INSTALL.md" not in head:
        errors.append("SKILL.md 前 20 行没有指向 INSTALL.md 的接入说明")

    if errors:
        shown = errors[:12]
        for item in shown:
            print(f"[必改] {item}")
        if len(errors) > len(shown):
            print(f"[必改] …… 另有 {len(errors) - len(shown)} 项，多为同一原因的连带结果")
        print(f"\n{len(errors)} 项必改，不可发布")
        return 1
    print(f"[通过] {root.name}：frontmatter、体积、产物一致性均符合要求")
    return 0


if __name__ == "__main__":
    sys.exit(main())
