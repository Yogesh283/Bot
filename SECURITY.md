# Security notes for Phase 1

This version stores application accounts only. It does not collect or store MetaTrader passwords, terminal paths, or orders.

## Passwords and sessions

- User passwords are hashed with Argon2id (19 MiB memory, 2 iterations, 1 lane). The hash is stored in PostgreSQL. The plaintext password is not stored, logged, or returned by the API. The single lane avoids an Argon2 thread-pool hang observed on this Windows setup.
- Validation errors omit the rejected input so a short or invalid password is not copied into the response body.
- Access tokens are HS256 JWTs. They expire after 15 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Each access token is tied to one refresh-session row. Logout, password reset, and account disable revoke that row, so the access token stops working immediately.
- Refresh tokens are random, stored only as a SHA-256 hash, and sent in an `HttpOnly` cookie. JavaScript on the page cannot read the cookie.
- A refresh replaces the previous token. Presenting a token that was already rotated revokes every session for that user.
- Logout clears the cookie and revokes the presented refresh token.
- The website keeps the access token in memory only.

## Administrator access

Administrator rights are not accepted from the registration form. The only promotion path is the local command:

`python -m app.cli.bootstrap_admin --email NAME --confirm`

It updates one existing user whose email is already verified. Without `--confirm` it exits and changes nothing. The API schema has no bootstrap route.

An administrator can list users, read audit events, and disable or enable an account. Disabling an account revokes its sessions. An administrator cannot disable their own account through the API. API responses do not include password hashes.

## Email links

Local development prints verification and password-reset links in the API console. Those links contain single-use secrets. The reset link expires after 30 minutes. Verification expires after 24 hours. Do not run with `ENVIRONMENT=production` until a real email provider replaces the console sender. In production the console sender refuses to emit the link.

Reset and verification pages remove the token from the address bar after reading it. The token can still appear in the API console and in browser history if the link was opened directly.

## Cookies and the local network

`COOKIE_SECURE=false` is required for `http://localhost`. Set it to `true` only behind HTTPS. Production startup refuses a placeholder `JWT_SECRET`, a secret shorter than 32 characters, or `COOKIE_SECURE=false`.

PostgreSQL and Redis listen on `127.0.0.1` only. They have no authentication beyond the local Docker password. Do not publish those ports on a public interface. Replace the example database password and `JWT_SECRET` before anyone else can reach this computer.

Login attempts are counted in Redis. The limits are 10 failures per email and 30 failures per address in 15 minutes, and 5 registrations per address per hour. If Redis is down, the API still starts and those limits are skipped until Redis answers. The admin health report shows Redis as unavailable in that case.

## Audit log

Security events are stored in `audit_logs`: registration, verification, sign-in success and failure, logout, reset, refresh-token reuse, admin promotion, and account enable or disable. The detail text does not include passwords or tokens.

## What this phase does not protect yet

The MT5 password stays in the official terminal. The API stores only a hash of the agent token, and that token is shown once. Heartbeat and log text that contain the words password or token are replaced before they are saved. Live and contest accounts are rejected. A Demo order is queued only after the user types DEMO and the bot is running. HTTPS termination, backups, and a production email provider are still required before this is shared.
