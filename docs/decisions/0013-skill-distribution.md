# 0013 分发形态：仓库不是安装单元

## 背景

技能要被 WorkBuddy、Codex、Claude Code 等宿主装上去，靠的是 Agent Skills 规范：一个目录，根下 `SKILL.md`，frontmatter 声明 `name` 与 `description`，宿主按「发现 → 激活 → 执行」三阶段渐进加载。

本仓库当前是一份开发中的项目：文档、样例、决策记录、版式引擎、离线依赖 wheel、本地 `.venv` 全在根目录。直接把它当技能目录，有四处过不去：

1. 规范要求 `name` 等于父目录名，且只含小写字母、数字、连字符。`name: startup-guide` 而目录叫 `StartUp-AI`，两条都不满足。
2. 发现阶段宿主只读 `name` 与 `description`，正文不加载。「断网怎么降级」写在正文深处，宿主在决定用不用这个技能时看不到。
3. 安装器的动作是复制整个目录，`.gitignore` 拦不住。根目录含 `.venv/`（800+ 个 py）与 `tools/wheels/`（27 MB）。
4. Codex 会把根目录 `AGENTS.md` 当项目上下文自动读入。本文件写的是「维护本仓库的规则」，agent 读完会去改文档，而不是帮用户做体检。

## 决定

1. **安装单元是 `dist/startup-guide/`**，由 `tools/build_skill.py` 从仓库生成并**入库**（生成物入库，是为了克隆即可安装、不必先装 Python，与 `tools/wheels/` 入库同一逻辑），不手改。目录名由脚本保证等于 `name`。
2. frontmatter 补齐 `license`、`compatibility`、`metadata.version`。`compatibility` 承载环境声明，是宿主在加载前唯一能看到的能力描述。
3. `AGENTS.md` 顶部加一行路由，把「维护」与「使用」分开；正文不得再要求使用者去读维护者文件。
4. 发布前跑 `tools/skill_check.py`，校验规范字段、体积上限与产物一致性，退出码 1 不可发布。

## 理由

- 改名仓库解决不了问题：规范约束的是**被安装后的目录名**，而仓库名还要承担项目识别、issue 链接、git remote 等职责。构建产物让两个名字各归其位。
- 产物一致性用哈希校验，而不是写进规则让人记住。规则会被遗忘，退出码不会。
- 产物入库而不是发 Release zip：克隆即可安装、不必先装 Python，和 wheels 入库同一个取舍。手改产物的风险由哈希校验兜住，依赖风险没有兜底。
- 把「维护者文件不进安装单元」写成硬约束，是因为它会以两种方式悄悄发生：有人直接把仓库拷进 skills 目录，或者有 agent 觉得「索引不全」而把 `docs/` 也打进产物。

## 后果

- 改 `SKILL.md`、`references/`、`data/`、`examples/`、`tools/*.py` 后必须重建并一起提交，否则 `skill_check.py` 报「产物已过期」。
- `SKILL.md` 的索引不再链接 `README.md`、`AGENTS.md`、`docs/`、`tools/README.md`；正文里「按 AGENTS.md 执行」改为「作为已安装技能运行时，本文件即全部规则」。
- 单文件形态（B）不生成机械拼接版：把 SKILL.md 与 references 首尾相接会产出 2000 行以上，且「见 `references/xxx.md`」这类指针在单文件里全部失效，等于制造第二套真相。B 形态的做法是手工带三份必需文件，见 `INSTALL.md`。
- MCP 形态（C）尚未实现。规则全在文档里，MCP 只该包确定性计算（资金带、H2 算式、源分级、渲染），包什么另行决策，不在此处提前承诺。
