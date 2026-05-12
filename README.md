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
| Node.js | 22 LTS |
| Python | 3.11+ |
| pre-commit | 3+ |
| GitHub CLI (`gh`) | optional but recommended |

All Python dependencies live inside Docker containers — do not `pip install`
on the host. See `CLAUDE.md` for the full host-cleanliness policy.

## Quick start

```
# (filled in by Stage 0)
```

## Project layout

```
# (filled in by Stage 0)
```

## Build stages

The full build plan and per-stage prompts live in [`prompts/`](./prompts/).
Start with `prompts/SUMMARY.md`.
