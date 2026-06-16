# Cocos Creator 3.8 — UI Module

**Last verified:** 2026-06-16

## Use For

- Menus and HUDs
- Runtime screens
- Mobile-safe layout
- Text, localization, and responsive UI

## Practices

- Build repeated UI as prefabs with small controller components.
- Keep screen flow separate from individual widget behavior.
- Use layout components deliberately; nested layouts can be expensive.
- Support touch and safe areas by default for mobile targets.
- Account for localized text expansion before implementation is considered done.

## Review Checklist

- Is each screen/controller small enough to reason about?
- Are widgets reusable prefabs instead of copied node trees?
- Are text overflow and localization expansion handled?
- Are UI updates event-driven rather than per-frame polling?
