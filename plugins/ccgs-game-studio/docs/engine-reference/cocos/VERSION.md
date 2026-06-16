# Cocos Creator — Version Reference

| Field | Value |
|-------|-------|
| **Engine Version** | Cocos Creator 3.8.x |
| **Reference Baseline** | Cocos Creator 3.8 Manual, Cocos Engine 3.8.7 API docs |
| **Project Pinned** | 2026-06-16 |
| **Last Docs Verified** | 2026-06-16 |
| **LLM Knowledge Cutoff** | May 2025 |
| **Risk Level** | MEDIUM — Cocos Creator 3.8 is close to the cutoff and project APIs are version-sensitive |

## Knowledge Gap Warning

Cocos Creator projects depend on editor serialization, TypeScript decorators,
asset UUIDs, native build settings, and platform-specific build templates. These
change more often than high-level gameplay patterns. Before suggesting code or
project settings, cross-check this directory and the official Cocos Creator 3.8
manual.

## Reference Sources

- Cocos Creator 3.8 Manual: https://docs.cocos.com/creator/3.8/manual/en/
- Cocos Creator 3.8 Manual (Chinese): https://docs.cocos.com/creator/3.8/manual/zh/
- Cocos Engine API docs/source: https://github.com/cocos/cocos-engine
- Cocos example projects: https://github.com/cocos/cocos-example-projects

## Engine Scope

This reference covers Cocos Creator 3.x projects that use:

- TypeScript game scripts imported from the `cc` module
- Component-based scene architecture with `Node` and `Component`
- Prefabs, scenes, asset bundles, resources, and editor-assigned properties
- 2D UI/gameplay, 3D rendering, animation, tweening, audio, physics, and native/web builds

## Specialist Routing

Use `cocos-specialist` for Cocos Creator architecture, TypeScript component
patterns, asset loading, prefab/scene organization, rendering, UI, physics,
platform build decisions, and code review.

If a project adds custom native engine code or JSB bindings, involve
`engine-programmer` and `devops-engineer` alongside `cocos-specialist`.
