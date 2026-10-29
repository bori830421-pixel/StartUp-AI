# 版式引擎

把一份 JSON（brief）渲染成 16:9 的 `.pptx`。**几何写死，内容全在 brief 里**——所以出图只要两秒，不用再调坐标。

## 它解决什么问题

手写坐标做 11 页 PPT，大约 40 分钟，其中八成时间花在「字怎么摆进方框」。同样的版式第二次还要重来一遍。

这个引擎把 11 种版式固化成页型函数，内容换成数据。第二次做同结构的测算，只写 brief。

## 装

```bash
pip install python-pptx -i https://mirrors.aliyun.com/pypi/simple/
```

默认源与清华源在国内常超时，用阿里云镜像。装不上不影响使用——按 `references/deck-spec.md` 的 L2/L3 降级交付。

## 用

```bash
cd tools
python deck_engine.py briefs/01-chenghai-zhaoyiming.json 输出.pptx
python deck_engine.py briefs/01-chenghai-zhaoyiming.json 输出.pptx --png preview/
```

- `--png`：Windows 下用 COM 导出逐页图片，用于目视复核（失败只告警，不影响出文件）
- `--strict`：自检有 `[必改]` 时返回退出码 1，适合放进流程里卡交付

退出码：`0` 正常 / `2` 缺依赖 / `3` brief 结构错误 / `4` 渲染失败。

## 文件

| 文件 | 职责 | 行数上限 |
| --- | --- | --- |
| `deck_kit.py` | 设计令牌、px/pt 换算、文本框/表格/面板等基础件 | 400 |
| `deck_layouts.py` | 11 种页型，每种只吃数据 | 400 |
| `deck_engine.py` | 命令行入口、自检、PNG 导出 | 200 |
| `briefs/*.json` | 内容。新增一份就是一个新演示文稿 | — |

新增页型：在 `deck_layouts.py` 复制最接近的一个，改几何、改字段，登记进 `LAYOUTS`。**不要在页型里写业务判断**，判断属于 brief 之前的那一步。

## 自检能查什么

跑完打印两类：

- `[必改]` 文字被后画的色块盖住（遮挡 30% 以上）、两个文字框压住彼此（重叠 50% 以上）。几何事实，必须修。
- `[提示]` 估算高度超出声明框高 25% 以上。估算偏保守，需目视确认。

自检**不判断好不好看**。标题是不是结论句、数字前后是否一致、假设有没有标注，仍然按 `references/deck-spec.md` 第 7 节人工过。

## 已知限制

- 中文字体写死 `微软雅黑`，英文 `Arial`。换字体改 `deck_kit.py` 的 `EA` / `LATIN`。
- 文本宽度是估算（全角按 1 字号、半角按 0.55 字号），所以 `[提示]` 会有误报，不会漏报。
- PNG 导出依赖本机装了 PowerPoint 或 WPS 且 COM 可用。导出失败不影响 `.pptx` 本身。
- 只覆盖 11 种页型。需要新结构时加页型，不要用拼凑的办法硬塞。
