# 参考模板索引

本目录保存可复用的方法与模板：怎么问、怎么算分、怎么分模式、怎么陪跑、怎么整理交付物。规则说「做什么」，这里说「具体怎么做」。

本目录不放判断结论（在 `../docs/`）、不放完整输入输出样例（在 `../examples/`）、不放行业数据（在 `../data/`）。

## 文件清单

| 文件 | 用途 | 状态 |
| --- | --- | --- |
| [intake-questions.md](./intake-questions.md) | 8 道选择题形式的引导盘点，把答不出的开放题变成答得出的选择题 | 现行 |
| [pattern-fork.md](./pattern-fork.md) | 体检前的模式分叉：分叉位置、各类目分叉、对四项的影响、三条纪律 | 现行 |
| [runtime-loop.md](./runtime-loop.md) | 运行时循环：分型→检索计划→执行→校验→判断→输出六步，含两轮检索预算与「什么算查到了」 | 现行 |
| [offline-degradation.md](./offline-degradation.md) | 离线降级：四类「搜不了」的判定、固定提示话术、无网络时哪些维度还能算、结论封顶规则 | 现行 |
| [search-playbook.md](./search-playbook.md) | 检索剧本：四类查询公式、七个原型各自的查询串模板、站点限定、垃圾识别 | 现行 |
| [research-protocol.md](./research-protocol.md) | 定向检索协议：结构靠推演、参数靠实测、事实靠原文；反证测试与交叉验证 | 现行 |
| [checkup-scorecard.md](./checkup-scorecard.md) | 七维评分口径：三个硬门槛加四个软约束，含分档与不做什么 | 现行 |
| [novice-guidance.md](./novice-guidance.md) | 面向新手的输出形态原则：三类简单思维与对应写法 | 现行 |
| [coaching-templates.md](./coaching-templates.md) | 单阶段陪跑骨架：目标、动作、交付物、话术、账本、判断点 | 现行 |
| [output-templates.md](./output-templates.md) | 报告、演示文稿、PDF 的章节结构与一致性检查 | 现行 |
| [deck-spec.md](./deck-spec.md) | 演示文稿交付规格：两类模板的页序、每页必须成立的判断、渲染三级降级 | 现行 |

## 阅读顺序

主流程顺序是 `intake-questions` → `pattern-fork` → `runtime-loop` → `checkup-scorecard`，`novice-guidance` 全程约束输出形态，`coaching-templates` 只在闸门放行后使用，`output-templates` 与 `deck-spec` 只在用户要文件时使用。

交付形式的两个文件分工：`output-templates.md` 给章节结构与一致性检查项，`deck-spec.md` 给页序、页型与渲染降级。要出文件时先读 `deck-spec.md`，它引用了 `tools/` 的引擎。

检索相关的四份文件分工，不要混着用：

| 文件 | 回答什么 | 什么时候翻 |
| --- | --- | --- |
| `runtime-loop.md` | 检索的流程与预算：怎么起、几轮停、什么算查到 | 每次评估开头 |
| `offline-degradation.md` | 没有网络时怎么降级：怎么判定、怎么告知、结论能到哪一档 | 检索跑不起来时 |
| `search-playbook.md` | 具体查询串怎么写、去哪搜、搜到什么算垃圾 | 生成检索计划时 |
| `research-protocol.md` | 三层依据怎么分工：结构不搜、参数实测、事实原文 | 判断能不能用某条信息时 |

## 新增约定

- 一份模板只解决一件事，不把提问、评分、话术混在一个文件里。
- 模板里的阈值与 `../docs/capability-index.md` 的能力状态保持一致；规则改了先改 `../AGENTS.md`，再改这里。
- 新增文件后在本文件登记，超过 120 行加「本文导航」。
