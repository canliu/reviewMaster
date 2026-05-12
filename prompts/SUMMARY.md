# Project Summary — Amazon Repeat Buyer Review Tool

## What we are building

A multi-tenant SaaS web application that helps Amazon sellers:

1. Upload their Amazon order export files (.xlsx).
2. Automatically identify **repeat buyers** — customers who purchased the same product more than once.
3. Request product reviews from those repeat buyers through three different methods.
4. Track which orders have already been requested so no one gets asked twice.

## Why repeat buyers

Repeat buyers are the highest-converting audience for review requests. They have already proven they like the product. Asking them for a review yields far better response rates and higher star ratings than asking first-time buyers.

## Core concept: Repeat Orders

A **repeat order** is defined as follows:

> When a single buyer purchases the same product **2 or more times**, **every** order that buyer placed for that product is classified as a repeat order — including the very first one.

The "same product" comparison is configurable per user:
- **ASIN** (strict, default) — exact variant match
- **SPU / parent product** (medium) — variants of the same product family count as the same
- **Product name** (loose) — fuzzy grouping by product name

A buyer is identified by a `buyer_key`:
- Primary: the anonymous Amazon email (e.g., `xxxxx@marketplace.amazon.com`)
- Fallback (when email is missing): hash of `shop_site + ship_country + ship_state + ship_city`

Repeat-buyer statistics are also scoped by `shop_site` — the same email seen across different marketplaces is treated as a different buyer.

## Three ways to request a review

For each repeat order, the seller can choose one of three methods:

1. **Manual mark** — seller goes to Amazon Seller Central themselves and clicks "Request a Review", then comes back and marks the order as done.
2. **Link redirect** — the app generates a deep link to the order detail page in Seller Central, opens it in a new tab, and after the seller confirms they clicked the Request-a-Review button, marks the order as done.
3. **SP-API automatic** — the app calls Amazon Selling Partner API (Solicitations endpoint) directly to send the request. Requires the seller to configure SP-API credentials.

Every order can only be requested **once**. The database enforces this. The UI must clearly distinguish requested vs not-requested orders and disable the action buttons for already-requested orders.

## Timing window

Amazon policy: a review can be requested between **5 and 30 days after the order is delivered**.

The order export does **not** contain an "actual delivery date" column. We use `estimated_delivery_utc` plus a one-day safety buffer as our approximation. The acceptable window in the app is therefore:

> `now - estimated_delivery_utc` is between 5 days and 30 days

Orders outside the window have their request buttons disabled in the UI, and the backend rejects requests outside the window with HTTP 400.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 + RQ (Redis Queue) |
| Migrations | Alembic |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Data fetching | TanStack Query |
| Tables | TanStack Table v8 |
| Forms | react-hook-form + zod |
| Excel parsing | pandas + openpyxl |
| Auth | JWT (access + refresh tokens) |
| Encryption | Envelope encryption with Fernet (cryptography library); KMS-ready architecture |
| SP-API client | python-amazon-sp-api |
| Deployment | Docker Compose (postgres, redis, backend, frontend, worker) |

## Multi-tenancy

Every business table carries a `user_id` foreign key. Every query is forcibly scoped by the current user from the JWT. There is no admin-level cross-tenant access in MVP.

A single user can manage multiple shop_sites (e.g., `p3:US`, `p3:CA`, `p3:UK`). The active shop_site is selected via a global shop switcher in the header and persists in the user's settings.

## Data model overview

Eight tables, listed below. Detailed columns and constraints live in `stage_0_skeleton.md`.

1. **users** — id, email, password_hash, timezone, created_at
2. **user_settings** — user_id, active_shop_site, repeat_grain (asin/spu/product_name), excluded_order_types (jsonb array), created_at, updated_at
3. **orders** — full order data, one row per Amazon order, with `buyer_key` derived at insert time. UNIQUE(user_id, order_id). The raw spreadsheet row is stored in `raw_json` for forward compatibility.
4. **buyer_product_stats** — aggregated stats per (user_id, shop_site, buyer_key, grain, group_value). Tracks order_count, first/last order time, total_amount. Refreshed after each upload.
5. **review_requests** — one row per requested order. UNIQUE(user_id, order_uuid) so an order can only be requested once. Stores method, status, requested_at, api_response, and (added in Stage 6) error_code. Correction notes live in a separate table.
6. **review_request_notes** — append-only correction and audit log, attached to the **order** (not to the review_request). This way the audit log survives the "failed retry" delete-and-reinsert pattern documented in Stage 5. Includes a `kind` field for user vs system-generated notes.
7. **upload_batches** — audit trail of all uploads. Tracks counts of new/updated/duplicate/error rows and a progress field for crash recovery.
8. **seller_credentials** — encrypted SP-API credentials, one row per user. Uses envelope encryption. Created in Stage 0, populated only in Stage 6.

