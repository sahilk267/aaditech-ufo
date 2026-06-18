---
name: Password reset token storage
description: Raw token is sent via email; SHA-256 hash is stored in DB for lookup.
---

## Rule
`POST /api/auth/forgot-password` generates a `secrets.token_urlsafe(32)` raw token, stores `hashlib.sha256(raw_token.encode()).hexdigest()` in `users.password_reset_token`, and emails the raw token in the reset URL.

`POST /api/auth/reset-password` hashes the incoming token before DB lookup — so DB compromise does not leak usable tokens.

**Why:** Standard security practice (same as bcrypt for passwords). A stolen DB row cannot be used to reset passwords.

**How to apply:** Never store raw reset tokens. Always hash before storing; hash again before comparing.
