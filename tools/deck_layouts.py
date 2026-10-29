# -*- coding: utf-8 -*-
"""测算类演示文稿的页型库：11 种固定版式，每种只吃数据。

几何写死在这里，内容全部来自 brief.json。新增页型时复制最接近的一个，
改几何、改字段，然后在 LAYOUTS 里登记 —— 不要在这里写业务判断。
"""
from pptx.enum.text import PP_ALIGN

from deck_kit import (PALETTE, CANVAS_W, CANVAS_H, MARGIN, CONTENT_W,
                      textbox, rect, header, table, bignum, bullets, paras, panel, color)

_ALIGN = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}


def _aligns(spec):
    return [_ALIGN[a] for a in spec] if spec else None


def _draw_table(slide, spec, y=None):
    """brief 里的 table 块统一入口，返回底边 y。"""
    t = spec['table']
    return table(slide, t.get('x', MARGIN), y if y is not None else t['y'],
                 t['cols'], t['rows'], row_h=t.get('row_h', 52), head_h=t.get('head_h', 50),
                 body_size=t.get('body_size', 20), head_size=t.get('head_size', 19),
                 aligns=_aligns(t.get('aligns')))


# ---------- 01 封面 ----------

def cover(slide, s, page, total):
    rect(slide, 0, 0, CANVAS_W, CANVAS_H, fill='navy')
    rect(slide, 64, 118, 40, 3, fill='cyan')
    textbox(slide, 118, 104, 700, 34, [{'text': s['kicker'], 'size': 20, 'color': 'lblue'}])
    textbox(slide, 64, 190, 1100, 260,
            [{'text': t, 'size': s.get('title_size', 78), 'color': 'white', 'bold': True,
              'line_spacing': 1.15} for t in s['title_lines']])
    textbox(slide, 64, 470, 1100, 120,
            [{'text': s['meta'], 'size': 26, 'color': 'lblue', 'line_spacing': 1.5},
             {'text': s['conclusion'], 'size': 22, 'color': 'white', 'line_spacing': 1.5,
              'space_before': 14}])
    rect(slide, 64, 636, 1152, 1, fill='navy2')
    textbox(slide, 64, 652, 800, 30, [{'text': s['footer_left'], 'size': 13, 'color': 'gray'}])
    textbox(slide, 900, 652, 316, 30,
            [{'text': s.get('footer_right', ''), 'size': 13, 'color': 'gray',
              'align': PP_ALIGN.RIGHT}])


# ---------- 02 三栏结论（CONTEXT / COMPLICATION / RESOLUTION） ----------

