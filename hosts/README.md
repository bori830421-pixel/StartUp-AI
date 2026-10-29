# 分宿主接入

## 本文导航

- [先判断宿主有哪种能力](#先判断宿主有哪种能力)
- [三种形态对照](#三种形态对照)
- [读哪一页](#读哪一页)

## 先判断宿主有哪种能力

不知道自己在什么宿主上时，按顺序问三个问题，第一个答「是」就停：

1. **能读写本地文件吗？** 给一段路径，它能不能把文件内容读出来 → 用 [directory.md](./directory.md)（A 形态）
2. **能启动子进程并说 MCP 吗？** 比如能配置 `mcpServers` 或「外部工具」 → 用 [mcp.md](./mcp.md)（C 形态）
3. **以上都不能，只能接收一段文本？** → 用 [plain-prompt.md](./plain-prompt.md)（B 形态）

三者可以叠加：目录技能 + MCP 一起装没有冲突，MCP 只是把确定性计算从推演变成调用。

## 三种形态对照

| | A 目录技能 | B 单文件 | C MCP |
| --- | --- | --- | --- |
| 落点 | `dist/startup-guide/` | `dist/startup-guide.flat.txt` | `tools/mcp_server.py` |
| 按需加载 | 有，能读 references 与 examples | 无，只有收录进去的 5 份 | 有，resources 全量可读 |
| 判断能力 | 完整 | 完整但细节薄 | 完整 |
| 典型宿主 | WorkBuddy、Claude Code、Codex、Cursor | 网页版对话、单轮 API | 只支持 MCP 的客户端 |
| 相对强度 | 最强，首选 | 最弱，够用 | 强，但多一层配置 |

**能装 A 就不要用 B。** B 没有按需加载，`SKILL.md` 里写「见 `references/xxx.md`」的地方，模型只能靠收录进去的那五份推断。

## 读哪一页

- [directory.md](./directory.md)：目录技能的落点、目录名约束、更新方式
- [mcp.md](./mcp.md)：MCP 配置写法、五个工具的语义、为什么工具里没有判断
- [plain-prompt.md](./plain-prompt.md)：单文件注入、体积代价、可以裁什么不能裁什么

三页都只写与这个技能相关的那部分，宿主自身怎么装插件以宿主文档为准。
