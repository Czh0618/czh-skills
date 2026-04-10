# czh-skills

个人 Claude Code Skill 集合。

## Skills

| Skill | 说明 | 触发方式 |
|-------|------|---------|
| [req-reverse-eng](skills/req-reverse-eng/) | AI 需求反向工程 — 将模糊的产品需求转化为结构化的选择题清单、决策矩阵和策略模式代码骨架 | `/req-reverse-eng` |
| [api-blame-solver](skills/api-blame-solver/) | 前后端联调排错专家 | `/api-blame-solver` |

## 安装

仓库采用多-skill 标准布局，所有 skill 统一放在 `skills/` 目录下。

如果你是手动安装到 Claude Code，可将单个 skill 目录复制或软链到 `~/.claude/skills/`：

```bash
ln -s $(pwd)/skills/req-reverse-eng ~/.claude/skills/req-reverse-eng
```

如果你使用 `npx skills`，优先让安装器从仓库中发现并安装 `skills/` 下的 skill：

```bash
npx skills add <repo> --list -a claude-code
npx skills add <repo> --skill req-reverse-eng -a claude-code
```
