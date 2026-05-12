# ReviewMaster

A multi-tenant SaaS web application that helps Amazon sellers:

1. Upload their Amazon order export files (.xlsx).
2. Automatically identify **repeat buyers** — customers who purchased the
   same product more than once.
3. Request product reviews from those repeat buyers through three different
   methods (manual mark, link redirect, or SP-API).
4. Track which orders have already been requested so no one gets asked twice.

**Status: pre-MVP, under construction.**

## For contributors

This project is being built in well-defined stages. If you have access to
the prompt files (under `prompts/`), start by reading **`prompts/SUMMARY.md`**
for the architectural overview, then read the stage file matching the
current git tag (e.g. read `prompts/stage_2_upload.md` if the most recent
tag is `v0.4-stage2`).

The full tag-to-stage mapping lives in SUMMARY.md's Build Order table.
The contributing workflow (branching, commits, tagging) is in
[`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Prerequisites

| Tool | Minimum version |
|---|---|
| git | 2.34+ |
| curl | any |
| Docker Engine | 24+ |
| Docker Compose plugin | 2.20+ |
| Node.js | 22 LTS (only needed if running the frontend on the host — not required for `docker compose`) |
| Python | 3.11+ (only needed for host-side `pre-commit` — not required for backend runtime) |
| pre-commit | 3+ |

All Python dependencies live inside Docker containers — do not `pip install`
on the host. See `CLAUDE.md` for the full host-cleanliness policy.

## Quick start

```bash
cp .env.example .env                      # defaults work for local dev as-is
docker compose up -d --build              # postgres, redis, backend, frontend, worker
docker compose exec backend alembic upgrade head   # apply migrations
```

Then open:

- Frontend: <http://localhost:3300>
- Backend health: <http://localhost:8088/health>
- API docs (Swagger): <http://localhost:8088/docs>

Host ports are shifted from the standard 8000/3000/5432/6379 because other
dev stacks on this machine occupy them; container-internal ports are
unchanged. See `docker-compose.yml` for the full mapping.

Tear down with `docker compose down` (data persists in the `pgdata` volume).
`docker compose down -v` wipes the database too.

## Common commands

```bash
# Backend
docker compose exec backend pytest -q                       # run tests
docker compose exec backend alembic upgrade head            # apply migrations
docker compose exec backend alembic revision -m "message"   # create a new migration

# Database
docker compose exec postgres psql -U postgres -d app        # interactive psql
docker compose exec postgres psql -U postgres -d app -c "\dt"   # list tables

# Frontend
docker compose exec frontend npm run lint                   # lint
docker compose exec frontend npm run build                  # production build

# Worker (RQ)
docker compose logs -f worker                               # watch queue activity
```

## Project layout

```
reviewMaster/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── core/               # config, db session, security, logger
│   │   ├── models/             # SQLAlchemy ORM — one file per table
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── api/                # FastAPI routers (one per resource)
│   │   ├── services/           # business logic (kept out of routers)
│   │   ├── workers/            # RQ job functions
│   │   └── utils/
│   ├── alembic/                # migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/                    # Next.js App Router pages
│   ├── components/             # React components (shadcn under ui/)
│   ├── lib/                    # utils, api client
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml          # local dev stack
├── .env.example                # documents every required env var
├── prompts/                    # build-stage specifications
├── scripts/verify_stage.sh     # automated quality gate
├── CLAUDE.md                   # standing rules for Claude Code
└── CONTRIBUTING.md             # workflow (branches, commits, tags)
```

## Build stages

The full build plan and per-stage prompts live in [`prompts/`](./prompts/).
Start with `prompts/SUMMARY.md`.

| Tag | Stage | Branch |
|---|---|---|
| `v0.0-init` | Dev environment + git | (on main) |
| `v0.1-stage0` | Skeleton + 8 tables | `stage-0-skeleton` |
| `v0.2-design` | Brand + components | `stage-design` |
| `v0.3-stage1` | Auth | `stage-1-auth` |
| `v0.4-stage2` | Excel upload | `stage-2-upload` |
| `v0.5-stage3` | User settings | `stage-3-settings` |
| `v0.6-stage4` | Repeat-order list | `stage-4-list` |
| `v0.7-stage5` | Manual + link request | `stage-5-request` |
| `v0.8-polish` | UX polish | `stage-polish` |
| `v0.9-stage6` | SP-API automation | `stage-6-spapi` |
| `v1.0` | Production ops | `stage-7-ops` |
