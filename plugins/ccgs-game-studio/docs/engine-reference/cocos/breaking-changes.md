# Cocos Creator 3.8 — Breaking Change Watchlist

**Last verified:** 2026-06-16

This is a practical watchlist for agent review. It is not a full migration guide.
For real upgrades, consult the official Cocos Creator manual and release notes.

## Cocos Creator 2.x to 3.x

- **Module system changed**: modern projects import APIs from `cc` instead of
  relying on global `cc.*` access.
- **TypeScript-first workflow**: decorators, class metadata, and editor
  serialization are central to component authoring.
- **3D and rendering pipeline changed substantially**: 3.x uses a modernized
  runtime with expanded 3D, materials, lighting, and native backends.
- **Asset workflows changed**: asset UUIDs, bundles, and editor serialization
  must be preserved during refactors.

## 3.x Minor Version Upgrades

Before upgrading within 3.x:

- Check component serialization compatibility for renamed classes and fields.
- Check Asset Bundle settings and platform build templates.
- Re-test native plugin and JSB integrations.
- Re-test physics backend behavior and collision callbacks.
- Re-profile UI batching and draw calls on target devices.

## Risk Domains

| Domain | Risk | Required Check |
|---|---|---|
| Editor serialization | High | Open scenes/prefabs after class or property renames. |
| Asset loading | High | Validate bundle names, paths, dependency release, and preload order. |
| Native builds | High | Rebuild iOS/Android/native platforms after engine updates. |
| Physics | Medium | Confirm collider support and collision event behavior. |
| UI | Medium | Test layout, safe area, font rendering, and batching on devices. |
| Rendering | Medium | Validate materials, post-processing, and custom pipeline code. |
