# Real-Time Transport Decision

Updated: April 2, 2026

## Purpose

Define the recommended transport strategy for live operator experiences such as alerts, logs, and operations timeline updates.

## Recommendation

Use a phased strategy:

1. Default to polling for standard admin screens.
2. Add selective Server-Sent Events (SSE) for alert, log, and operations timeline feeds.
3. Defer WebSocket until a clear bidirectional live-control use case exists.

## Why

- Current product behavior is mostly request/response plus periodic refresh.
- Most operator views are read-heavy, not interactive-control channels.
- SSE is simpler than WebSocket for one-way live streams and fits alerts/logs/timeline well.
- WebSocket adds more state, scaling, auth, and reconnect complexity than the current product needs.

## Recommended Scope

### Polling remains fine for

- tenant settings
- releases
- backup operations
- admin configuration pages

### SSE should be introduced for

- live alert feed
- log/event feed
- merged operations timeline
- optional supportability feed for queue/backup status

### WebSocket remains deferred for

- remote shell/interactive control
- collaborative operator workflows
- bidirectional live command/control channels

## Delivery Order

1. Keep current polling for existing SPA pages.
2. Add SSE endpoint(s) for `alerts`, `logs`, and `operations/timeline`.
3. Update frontend pages to consume SSE only where freshness materially helps operators.

## Status

This decision is now partially implemented.

Implemented on April 2, 2026:

- `GET /api/alerts/stream` for live-ish alert delivery/incident snapshots
- `GET /api/operations/timeline/stream` for merged operator timeline snapshots
- frontend SSE consumers on Alerts and Audit pages
- gateway proxy buffering disabled for the current SSE routes

Still deferred:

- logs SSE feed
- supportability feed
- any WebSocket-based bidirectional control path
