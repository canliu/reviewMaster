# Stage 7 — Production Operations: Deployment, Monitoring, Backups, Rate Limiting

> Runs **after** `stage_6_spapi.md`. Turns the working app into something operable in production. Nothing in this stage is user-visible — it's all infrastructure, observability, and safety.

## Goal

Make the app deployable to a real server with HTTPS, monitored for errors and performance, backed up automatically, and protected from abuse and accidents. After this stage, the app can serve real paying users without midnight emergencies.

## Scope

1. Production Docker Compose (separate from dev)
2. HTTPS via Caddy (reverse proxy + automatic Let's Encrypt)
3. Application secrets management
4. Database backups (automatic, off-server)
5. Error monitoring (Sentry)
6. Application logging (structured JSON to stdout, aggregated)
7. Health checks and uptime monitoring
8. Rate limiting (API-level, per user)
9. Security hardening (headers, CORS, CSP)
10. CI/CD via GitHub Actions
11. Operational runbooks

## Choice of host

Stay flexible. We document deployment for **a single Linux VPS** (e.g. Hetzner, DigitalOcean, Vultr) because:
- It's the cheapest path to production for an early-stage tool ($10–20/mo).
- Most Amazon-seller-tool users have <100 simultaneous sessions; a single 4-core VPS handles that easily.
- It's a stepping stone — moving to k8s or managed PaaS later is straightforward once revenue justifies it.

If you prefer Fly.io / Railway / Render, the same patterns apply — note alternative commands but center the prompt on a plain Linux VPS.

## 1. Production Docker Compose

Create `docker-compose.prod.yml` (separate from the dev compose):

Differences from dev:
- No bind mounts of source code.
- All images use specific tags, not `latest`.
- Frontend and backend run from pre-built images (built by CI, see section 10).
- Postgres has a named volume and an explicit `restart: unless-stopped`.
- Redis has AOF persistence enabled.
- A new `caddy` service handles HTTPS termination.
- No exposed ports except 80 and 443 (everything else is on the internal network).

Sample structure (do not paste env values, only the shape):

```yaml
services:
  caddy:
    image: caddy:2.7-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [backend, frontend]

  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    env_file: [.env.prod]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U postgres"], interval: 10s, timeout: 5s, retries: 5 }

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes: [redisdata:/data]

  backend:
    image: ghcr.io/${GH_USER}/reviewmaster-backend:${TAG}
    restart: unless-stopped
    env_file: [.env.prod]
    depends_on: { postgres: { condition: service_healthy }, redis: { condition: service_started } }

  worker:
    image: ghcr.io/${GH_USER}/reviewmaster-backend:${TAG}
    restart: unless-stopped
    command: ["rq", "worker", "default"]
    env_file: [.env.prod]
    depends_on: { postgres: { condition: service_healthy }, redis: { condition: service_started } }

  frontend:
    image: ghcr.io/${GH_USER}/reviewmaster-frontend:${TAG}
    restart: unless-stopped
    env_file: [.env.prod]

volumes:
  pgdata:
  redisdata:
  caddy_data:
  caddy_config:
```

`.env.prod` is **never committed** — it's created on the server during deployment.

## 2. HTTPS via Caddy

Create `Caddyfile`:

```
{$DOMAIN} {
    encode gzip zstd

    @api path /api/*
    handle @api {
        reverse_proxy backend:8000
    }

    handle {
        reverse_proxy frontend:3000
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
        # Note: 'unsafe-inline' on script-src and style-src is a temporary compromise
        # for Next.js inline scripts. Replace with nonce-based CSP once we have time
        # to wire next.js's middleware nonce injection. Tracked as a post-v1.0 task.
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://browser.sentry-cdn.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://*.sentry.io https://api.amazonaws.com https://*.amazon.com"
    }
}
```

Caddy auto-fetches Let's Encrypt certs. Set `DOMAIN` in `.env.prod`.

## 3. Secrets management

For MVP scale, secrets live in `.env.prod` on the server. We do not yet integrate Vault or AWS Secrets Manager — those are reasonable post-Stage-7 upgrades.

Required secrets:
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET` (regenerate for prod — never reuse the dev one)
- `ENCRYPTION_KEK` (regenerate)
- `SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`
- `DOMAIN`
- `CORS_ORIGINS`
- `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY`, `BACKUP_S3_ENDPOINT` (see backups)

Document each in `.env.prod.example` (committed) and `OPERATIONS.md`.

## 4. Database backups

A nightly backup of Postgres, encrypted, uploaded off-server.

**Scheduling approach**: use **host-level cron** running `docker compose exec` against the running postgres container, not in-container cron. Rationale: in-container cron requires keeping a daemon alive in a container that has no other purpose, and survives container restarts poorly. Host cron is simpler, more visible (`crontab -l` on the VPS), and easier to debug.

Add a script `scripts/backup.sh` in the repo (committed) and install it via the deploy script.

The script `scripts/backup.sh`:

1. Run `docker compose -f /opt/reviewmaster/docker-compose.prod.yml exec -T postgres pg_dump -U postgres --format=custom app > /tmp/backup-$(date +%F).dump`
2. Encrypt with `age` (https://github.com/FiloSottile/age) using a public key whose private key is stored offline (printed once on paper or in a password manager).
3. Compress with `zstd`.
4. Upload to S3-compatible storage (Backblaze B2, Cloudflare R2, Wasabi — anything cheap that supports the S3 API).
5. Rotate: keep last 7 daily, last 4 weekly (Sundays), last 12 monthly (1st of month).
6. Log success/failure to `/var/log/reviewmaster-backup.log` and to stdout (so host cron emails on failure).

Cron entry installed by `scripts/deploy.sh` on first deploy:
```
0 3 * * * /opt/reviewmaster/scripts/backup.sh >> /var/log/reviewmaster-backup.log 2>&1
```

Test the **restore** procedure as part of acceptance. A backup nobody has restored is not a backup.

### Restore drill (manual, documented)

```
# Pull the latest backup
aws s3 cp s3://$BUCKET/$(date +%F).sql.age.zst /tmp/dump.age.zst --endpoint $ENDPOINT

# Decrypt
age -d -i ~/.ssh/backup-key /tmp/dump.age.zst > /tmp/dump.sql

# Restore (test database first!)
pg_restore --create -d postgres /tmp/dump.sql
```

Document this in `RESTORE.md` in the repo root.

## 5. Error monitoring with Sentry

### Backend integration

`pip install sentry-sdk[fastapi]`. In `app/main.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if settings.SENTRY_DSN_BACKEND:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN_BACKEND,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=settings.ENV,
    )
