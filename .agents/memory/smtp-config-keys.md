---
name: SMTP config keys in tasks.py
description: smtp_user, smtp_password, smtp_tls, smtp_ssl, webhook_secret must be explicitly forwarded from app.config.
---

## Rule
`server/tasks.py::dispatch_alert_notifications()` builds a `config` dict from `current_app.config`. The full set of keys that `NotificationService.dispatch_notifications()` expects includes:

- `smtp_user`, `smtp_password` (auth)
- `smtp_tls`, `smtp_ssl` (transport security)
- `webhook_secret` (HMAC signing)

These were missing before the 2026-06-18 session and were added to both `tasks.py` and `server/config.py` as `ALERT_SMTP_USER`, `ALERT_SMTP_PASSWORD`, `ALERT_SMTP_TLS`, `ALERT_SMTP_SSL`, `ALERT_WEBHOOK_SECRET`.

**Why:** `notification_service.py` was rewritten to properly call `server.send_message(msg)` with STARTTLS/SSL/auth, but `tasks.py` wasn't forwarding the new keys, so auth would always fail silently.

**How to apply:** When adding new config keys to `notification_service.py`, update the config dict in `tasks.py` in the same change.
