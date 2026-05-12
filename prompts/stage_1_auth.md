# Stage 1 — Authentication

> Builds on Stage 0. Adds user registration, login, token refresh, and a protected dashboard shell on the frontend.

## Goal

A user can register, log in, stay logged in across refreshes, and visit a protected page. No real features yet — just the auth shell. All later stages will assume `get_current_user` is available as a FastAPI dependency.

## Backend endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | none | Create a new user |
| POST | `/api/auth/login` | none | Exchange email+password for tokens |
| POST | `/api/auth/refresh` | refresh token | Exchange refresh token for a new access token |
| GET | `/api/auth/me` | access token | Return the current user |
| POST | `/api/auth/logout` | access token | No-op (stateless JWT) but returns 204 for symmetry |

### Rules

- Passwords hashed with `bcrypt` (use `passlib`).
- Password policy: minimum 8 characters, at least one letter and one digit. Reject with a clear validation message.
- Email lowercased on registration and login.
- Duplicate email → HTTP 409 `EMAIL_EXISTS`.
- Wrong password → HTTP 401 `INVALID_CREDENTIALS` (same message as "user not found" — do not leak existence).
- Access token TTL 60 minutes; refresh token TTL 30 days. Both signed with `JWT_SECRET` (HS256).
- The JWT payload carries `sub` (user id as string), `type` (`'access'` or `'refresh'`), `iat`, `exp`.
- On register, also create a matching empty row in `user_settings` for that user, in the same transaction.

### The `get_current_user` dependency

This is the most important deliverable of Stage 1. Every later stage will reuse it.

- Reads the `Authorization: Bearer <token>` header.
- Validates the JWT and confirms `type == 'access'`.
- Loads the user from the database.
- Raises 401 on any failure with body `{"detail": "...", "code": "..."}`.

## Frontend pages

| Path | Auth | Purpose |
|---|---|---|
| `/login` | guest | Email + password form |
| `/register` | guest | Email + password + confirm-password form |
| `/dashboard` | required | Empty placeholder with the user's email shown and a Logout button |

### Rules

- Forms use `react-hook-form` + `zod`. Show field-level validation errors.
- Tokens stored in `localStorage` (acceptable for MVP — note this in a comment).
- A wrapper in `frontend/lib/auth.ts` exposes `login`, `logout`, `register`, `getMe`, `isAuthenticated`.
- `frontend/lib/api.ts` axios instance:
  - Reads access token from localStorage and adds `Authorization` header on every request.
  - On 401 response, attempts a single refresh call. On refresh failure, clears tokens and redirects to `/login`.
- A Next.js middleware (or layout-level guard) protects `/dashboard/*` — unauthenticated users are redirected to `/login`.
- Logged-in users hitting `/login` or `/register` are redirected to `/dashboard`.

## Tests (backend)

Create `backend/tests/test_auth.py` covering:
- Successful registration creates both `users` and `user_settings` rows.
- Duplicate email registration returns 409.
- Weak password (e.g. `"abcdefgh"` — no digit) returns 422.
- Login with correct credentials returns both tokens.
- Login with wrong password returns 401.
- `GET /api/auth/me` with a valid token returns the user.
- `GET /api/auth/me` with an expired token returns 401.
- `POST /api/auth/refresh` with a refresh token returns a fresh access token.
- `POST /api/auth/refresh` with an access token (wrong type) returns 401.

## Acceptance checks

1. Manual flow: register a new user → automatically logged in → see `/dashboard` with my email shown.
2. Log out → redirected to `/login`.
3. Log back in → `/dashboard` again.
4. Open browser devtools, delete the access token from localStorage, refresh the page → should still be logged in (refresh token kicks in). Then delete both tokens → redirected to `/login`.
5. `docker compose exec backend pytest tests/test_auth.py` is fully green.
6. Inspect the database: every `users` row has exactly one matching `user_settings` row.

## Out of scope

- Password reset.
- Email verification.
- OAuth / social login.
- Account deletion.
- Team or multi-seat features.
