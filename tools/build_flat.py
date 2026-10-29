#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能压成单文件形态 dist/startup-guide.flat.txt（B 形态）。

给只能接受一段文本的宿主（网页版对话、API 单轮）当系统提示，
对应 INSTALL.md 第 2 节 B 形态。收录清单固定为 SKILL.md 加四份
关键 references：怎么问、模式分叉、怎么算、断网降级。

三条设计事实：
- 机械拼接，不做编辑式删改：产物必须能被 --check 逐字节复验。
- SKILL.md 的 frontmatter 剥掉：那是给安装器看的，不是给提示词用的。
- 扩展名用 .txt：单文件约 800 行，写成 .md 会越过硬上限 300 行，
  doc_check 门禁必红；它是粘贴用载荷，不是待维护文档。
- 产物放在 dist/ 顶层、不在 dist/startup-guide/ 内，与 skill_check.py
  的校验范围（目录技能）互不重叠；本工具自带 --check 拦过期。

用法：
    python tools/build_flat.py            # 生成；SKILL.md 或 references/ 改动后重跑
    python tools/build_flat.py --check    # 只校验是否最新，0 最新 / 1 过期或缺失
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "dist" / "startup-guide.flat.txt"

# （相对路径，用途标签，是否剥 frontmatter）
PARTS = (
    ("SKILL.md", "主流程与硬约束", True),
    ("references/intake-questions.md", "怎么问：8 道引导题", False),
    ("references/pattern-fork.md", "模式分叉：先定用哪套成本算", False),
    ("references/checkup-scorecard.md", "怎么算：七维体检评分口径", False),
    ("references/offline-degradation.md", "断网降级：先告知再降级", False),
)

HEADER = """# 创业指南技能 · 单文件版（B 形态）

> 本文件由 tools/build_flat.py 生成，不要手改；源文件改动后重新生成，--check 会拦下过期产物。
> 用途：给只能接受一段文本的宿主（网页版对话、API 单轮）。把本文件全文作为系统提示，即可执行完整体检流程。
> 降级声明：当前环境没有联网工具时，结论封顶在「信息不足」——不判放行也不判不建议启动；不把行业卡当查过，不把推演当核实。
> 与目录形态（A，dist/startup-guide/）同源但能力弱：未收录的 references（运行时检索、检索串模板等）按问题临时补进对话。

以下依次收录：SKILL.md（主流程与硬约束）、intake-questions（怎么问）、
pattern-fork（模式分叉）、checkup-scorecard（怎么算）、offline-degradation（断网降级）。"""


def strip_frontmatter(text: str) -> str:
    """只剥 SKILL.md 的 YAML frontmatter；没有则原样返回。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[end + 4:].lstrip("\n")
    return text


def build() -> str:
    parts = [HEADER]
    for rel, label, strip in PARTS:
        text = (REPO / rel).read_text(encoding="utf-8")
        if strip:
            text = strip_frontmatter(text)
        parts.append(f"========== 收录：{rel}（{label}）==========\n\n{text.rstrip()}")
    return "\n\n".join(parts) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="生成 B 形态单文件 startup-guide.flat.txt")
    parser.add_argument("--check", action="store_true", help="只校验产物是否最新，不写文件")
    args = parser.parse_args()

    missing = [rel for rel, _, _ in PARTS if not (REPO / rel).is_file()]
    if missing:
        print(f"[必改] 收录清单有文件不存在：{', '.join(missing)}")
        return 1
    fresh = build()

    if args.check:
        if not OUT.is_file():
            print(f"[必改] 缺 {OUT.relative_to(REPO)}，先跑 python tools/build_flat.py")
            return 1
        if OUT.read_text(encoding="utf-8") != fresh:
            print(f"[必改] {OUT.relative_to(REPO)} 已过期（源文件改过），需重新生成")
            return 1
        print(f"[通过] {OUT.name} 与源文件一致")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(fresh, encoding="utf-8")
    print(f"已生成 {OUT.relative_to(REPO)}：{len(fresh.splitlines())} 行，"
          f"{OUT.stat().st_size / 1024:.1f} KB")
    print("下一步：python tools/build_flat.py --check（源文件改动后重跑生成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
