# Cocos Creator 3.8 — Current Best Practices

**Last verified:** 2026-06-16

This file captures Cocos Creator practices that agents must prefer when working
on Cocos projects. It supplements, not replaces, official documentation.

## TypeScript Components

- Use TypeScript components that extend `Component` from the `cc` module.
- Declare editor-visible scripts with `_decorator`, `@ccclass`, and `@property`.
- Keep one primary component class per script file.
- Use explicit TypeScript types for serialized fields and public APIs.
- Do not put long-running work in `update()` unless the component truly needs
  per-frame behavior.

```ts
import { _decorator, Component, Animation } from 'cc';
const { ccclass, property } = _decorator;

@ccclass('PlayerController')
export class PlayerController extends Component {
  @property(Animation)
  public bodyAnim: Animation | null = null;

  start(): void {
    // Initialize runtime state after editor references are available.
  }
}
```

## Scene and Prefab Architecture

- Use prefabs for reusable entities and UI widgets; avoid copy-pasting scene
  node hierarchies.
- Keep scene roots small: global managers, cameras, root canvases, and feature
  containers should be separate nodes with clear responsibilities.
- Prefer editor-assigned `@property(Node)` references for stable dependencies.
  Avoid fragile string paths unless the target is local and documented.
- Do not mutate prefab assets at runtime. Instantiate prefabs and mutate the
  instance.
- Keep gameplay state in components/services, not in scene hierarchy naming.

## Asset Loading

- Prefer editor references for required local assets.
- Use Asset Bundles for DLC, remote content, large feature packs, and staged
  loading.
- Use `resources` only for small shared assets that truly need path-based
  runtime loading.
- Release dynamically loaded assets when no longer needed; define ownership
  rules for caches.
- Avoid synchronous-looking loading flows in gameplay-critical paths. Use
  loading screens or preloading for large bundles and scenes.

## UI

- Treat UI as prefabs and screens with lifecycle methods; do not mix large UI
  flows into gameplay components.
- Use layout components intentionally. Excessive nested layouts can become a
  performance issue on mobile.
- Keep touch targets and safe areas explicit for mobile builds.
- Avoid assuming hover. Many Cocos projects target mobile or playable ads.

## Performance

- Avoid per-frame allocations in `update()`.
- Pool frequently spawned nodes such as bullets, damage numbers, particles, and
  enemies.
- Disable inactive systems instead of checking flags every frame.
- Batch sprites where possible by sharing materials/textures and reducing state
  changes.
- Profile on target devices. Editor performance is not a reliable mobile proxy.

## Build and Platform

- Treat web, iOS, Android, mini-game, and native desktop builds as separate
  platform profiles.
- Keep platform SDK integrations isolated behind adapters.
- Do not introduce third-party native plugins without a rollback plan and build
  validation on every target platform.
- For playable ads, keep bundle size, startup time, and network independence as
  first-class constraints.
