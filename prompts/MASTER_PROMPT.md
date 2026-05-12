# MASTER_PROMPT.md — One-Shot Startup and Daily Driver

> This is the only prompt you paste to Claude Code on day one. After that, you steer with single-word commands.

## How to use this file

**Day zero (one-time setup)**: drop these files into the `reviewMaster/` folder:

```
reviewMaster/
├── CLAUDE.md                  ← from this delivery, goes at the repo root
├── prompts/
│   ├── SUMMARY.md
│   ├── MASTER_PROMPT.md       ← this file
│   ├── stage_init.md
│   ├── stage_0_skeleton.md
│   ├── stage_design.md
│   ├── stage_1_auth.md
│   ├── stage_2_upload.md
│   ├── stage_3_settings.md
│   ├── stage_4_list.md
│   ├── stage_5_request.md
│   ├── stage_polish.md
│   ├── stage_6_spapi.md
│   └── stage_7_ops.md
└── scripts/
    └── verify_stage.sh        ← run `chmod +x scripts/verify_stage.sh`
```

Do not initialize git yet — Claude Code does that in stage_init.

**Day one (cold start)**: open Claude Code in the `reviewMaster/` folder and paste the entire **"COLD START PROMPT"** section below as your first message.

**Every other day**: just type one of the short commands listed under "Daily commands" below. Claude Code already knows what to do because it loaded `CLAUDE.md` on startup.

---

## COLD START PROMPT

```
We are building ReviewMaster, a multi-tenant SaaS web app for Amazon sellers that finds repeat buyers in their order data and helps them request reviews.

Your standing rules and workflow are in CLAUDE.md at the project root. Read it now in full before doing anything else.

The build plan lives in prompts/. SUMMARY.md gives the overview; stage_init.md through stage_7_ops.md define each stage's scope and acceptance criteria. There are 11 stages total.

Now do the following, in order:

1. Read prompts/SUMMARY.md fully.
2. Read CLAUDE.md fully.
3. Run `git tag --sort=-creatordate | head -5` to determine the latest completed stage. If there are no tags yet, the next stage is `stage_init`.
4. Identify the next stage's prompt file.
5. Read that file fully.
6. Print a short plan: which stage you are about to start, the high-level steps, and any clarifications you need from me before beginning.
7. Wait for me to type `go` before writing any code.

Do not skip steps. Do not begin coding before I say `go`.
```

---

## Daily commands

Once Claude Code has loaded `CLAUDE.md`, you steer the entire build with these one-word commands. Do not paste long prompts again.

| Command | What Claude Code does |
|---|---|
| `go` | Begin executing the plan it just proposed. |
| `next` | Stage is verified by you. Merge branch to main, tag, delete branch, read the next stage's prompt, propose a plan, wait for `go`. |
| `fix <description>` | Stay on current branch. Fix the issue described. Re-run verify. Re-issue Handoff. |
| `status` | Print current branch, current stage, last commit, `git status`, and last verify result. |
| `verify` | Re-run `scripts/verify_stage.sh <current_stage>` and report results. |
| `rollback` | Discard everything on the current stage branch and start the stage over (asks for confirmation first). |
| `pause` | Stop work and wait. Used if you need to leave the desk mid-stage. |
| `resume` | Pick up from `pause` — Claude Code prints `status` then waits for next instruction. |
| `explain <thing>` | Ask for an explanation of any decision Claude Code made. Pure read; no code changes. |
| `plan` | Re-print the plan for the current stage without acting on it. |
| `skip <check>` | Mark one specific acceptance check as "human-verified-skipped" in the Handoff message. Use sparingly, only when an automation can't realistically test it. |

## Optional cold-start variations

If you want to start from a specific stage (e.g. you completed stage 0 manually and want Claude Code to pick up from stage 1):

```
Resume the ReviewMaster build at stage 1. Read CLAUDE.md, then prompts/SUMMARY.md, then prompts/stage_1_auth.md. Verify the repo is in the expected post-stage-0 state (check that tag v0.1-stage0 exists and the project skeleton is in place). If anything is off, stop and tell me. If everything looks right, propose the stage 1 plan and wait for `go`.
```

If you want Claude Code to redo a stage from scratch (e.g. stage 4 came out badly):

```
We need to redo stage 4. Run `git reset --hard v0.5-stage3` to discard stage 4's work (resets to the post-stage-3 state). Delete the stage-4-list branch if it exists. Then start stage 4 fresh, per the plan in prompts/stage_4_list.md.
```

## What to do when something goes off the rails

**Claude Code is doing too much / making up requirements** → type `pause`, then explain what to drop. Then `resume`.

**Claude Code keeps failing the verify script on the same check** → type `explain why <check> is failing`. If you don't like the answer, type `fix <better approach>`.

**Stage is taking too long with no progress** → type `status`. If it's stuck on one thing, type `skip <specific check>` to bypass that single check, with the understanding that you'll verify it manually.

**You realize a previous stage has a bug** → type `pause`. Then: `Roll back to the tag for stage <N>. We need to redo stage <N+1> because <reason>.` Claude Code will look up the right tag in SUMMARY.md's Build Order table, reset, and you continue from there.

## The Quality Gate

Every stage ends with a Handoff message from Claude Code. The Handoff lists items under **"What you should verify manually."** Those items are your responsibility — not Claude Code's.

Take 10 minutes to actually click through them. Do not rely on verify_stage.sh alone. Common things only humans can judge:
- Does the UI feel right at first sight?
- Is the empty state copy actually helpful?
- Does the error message make sense to a non-technical user?
- Does the page load feel snappy or sluggish?

Only after you've checked those should you type `next`.

## Recovery from common pitfalls

- **Claude Code says "I'll add X for completeness" without asking**: stop it with `pause`. Remind it of Rule 3 (stay in scope). Then `resume`.
- **Claude Code claims the tests pass but you suspect they didn't**: type `verify`. The script tells the truth.
- **You accidentally typed `next` before verifying**: that's why we tag and use feature branches. Type `pause`, then `rollback`, then start the stage over.
- **Claude Code asks too many clarifying questions and stalls**: that's actually the right behavior per Rule 1. Answer them. If a question is silly, point it out and answer briefly.

## End of the build

When stage 7 finishes and you type `next`, Claude Code will report:

```
All stages complete. Tag v1.0 created. The build plan in prompts/ is fully executed.

From here on, you maintain and extend ReviewMaster as a normal codebase. The prompt files are reference documentation for what was built. CLAUDE.md still applies for any future Claude Code sessions.
```

At that point, archive the prompts and ship.
