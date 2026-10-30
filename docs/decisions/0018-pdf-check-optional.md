# 0018 PDF 几何检查从必需依赖降为可选层

- 状态：已采纳（修订 0010 的依赖口径，三级降级本身不变）
- 日期：2026-10-30

## 背景

0010 定的是「引擎可选、渲染三级降级」，落地时却把验证手段写成了前置条件：`requirements.txt` 里 PyMuPDF 与 comtypes 是默认依赖，`setup.bat` 默认安装，`doctor.py` 缺一项就判「不能出稿」，README 与 `SKILL.md` 都写着「缺一项会明确说缺什么并停下」。

本机实测暴露了这个口径的问题：三路渲染器全废。没有 PowerPoint；LibreOffice 导出的 PDF 没有字体表，文字全成字形序号；WPS 免费版 `SaveAs` / `ExportAsFixedFormat` 都报 `-2147467259`。用户只想拿到一个 `.pptx`，却被告知环境不全——**卡住交付的不是交付物，是检查交付物的手段**。

另一处实测：`soffice.exe` 路径存在，但子进程被降到 Low IL、`%TEMP%` 不可写，每次启动等约 50 秒后失败。只看文件存在就判「兜底可用」，几何检查永远跑不起来而报告说没问题。

## 决定

1. **依赖分两层。** `tools/requirements.txt` 只留 `python-pptx`（出 PPTX 必需）；PDF 检查依赖移到 `tools/requirements-pdf-check.txt`（PyMuPDF 仍锁 1.24.x，加 comtypes）。
2. **安装显式化。** `setup.bat` 默认只装基础层；`--with-pdf-check` 才装可选层，且**不安装** PowerPoint / LibreOffice / WPS——渲染器由用户自理。
3. **体检分模式。** `doctor.py` 默认只判基础环境；`--pdf` 才真转一次（出稿 → 转 PDF → 验文字可读），结论按实测结果给，不按文件存在给。
4. **出稿与检查解耦。** `make-ppt.bat` 默认出稿即完成，`--check` 才跑几何检查。`references/deck-spec.md` 第 6 节的 L1 不再要求 PDF 或 PNG。
5. **说清做了什么、没做什么。** 未做几何检查要在交付时说明，但不表述为「环境不全不能出稿」。

## 理由

- **验证手段不能成为交付前提。** 与 0007「卡片只决定搜什么、不提供结论」同构：几何检查只决定结论有多可信，不决定能不能交付。
- **不可控的外部软件不该进必需项。** 三路渲染器全废是本机事实，不是配置疏忽；把「能不能交付」挂在用户没装的软件上，等于把交付能力外包给环境。
- **真转一次比查路径可信。** 上面 `soffice` 的例子说明「装没装」和「能不能用」是两件事，所以 `--pdf` 按真实转换结果判定。

## 后果

- `dist/startup-guide/tools/` 多一个 `requirements-pdf-check.txt`，已在 `build_skill.py` 的 `TOOL_FILES` 登记。
- 四处文档同步：`README.md` 部署段、`tools/README.md` 的「装」与「依赖版本」两节、`references/deck-spec.md` 第 6/7 节、`SKILL.md` 的必须遵守。
- **接受的代价**：几何检查从「交付前必过」变成「按需」，`[必改]` 项清零只在用户要求检查时作为卡交付条件。版式缺陷的兜底因此只剩引擎自检加人工四关，交付质量的口径变宽了。
- 装好 PowerPoint 后仍应跑一次 `deck_lint` 补证据，那是补证据，不是补前置条件。
- 0010 的三级降级结构不变，本次只改「每一级需要什么」。