## Data privacy and retention

The orders table contains buyer PII (anonymous Amazon emails plus ship-to city/state/country). To minimize exposure:
- Buyer emails are never logged.
- Buyer emails are scrubbed from Sentry telemetry (Stage 7).
- `raw_json` is treated as opaque and never logged.
- Account deletion (post-v1.0) cascades to all business tables via the `ON DELETE CASCADE` foreign keys on `user_id`.
- We retain order data indefinitely while the user account exists — sellers need historical data to identify repeat buyers across years.

Full GDPR data-export and right-to-erasure flows are post-v1.0.

## Pipeline overview

```
[Excel file]
      │
      ▼
[POST /api/uploads] ──► creates upload_batch (processing)
      │
      └─► [RQ worker]
              │
              1. parse rows with pandas
              2. validate required columns
              3. compute buyer_key per row
              4. upsert into orders (ON CONFLICT user_id+order_id)
              5. recompute buyer_product_stats for affected groups
              6. mark batch as completed with counts
              │
              ▼
[Repeat order list] ──► query orders JOIN buyer_product_stats
                          WHERE order_count >= 2
                          LEFT JOIN review_requests
                          filter by shop_site, asin, has_review, in_window
                          paginate, return
      │
      ▼
[Seller picks orders, picks method]
      │
      ├── manual: insert review_request (status=sent)
      ├── link:   insert review_request (status=pending), return URL, confirm later
      └── api:    insert review_request (status=pending), enqueue RQ job
                                                            │
                                                            ▼
                                              [SP-API worker calls Solicitations]
                                                            │
                                                            └─► update status (sent / failed)
```

## Build order — init + 8 stages

The full path from empty folder to production-ready v1.0:

| Stage | Phase | Branch name | Tag on completion | Deliverable |
|---|---|---|---|---|
| init | Bootstrap | (work on main) | `v0.0-init` | Dev environment, git init, GitHub remote, project dotfiles |
| 0 | Foundation | `stage-0-skeleton` | `v0.1-stage0` | Project skeleton, Docker Compose, all 8 tables, migrations |
| design | Foundation | `stage-design` | `v0.2-design` | Brand, design tokens, shared components, app shell |
| 1 | MVP | `stage-1-auth` | `v0.3-stage1` | Auth (register, login, refresh, /me) |
| 2 | MVP | `stage-2-upload` | `v0.4-stage2` | Excel upload + parsing + dedup + stats refresh + crash recovery |
| 3 | MVP | `stage-3-settings` | `v0.5-stage3` | User settings (shop switcher, repeat grain, excluded order types, timezone) |
| 4 | MVP | `stage-4-list` | `v0.6-stage4` | Repeat-order list with filters, KPIs, pagination, buyer purchase history |
| 5 | MVP | `stage-5-request` | `v0.7-stage5` | Manual mark + link redirect method + correction notes + CSV export |
| polish | Post-MVP | `stage-polish` | `v0.8-polish` | Onboarding, empty states, mobile, a11y, keyboard shortcuts, micro-interactions |
| 6 | Post-MVP | `stage-6-spapi` | `v0.9-stage6` | SP-API integration: credentials with envelope encryption, automatic solicitations |
| 7 | Post-MVP | `stage-7-ops` | `v1.0` | Production deployment, HTTPS, backups, monitoring, rate limiting, CI/CD |

The tag column is authoritative — when in doubt, use exactly the string in that column. The branch column is also authoritative; do not improvise variations.

**Minimum shippable product**: init → 0 → design → 1 → 2 → 3 → 4 → 5. At that point you have a working internal tool.

**Minimum public-launchable product**: + polish + 7. SP-API (stage 6) can wait until users ask for it.

Stages 6 (SP-API) and 7 (advanced ops) are post-MVP and intentionally left out of this prompt set.

## Non-goals for v1.0

