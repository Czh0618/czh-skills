# Cocos Creator 3.8 — Animation Module

**Last verified:** 2026-06-16

## Use For

- 2D/3D character animation
- UI motion
- Skeletal animation
- Tweened motion and small gameplay effects

## Practices

- Use `Animation` or skeletal animation components for authored clips.
- Use `tween` for simple procedural transitions and UI/gameplay polish.
- Keep animation state changes explicit; avoid scattering `play()` calls across
  unrelated components.
- Route gameplay decisions through state machines; animation should reflect state,
  not own game rules.
- Cache component references in `start()` or editor properties.

## Review Checklist

- Are clips and animation components assigned through the editor where possible?
- Does gameplay state remain outside animation callbacks?
- Are tweens stopped or scoped when nodes are disabled/destroyed?
- Are animation names centralized or documented to avoid string drift?
