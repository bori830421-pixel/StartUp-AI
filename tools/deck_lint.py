# -*- coding: utf-8 -*-
"""交付前几何检查：把「导出图用眼睛看」换成一条命令。

用法：
    python deck_lint.py 输出.pptx [--tol 5] [--png 目录] [--keep]
    python deck_lint.py tools/briefs/xx.json      # 先渲染，再检查
    python deck_lint.py 输出.pptx --engine PowerPoint   # 指定渲染器

为什么要它：deck_engine 的自检只比对文字框自身的估高与框高，管不到
「文字框 vs 它背后的色块」，也管不到渲染器实际怎么断行。这两类问题
过去只能靠「转 PDF → 转 PNG → 逐页看图」，一轮 50 秒。本工具从 PDF
拿真实坐标，一次输出全部可判定缺陷。

转 PDF 的渲染器按优先级自动选择：PowerPoint COM（实测 1.9s）
→ LibreOffice（实测 42.7s 冷启动）→ WPS COM（放最后：兼容 COM 接口，
但渲染细节与真实 PowerPoint 差异最大）。用哪个会回显在输出第一行。

注意：不同引擎的行高舍入不同，同一份稿子的 [提示] 项可能相差 ±1pt
（例如「贴底色块下边 -1pt」）。[必改] 项在三种引擎下结论一致。
换引擎等于换基准，验收基线要重跑一次。

检查项（坐标全部来自 PDF 渲染结果，不是估算）：
    [必改] 越出色块  文字落在某个填充矩形内，但某一边超出该矩形（>tol，默认 5pt，约 7px 视觉可见）
    [必改] 出页面    文字 bbox 越过页面边界
    [必改] 行首标点  某行以标点开头（中文排版的硬伤）
    [必改] 文字重叠  两行文字互相压住一半以上
    [提示] 残行      某行只有 1–2 个非字母数字字符（「。」「停。」）

退出码：0 干净；1 有必改项；2 缺依赖；3 转换或渲染失败
"""
import os
import subprocess
import sys
import tempfile

# 中文 Windows 的控制台默认不是 UTF-8，不加这段中文提示会变乱码。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

try:
    import pymupdf
except ImportError:
    sys.stderr.write('缺 pymupdf。装完再跑：\n'
                     '  python -m pip install pymupdf -i https://mirrors.aliyun.com/pypi/simple/\n')
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
SOFFICE_PATHS = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/usr/bin/soffice',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
]
BAD_HEAD = '，。、；：！？）」』%,.;:!?)]}'
PP_SAVE_AS_PDF = 32


def find_soffice():
    for p in SOFFICE_PATHS:
        if os.path.exists(p):
            return p
    from shutil import which
    return which('soffice') or which('libreoffice')


def via_powerpoint(pptx, out_dir):
    """PowerPoint COM 导 PDF。比 LibreOffice 快一个数量级（实测 1.9s vs 42.7s）。"""
    import comtypes.client
    pdf = os.path.join(out_dir, 'pp-%s.pdf' % os.path.splitext(os.path.basename(pptx))[0])
    app = comtypes.client.CreateObject('PowerPoint.Application')
    try:
        pres = app.Presentations.Open(os.path.abspath(pptx), WithWindow=False)
        try:
            pres.SaveAs(os.path.abspath(pdf), PP_SAVE_AS_PDF)
        finally:
            pres.Close()
    finally:
        try:
            app.Quit()
        except Exception:
            pass
    if not os.path.exists(pdf):
        raise RuntimeError('PowerPoint 没有产出 PDF')
    return pdf, 'PowerPoint'


def via_wps(pptx, out_dir):
    """WPS 兼容 PowerPoint 的 COM 接口，排在最后 —— 行为差异最大，以实测为准。"""
    import comtypes.client
    pdf = os.path.join(out_dir, 'wps-%s.pdf' % os.path.splitext(os.path.basename(pptx))[0])
    app = comtypes.client.CreateObject('Kwpp.Application')
    try:
        pres = app.Presentations.Open(os.path.abspath(pptx), WithWindow=False)
        try:
            pres.SaveAs(os.path.abspath(pdf), PP_SAVE_AS_PDF)
        finally:
            pres.Close()
    finally:
        try:
            app.Quit()
        except Exception:
            pass
    if not os.path.exists(pdf):
        raise RuntimeError('WPS 没有产出 PDF')
    return pdf, 'WPS'


def via_soffice(pptx, out_dir):
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError('找不到 LibreOffice（soffice）')
    subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', out_dir, pptx],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(pptx))[0] + '.pdf')
    if not os.path.exists(pdf):
        raise RuntimeError('PDF 没有生成：%s' % pdf)
    return pdf, 'LibreOffice'


# 顺序即优先级：PowerPoint 最快且与 PowerPoint 里看到的一致；LibreOffice 次之；
# WPS 排最后——它兼容 COM 接口，但渲染细节与真实 PowerPoint 差异最大。
RENDERERS = [('PowerPoint', via_powerpoint), ('LibreOffice', via_soffice), ('WPS', via_wps)]


def to_pdf(pptx, out_dir, prefer=None):
    """按优先级找一个能用的渲染器把 pptx 转成 PDF，返回 (pdf 路径, 渲染器名)。

    prefer 可指定 'PowerPoint' / 'LibreOffice' / 'WPS'，失败则继续按默认顺序。
    全部失败时抛出带每种失败原因的异常，不静默降级。
    """
    order = list(RENDERERS)
    if prefer:
        order.sort(key=lambda r: 0 if r[0].lower() == prefer.lower() else 1)

    errors = []
    for name, fn in order:
        try:
            pdf, used = fn(pptx, out_dir)
            return pdf, used
        except Exception as exc:
            errors.append('%s: %s' % (name, str(exc).splitlines()[0][:120]))
    raise RuntimeError('没有可用的渲染器转 PDF（几何检查需要它）\n  ' + '\n  '.join(errors))


