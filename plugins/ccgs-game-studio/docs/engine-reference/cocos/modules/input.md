# Cocos Creator 3.8 — Input Module

**Last verified:** 2026-06-16

## Use For

- Touch input
- Mouse and keyboard input
- Gamepad or platform-specific controls
- UI interaction routing

## Practices

- Design touch first for mobile-first or playable-ad projects.
- Route raw input into intent methods such as `move`, `jump`, `select`, or
  `cancel`.
- Keep input registration and cleanup in component lifecycle methods.
- Avoid hover-only UI interactions.
- For cross-platform games, isolate input mapping behind a small adapter.

## Review Checklist

- Are listeners cleaned up when the component is disabled or destroyed?
- Does UI input avoid conflicting with gameplay input?
- Are touch target sizes and safe areas specified?
- Are platform-specific assumptions documented in technical preferences?
