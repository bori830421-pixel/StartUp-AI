# 文档目录索引

本目录保存技能的结构性说明：它是什么、由哪些模块组成、能力到什么程度、怎么验证，以及每个结构性改动的原因。

本目录不放行为样例（见 `../examples/`）、不放可复用模板（见 `../references/`）、不放行业数据（见 `../data/`）。

## 文件清单

| 文件 | 用途 | 状态 |
| --- | --- | --- |
| [architecture-map.md](./architecture-map.md) | 产品目的、主流程、能力模块、数据边界、文件边界 | 现行 |
| [capability-index.md](./capability-index.md) | 能力清单、成熟度状态、对应样例、条目编写约定 | 现行 |
| [verification-guide.md](./verification-guide.md) | 验收场景、交付前检查、闸门退化形态、文档变更验证方式 | 现行 |
| [decisions/](./decisions/) | 决策记录，一主题一文件，编号连续 | 11 份 |

## 决策记录

决策记录按编号递增，不复用编号，不合并成一个大文件。每份回答四件事：背景、决定、理由、后果。

| 编号 | 主题 | 状态 |
| --- | --- | --- |
| [0001](./decisions/0001-scope-and-boundaries.md) | 范围与边界 | 已采纳 |
| [0002](./decisions/0002-two-stage-gate.md) | 两阶段与闸门 | 已采纳 |
| [0003](./decisions/0003-data-layer.md) | 行业档案与数据分级 | 已采纳 |
| [0004](./decisions/0004-pattern-fork.md) | 模式分叉前置 | 已采纳 |
| [0005](./decisions/0005-file-size-and-navigation.md) | 文件规模与导航索引 | 已采纳 |
| [0006](./decisions/0006-archetype-layer.md) | 按原型分类，不按行业分类 | 已采纳 |
| [0007](./decisions/0007-runtime-retrieval.md) | 技能是运行时流程，不是静态知识库 | 已采纳 |
| [0008](./decisions/0008-offline-degradation.md) | 没有联网时的降级规则 | 已采纳 |
| [0009](./decisions/0009-franchise-h2-and-budget.md) | 加盟类：预算按必查项算，H2 走净现金流 | 已采纳（修订 0007 的预算口径） |
| [0010](./decisions/0010-deck-engine.md) | 版式引擎：只排版不判断，三级降级 | 已采纳 |
| [0011](./decisions/0011-h1-channel-quantity.md) | H1：渠道不能单独充数，至少 3 个要说清背后客户量 | 已采纳 |

## 新增约定

- 结构性说明改动写进对应的三份主文件；跨模块的取舍写新决策记录，不追加到旧记录。
- 决策记录文件名 `NNNN-主题.md`，四位编号，取当前最大编号加一。
- 新增文件后，在本文件的文件清单里登记；超过 120 行的文件在顶部加「本文导航」。
- 阈值与自检口径见 `../AGENTS.md` 的「文件规模与导航约束」。
