# Cocos Creator 3.8 — Deprecated and Risky Patterns

**Last verified:** 2026-06-16

Quick lookup table for patterns that agents should avoid or verify before use.

| Avoid / Verify | Prefer | Notes |
|---|---|---|
| Cocos Creator 2.x global `cc.*` scripting style | ES module imports from `cc` | Cocos Creator 3.x TypeScript projects import engine APIs from `cc`. |
| JavaScript-only components for new code | TypeScript components with explicit types | CCGS Cocos support assumes TypeScript by default. |
| Runtime `find()` / long node path lookups for core dependencies | `@property` editor references or local `getComponent()` | String paths are fragile under prefab/scene refactors. |
| Loading all gameplay assets from `resources` | Editor references, Asset Bundles, or scoped resources usage | `resources` is convenient but can hide ownership and memory costs. |
| Creating/destroying high-frequency nodes every frame | Node pooling | Common for bullets, effects, enemy waves, and UI flyouts. |
| Per-frame `update()` polling for event-driven state | Events, input callbacks, timers, tweens, or state machines | Reduces CPU and allocation pressure. |
| Mixing UI flow, gameplay logic, and asset loading in one component | Separate screen controllers, gameplay components, and loading services | Prevents large, fragile components. |
| Editing generated/native build output as source of truth | Project scripts, build templates, documented native plugins | Generated output may be overwritten by Creator. |
| Assuming editor behavior matches device behavior | Build and profile on target devices | Especially important for mobile, mini-game platforms, and Web. |

## Migration Notes

When reviewing older Cocos code, check whether it was authored for Cocos Creator
2.x or 3.x. Do not mechanically rewrite APIs without testing editor
serialization, prefab references, and build output.
