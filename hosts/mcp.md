# C 形态：MCP

适用：支持 MCP 的客户端。零依赖——服务端只用 Python 标准库手写 stdio JSON-RPC，不需要 `pip install mcp`。

## 配置

把 `dist/startup-guide/tools/mcp_server.py` 的绝对路径填进去：

```json
{
  "mcpServers": {
    "startup-guide": {
      "command": "python3",
      "args": ["/绝对路径/dist/startup-guide/tools/mcp_server.py"]
    }
  }
}
```

Windows 上 `command` 用 `python`。路径里不要用 `~`，多数客户端不展开。

服务端自己按 `__file__` 上溯定位根目录，所以**工作目录无关**，但也因此：`mcp_server.py` 必须留在 `dist/startup-guide/tools/` 里，不能单独拷走——它要读同级的 `data/params.json` 和 `references/`。

## 五个工具

| 工具 | 输入（参数名照抄） | 输出 | 不做的事 |
| --- | --- | --- | --- |
| `capital_band` | `amount_cny`（数字，人民币元） | B1–B6 档、能碰/碰不了的原型、致命约束、接着必问的三个数 | 不说能不能做 |
| `h2_check` | `case`（`A`/`B`）与 `fixed_cost_items`（整数，必填）；A 加 `available_fund` / `monthly_fixed` / `months_to_first_income`；B 加 `working_capital` / `monthly_net_outflow`，`ramp_months` 可省 | 可撑月数、所需月数、通过/不通过/信息不足、算式 | 不在缺项时替用户填数 |
| `taxonomy_lookup` | `keyword`（用户口中的方向） | 国标门类、可及度、原型候选 | 不给成本数据 |
| `source_grade` | `url`（链接或域名） | A–E 级、用法限制、L1–L4 组合规则 | 不判断内容真假 |
| `search_budget` | `required_online`（整数） | 检索预算（×2，上限 12） | 不决定查什么 |

**参数名照抄，别按中文意思猜。** 实测过：把预算写成 `budget` 会返回 `amount_cny 必须是非负数字`。客户端应以 `tools/list` 里的 `inputSchema` 为准，不要从描述文字反推字段名——描述说的是「预算金额」，字段叫 `amount_cny`。

**工具里没有判断。** 判断永远在提示词侧——这条边界与决策记录 0010「引擎只排版不判断」是同一条。这么切的原因：判断一旦进代码，就会出现「文档里的 H2 公式」和「代码里的 H2 公式」各自漂移，而用户看到的永远是其中一份。

`h2_check` 的 `fixed_cost_items` 是必填的，看起来多余，其实是文档规则的直接翻译：月度固定支出必须由店租、人工、生活开支、其他固定项三项以上构成，缺项时只能判「信息不足」，不许用行业常规值填分母。少这一项，工具就会替用户编数。

## 资源与提示

- `resources`：全量只读资源，`skill://SKILL.md`、`skill://references/*`、`skill://data/*`、`skill://examples/*`、`skill://hosts/*`，按目录自动枚举，新增文件不用改代码。只支持 MCP、没有文件系统权限的客户端也能拿到完整方法论。
- `prompts`：`checkup`，参数 `direction` / `budget` / `notes`。它把用户输入装进两阶段流程，不替你做判断。

## 装完验证

先不接宿主，直接验服务端：

```bash
python3 tools/mcp_server.py --selftest   # 15 项工具断言，退出码 0
python3 tools/mcp_server.py --list       # 看暴露了什么
```

再接宿主，用 `install` 用例那句话提问，判据同目录形态三条。

## 一个坑

MCP 工具返回的是「算式与判定」，不是结论。宿主如果直接把 `h2_check` 的输出念给用户，用户会看到一句「不通过」却不知道为什么。正确用法是先按 `SKILL.md` 走完模式分叉，再拿 `h2_check` 算一个数，最后把依据讲成人话。这也是为什么 `tools/call` 的返回里带着 `formula` 字段——让模型有东西可讲。