```

In RQ workers, set up Sentry similarly.

### Frontend integration

`npm install @sentry/nextjs`. Run the wizard or configure manually. Disable Replay for now (privacy).

### What to exclude

Filter from telemetry:
- `password`, `password_hash`, `refresh_token`, `lwa_client_secret`, `dek_encrypted`, `refresh_token_ciphertext`, `lwa_client_secret_ciphertext`
- Anything in `raw_json` of orders (we don't know what's in there, default conservative)
- Buyer emails (PII)

Add a `before_send` hook that scrubs these fields from any captured event.

### Alerts

In Sentry, configure alerts for:
- New issue affecting more than 1 user
- Issue spike (>50 events/hour for the same event)
- Performance regression: P95 of `POST /api/uploads` >120s

## 6. Application logging

### Backend

Use `structlog` for JSON-formatted logs to stdout. Docker collects them; you can ship them to Loki, Datadog, or just `journalctl` for low-budget setups.

Standard fields on every log line:
- `event` — short snake_case message
- `level`
- `timestamp` — ISO 8601 UTC
- `user_id` — if request is authenticated
- `request_id` — generated by middleware, propagated via `X-Request-ID` header
- `route`
- `latency_ms` — for request logs

A middleware in `app/main.py` logs every request: method, route, status, latency, user_id, request_id.

Sensitive fields never get logged: passwords, tokens, ciphertexts.

### Frontend

Server-side logs (Next.js): structured JSON to stdout. Client-side errors flow into Sentry — no console-log spam in production.

## 7. Health checks and uptime monitoring

### Health endpoints

- `GET /health` — liveness; returns 200 if process is up.
- `GET /health/ready` — readiness; checks Postgres + Redis connectivity; returns 200 only if all dependencies respond.

Caddy hits `/health/ready` on backend startup and refuses traffic until it returns 200.

### External uptime checks

Set up an account at UptimeRobot, BetterStack, or similar (free tier sufficient):
- HTTPS check on `https://{DOMAIN}` every 1 minute
- HTTPS check on `https://{DOMAIN}/health` every 1 minute
- HTTPS check on `https://{DOMAIN}/health/ready` every 5 minutes