def filled_boxes(page):
    """页面上所有够大的填充矩形，按面积升序 —— 升序让第一个命中即最内层。"""
    out = []
    for d in page.get_drawings():
        if d.get('fill') is None:
            continue
        r = d['rect']
        if r.width < 8 or r.height < 8:      # 分隔线、色条不算容器
            continue
        out.append((r.x0, r.y0, r.x1, r.y1))
    out.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    return out


def text_lines(page):
    """每行文字一条：(bbox, 文本)。按行聚合，避免同一行被拆成多个 span。"""
    out = []
    for blk in page.get_text('dict')['blocks']:
        for ln in blk.get('lines', []):
            txt = ''.join(s['text'] for s in ln['spans'])
            if txt.strip():
                out.append((tuple(ln['bbox']), txt))
    return out


def host_box(bbox, boxes):
    """文字归属哪个色块。取上中、正中、下中三点探测 —— 只用中心点会漏掉
    「整行滑出色块」的情况：那一行的中心已经在色块外，找不到宿主就不报越界。"""
    cx = (bbox[0] + bbox[2]) / 2
    probes = ((cx, bbox[1] + 2), (cx, (bbox[1] + bbox[3]) / 2), (cx, bbox[3] - 2))
    for b in boxes:
        for px_, py_ in probes:
            if b[0] <= px_ <= b[2] and b[1] <= py_ <= b[3]:
                return b
    return None


def lint_page(no, page, tol):
    fatal, hints = [], []
    boxes = filled_boxes(page)
    lines = text_lines(page)
    W, H = page.rect.width, page.rect.height

    for bbox, txt in lines:
        s = txt.strip()
        host = host_box(bbox, boxes)
        if host:
            over = max(host[0] - bbox[0], host[1] - bbox[1],
                       bbox[2] - host[2], bbox[3] - host[3])
            if over > tol:
                fatal.append('p%02d 越出色块 %+.0fpt：%r' % (no, over, s[:18]))
            elif host[3] - bbox[3] < 4 and host[3] - bbox[3] > -tol:
                # 没越界但几乎贴住底边：色块内边距被吃光，视觉上就是压线
                hints.append('p%02d 贴底色块下边 %.0fpt：%r'
                             % (no, host[3] - bbox[3], s[:18]))
        if bbox[0] < -tol or bbox[1] < -tol or bbox[2] > W + tol or bbox[3] > H + tol:
            fatal.append('p%02d 出页面：%r' % (no, s[:18]))
        if s[0] in BAD_HEAD:
            # 「。」「！」开头的行等于半行空白，必改；逗号顿号开头的行读得下去，降为提示
            (fatal if s[0] in '。！？' else hints).append(
                'p%02d 行首标点：%r' % (no, s[:18]))
        elif s in '。，、；：！？':
            hints.append('p%02d 残行：%r' % (no, s))

    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, b = lines[i][0], lines[j][0]
            ox = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            oy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if small > 0 and ox * oy > 0.5 * small:
                fatal.append('p%02d 文字重叠：%r × %r'
                             % (no, lines[i][1].strip()[:14], lines[j][1].strip()[:14]))
    return fatal, hints


def export_png(pdf, out_dir):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc, 1):
        page.get_pixmap(dpi=110).save(os.path.join(out_dir, 'p%02d.png' % i))
    print('PNG %d 张 → %s' % (doc.page_count, out_dir))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    src = argv[1]
    tol = float(argv[argv.index('--tol') + 1]) if '--tol' in argv else 5.0
    png_dir = argv[argv.index('--png') + 1] if '--png' in argv else None
    keep = '--keep' in argv
    prefer = argv[argv.index('--engine') + 1] if '--engine' in argv else None
    tmp = tempfile.mkdtemp(prefix='decklint-')

    pptx = src
    if src.lower().endswith('.json'):
        pptx = os.path.join(tmp, os.path.splitext(os.path.basename(src))[0] + '.pptx')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'deck_engine.py'), src, pptx])
        if r.returncode != 0:
            sys.stderr.write('渲染失败，退出码 %d\n' % r.returncode)
            return 3

    try:
        pdf, engine = to_pdf(pptx, tmp, prefer)
    except Exception as exc:
        sys.stderr.write('转 PDF 失败：%s\n' % exc)
        return 3
    # 回显渲染器：不同引擎的断行与行高舍入不同，[提示] 项可能相差 ±1pt，
    # 让人知道这次结论是拿哪个基准算出来的。
    print('渲染器：%s' % engine)

    doc = pymupdf.open(pdf)
    fatal, hints = [], []
    for i, page in enumerate(doc, 1):
        f, h = lint_page(i, page, tol)
        fatal.extend(f)
        hints.extend(h)

    print('检查 %d 页：%d 条必改，%d 条提示' % (doc.page_count, len(fatal), len(hints)))
    for w in fatal:
        print('  [必改] ' + w)
    for w in hints:
        print('  [提示] ' + w)
    if not fatal and not hints:
        print('干净：无越界、无行首标点、无残行、无重叠')
    if png_dir:
        export_png(pdf, png_dir)
    if not keep:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print('临时目录保留：%s' % tmp)
    return 1 if fatal else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
