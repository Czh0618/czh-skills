# Cocos Creator 3.8 — Physics Module

**Last verified:** 2026-06-16

## Use For

- 2D rigid bodies and colliders
- 3D rigid bodies and colliders
- Collision callbacks
- Simple character/environment interactions

## Practices

- Pick 2D or 3D physics intentionally per system; do not mix unless the design
  requires it.
- Keep collision layers/groups documented in technical preferences or a control
  manifest.
- Avoid changing mesh collider data after initialization without verifying engine
  support.
- Use trigger/collision callbacks for events; avoid polling broad physics state
  every frame.
- Profile physics on target devices, especially mobile.

## Known Constraints To Verify

- Built-in and external physics backends differ in collider support.
- Some sweep and advanced rigid body features may not exist in every backend.
- Dynamic rigid bodies have shape restrictions for terrain, plane, or non-convex
  mesh use cases.

## Review Checklist

- Are collision groups named and documented?
- Are physics materials and default settings pinned?
- Are expensive collider shapes avoided for dynamic actors?
- Are callbacks unsubscribed or scoped safely?