Alert via email + (optional) Slack webhook.

## 8. API rate limiting

Use `slowapi` (FastAPI port of flask-limiter) backed by Redis.

Default limits:

| Endpoint pattern | Limit |
|---|---|
| `POST /api/auth/login` | 5/minute per IP |
| `POST /api/auth/register` | 3/hour per IP |
| `POST /api/uploads` | 10/hour per user |
| `POST /api/review-requests` | 100/minute per user (covers batch operations) |
| `POST /api/sp-api/test-connection` | 10/minute per user |
| All other authenticated endpoints | 600/minute per user |
| All other unauthenticated endpoints | 60/minute per IP |

Return 429 with a `Retry-After` header on limit. The frontend shows a friendly toast: "Slow down — try again in N seconds."

## 9. Security hardening

- **CORS:** allow only `https://{DOMAIN}` in `CORS_ORIGINS`. No wildcards in production.
- **Cookies:** if/when we move tokens from localStorage to cookies, set `Secure; HttpOnly; SameSite=Lax`. Until then, document the localStorage tradeoff in `SECURITY.md`.
- **CSP:** as defined in the Caddyfile above. Verify Sentry frontend integration doesn't violate it.
- **Password hashing:** confirm bcrypt is at cost factor ≥12.
- **JWT rotation:** confirm `JWT_SECRET` and `ENCRYPTION_KEK` are unique to production.
- **Dependency scanning:** add `pip-audit` and `npm audit` to the CI pipeline; fail the build on critical CVEs.
- **No public Postgres:** the `postgres` service is on the internal network only — no host port mapping in `docker-compose.prod.yml`.
- **SSH hardening on the host:** key-only auth, disable root login, fail2ban. Document in `SERVER_SETUP.md`.

## 10. CI/CD via GitHub Actions

Three workflows in `.github/workflows/`:

### `test.yml`

Triggered on every push to any branch and on PRs:
- Backend: `pytest`, `ruff check`, `black --check`, `mypy` (loose mode).
- Frontend: `npm run lint`, `npm run test`, `npm run build` (just to catch type errors).
- `pip-audit` and `npm audit` (fail only on critical).

### `release.yml`

Triggered on git tags matching `v*`:
- Build backend and frontend Docker images.
- Push to GHCR as `ghcr.io/{owner}/reviewmaster-{backend,frontend}:{tag}` and also `:latest`.

### `deploy.yml`

Triggered manually (workflow_dispatch) with a tag input:
- SSH into the prod VPS using a deploy key.
- Run `scripts/deploy.sh ${TAG}`.

`scripts/deploy.sh`:
1. `docker compose -f docker-compose.prod.yml pull`
2. Run new backend migrations: `docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head`
3. `docker compose -f docker-compose.prod.yml up -d`
4. Wait for `/health/ready` to return 200; bail if it doesn't within 60s and roll back.

Document rollback: `git checkout <prev-tag> && bash scripts/deploy.sh <prev-tag>`.

## 11. Operational runbooks

This stage produces these documentation files at the repo root. Each is required and checked by the verify script:

- **`OPERATIONS.md`** — first-time setup, deploy, rollback, secret rotation, scaling, onboarding new operators
- **`RESTORE.md`** — backup restoration procedure
- **`SECURITY.md`** — security posture summary (cookies/localStorage tradeoff, CSP rationale, threat model assumptions)
- **`SERVER_SETUP.md`** — host hardening notes (SSH, firewall, fail2ban)
- **`INCIDENTS.md`** — incident log template

### `OPERATIONS.md` contents

Add these sections (each one paragraph + commands):

- **First-time server setup** — install Docker, create user, configure firewall, set up SSH keys
- **Deploying a new version** — link to deploy workflow
- **Rolling back** — link to commands above
- **Restoring from backup** — link to `RESTORE.md`
- **Rotating JWT_SECRET** — invalidates all sessions, document the user impact
- **Rotating ENCRYPTION_KEK** — re-wraps every DEK, requires downtime; script `scripts/rotate_kek.py`
- **Scaling up** — bigger VPS, separate Postgres, add worker replicas
- **Onboarding a new operator** — what creds they need, what they don't

Add `INCIDENTS.md` template:
```
# Incident: <one-line summary>
Date: 2026-XX-XX
Duration: ...
Impact: ...

## Timeline (UTC)
- HH:MM — ...

## Root cause
...

## Resolution
...

## Action items
- [ ] ...
```

## Tests

Most of this stage isn't unit-testable in the traditional sense. Instead:

- **Smoke test the CI pipeline**: open a draft PR and verify all checks run.
- **Restore drill** (manual): perform the full backup → restore cycle on a staging server before declaring the stage done.
- **Load test**: use `locust` or `k6` to hammer the production stack with 50 simulated concurrent sessions for 10 minutes. Watch for memory leaks, slow queries, dropped requests.
- **Failure injection**: kill `redis`, then `postgres`, then `backend` one at a time and verify the stack recovers within 30 seconds.
- **Rate-limit test**: a script that fires 100 logins from one IP in a minute, confirms 429s and `Retry-After` headers.

## Acceptance checks

1. `git tag v1.0` → CI builds images and pushes to GHCR.
2. Manually trigger deploy.yml → app comes up on the VPS at `https://{DOMAIN}` with a valid Let's Encrypt cert.
3. Visit the app, walk through register → upload → repeat orders → mark requested → SP-API connect. Everything works as in dev.
4. Trigger an error (temporarily add `1/0` to a route) → it appears in Sentry within 30 seconds with the right user_id and request_id.
5. `docker compose -f docker-compose.prod.yml logs backend | jq` shows structured JSON logs.
6. Wait 24 hours; verify a backup file appeared in the S3 bucket; decrypt and restore it to a scratch Postgres instance.
7. Hammer `POST /api/auth/login` from the same IP 10 times in 30 seconds → the 6th–10th return 429 with `Retry-After`.
8. Run `nmap` on the public IP — only ports 22, 80, 443 are open.
9. Stop the postgres container; the backend's `/health/ready` returns 503; Caddy returns a 503 page to users; the issue surfaces in Sentry and UptimeRobot within 1 minute.
10. UptimeRobot has been pinging the public domain for at least an hour without an outage.

## Out of scope

- Multi-region / HA Postgres.
- Kubernetes.
- Auto-scaling.
- DDoS protection at the network layer (Caddy + rate limiting is enough for our scale; add Cloudflare in front if needed).
- Full HIPAA / GDPR / SOC2 compliance work — covered separately if/when we go to enterprise customers.
- Real-time observability dashboards (Grafana, Datadog) — Sentry + structured logs cover us for now.
- Penetration test — book one once we have paying users.

## Closing the loop

After Stage 7 acceptance, tag `v1.0` and ship.

Post-launch priorities (NOT in this prompt set, but worth a paragraph in `ROADMAP.md`):
- Team / multi-user accounts (sub-sellers, agencies)
- Listings API for asking review at fulfillment time
- Slack / email digests of weekly review opportunities
- AI suggestions for which buyers are most likely to leave 5-star reviews
- White-label / reseller version
