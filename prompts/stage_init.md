# Stage Init — Dev Environment and Git Setup

> Run this **before** `stage_0_skeleton.md`. It prepares the developer machine and initializes the git repository inside the existing `reviewMaster` folder.

## Context

- The folder `reviewMaster` already exists (created manually by the user). You will work inside it.
- Target OS: **Ubuntu / Debian Linux**.
- Remote: **GitHub**. The remote repository may or may not exist yet — handle both cases.
- This stage produces **no application code**. It only sets up tooling, dotfiles, and git.

## Goal

After this stage:
1. All system tools required for development are installed and verified.
2. `reviewMaster/` is a clean git repository on the `main` branch.
3. Standard project-level dotfiles exist (`.gitignore`, `.gitattributes`, `.editorconfig`, etc.).
4. A first commit is made and tagged `v0.0-init`.
5. The remote `origin` is configured (if the user supplies a URL) or documented as pending.

## Step 1 — Verify and install system tools

For each tool, check whether it is installed. **Only install if missing.** Do not upgrade or overwrite existing installations.

Required tools and minimum versions:

| Tool | Minimum version | Install method (Ubuntu/Debian) |
|---|---|---|
| git | 2.34+ | `sudo apt install git` |
| curl | any | `sudo apt install curl` |
| Docker Engine | 24+ | follow https://docs.docker.com/engine/install/ubuntu/ — do **not** auto-run, print the steps and ask the user to run them |
| Docker Compose plugin | 2.20+ | bundled with Docker Engine installation above |
| Node.js | 22 LTS | install **nvm** (https://github.com/nvm-sh/nvm), then `nvm install 22 && nvm alias default 22` |
| Python | 3.11+ | `sudo apt install python3.11 python3.11-venv python3-pip` (add `deadsnakes` PPA if not in default repo) |
| pre-commit | 3+ | `pip install --user pre-commit` |
| GitHub CLI (`gh`) | latest | `sudo apt install gh` (optional but recommended) |

Process for each tool:
1. Run `<tool> --version` (or equivalent). If success and version is acceptable, print "✓ <tool> <version> already installed".
2. If missing or too old, print "✗ <tool> missing — installing..." and run the install command.
3. For Docker specifically: do **not** auto-install. Docker requires `sudo`, repository setup, and post-install steps (adding the user to the `docker` group, logging out and back in). Instead, print the exact commands the user should run and **pause for them to confirm completion** before proceeding. Verify with `docker run --rm hello-world` after they confirm.

If any required tool cannot be installed or verified, stop and report — do not continue to git setup.

## Step 2 — Configure global git (only if not already set)

Check the following git globals. **If any is missing**, ask the user for the value interactively and set it. If already set, leave it alone.

- `user.name`
- `user.email`
- `init.defaultBranch` (must be `main` — set this even if other globals exist)
- `core.autocrlf` (must be `input` on Linux)
- `pull.rebase` (set to `false` — default merge behavior, predictable for a beginner-friendly repo)

Print the resulting `git config --global --list` for confirmation.

## Step 3 — Initialize the repository

Inside `reviewMaster/`:

1. If `.git/` does not exist, run `git init -b main`.
2. If `.git/` already exists, verify the current branch is `main`; if not, rename it: `git branch -m main`.
3. Confirm `reviewMaster/` is empty (or list any pre-existing files so we don't overwrite them). If non-empty, do not touch existing files unless instructed.

## Step 4 — Create project-level dotfiles

Create the following files in the repo root. Each should be production-quality, not a stub.

### `.gitignore`
Must cover:
- Python: `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.venv/`, `venv/`, `build/`, `dist/`
- Node: `node_modules/`, `.next/`, `out/`, `.turbo/`, `coverage/`, `npm-debug.log*`, `yarn-error.log`
- Env / secrets: `.env`, `.env.local`, `.env.*.local`, but **keep** `.env.example`
- Editors: `.vscode/`, `.idea/`, `*.swp`, `*.swo`, `.DS_Store`
- Docker volumes / logs: `pgdata/`, `redisdata/`, `*.log`
- Project-specific: `/tmp/`, `uploads/`. For `.xlsx` files: use a **root-only glob** like `/*.xlsx` so test fixtures under `backend/tests/fixtures/*.xlsx` and any in `samples/` are NOT ignored. Add an explicit comment in `.gitignore` explaining this.
- OS noise: `Thumbs.db`, `Desktop.ini`

### `.gitattributes`
- Normalize text files to LF on commit: `* text=auto eol=lf`
- Mark common binary types as binary: `*.xlsx`, `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.pdf`, `*.zip`
- Mark lockfiles as merge=ours candidates (don't auto-resolve): leave a comment explaining

### `.editorconfig`
- root = true
- Default: utf-8, LF, trim trailing whitespace, insert final newline, 2-space indent
- Override for Python: 4-space indent
- Override for Markdown: do not trim trailing whitespace (markdown uses `  ` for line break)

### `.pre-commit-config.yaml`
Initial hooks (these run on every commit):
- `pre-commit-hooks`: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-added-large-files` (max 5 MB), `check-merge-conflict`, `detect-private-key`
- `detect-secrets` from Yelp (https://github.com/Yelp/detect-secrets) — initialize a baseline with `detect-secrets scan > .secrets.baseline` after the file is created, commit the baseline. This catches accidental commits of API keys, refresh tokens, etc.
- Leave **language-specific hooks (ruff, black, prettier) commented out for now** with a TODO note saying they will be enabled once Stage 0 installs the toolchain. This avoids hook failures on a repo with no code yet.

Run `pre-commit install` after creating the file so the hook is wired into `.git/hooks/pre-commit`.

### `CONTRIBUTING.md`
Short doc covering:
- Branching: every stage gets its own feature branch off `main`, named `stage-<id>-<slug>` (e.g. `stage-0-skeleton`, `stage-1-auth`, `stage-design`, `stage-polish`, `stage-6-spapi`). Do all stage work on the branch. Never push to `main` directly after this initial setup.
- Merging: when a stage's acceptance checks pass, squash-merge (or merge commit, your call — be consistent) the branch into `main`. Delete the branch after merge.
- Commits: **Conventional Commits** — examples for `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `build`.
- Each stage ends with: tests green → manual acceptance → merge to `main` → tag main with the string specified in SUMMARY.md's Build Order table → `git push --tags`. Never invent tag names; copy them from the table.
- Optional but recommended: enable branch protection on `main` in GitHub (settings → branches) requiring PRs and passing checks, once Stage 7 has CI in place.
- How to run pre-commit manually: `pre-commit run --all-files`.

### `README.md`
A scaffold the later stages will fill in. Include:
- Project name and one-paragraph description (taken from the SUMMARY document — copy the "What we are building" section).
- "Status: pre-MVP, under construction."
- **A prominent "For contributors" section near the top: "This project is being built in well-defined stages. If you have access to the prompt files (under `prompts/`), start by reading `prompts/SUMMARY.md` for the architectural overview, then read the stage file matching the current git tag (e.g. `prompts/stage_2_upload.md` if the most recent tag is `v0.4-stage2`). The full tag-to-stage mapping is in SUMMARY.md's Build Order table."**
- "Prerequisites" section listing the tools from Step 1.
- "Quick start" placeholder: `# (filled in by Stage 0)`.
- "Project layout" placeholder: `# (filled in by Stage 0)`.
- "Build stages" pointing to `prompts/` if the user has the prompt files in the repo.

### `.env.example` (placeholder)
Empty file with a single comment: `# Filled in by Stage 0. Do not commit your real .env.`

### `CLAUDE.md` and `prompts/` (already provided)

If the user has placed `CLAUDE.md` at the repo root and the stage prompts under `prompts/`, leave them alone — they are operational artifacts, not generated outputs. Confirm they exist:

- `CLAUDE.md` at repo root
- `prompts/SUMMARY.md`
- `prompts/MASTER_PROMPT.md`
- `prompts/stage_*.md` (all stage files)
- `scripts/verify_stage.sh` (mark executable: `chmod +x scripts/verify_stage.sh`)

If any are missing, stop and report — the user expected them to be present before starting this stage.

## Step 5 — Configure the GitHub remote

Ask the user one question:

> "Have you already created an empty GitHub repository for this project? Paste the URL (HTTPS or SSH), or type `skip` to leave the remote unconfigured for now."

Handle three cases:

1. **User pastes a URL** — run `git remote add origin <url>`, verify with `git remote -v`, but do **not** push yet (we haven't committed anything). Note: nothing is pushed in this stage. Pushing happens after the first commit below.

2. **User types `skip`** — leave the remote unconfigured. Print a short hint: "Later, create a repo on GitHub and run `git remote add origin <url> && git push -u origin main`."

3. **User has `gh` installed and wants to auto-create** — only offer this if `gh auth status` shows they are logged in. Then offer: "Create a new private GitHub repo named `reviewMaster` under your account?" If yes, run `gh repo create reviewMaster --private --source=. --remote=origin` (does **not** push automatically).

## Step 6 — First commit and tag

Inside `reviewMaster/`:

```bash
git add .
git commit -m "chore: initialize project (dotfiles, pre-commit, contributing guide)"
git tag v0.0-init
```

If a remote was configured, ask the user:

> "Push the initial commit and tag to GitHub now? (yes/no)"

If yes:
```bash
git push -u origin main
git push --tags
```

If no, print the exact commands so they can do it manually later.

## Step 7 — Final verification

Print a summary:
- `git status` (should be clean)
- `git log --oneline` (should show one commit)
- `git tag` (should show `v0.0-init`)
- `git remote -v` (the remote, or "not configured")
- The output of `pre-commit --version`
- The output of `docker compose version`
- The output of `node --version` and `python3.11 --version`

If everything looks right, print:

> "Initialization complete. Next: hand `stage_0_skeleton.md` to Claude Code."

## Acceptance checks

1. `cd reviewMaster && git status` shows a clean working tree on `main`.
2. `git log` shows the initial commit.
3. `git tag` lists `v0.0-init`.
4. `.gitignore`, `.gitattributes`, `.editorconfig`, `.pre-commit-config.yaml`, `CONTRIBUTING.md`, `README.md`, `.env.example` all exist at the repo root.
5. `CLAUDE.md` at repo root and `prompts/` directory with all expected files are present.
6. `scripts/verify_stage.sh` exists and is executable.
7. `pre-commit run --all-files` succeeds (it should — there's no code yet to lint).
8. `docker run --rm hello-world` succeeds.
9. `node --version` reports v22.x.x.
10. `python3.11 --version` reports 3.11.x.
11. `bash scripts/verify_stage.sh init` exits 0.
12. If a GitHub remote was configured and pushed: the commit and tag are visible on GitHub.

## Out of scope

- No application code, no Docker Compose file yet (Stage 0 creates it).
- No frontend or backend dependencies installed yet (Stage 0 does this).
- No CI/CD pipeline (post-MVP).
- No secrets management beyond the `.env` / `.env.example` pattern.
