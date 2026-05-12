# Contributing to ReviewMaster

This project is built in well-defined stages. Read `prompts/SUMMARY.md` first
for the architectural overview, then the stage file that matches the current
git tag.

## Branching

- Every stage gets its own feature branch off `main`, named
  `stage-<id>-<slug>` for numbered stages (e.g. `stage-0-skeleton`,
  `stage-1-auth`) or `stage-<id>` for named ones (`stage-design`,
  `stage-polish`). The exact branch name for each stage is in SUMMARY.md's
  Build Order table — don't improvise.
- All stage work happens on the branch. After the initial `stage_init` setup,
  **never commit directly to `main`**.

## Merging

When a stage's acceptance checks pass and the human Quality Gate is clean:

1. Merge the branch into `main`. Use squash-merge OR a no-ff merge commit —
   pick one style and use it consistently across every stage.
2. Tag `main` with the exact tag string from SUMMARY.md's Build Order table
   (e.g. `v0.1-stage0`). Never invent tag names.
3. `git push origin main && git push --tags`.
4. Delete the merged branch: `git branch -d stage-<id>-<slug>`.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — a new user-facing feature
- `fix:` — a bug fix
- `chore:` — tooling, config, dependencies
- `docs:` — documentation only
- `test:` — tests only
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `build:` — build system or external dependencies

Examples:

```
feat(auth): add /api/auth/refresh endpoint
fix(upload): reject .xls files with a clearer error message
chore: bump ruff to 0.6.10
```

## Pre-commit hooks

Hooks are configured in `.pre-commit-config.yaml`. They run automatically on
`git commit`. To run them across the whole repo on demand:

```bash
pre-commit run --all-files
```

Language-specific linters (ruff, prettier) are commented out in the config
and will be enabled by Stage 0 once the toolchain is in place.

## Stage checklist

Each stage ends with:

1. All automated tests green (`bash scripts/verify_stage.sh <stage_id>`).
2. Human Quality Gate passes (UI clicked through, edge cases sanity-checked).
3. Merge branch to `main`.
4. Tag `main` with the exact string from SUMMARY.md's Build Order table.
5. `git push --tags`.

## Branch protection (recommended, post-Stage-7)

Once Stage 7 adds CI, enable branch protection on `main` in GitHub:
Settings → Branches → require PRs and passing checks before merge.