def three_col(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    for i, c in enumerate(s['cols']):
        x = MARGIN + i * 394
        rect(slide, x, top + 6, 64, 3, fill='navy')
        textbox(slide, x, top + 16, 370, 26, [{'text': c['tag'], 'size': 15, 'color': 'cyan', 'bold': True}])
        textbox(slide, x, top + 46, 370, 34, [{'text': c['label'], 'size': 26, 'color': 'navy', 'bold': True}])
        textbox(slide, x, top + 96, 370, 230,
                [{'text': c['body'], 'size': 21, 'color': 'dgray', 'line_spacing': 1.65}])
        rect(slide, x, top + 330, 370, 1, fill='lgray')
        bignum(slide, x, top + 344, 370, 130, c['num'], c['unit'], value_size=66, unit_size=18)


# ---------- 03 输入条件（表格 + 右侧假设 + 底部两栏对照） ----------

def table_assumptions(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    _draw_table(slide, s, y=top + 10)
    # 右侧假设列
    lines = [{'text': s.get('assumption_title', '假设'), 'size': 19, 'color': 'cyan', 'bold': True}]
    for i, a in enumerate(s['assumptions']):
        lines.append({'text': a['v'], 'size': a.get('v_size', 26), 'color': 'navy', 'bold': True,
                      'space_before': 10 if i == 0 else 12})
        lines.append({'text': a['k'], 'size': 15, 'color': 'gray', 'space_before': 2})
        if a.get('note'):
            lines.append({'text': a['note'], 'size': 13, 'color': 'gray', 'space_before': 1})
    textbox(slide, 1050, top + 10, 170, 280, lines)
    # 底部两栏
    sub_y = top + 326
    for i, b in enumerate(s['blocks']):
        x = MARGIN if i == 0 else 750
        rect(slide, x, sub_y, 470, 192, fill='xlgray')
        textbox(slide, x + 28, sub_y + 22, 414, 30,
                [{'text': b['title'], 'size': 18, 'color': b.get('color', 'green'), 'bold': True}])
        bullets(slide, x + 28, sub_y + 52, 414, 130, b['items'], size=18,
                spacing=b.get('spacing', 1.5))


# ---------- 04 成本拆解（表格 + 右侧深色缓冲卡） ----------

def table_card(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    bottom = _draw_table(slide, s, y=top + 6)
    # 表格行数少时左下会空出一大片，用可选 left_notes 补一段解读
    ln = s.get('left_notes')
    if ln:
        ly = max(bottom + 34, top + 300)
        room = CANVAS_H - 56 - (ly + 38)   # 底部留 56px 给页脚
        if room > 60:                       # 塞不下就不画，宁可空着
            textbox(slide, MARGIN, ly, 700, 32,
                    [{'text': ln['title'], 'size': 19, 'color': ln.get('color', 'cyan'), 'bold': True}])
            bullets(slide, MARGIN, ly + 38, 700, room, ln['items'], size=19,
                    spacing=ln.get('spacing', 1.7))
    c = s['card']
    cx = c.get('x', 820)
    rect(slide, cx, top + 6, 400, 470, fill='navy')
    textbox(slide, cx + 36, top + 46, 330, 40, [{'text': c['label'], 'size': 20, 'color': 'lblue'}])
    textbox(slide, cx + 36, top + 96, 330, 110,
            [{'text': c['value'], 'size': c.get('value_size', 74), 'color': 'white', 'bold': True,
              'line_spacing': 1.0}], wrap=False)
    rect(slide, cx + 36, top + 226, 328, 1, fill='navy2')
    paras(slide, cx + 36, top + 244, 330, 210,
          [{'t': p, 'c': 'white' if i == 0 else 'lblue'} for i, p in enumerate(c['notes'])],
          size=20, spacing=1.6, gap=10)


# ---------- 05 保本线（大数字 + 成本明细 + 右侧说明） ----------

def bignum_costlist(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    textbox(slide, MARGIN, top + 4, 700, 40, [{'text': s['caption'], 'size': 20, 'color': 'gray'}])
    textbox(slide, MARGIN, top + 44, 700, 150,
            [{'text': s['value'], 'size': s.get('value_size', 130), 'color': 'navy',
              'bold': True, 'line_spacing': 1.0}], wrap=False)
    textbox(slide, MARGIN, top + 196, 700, 44, [{'text': s['unit'], 'size': 24, 'color': 'dgray'}])
    rect(slide, MARGIN, top + 258, 640, 1, fill='lgray')
    yy = top + 274
    for row in s['costs']:
        textbox(slide, MARGIN, yy, 200, 32, [{'text': row['k'], 'size': 20, 'color': 'dgray'}])
        textbox(slide, 270, yy, 120, 32,
                [{'text': row['v'], 'size': 20, 'color': 'navy', 'bold': True, 'align': PP_ALIGN.RIGHT}])
        textbox(slide, 410, yy, 290, 32, [{'text': row.get('note', ''), 'size': 17, 'color': 'gray'}])
        yy += 38
    textbox(slide, MARGIN, yy + 6, 660, 62,
            [{'text': s['total'], 'size': 20, 'color': 'navy', 'bold': True}])
    p = s['panel']
    ix, iy = panel(slide, 760, top + 4, 460, 430)
    paras(slide, ix, iy + 30, 390, 380,
          [{'t': p['title'], 'size': 24, 'c': 'navy', 'b': True}] +
          [{'t': t, 'c': 'cyan' if t == p['items'][-1] else 'dgray'} for t in p['items']],
          size=20, spacing=1.6, gap=12)


# ---------- 06 情形对比（表格 + 条形图 + 右侧洞察） ----------

def table_bar(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    _draw_table(slide, s, y=top + 6)
    b = s['bar']
    textbox(slide, MARGIN, top + 276, 700, 28, [{'text': b['caption'], 'size': 17, 'color': 'gray'}])
    yy = top + 314
    # vmax 取「用户值」与「实际最大值」的较大者：用户把 max 设小了会导致条超宽，
    # 设大了只是条变短，无害。所以这里只能往上取，不能直接用用户值。
    vmax = max(b.get('max') or 0, max(r['v'] for r in b['rows']))
    for r in b['rows']:
        # 名称框留 118px：4 个中文字在 18 号下约 72px，70px 会折行压到下一行
        textbox(slide, MARGIN, yy + 4, 118, 30, [{'text': r['name'], 'size': 18, 'color': 'dgray'}])
        w = max(6, min(460, int(r['v'] / vmax * 460)))
        rect(slide, MARGIN + 128, yy, w, 34, fill=r.get('c', 'navy'))
        textbox(slide, MARGIN + 138 + w, yy + 3, 110, 30,
                [{'text': r['label'], 'size': 18, 'color': 'navy', 'bold': True}])
        yy += 52
    p = s['panel']
    rect(slide, 820, top + 252, 400, 268, fill='xlgray')
    # spacing 1.45：五条内容 × 19 号刚好留 10pt 底边距，1.55 会把最后一行压到面板边线上
    paras(slide, 852, top + 276, 340, 230,
          [{'t': p['title'], 'size': 22, 'c': 'navy', 'b': True}] +
          [{'t': t, 'c': 'cyan' if t == p['items'][-1] else 'dgray'} for t in p['items']],
          size=19, spacing=1.45, gap=10)


# ---------- 07 两栏对照（左右面板 + VS） ----------

def two_panel(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    for i, p in enumerate(s['panels']):
        x = MARGIN + i * 600
        rect(slide, x, top + 6, 560, 400, fill=p.get('bg', 'xlgray'))
        textbox(slide, x + 40, top + 40, 480, 32,
                [{'text': p['label'], 'size': 22, 'color': p.get('sc', 'gray'), 'bold': True}])
        textbox(slide, x + 40, top + 78, 480, 60,
                [{'text': p['head'], 'size': 40, 'color': p.get('tc', 'navy'), 'bold': True}])
        textbox(slide, x + 40, top + 160, 480, 40,
                [{'text': p['mid'], 'size': 22, 'color': p.get('tc', 'navy')}])
        rect(slide, x + 40, top + 212, 480, 1, fill=p.get('rule', 'lgray'))
        textbox(slide, x + 40, top + 232, 480, 40,
                [{'text': p.get('sub_label', '保本线'), 'size': 18, 'color': p.get('sc', 'gray')}])
        bignum(slide, x + 40, top + 264, 480, 110, p['sub'], p['sub_unit'],
               value_size=64, unit_size=20, value_color=p.get('tc', 'navy'),
               unit_color=p.get('sc', 'gray'))
    if s.get('vs', True):
        rect(slide, 628, top + 176, 44, 44, fill='cyan')
        textbox(slide, 628, top + 184, 44, 30,
                [{'text': 'VS', 'size': 18, 'color': 'white', 'bold': True, 'align': PP_ALIGN.CENTER}])
    if s.get('takeaway'):
        textbox(slide, MARGIN, top + 424, CONTENT_W, 70,
                [{'text': s['takeaway'], 'size': 21, 'color': 'dgray', 'line_spacing': 1.55}])


# ---------- 08 表格 + 脚注（七维体检） ----------

def table_footnote(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    bottom = _draw_table(slide, s, y=top + 6)
    if s.get('note'):
        textbox(slide, MARGIN, bottom + 20, CONTENT_W, 40,
                [{'text': s['note'], 'size': 18, 'color': 'gray'}])


# ---------- 09 卡片组（风险清单） ----------

def cards(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    n = len(s['cards'])
    gap = 20
    cw = int((CONTENT_W - gap * (n - 1)) / n)
    for i, c in enumerate(s['cards']):
        x = MARGIN + i * (cw + gap)
        # 卡片高 520（top+6 → top+526）。act 框底 top+520 必须落在卡片内，
        # 留 6px 呼吸；框高 128 装得下「小标题 + 两行 17pt 动作」，动作文案按两行写。
        rect(slide, x, top + 6, cw, 520, fill='white', line='lgray', line_w=1)
        rect(slide, x, top + 6, cw, 4, fill='navy')
        textbox(slide, x + 24, top + 30, cw - 48, 40,
                [{'text': c['num'], 'size': 30, 'color': 'lgray', 'bold': True}])
        textbox(slide, x + 24, top + 80, cw - 48, 70,
                [{'text': c['title'], 'size': 23, 'color': 'navy', 'bold': True, 'line_spacing': 1.25}])
        textbox(slide, x + 24, top + 168, cw - 48, 200,
                [{'text': c['body'], 'size': 18, 'color': 'dgray', 'line_spacing': 1.65}])
        rect(slide, x + 24, top + 386, cw - 48, 1, fill='lgray')
        textbox(slide, x + 24, top + 392, cw - 48, 128,
                [{'text': c.get('act_title', '你能做的'), 'size': 15, 'color': 'cyan', 'bold': True},
                 {'text': c['act'], 'size': 17, 'color': 'dgray', 'line_spacing': 1.55,
                  'space_before': 6}])


# ---------- 10 动作时间线（步骤 + 判断标准条） ----------

def timeline(slide, s, page, total):
    top = header(slide, s['title'], page, total, s.get('source'))
    n = len(s['steps'])
    gap = 20
    cw = int((CONTENT_W - gap * (n - 1)) / n)
    rect(slide, MARGIN, top + 56, CONTENT_W, 2, fill='navy')
    for i, st in enumerate(s['steps']):
        x = MARGIN + i * (cw + gap)
        rect(slide, x, top + 47, 18, 18, fill='navy')
        textbox(slide, x, top + 8, cw, 30, [{'text': st['when'], 'size': 17, 'color': 'cyan', 'bold': True}])
        textbox(slide, x, top + 84, cw, 40, [{'text': st['title'], 'size': 24, 'color': 'navy', 'bold': True}])
        textbox(slide, x, top + 128, cw - 8, 170,
                [{'text': st['body'], 'size': 18, 'color': 'dgray', 'line_spacing': 1.65}])
    j = s.get('judge')
    if j:
        rect(slide, MARGIN, top + 316, CONTENT_W, 150, fill='navy')
        textbox(slide, 96, top + 340, 1088, 40,
                [{'text': j['title'], 'size': 20, 'color': 'lblue', 'bold': True}])
        textbox(slide, 96, top + 376, 1088, 80,
                [{'text': j['text'], 'size': 22, 'color': 'white', 'line_spacing': 1.5}])


# ---------- 11 收尾（深色一句话） ----------

def closing(slide, s, page, total):
    rect(slide, 0, 0, CANVAS_W, CANVAS_H, fill='navy')
    rect(slide, 64, 200, 40, 3, fill='cyan')
    textbox(slide, 64, 232, 1100, 240,
            [{'text': t, 'size': s.get('statement_size', 62), 'color': 'white', 'bold': True,
              'line_spacing': 1.25} for t in s['statement']])
    textbox(slide, 64, 520, 1100, 90,
            [{'text': t, 'size': 22, 'color': 'lblue', 'line_spacing': 1.6} for t in s['supports']])
    rect(slide, 64, 636, 1152, 1, fill='navy2')
    textbox(slide, 64, 652, 900, 30, [{'text': s.get('footer', ''), 'size': 13, 'color': 'gray'}])


LAYOUTS = {
    'cover': cover,
    'three-col': three_col,
    'table-assumptions': table_assumptions,
    'table-card': table_card,
    'bignum-costlist': bignum_costlist,
    'table-bar': table_bar,
    'two-panel': two_panel,
    'table-footnote': table_footnote,
    'cards': cards,
    'timeline': timeline,
    'closing': closing,
}
