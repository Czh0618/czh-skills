# Cocos Creator 3.8 — Audio Module

**Last verified:** 2026-06-16

## Use For

- Music playback
- SFX playback
- UI feedback sounds
- Platform-aware audio policies

## Practices

- Centralize music and global SFX routing in an audio service component.
- Keep gameplay components responsible for intent, not mixer policy.
- Avoid loading large audio clips during gameplay-critical moments.
- Respect mobile autoplay, focus, and interruption behavior.
- Pool or reuse frequently played short SFX when the project shows overhead.

## Review Checklist

- Is there a clear owner for music, SFX, and volume settings?
- Are audio assets preloaded or referenced explicitly?
- Are platform interruptions handled for mobile builds?
- Are repeated UI sounds rate-limited where necessary?
