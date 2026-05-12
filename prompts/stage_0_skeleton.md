# Stage 0 — Project Skeleton and Data Model

> Read `SUMMARY.md` first if you haven't. This stage builds the foundation only — no business logic.

## Goal

Create a complete, runnable project skeleton with all infrastructure pieces wired up, all database tables created, and minimal smoke endpoints to prove the stack is alive.

## Tech stack (must follow exactly)

- Backend: Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic
- DB: PostgreSQL 15
- Cache / queue: Redis 7 + RQ
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui
- Deployment: Docker Compose

## Project structure

```
repo/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/         (config, security, db session, logger)
│   │   ├── models/       (one file per SQLAlchemy model)
│   │   ├── schemas/      (Pydantic request/response models)
│   │   ├── api/          (FastAPI routers, one per resource)
│   │   ├── services/     (business logic — empty placeholders for now)
│   │   ├── workers/      (RQ job functions — empty placeholders for now)
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Database tables (all created in this stage)

Use UUID primary keys throughout. Use `timestamptz` for all timestamps. Add the indicated indexes.

### 1. `users`
- `id` UUID PK
- `email` text UNIQUE NOT NULL
- `password_hash` text NOT NULL
- `timezone` text NOT NULL DEFAULT `'UTC'`
- `created_at`, `updated_at` timestamptz NOT NULL DEFAULT now()

### 2. `user_settings`
- `user_id` UUID PK, FK→users.id ON DELETE CASCADE
- `active_shop_site` text NULL  (defaults to first shop_site seen in uploads)
- `repeat_grain` text NOT NULL DEFAULT `'asin'`  (enum check: `'asin' | 'spu' | 'product_name'`)
- `excluded_order_types` jsonb NOT NULL DEFAULT `'[]'`  (array of strings like `["退货"]`)
- `created_at`, `updated_at`

### 3. `orders`
- `id` UUID PK
- `user_id` UUID NOT NULL FK→users.id ON DELETE CASCADE
- `order_id` text NOT NULL  (Amazon order number)
- `shop_site` text NOT NULL
- `asin` text NULL
- `msku`, `sku`, `spu` text NULL
- `product_name`, `product_title`, `parent_product_name` text NULL
- `order_type` text NULL
- `buyer_email` text NULL
- `buyer_key` text NOT NULL  (see Stage 2 for how it's derived; for now just a text column)
- `order_time_utc` timestamptz NULL
- `ship_time_utc` timestamptz NULL
- `estimated_delivery_utc` timestamptz NULL
- `item_price` numeric(12,2) NULL
- `currency` text NULL
- `quantity` integer NULL
- `ship_city`, `ship_state`, `ship_country` text NULL
- `tracking_number`, `carrier` text NULL
- `raw_json` jsonb NOT NULL  (every column from the source row)
- `created_at`, `updated_at`

Constraints and indexes:
- UNIQUE (`user_id`, `order_id`)
- INDEX (`user_id`, `shop_site`, `buyer_key`, `asin`)
- INDEX (`user_id`, `shop_site`, `buyer_key`, `spu`)
- INDEX (`user_id`, `estimated_delivery_utc`)
- INDEX (`user_id`, `shop_site`)

### 4. `buyer_product_stats`
Aggregated per (user, shop, buyer, product). Refreshed by upload worker.

- `user_id` UUID
- `shop_site` text
- `buyer_key` text
- `grain` text  (`'asin' | 'spu' | 'product_name'`)
- `group_value` text  (the actual ASIN or SPU or product_name string)
- `order_count` integer NOT NULL
- `first_order_at`, `last_order_at` timestamptz
- `total_amount` numeric(14,2)
- `updated_at` timestamptz

Constraint:
- PRIMARY KEY (`user_id`, `shop_site`, `buyer_key`, `grain`, `group_value`)
- INDEX (`user_id`, `shop_site`, `grain`, `order_count`)  (for "give me all groups with count ≥ 2")

### 5. `review_requests`
- `id` UUID PK
- `user_id` UUID NOT NULL FK
- `order_uuid` UUID NOT NULL FK→orders.id ON DELETE CASCADE  (note: this is orders.id not orders.order_id)
- `method` text NOT NULL CHECK IN (`'manual'`, `'link'`, `'api'`)
- `status` text NOT NULL CHECK IN (`'pending'`, `'sent'`, `'failed'`)
- `requested_at` timestamptz NOT NULL DEFAULT now()
- `api_response` jsonb NULL
- `created_at`, `updated_at`

Constraint:
- UNIQUE (`user_id`, `order_uuid`)  — an order can only be requested once

### 6. `review_request_notes`
Append-only correction and audit log. Attached to the **order**, not to the review_request — this way the audit log survives the "failed retry" delete-and-reinsert pattern documented in Stage 5.

- `id` UUID PK
- `user_id` UUID NOT NULL FK→users.id ON DELETE CASCADE
- `order_uuid` UUID NOT NULL FK→orders.id ON DELETE CASCADE
- `review_request_id` UUID NULL  (intentionally not a FK — references a row that may be deleted; preserves the id string for forensic queries)
- `note` text NOT NULL
- `kind` text NOT NULL CHECK IN (`'user'`, `'system'`)  (system notes are auto-generated, e.g. failure summaries; user notes are seller-written)
- `created_at` timestamptz NOT NULL DEFAULT now()

Index: (`user_id`, `order_uuid`, `created_at` DESC).

### 7. `upload_batches`
- `id` UUID PK
- `user_id` UUID NOT NULL FK
- `filename` text NOT NULL
- `file_size_bytes` bigint NOT NULL
- `total_rows`, `new_rows`, `updated_rows`, `duplicate_rows`, `error_rows` integer NOT NULL DEFAULT 0
- `progress` integer NOT NULL DEFAULT 0  (rows processed so far — for crash recovery)
- `status` text NOT NULL CHECK IN (`'processing'`, `'completed'`, `'failed'`)
- `error_detail` jsonb NULL
- `started_at` timestamptz NOT NULL DEFAULT now()
- `completed_at` timestamptz NULL

### 8. `seller_credentials`
- `user_id` UUID PK FK
- `dek_encrypted` bytea NOT NULL  (the data-encryption-key, encrypted by the master KEK)
- `refresh_token_ciphertext` bytea NOT NULL  (refresh_token encrypted with the DEK)
- `lwa_client_id` text NOT NULL
- `lwa_client_secret_ciphertext` bytea NOT NULL
- `selling_partner_id`, `marketplace_id` text NOT NULL
- `created_at`, `updated_at`

This table is created now but populated only in Stage 6.

## Skeleton requirements

- `backend/app/main.py` boots FastAPI, mounts CORS middleware, exposes `GET /health` returning `{"status": "ok"}`.
- `backend/app/core/config.py` reads from env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_TTL_MINUTES=60`, `REFRESH_TOKEN_TTL_DAYS=30`, `ENCRYPTION_KEK`, `CORS_ORIGINS`.
- `backend/app/core/db.py` exposes an async SQLAlchemy session factory and an async dependency `get_db`.
- One SQLAlchemy model file per table under `app/models/`.
- Alembic configured with a single initial migration that creates all 8 tables and indexes.
- `frontend/app/page.tsx` shows a minimal welcome page proving Next.js + Tailwind + shadcn/ui work. Install at least the `Button` shadcn component as a smoke test.
- `frontend/lib/api.ts` is a stub axios instance pointing at `NEXT_PUBLIC_API_BASE_URL` — no auth logic yet.
- `docker-compose.yml` brings up: `postgres`, `redis`, `backend` (with `--reload`), `frontend` (in dev mode), `worker` (placeholder — runs `rq worker default` against Redis).
- `.env.example` lists every env var used.
- `.gitignore` covers Python, Node, env files, IDE noise.
- `README.md` has: prerequisites, one-line bring-up command, how to run migrations, how to run tests.

## Acceptance checks

1. `docker compose up -d` succeeds; all 5 containers report healthy.
2. `curl http://localhost:8000/health` returns `{"status":"ok"}`.
3. `http://localhost:3000` shows the welcome page with a shadcn Button visible.
4. `docker compose exec backend alembic upgrade head` succeeds.
5. `docker compose exec postgres psql -U postgres -d app -c "\dt"` lists all 8 tables.
6. `docker compose exec postgres psql -U postgres -d app -c "\d orders"` shows the expected UNIQUE constraint and indexes.
7. `docker compose exec backend pytest` runs (even if there are no tests yet, the runner must exit 0).
8. The worker container is running and connected to Redis (no jobs to process yet — that's fine).

## Out of scope for this stage

- No authentication logic.
- No upload logic.
- No business endpoints.
- No frontend pages beyond the welcome page.
- No tests beyond proving pytest runs.
