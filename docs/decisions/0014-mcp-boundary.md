# 0014 MCP 边界：只包确定性计算，用 resources 补足无文件系统的宿主

## 背景

0013 定下发形态时，明确写了「MCP 形态尚未实现」，并给了一条理由：判断全在文档里，MCP 只该包确定性计算，早做只会加安装复杂度。

这条理由只对了一半。真正的缺口不是「工具不够用」，是**只支持 MCP、没有文件系统权限的宿主拿不到那 77 个 Markdown**。这类宿主装了 MCP 只能调几个函数，读不到 `references/`——那等于拿到一副骨架，没有肉。

另一半仍然成立：给 MCP 加「判断」是错的。工具一旦会下结论，文档里的公式和代码里的公式就会各自漂移，而用户永远只看到其中一份。

## 决定

实现 `tools/mcp_server.py`，暴露三样东西：

| 能力 | 内容 | 是否含判断 |
| --- | --- | --- |
| tools | `capital_band`、`h2_check`、`taxonomy_lookup`、`source_grade`、`search_budget` | 否，全部纯函数 |
| resources | `SKILL.md`、`INSTALL.md`、`references/`、`data/`、`examples/`、`hosts/` 的全量只读资源，按目录自动枚举 | — |
| prompts | `checkup`（方向 + 预算 → 装进两阶段流程） | 否，只组装输入 |

三条实现约束：

1. **零依赖。** 不装 `mcp` SDK，用标准库手写 stdio JSON-RPC（按行分隔的 JSON，`initialize` / `tools/list` / `tools/call` / `resources/*` / `prompts/*` / `ping`，错误码 −32700 / −32600 / −32601 / −32602）。
2. **阈值只读 `data/params.json`**，服务端里不出现任何硬编码数字。
3. **`h2_check` 的 `fixed_cost_items` 必填。** 覆盖不足 3 项时返回「信息不足」，不允许用行业常规值填分母。

## 理由

**为什么手写协议而不是装 SDK。** 仓库对外的承诺是「克隆即用、零环境依赖」，`tools/wheels/` 入库就是这个逻辑。MCP 的 stdio 传输本质就是 JSON-RPC over stdin/stdout，标准库完全够，装了 SDK 反而引入版本漂移与安装前置条件。代价是要自己跟协议版本（目前接受 2025-06-18 / 2025-03-26 / 2024-11-05，其余回落最新）。

**为什么 resources 比 tools 更重要。** 这个技能的价值 99% 在文档里。只给工具，等于让宿主「能算但不知道为什么要这么算」。resources 让没有文件系统权限的客户端也能读全文，MCP 才不是降级形态，而是另一种拿得到全量的方式。

**为什么 `fixed_cost_items` 要在参数里出现。** 文档写「月度固定支出必须由店租、人工、生活开支、其他固定项三项以上构成，缺项只能判信息不足」。这句话如果只写在文档里，工具默认取 3 就是系统在替用户编数——正是文档最反对的事。把它变成一个必填参数，规则就从「靠模型记得」变成「结构上做不到」。

**为什么不做 `deck_render`。** 出 pptx 要 `python-pptx`，一引入就破坏零依赖。要文件仍走 `tools/deck_engine.py`（有 `.venv` 与离线 wheels 兜底），MCP 不承担这条路径。

**为什么 `hosts/` 进安装单元。** 它原本被当成接入文档放在仓库根，但装完之后用户仍可能需要它（比如宿主换了要换形态）。且 `INSTALL.md` 在安装单元内，链接 `hosts/` 若不在单元内就是死链。它不属于维护者资料，进单元不违反 0013。

## 后果

- **改阈值要动两处**：文档 + `data/params.json`。`skill_check.py` 的 `check_params` 逐项断言资金带切点、H2 缓冲与爬坡期、检索预算、七种原型名一致，改单边即红。这不是两套真相，是一条链上的两个视图，由退出码锁住。
- **`mcp_server.py` 不能单独拷走**：它按 `__file__` 上溯定位根目录，要读同级的 `data/params.json` 与 `references/`。装到别处必须整目录。
- **协议版本要跟**：MCP 还在演进，新增版本时改 `PROTOCOLS` 常量即可，但每加一个都要在 `--selftest` 里补一条断言。
- **尚未在真实第三方客户端里联调**：目前只做到管道级协议测试（`printf ... | python tools/mcp_server.py` 走完 initialize → tools/list → tools/call → resources/list）、`--selftest` 的 15 项断言、以及装到 `~/.workbuddy/skills/` 后在新位置复验。真机上「客户端认不认这份 `serverInfo`」没有验过，第一次接入时按 `hosts/mcp.md` 的排查表走。
- **不做的事**：不给工具加「判断」，不把 `examples/` 的验收断言搬进 MCP（那是 `skill_smoke.py` 的职责，且需要人读输出）。
