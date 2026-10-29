# 版式引擎

## 本文导航

- [它解决什么问题](#它解决什么问题)
- [装](#装)
- [用](#用)
- [交付前几何检查](#交付前几何检查)
- [文件](#文件)
- [部署踩过的坑](#部署踩过的坑)
- [自检能查什么](#自检能查什么)
- [已知限制](#已知限制)

把一份 JSON（brief）渲染成 16:9 的 `.pptx`。**几何写死，内容全在 brief 里**——所以出图只要两秒，不用再调坐标。

## 它解决什么问题

手写坐标做 11 页 PPT，大约 40 分钟，其中八成时间花在「字怎么摆进方框」。同样的版式第二次还要重来一遍。

这个引擎把 11 种版式固化成页型函数，内容换成数据。第二次做同结构的测算，只写 brief。

## 装

**双击项目根目录的 `setup.bat` 就行**，不需要联网，也不需要先装 Python 包。

它会：找一个可用的 Python（3.9+）→ 在项目根目录建 `.venv`（不动系统 Python）→ 从 `tools/wheels/` 离线装依赖 → 出 3 页 pptx 做冒烟测试 → 跑环境体检。全部通过才说「可以出 PPT 了」。

装完检查环境：

```bash
python tools/doctor.py        # 逐项列出必需/告警，结论直说能不能出稿
```

必需项缺一个就不能出：Python、python-pptx、PyMuPDF、**PDF 渲染器（三选一）**。字体只告警，不影响出稿。

### PDF 渲染器：三选一

几何检查需要把 pptx 转成 PDF 才能读到真实断行。**不要求必须装 LibreOffice**，下面三种任有其一即可，按这个优先级自动选择。

耗时一栏是在一台 Windows 机器上的参考值，**换个环境会差很多**（机械硬盘、杀毒软件、Office 版本都会影响）。用它的理由不是绝对速度，而是「PowerPoint 渲染的版式就是用户在 PowerPoint 里看到的那个」：

| 顺序 | 渲染器 | 参考耗时 | 说明 |
| --- | --- | --- | --- |
| 1 | **PowerPoint**（COM） | 约 2s | 与用户在 PowerPoint 里看到的完全一致，所以排第一 |
| 2 | **LibreOffice** | 冷启动较慢（数十秒量级） | 免安装生态最广，但明显慢于前两者 |
| 3 | **WPS**（COM） | 约 2s | 兜底。兼容 COM 接口，但渲染细节与真实 PowerPoint 差异最大，所以排最后 |

**三种都没有时，出稿照常，但几何检查跳过。** 这不是错误配置，是环境差异——`doctor.py` 会把这个情况标成必需项缺失并给出安装指引，是否安装由用户决定。

用 `--engine` 可强制指定：

```bash
python tools/deck_lint.py 输出.pptx --engine PowerPoint
```

每次运行会在第一行回显实际用了哪个渲染器。

> **换引擎等于换基准。** 三种引擎的行高舍入不同，同一份稿子的 `[提示]` 项可能相差 ±1pt（例如「贴底色块下边 -1pt」在 LibreOffice 下报、在 PowerPoint 下不报）。`[必改]` 项在三种引擎下结论一致——那才是卡交付的条件。

### 为什么不用 `pip install` 一行命令

一台机器常有多个 Python 解释器，`pip install` 装到哪一个取决于 PATH 顺序，下次换个终端就可能又找不到包。`setup.bat` 显式探测解释器并校验版本，再用项目内 `.venv`，所以装到哪一个是确定的。

### 依赖版本（固定）

见 `tools/requirements.txt`。两个必须说明的锁：

- `PyMuPDF` 锁 `1.24.x`：2.x 会连带拉 onnxruntime / numpy / pymupdf4llm，体积从 15.5 MB 涨到 100 MB。
- `comtypes` 必须装：只有 292 KB，但它决定了能不能走 PowerPoint / WPS 渲染（通常远快于 LibreOffice 冷启动），同时是 `--png` 导图的前提。

`tools/wheels/` 里是这 7 个 wheel（27.2 MB），入库，所以克隆即可离线部署。

## 用

```bash
make-ppt.bat tools\briefs\01-chenghai-zhaoyiming.json 输出.pptx     # 渲染 + 几何检查
make-ppt.bat --list                                            # 列现成用例
```

也可以直接调脚本（先确保用 `.venv` 里的解释器）：

```bash
.venv\Scripts\python.exe tools\deck_engine.py tools/briefs/01-chenghai-zhaoyiming.json 输出.pptx
python tools/deck_lint.py 输出.pptx --png preview/             # 已渲染的稿子，顺带导图
```

- `--png`：Windows 下用 COM 导出逐页图片，用于目视复核（失败只告警，不影响出文件）
- `--strict`：自检有 `[必改]` 时返回退出码 1，适合放进流程里卡交付

退出码：`0` 正常 / `2` 缺依赖 / `3` brief 结构错误 / `4` 渲染失败。

## 交付前几何检查

`deck_engine` 的自检只比对文字框自身的估高与框高，**管不到「文字框 vs 它背后的色块」，也管不到渲染器实际怎么断行**。这两类问题过去只能靠「转 PDF → 转 PNG → 逐页看图」，一轮 50 秒。

`deck_lint.py` 把 PDF 的真实坐标读出来，一次给出全部可判定缺陷：

```bash
python deck_lint.py 输出.pptx              # 已渲染的稿子
python deck_lint.py briefs/xx.json        # 先渲染再查，临时文件自动清理
python deck_lint.py 输出.pptx --png out/  # 顺手导出逐页图，供人工抽查
```

| 级别 | 检查 | 判据 |
| --- | --- | --- |
| 必改 | 越出色块 | 文字落在某个填充矩形内，但某一边超出 > 5pt（约 7px） |
| 必改 | 出页面 | 文字 bbox 越过页面边界 |
| 必改 | 行首标点 | 某行以「。！？」开头——等于半行空白 |
| 必改 | 文字重叠 | 两行文字压住彼此一半以上 |
| 提示 | 贴底色块下边 | 没越界但离底边不足 4pt，内边距被吃光，视觉上就是压线 |
| 提示 | 行首标点 | 以「，、；：」开头，读得下去，但不够干净 |
| 提示 | 残行 | 只剩一个标点独自成行 |

`--tol` 调越界容差（默认 5pt）。退出码 `0` 干净 / `1` 有必改项，可以串进脚本。

依赖一个 PDF 渲染器（PowerPoint / LibreOffice / WPS 任选其一，自动选择）转 PDF，一种都没有会直接报错，不会假装通过。

## 文件

| 文件 | 职责 | 行数上限 |
| --- | --- | --- |
| `deck_kit.py` | 设计令牌、px/pt 换算、文本框/表格/面板等基础件 | 400 |
| `deck_layouts.py` | 11 种页型，每种只吃数据 | 400 |
| `deck_engine.py` | 命令行入口、自检、PNG 导出 | 200 |
| `deck_lint.py` | 读 PDF 真实坐标做几何检查，出缺陷清单 | 250 |
| `doc_check.py` | 文档结构自检：体积上限、本文导航、锚点、相对链接；纯标准库，跨平台 | 300 |
| `build_skill.py` | 构建可安装技能目录 `dist/startup-guide/`，剔除 `.venv` 与 wheels；安装清单见根目录 `INSTALL.md` | 200 |
| `skill_check.py` | 校验安装产物：frontmatter 规范、目录名一致、体积、产物是否过期 | 250 |
| `skill_smoke.py` | 接入冒烟验收：打印 4 个验收输入（INSTALL 第 3 节与样例 09/12/16），校验宿主输出形态并以退出码给结论；只验形态不判内容，维护者侧工具不进安装单元 | 300 |
| `build_flat.py` | 生成 B 形态单文件 `dist/startup-guide.flat.txt`：SKILL.md 加 4 份关键 references 机械合并，给只有对话框的宿主当系统提示；`--check` 拦过期产物，`.txt` 载荷不占文档行数口径 | 150 |
| `mcp_server.py` | MCP 服务端（stdio JSON-RPC，纯标准库不装 SDK）：5 个只读工具 + 全量 resources + `checkup` prompt；阈值全读 `data/params.json`，工具里不含判断。`--selftest` 断言，`--list` 看暴露面 | 300 |
| `mcp_tools.py` | MCP 的工具层：五个只读工具与 `TOOLS` 表。只算数不下判断；拆出来是为了守住单文件 400 行上限 | 300 |
| `bootstrap.py` | 部署：建 `.venv`、离线装 wheel、冒烟测试 | 300 |
| `doctor.py` | 环境体检：必需/告警分级，缺全部渲染器才判不能出稿 | 300 |
| `requirements.txt` | 固定版本清单，给想联网装同一套的人用 | — |
| `wheels/*.whl` | 离线依赖源，6 个文件 26.9 MB，入库 | — |
| `briefs/*.json` | 内容。新增一份就是一个新演示文稿 | — |

`doc_check.py` 不依赖 `python-pptx`，只查 Markdown 与代码文件的结构，是 `AGENTS.md`「交付前自检」的指定命令：

```bash
python tools/doc_check.py              # 有缺陷退出码 1
python tools/doc_check.py --verbose    # 附带体积排行
```

它替代原来那条 `find ... -exec wc -lc`——那条在 Windows 上不可用，导致「本文导航」「锚点」两项检查长期没人真正跑过。首次接入时它当场查出 8 个此前漏掉的文件（6 个缺导航、2 个导航与标题不一致）。

## 部署踩过的坑

下面两条是 **Windows 平台的通用行为**，不是某台机器的特殊现象，任何中文 Windows 上都会遇到：

| 坑 | 表现 | 正确做法 |
| --- | --- | --- |
| `.bat` 存成 UTF-8 无 BOM | cmd.exe 按系统 ANSI 码页（中文 Windows 是 936）解析，把 `set PYTHONIOENCODING` 吃掉首字母，报 `'ONIOENCODING' is not recognized` | 存成 **UTF-8 with BOM**，并在开头 `chcp 65001` |
| 用 `errorlevel` 判断 `py -3.12` 是否存在 | 版本不存在时 `py` 只往 stderr 报错、**退出码仍是 0**，导致误选到下一个版本 | 用 `for /f` 捕获它打印的版本号，只有打出来的值等于请求版本才算找到 |

这条依赖机器上装了什么，**不保证任何环境都有**：

| 依赖 | 缺了会怎样 | 怎么处理 |
| --- | --- | --- |
| PowerPoint / WPS / LibreOffice | 几何检查转不了 PDF | 三者任选其一（见「装」一节的渲染器表），`doctor.py` 会告警 |
| 微软雅黑字体 | 用替代字体，版式可能偏移 | 只告警，不拦出稿 |
| comtypes | `--png` 导图不可用 | 已随 wheels 安装，正常都有 |

另外，中文提示全部由 Python 打印（Python 侧 `sys.stdout.reconfigure(encoding='utf-8')`），`deck_engine.py` 与 `deck_lint.py` 都在缺依赖提示**之前**加了这段，否则连「缺 python-pptx」那条本身都是乱码。


现有 brief：

| 文件 | 场景 | 用途 |
| --- | --- | --- |
| `01-chenghai-zhaoyiming.json` | 加盟测算，11 页 | 主回归基准，数字已核 |
| `02-park-kite.json` | 公园摆摊卖风筝，9 页 | 覆盖度测试：结构完全不同的场景能否零改代码出图。**数字为示意，只作写法参考，不可当数据引用** |
| `_stress.json` | 故意超载的 4 页 | 压力用例：8 行表格 + 补注、`max` 设小的条形图、5 张卡、5 步时间线。改几何后跑一遍，确认不会画到页外 |

新增页型：在 `deck_layouts.py` 复制最接近的一个，改几何、改字段，登记进 `LAYOUTS`。**不要在页型里写业务判断**，判断属于 brief 之前的那一步。

## 自检能查什么

跑完打印两类：

- `[必改]` 三类，都是几何事实：
  - **遮挡**：文字被后画的色块盖住 30% 以上面积，一定看不见。
  - **重叠**：两个文字框压住彼此 50% 以上，一定有字叠在一起。
  - **出界**：文字估算底边画到页面外（`> 720px`）。这类必须用估算高度判，因为声明框大而内容少的框，框出界但字没出界。
- `[提示]` 估算高度超出声明框高 25% 以上。估算偏保守，需目视确认。

自检**不判断好不好看**。标题是不是结论句、数字前后是否一致、假设有没有标注，仍然按 `references/deck-spec.md` 第 7 节人工过。

自检的盲区交给 `deck_lint.py`：文字框与背后色块的关系、渲染器实际断行、行首标点，都由它从 PDF 坐标判定。两个工具的分工是——引擎管「声明对不对」，lint 管「画出来对不对」。

## 已知限制

- 中文字体写死 `微软雅黑`，英文 `Arial`。换字体改 `deck_kit.py` 的 `EA` / `LATIN`。
- 文本宽度是估算（全角按 1 字号、半角按 0.55 字号），所以 `[提示]` 会有误报，不会漏报。真实断行只有渲染出来才知道——以 `deck_lint.py` 的结果为准。
- PNG 导出依赖系统中装了 PowerPoint 或 WPS 且 COM 可用。导出失败不影响 `.pptx` 本身。
- 只覆盖 11 种页型。需要新结构时加页型，不要用拼凑的办法硬塞。
- 表格行数少的页（`table-card`）左下会空出一片，用可选 `left_notes`（`{title, items}`）补一段解读。不写就空着；空间不够时自动不画，宁可空着也不出界。
- 条形图的品类名称框固定 118px，超过 6 个中文字会折行。名称写短，长名放表格里。`bar.max` 小于实际最大值时按实际最大值算，比例不会失真。
- `cards` 的「你能做的」只放得下 2 行动作。写 3 行会顶到卡片底边，`[提示]` 会报框偏紧。
- `cards` 建议 3–4 张。5 张时每张宽度只剩 214px，正文会折成 6 行以上，属于内容超载，应改成分两页或缩文案。