- No team / multi-user-per-account workflows (one login = one tenant)
- No admin dashboard
- No analytics or charts beyond the KPI cards
- No email notifications
- No mobile native app (web is responsive — see stage_polish)
- No internationalization (UI is English-only)
- No dark mode

## Conventions Claude Code should follow

- **Type safety**: strict TypeScript on the frontend, Pydantic v2 everywhere on the backend.
- **No business logic in routers**: routers parse input and delegate to `services/*.py`.
- **No raw SQL except where index-critical**: use SQLAlchemy expressions; raw SQL is acceptable for the stats-refresh upsert.
- **Every endpoint scoped by user_id**: never trust client-provided user_id, always derive from JWT.
- **Idempotent uploads**: same file uploaded twice produces zero new rows.
- **Tests live next to features**: every stage must include pytest tests for its backend logic.
- **Migrations are append-only**: never edit an applied migration; create a new one.
- **Secrets in env vars only**: `.env.example` documents them; real values come from `.env` (gitignored).
- **Branching per stage**: for each stage X, create a feature branch off `main` named `stage-X-<slug>` (e.g. `stage-0-skeleton`, `stage-1-auth`, `stage-design`, `stage-polish`). Do all work on the branch. When the acceptance checks pass, merge to `main` (squash or merge commit — your choice), then tag `main` with `v0.X-stageX`. Never commit directly to `main` after the initial `stage_init` setup.

## How to use these prompt files

There are 11 prompt files plus this summary:

1. `stage_init.md` — bootstrap
2. `stage_0_skeleton.md` — backend/frontend scaffolding and database tables
3. `stage_design.md` — visual foundation
4. `stage_1_auth.md` through `stage_5_request.md` — MVP business features
5. `stage_polish.md` — UX refinement
6. `stage_6_spapi.md` — SP-API automation
7. `stage_7_ops.md` — production deployment

Alongside these prompts you have three operational helpers:

- **`CLAUDE.md`** at the repo root — standing rules Claude Code auto-loads each session.
- **`MASTER_PROMPT.md`** in `prompts/` — the cold-start prompt you paste once on day one, plus a list of single-word steering commands (`go`, `next`, `verify`, `status`, `rollback`).
- **`scripts/verify_stage.sh`** — the automated quality gate. Run with the stage id (`bash scripts/verify_stage.sh 2`). Each stage's verify function checks what machines can check; human verification covers the rest.

## Handoff Protocol (applies to every stage)

This protocol is mandatory at the end of every stage. It replaces ad-hoc "I think it's done" messages with a fixed shape, which makes the human review fast and the state machine predictable.

When Claude Code believes a stage is complete:

1. It runs `bash scripts/verify_stage.sh <stage_id>`.
2. If verify exits non-zero, it fixes the failures and re-runs.
3. Once verify exits zero, it outputs the Handoff message exactly as specified in `CLAUDE.md` and stops.
4. The human runs the manual Quality Gate items in the Handoff (10 minutes of real clicking).
5. The human types `next` to advance, or `fix <description>` to iterate on the same branch.

The full Handoff message format lives in `CLAUDE.md` under "The Handoff Protocol".

## Quality Gate vs verify script

Two layers of verification per stage, intentionally separated:

| Layer | Who runs it | Checks |
|---|---|---|
| **verify_stage.sh** | Claude Code, automatically | Tests pass, endpoints respond, files exist, lint clean, migrations applied, no leaked secrets — anything reducible to a script |
| **Quality Gate** | Human, manually | UI feel, copy clarity, performance perception, real-data sanity check, edge cases the script can't simulate |

A stage is "done" only when both pass. Neither substitutes for the other.

## Pasting prompts vs steering

Hand the prompt files to Claude Code **one at a time, in order**. Do not paste multiple stages at once — Claude Code will lose focus and produce mixed quality.

**Start with `MASTER_PROMPT.md`'s COLD START section** on day one. After that, use the single-word commands (`go`, `next`, `verify`, etc.) — never re-paste a stage prompt. Claude Code reads them itself from disk.

Then for each subsequent stage:
1. Make sure the previous stage's tests pass and the app runs locally.
2. Commit and tag the previous stage.
3. Read the next stage's prompt yourself to confirm scope.
4. Paste it into Claude Code.

After each stage:
1. Run the acceptance checks listed at the bottom of the prompt.
2. Manually exercise the new feature end-to-end.
3. Fix any bugs Claude Code missed before moving on.
