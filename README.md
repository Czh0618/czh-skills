# czh-skills

个人 Claude Code Skill 集合。

## Skills

| Skill | 说明 | 触发方式 |
|-------|------|---------|
| [req-reverse-eng](skills/req-reverse-eng/) | AI 需求反向工程 — 将模糊的产品需求转化为结构化的选择题清单、决策矩阵和策略模式代码骨架 | `/req-reverse-eng` |
| [api-blame-solver](skills/api-blame-solver/) | 前后端联调排错专家 | `/api-blame-solver` |
| [java-refactor](skills/java-refactor/) | Java 代码重构教练 — 基于 Fowler《重构》与 Martin《代码整洁之道》的系统化诊断 + 排序后的可执行重构步骤；含 Feathers 遗留代码、Effective Java、DDD 战术补充章节 | `/java-refactor` |
| [ccgs-game-studio](skills/ccgs-game-studio/) | Claude Code Game Studios 插件安装入口；完整能力打包在 `plugins/ccgs-game-studio/` | `/ccgs-game-studio` |

## Plugins

| Plugin | 说明 | 兼容 |
|--------|------|------|
| [ccgs-game-studio](plugins/ccgs-game-studio/) | Claude Code Game Studios 插件包：73 个游戏开发 workflow skills、50 个 specialist agents、hooks、rules、templates、Unity/Unreal/Godot/Cocos engine references | Claude Code Plugin / Codex Plugin |

## 安装

仓库采用多-skill 标准布局，所有 skill 统一放在 `skills/` 目录下。

如果你是手动安装到 Claude Code，可将单个 skill 目录复制或软链到 `~/.claude/skills/`：

```bash
ln -s $(pwd)/skills/req-reverse-eng ~/.claude/skills/req-reverse-eng
```

如果你使用 `npx skills`，建议明确指定要安装的根级 skill：

```bash
npx skills add <repo> --skill req-reverse-eng -a claude-code
```

注意：本仓库同时包含插件包 `plugins/ccgs-game-studio/`。`npx skills`
会递归发现插件内部的 `plugins/ccgs-game-studio/skills/**/SKILL.md`，因此
`npx skills add <repo> --list` 会列出 CCGS 插件内的 73 个 workflow
skills。这些 workflow skills 依赖插件内的 agents、templates、hooks、rules
和 engine references，不建议作为分散 skill 单独安装。

## 安装 CCGS Game Studio Plugin

`ccgs-game-studio` 不是分散 skill，而是完整插件包。不要只复制其中某个 workflow skill；这些 skill 依赖 agents、templates、engine references 和 CCGS 支撑文档。

### Claude Code

在本仓库根目录运行：

```bash
claude plugin marketplace add .
claude plugin install ccgs-game-studio@czh-skills
```

单次会话测试：

```bash
claude --plugin-dir plugins/ccgs-game-studio
```

### Codex

在本仓库根目录运行：

```bash
codex plugin marketplace add .
codex plugin add ccgs-game-studio@czh-skills
```

### npx skills 入口

如果只想通过 `npx skills` 发现安装说明，可只安装 bootstrap skill：

```bash
npx skills add <repo> --skill ccgs-game-studio -a claude-code
```

完整 CCGS 能力请使用上面的 Claude Code Plugin 或 Codex Plugin 安装方式。
