# 安装与接入

> 给智能体：读完第 1–4 节即可完成接入，不需要再读别的文件，除了第 2 步指定的那一份。
> 给维护者：产物由 `tools/build_skill.py` 生成，规则见 `AGENTS.md`「分发与打包约束」，不要手改 `dist/`。

## 1. 这是什么

一个创业方向评估技能。输入「方向 + 预算」，输出「现在该不该开始」的四档判断：放行、有条件放行、信息不足、不建议启动。

全部是流程规则，不含判断代码。判断靠提示词，脚本只做排版与结构自检。所以它能在任何能读文件的宿主上跑。

## 2. 三选一，先判定宿主能力

| 判定 | 形态 | 动作 |
| --- | --- | --- |
| 存在 `~/.workbuddy/skills/`、`.agents/skills/` 或 `.claude/skills/` | A 目录技能（推荐） | 把 `dist/startup-guide/` 整个复制进该目录 |
| 只能接受一段文本（网页版对话、API 单轮） | B 单文件 | 把 `dist/startup-guide.flat.txt` 全文作为系统提示：SKILL.md 加 4 份关键 references 的合并单文件，由 `tools/build_flat.py` 生成；其余 references 按问题临时补 |
| 支持 MCP | C MCP | 配置 `{"command":"python3","args":["<绝对路径>/dist/startup-guide/tools/mcp_server.py"]}`，零依赖，不必装 SDK |

三种形态的细节、落点与各自的坑见 [hosts/](./hosts/README.md)：目录形态看 [directory.md](./hosts/directory.md)，MCP 看 [mcp.md](./hosts/mcp.md)，纯文本看 [plain-prompt.md](./hosts/plain-prompt.md)。不确定就不看，上面这张表够用。

`dist/startup-guide/` 已在仓库里，克隆即可用，不需要先装 Python。只有改了源文件才需要重建（`python tools/build_skill.py`）。

**目录名必须是 `startup-guide`。** 规范要求 frontmatter 的 `name` 与父目录名一致，且只含小写字母、数字、连字符。改成 `StartUp-AI` 这类名字，宿主会拒绝安装或装成一个找不到的名字。

B 形态的能力弱于 A：单文件没有按需加载，`SKILL.md` 里写「见 `references/xxx.md`」的地方，模型只能靠你补进去的那几份推断。能装目录就别用 B。

## 3. 验证（30 秒，必做）

原样发送这句话，不要加额外提示：

> 我想在小区门口摆摊卖烤肠，预算 3000，帮我看看能不能做。

三条同时成立才算接上：

1. 先问经营模式或给模式对比，**没有直接算钱**
2. 输出里出现 H1 / H2 / H3 中的至少两项
3. 结尾是一个当天能做的动作，不是一段总结

这三条可以自动校验：把宿主回复存成 UTF-8 文件，在克隆的仓库里跑 `python tools/skill_smoke.py --check install 回复.txt`，退出码 0 即接上；另有 09 / 12 / 16 三个进阶用例，`--list` 查看。工具在仓库 `tools/` 下，不在安装单元内。

## 4. 失败怎么办

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 找不到 `dist/startup-guide/` | 只下了一部分文件，不是完整克隆 | 重新克隆，或跑 `python tools/build_skill.py` |
| 技能没被触发 | description 未命中 | 显式调用 `$startup-guide`（Codex）或 `@startup-guide`（WorkBuddy） |
| 一上来给完整计划 | `SKILL.md` 被截断，闸门那段没加载 | 改走 B 形态，整份注入 |
| 提示缺 Python 或字体 | 只影响 `tools/` 出 pptx | 跳过；PPT 降级为可粘贴文案，主流程不受影响 |
| 断网时仍说「可以做」 | 降级规则没生效 | 确认 `references/offline-degradation.md` 在安装目录内 |
| 找不到 `AGENTS.md` 或 `docs/` | 正常，安装单元不含它们 | 那是维护者资料，运行时不需要 |
| 找不到 `tools/wheels/` | 正常，离线依赖不随技能分发 | 需要出 PPT 时自行 `pip install python-pptx` |
| 找不到 `dist/startup-guide.flat.txt`（B 形态） | 产物未生成或已过期 | 跑 `python tools/build_flat.py` 生成，`--check` 确认最新 |
| MCP 连不上或工具列表为空 | 路径没写成绝对路径，或 `mcp_server.py` 被单独拷走了 | 它要读同级的 `data/params.json`，必须留在 `dist/startup-guide/tools/` 里 |
| MCP 工具报「工具执行失败」 | 参数类型不对（金额传了字符串） | 先跑 `python3 tools/mcp_server.py --selftest` 排除服务端问题 |

## 5. 不要做什么

- 不要把仓库根目录整体拷进技能目录：会带上 `.venv/` 与 27 MB 的 `tools/wheels/`，而且目录名不等于 `name`。
- 不要手改 `dist/`：它每次构建都会被覆盖，改了等于没改。
- 不要为了「更完整」补写行业数据：这个技能只做结构推演，参数必须由用户实测。
