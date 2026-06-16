# Cocos Creator 3.8 — Networking Module

**Last verified:** 2026-06-16

## Use For

- HTTP APIs
- WebSocket realtime features
- Remote configuration
- Asset/CDN integration

## Practices

- Keep network code outside gameplay components; use services/adapters.
- Define request/response DTOs with TypeScript interfaces.
- Add timeout, retry, and cancellation behavior explicitly.
- Do not trust client-side state for economy, purchases, or competitive outcomes.
- Isolate platform SDKs and mini-game APIs behind adapters.

## Review Checklist

- Are API contracts typed and validated?
- Are failures surfaced to UI without blocking the game loop?
- Are secrets absent from client code?
- Are live-ops configs cached and versioned?
