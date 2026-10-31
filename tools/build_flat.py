#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能压成单文件形态 dist/startup-guide.flat.txt（B 形态）。

给只能接受一段文本的宿主（网页版对话、API 单轮）当系统提示，
对应 INSTALL.md 第 2 节 B 形态。收录清单固定为 SKILL.md 加五份
关键 references：怎么问、模式分叉、怎么算、检索兜底、断网降级。

两条与「检索」相关的收录理由（决策记录 0015）：
- search-fallback 必须在 offline-degradation 之前收：两类「搜不了」的
  判断入口都在它那里，放前面，模型才会先判「没工具」再判「没网」。
- 头部不再写平级的降级声明：写了「无联网即封顶」，遇到缺密钥的宿主
  会直接跳过兜底，把本可救的问题退回给用户。

三条设计事实：
- 机械拼接，不做编辑式删改：产物必须能被 --check 逐字节复验。
- SKILL.md 的 frontmatter 剥掉：那是给安装器看的，不是给提示词用的。
- 扩展名用 .txt：单文件约 800 行，写成 .md 会越过硬上限 520 行，
  doc_check 门禁必红；它是粘贴用载荷，不是待维护文档。
- 产物放在 dist/ 顶层、不在 dist/startup-guide/ 内，与 skill_check.py
  的校验范围（目录技能）互不重叠；本工具自带 --check 拦过期。

体积口径（决策 0019）：token 占用由本工具算出并打印，不写死在文档里。
手写数字必漂——0015 估的是 15,300，实际已到 18,000 量级，而文档一直停在
12,600。估算按汉字 1 token、非汉字 4 字符/token，用唯一一次真实测量
（17,857 字符 ≈ 12,600 token）校准过。

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
    ("references/search-fallback.md", "检索兜底：有网没工具时怎么查", False),
    ("references/offline-degradation.md", "断网降级：先告知再降级", False),
)

HEADER = """# 创业指南技能 · 单文件版（B 形态）

> 本文件由 tools/build_flat.py 生成，不要手改；源文件改动后重新生成，--check 会拦下过期产物。
> 用途：给只能接受一段文本的宿主（网页版对话、API 单轮）。把本文件全文作为系统提示，即可执行完整体检流程。
> 检索声明（分档，按顺序判）：① 会话里有可用搜索工具 → 直接用；② 搜索工具存在但报凭据错误（缺 API key、401、未配置）→ 先按「检索兜底」用公开端点查，最多 3 个端点，每个只试一条；③ 连外部网址都打不开、或公开端点全失败 → 按「断网降级」先告知再降级，结论封顶在「信息不足」，不判放行也不判不建议启动，并在提示里写明试过哪些端点、各报什么错。
> 降级不等于放弃：断网或全端点失败时，结论封顶在「信息不足」——不判放行也不判不建议启动；不把行业卡当查过，不把推演当核实。
> 与目录形态（A，dist/startup-guide/）同源但能力弱：未收录的 references（运行时检索、检索串模板等）按问题临时补进对话。
> 本文件只收运行时指令。维护者的实测记录、文档导航这类内容不进载荷——它们不改变模型该怎么做，只占上下文。

以下依次收录：SKILL.md（主流程与硬约束）、intake-questions（怎么问）、
pattern-fork（模式分叉）、checkup-scorecard（怎么算）、search-fallback（检索兜底）、
offline-degradation（断网降级）。"""

# 源文件里用这两行圈出「只给维护者看、运行时用不上」的段落。
# 用标记而不是在 build 里写行号：行号会随源文件改动错位，标记不会，
# 而且标记本身说明了为什么这段不进载荷。
SKIP_OPEN = "<!-- flat:skip -->"
SKIP_CLOSE = "<!-- flat:skip-end -->"


def estimate_tokens(text: str) -> int:
    """粗估 token：汉字 1 个算 1，其余 4 字符算 1。

    用唯一一次真实测量校准过——旧版 17,857 字符实测约 12,600 token，
    该文件的汉字占比与本文件接近，两种算法差在 5% 以内。它不是精确值，
    但足以判断「装不装得下」，而这正是唯一要回答的问题。
    """
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return int(cjk + (len(text) - cjk) / 4)


def strip_skipped(text: str, rel: str) -> str:
    """去掉被 <!-- flat:skip --> 圈住的段落，保留其余内容原样。"""
    out, pos = [], 0
    while True:
        start = text.find(SKIP_OPEN, pos)
        if start < 0:
            out.append(text[pos:])
            return "".join(out)
        end = text.find(SKIP_CLOSE, start)
        if end < 0:
            # 标记不闭合是源文件的错，不能静默截断到文件尾
            raise ValueError(f"{rel}：{SKIP_OPEN} 没有配对的 {SKIP_CLOSE}")
        out.append(text[pos:start])
        pos = end + len(SKIP_CLOSE)


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
        text = strip_skipped(text, rel)
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
        out_rel = OUT.relative_to(REPO)
        if not OUT.is_file():
            print(f"[必改] 缺 {out_rel}，先跑 python tools/build_flat.py")
            return 1
        # 逐字节比，不用 read_text：它会把 CRLF 归一化，行尾漂移就查不出来了
        want, have = fresh.encode("utf-8"), OUT.read_bytes()
        if have != want:
            if have.replace(b"\r\n", b"\n") == want:
                print(f"[必改] {out_rel} 行尾不是 LF（.gitattributes 要求 eol=lf），需重新生成")
            else:
                print(f"[必改] {out_rel} 已过期（源文件改过），需重新生成")
            return 1
        print(f"[通过] {OUT.name} 与源文件逐字节一致")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 显式 newline="\n" 不可省：默认按平台翻译行尾，Windows 下会写出 CRLF，
    # 而 .gitattributes 规定 *.txt 为 eol=lf，结果每跑一次构建工作区就多一处假脏。
    # 用 open 而非 Path.write_text(newline=...)，因为后者要 Python 3.10+，本项目支持 3.9+。
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh)
    tokens = estimate_tokens(fresh)
    print(f"已生成 {OUT.relative_to(REPO)}：{len(fresh.splitlines())} 行，"
          f"{OUT.stat().st_size / 1024:.1f} KB，约 {tokens:,} token")
    for ctx in (8192, 32768, 131072):
        print(f"  {ctx // 1024}k 宿主：{tokens / ctx * 100:.0f}%"
              + ("（装不下）" if tokens > ctx else ""))
    print("下一步：python tools/build_flat.py --check（源文件改动后重跑生成）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
