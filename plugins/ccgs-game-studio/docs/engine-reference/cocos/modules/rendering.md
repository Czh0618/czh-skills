# Cocos Creator 3.8 — Rendering Module

**Last verified:** 2026-06-16

## Use For

- Sprite batching
- Materials and effects
- 2D/3D cameras
- Lighting and post-processing
- Custom render pipeline decisions

## Practices

- Share materials and textures when possible to preserve batching.
- Treat custom materials/effects as technical assets with owners and tests.
- Keep camera setup explicit per scene.
- Avoid overdraw-heavy UI and particle effects on mobile.
- Use real device profiling for draw calls, fill rate, and shader cost.

## Review Checklist

- Are materials reused instead of duplicated per instance?
- Are particles and post-processing within the performance budget?
- Are 2D and 3D render layers/cameras documented?
- Are custom effects compatible with target platforms?
