#!/usr/bin/env python3
"""把仓库构建成可安装的技能目录 dist/startup-guide/。

仓库是事实来源，dist 是产物：不入库、不手改、每次重建。
用法：python tools/build_skill.py [--out dist]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_NAME = "startup-guide"

ROOT_FILES = ("SKILL.md", "INSTALL.md", "LICENSE")
TREE_GLOBS = {
    "references": ("**/*.md",),
    "data": ("**/*.md", "params.json"),
    "examples": ("*.md",),
    "hosts": ("*.md",),
}
TOOL_FILES = (
    "deck_engine.py",
    "deck_layouts.py",
    "deck_kit.py",
    "deck_lint.py",
    "mcp_server.py",
    "mcp_tools.py",
    "requirements.txt",
    "requirements-pdf-check.txt",
)
TOOL_GLOBS = {"briefs": "*.json"}
FORBIDDEN = (
    ".venv",
    ".git",
    "__pycache__",
    "wheels",
    "node_modules",
    ".workbuddy-ai",
    ".DS_Store",
)


def _forbidden(path: Path) -> bool:
    return any(part in FORBIDDEN for part in path.parts)


def collect_files() -> list[tuple[Path, Path]]:
    """返回 [(源文件, 相对安装根的路径)]，顺序稳定，构建与校验共用。"""
    pairs: list[tuple[Path, Path]] = []
    for name in ROOT_FILES:
        src = REPO / name
        if src.is_file():
            pairs.append((src, Path(name)))
    for folder, patterns in TREE_GLOBS.items():
        base = REPO / folder
        if not base.is_dir():
            continue
        for pattern in patterns:
            for src in sorted(base.glob(pattern)):
                if src.is_file() and not _forbidden(src):
                    pairs.append((src, src.relative_to(REPO)))
    tools = REPO / "tools"
    for name in TOOL_FILES:
        src = tools / name
        if src.is_file():
            pairs.append((src, Path("tools") / name))
    for folder, pattern in TOOL_GLOBS.items():
        for src in sorted((tools / folder).glob(pattern)):
            pairs.append((src, src.relative_to(REPO)))
    return pairs


def copy_all(pairs: list[tuple[Path, Path]], out: Path) -> None:
    for src, rel in pairs:
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建可安装技能目录")
    parser.add_argument("--out", default="dist", help="输出目录，默认 dist")
    args = parser.parse_args()

    target = REPO / args.out / SKILL_NAME
    if target.exists():
        shutil.rmtree(target)
    pairs = collect_files()
    if not pairs:
        print("没有可打包的文件，检查 ROOT_FILES / TREE_GLOBS 是否对得上仓库")
        return 1
    copy_all(pairs, target)

    total = sum((target / rel).stat().st_size for _, rel in pairs)
    print(f"已生成 {target.relative_to(REPO)}")
    print(f"文件 {len(pairs)} 个，{human_size(total)}")
    print("下一步：python tools/skill_check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
