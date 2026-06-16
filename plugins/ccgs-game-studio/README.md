# CCGS Game Studio Plugin

This plugin packages Claude Code Game Studios as a reusable plugin bundle.

It includes:

- 73 game-development workflow skills in `skills/`
- 50 specialist agents in `agents/`
- Original Claude Code project assets under `.claude/`
- Unity, Unreal, Godot, and Cocos Creator engine references under `docs/engine-reference/`
- Skill testing specs under `CCGS Skill Testing Framework/`
- Upstream documentation copied into this plugin package

## Claude Code Install

From this repository root:

```bash
claude plugin marketplace add .
claude plugin install ccgs-game-studio@czh-skills
```

For one-session testing without marketplace installation:

```bash
claude --plugin-dir plugins/ccgs-game-studio
```

## Codex Install

Add the repo marketplace, then install the plugin:

```bash
codex plugin marketplace add .
codex plugin add ccgs-game-studio@czh-skills
```

## Runtime Notes

The original CCGS skills were authored for a full Claude Code template project.
Many instructions reference project paths such as `.claude/docs/`,
`docs/engine-reference/`, `design/`, `production/`, `src/`, and `tests/`.

This plugin preserves the support files inside the plugin package. When a skill
needs a CCGS support file that is missing from the target project, use the
bundled copy from the plugin root. In Claude Code, plugin resources are available
under `${CLAUDE_PLUGIN_ROOT}`. In other hosts, resolve bundled resources relative
to this plugin directory.

Project artifacts still belong in the target repository. Do not write generated
game design docs, production plans, source files, or tests back into the plugin
package unless explicitly maintaining the plugin itself.

## npx skills Compatibility

This package intentionally keeps workflow skills under `skills/` because that is
the directory both Claude Code and Codex plugin discovery expect.

If this plugin is stored inside a repository that is also used as an `npx skills`
source, `npx skills add <repo> --list` may recursively list the 73 bundled CCGS
workflow skills. Treat those entries as plugin-internal workflow skills. Install
`ccgs-game-studio` through the plugin marketplace entries instead of installing
the workflow skills one by one.

## Upstream

Original project: https://github.com/Donchitos/Claude-Code-Game-Studios
