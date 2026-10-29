# -*- coding: utf-8 -*-
"""测算类演示文稿引擎：吃 brief.json，出 .pptx。

用法：
    python deck_engine.py brief.json [out.pptx] [--png 预览目录] [--strict]

退出码：
    0 正常（可能有告警）
    2 缺依赖（按提示装 python-pptx 后重试）
    3 brief 结构错误
    4 渲染或保存失败

自检只做三件确定性的事：文字可能溢出、文字被后画的色块盖住、文字框互相重叠。
真正的版式验收仍需看导出的图 —— 自检通过不等于好看。
"""
import json
import os
import subprocess
import sys

# 中文 Windows 的控制台默认不是 UTF-8，不加这段中文提示会变乱码。
# 必须放在缺依赖提示之前，否则「缺 python-pptx」那条本身就看不清。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

try:
    from pptx import Presentation
except ImportError:
    sys.stderr.write(
        '缺 python-pptx。装完再跑：\n'
        '  pip install python-pptx -i https://mirrors.aliyun.com/pypi/simple/\n'
        '装不上就退回文本大纲交付（见 references/deck-spec.md 的渲染三级降级）。\n')
    sys.exit(2)

from deck_kit import px, CANVAS_W, CANVAS_H, reset_registry, registry
from deck_layouts import LAYOUTS


def check_page(no, title):
    """确定性自检，返回 (致命, 提示) 两组字符串。

    致命项只看声明框，是几何事实：
      遮挡 —— 后画的色块盖住文字 30% 以上面积，一定会看不见；
      重叠 —— 两个文字框相互压住 50% 以上，一定有字叠在一起；
      出界 —— 文字估算底边画到页面外，导出后直接看不到。
    提示项用估算高度判断框是否留得太紧，属主观，需目视确认。

    不拿估算高度做遮挡与重叠判定：估算偏保守，单行文字会被误判。
    出界判定必须用估算高度 —— 声明框大而内容少的框，框出界但字没出界。
    """
    fatal, hints = [], []
    items = registry()
    texts = [r for r in items if r[1] == 'text']
    rects = [r for r in items if r[1] == 'rect']

    def overlap(a, b):
        ox = max(0, min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2]))
        oy = max(0, min(a[3] + a[5], b[3] + b[5]) - max(a[3], b[3]))
        return ox * oy

    for order, _kind, x, y, w, h, meta in texts:
        if meta['est'] > h * 1.25 + 4:
            hints.append('p%02d 框偏紧：%r 估高 %.0f > 框高 %d'
                         % (no, meta['preview'], meta['est'], h))
        # 8px 容差：亚像素取整不应报错
        bottom = y + max(meta['est'], 1)
        if bottom > CANVAS_H + 8:
            fatal.append('p%02d 超出画布：%r 底边 %.0f > %d'
                         % (no, meta['preview'], bottom, CANVAS_H))

    for t in texts:
        for r in rects:
            if r[0] > t[0] and overlap(t, r) > 0.3 * t[4] * t[5]:
                fatal.append('p%02d 被遮挡：%r 被后画的色块盖住' % (no, t[6]['preview']))
                break

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            smaller = min(a[4] * a[5], b[4] * b[5])
            if overlap(a, b) > 0.5 * smaller:
                fatal.append('p%02d 文字重叠：%r × %r'
                             % (no, a[6]['preview'], b[6]['preview']))
    return fatal, hints


def export_png(pptx_path, out_dir):
    """Windows 下用 COM 导出逐页 PNG；失败只告警，不影响交付。"""
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    ps = (
        '$ErrorActionPreference="Stop";'
        '$app=New-Object -ComObject PowerPoint.Application;'
        '$p=$app.Presentations.Open("%s",$true,$false,$false);'
        '$p.Export("%s","PNG",1280,720);$p.Close();$app.Quit()'
        % (pptx_path, out_dir)
    )
    try:
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        n = len([f for f in os.listdir(out_dir) if f.lower().endswith('.png')])
        print('PNG %d 张 → %s' % (n, out_dir))
    except Exception as exc:
        print('PNG 导出跳过（%s）—— 手工打开文件目视复核' % type(exc).__name__)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    brief_path = argv[1]
    rest = [a for a in argv[2:] if not a.startswith('--')]
    png_dir = None
    if '--png' in argv:
        i = argv.index('--png')
        if i + 1 < len(argv):
            png_dir = argv[i + 1]
            rest = [a for a in rest if a != png_dir]
    strict = '--strict' in argv

    try:
        with open(brief_path, encoding='utf-8') as f:
            brief = json.load(f)
    except Exception as exc:
        sys.stderr.write('读不了 brief：%s\n' % exc)
        return 3
    slides = brief.get('slides') or []
    if not slides:
        sys.stderr.write('brief 里没有 slides\n')
        return 3
    bad = [s.get('type') for s in slides if s.get('type') not in LAYOUTS]
    if bad:
        sys.stderr.write('未知页型 %s，可用：%s\n' % (bad, ', '.join(LAYOUTS)))
        return 3

    prs = Presentation()
    prs.slide_width = px(CANVAS_W)
    prs.slide_height = px(CANVAS_H)
    blank = prs.slide_layouts[6]

    all_fatal, all_hints = [], []
    total = len(slides)
    for i, spec in enumerate(slides, 1):
        reset_registry()
        slide = prs.slides.add_slide(blank)
        LAYOUTS[spec['type']](slide, spec, i, total)
        f, h = check_page(i, spec.get('title', spec['type']))
        all_fatal.extend(f)
        all_hints.extend(h)

    out = rest[0] if rest else os.path.splitext(brief_path)[0] + '.pptx'
    try:
        prs.save(out)
    except PermissionError:
        stem, ext = os.path.splitext(out)
        out = stem + '_v2' + ext
        prs.save(out)
        print('原文件被占用，改存：%s' % out)

    print('SAVED %s（%d 页）' % (out, total))
    for w in all_fatal:
        print('  [必改] ' + w)
    for w in all_hints:
        print('  [提示] ' + w)
    if not all_fatal and not all_hints:
        print('自检通过：无遮挡、无重叠、无框偏紧')
    elif not all_fatal:
        print('自检通过（有 %d 条提示，需目视确认）' % len(all_hints))
    if png_dir:
        export_png(out, png_dir)
    return 1 if (strict and all_fatal) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
