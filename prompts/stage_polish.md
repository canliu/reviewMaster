# Stage Polish — Onboarding, Empty States, Responsiveness, Accessibility, Performance

> Runs **after** `stage_5_request.md` — MVP is functionally complete. This stage takes the working app and makes it feel finished.

## Goal

Take the functional MVP from Stage 5 and raise the perceived quality bar: first-time user experience, empty states with personality, responsive behavior, error edges, keyboard navigation, and a few small delights. **No new features.** No backend changes except where strictly needed for telemetry-free UX (e.g. tracking whether a user has dismissed an onboarding tooltip — and even that we keep client-side).

## Scope

1. First-time user onboarding flow (3 steps)
2. Empty-state illustrations for every list
3. Loading skeletons (replace remaining spinners)
4. Mobile breakpoints down to 375px
5. Error boundary polish per route
6. Keyboard shortcuts
7. Toast notification audit (consistent across the app)
8. Form UX (inline validation, autofocus, autocomplete hints)
9. Micro-interactions (small, restrained)
10. Accessibility audit and fixes

Strict no-go list: no new pages, no new endpoints, no new database tables.

## 1. Onboarding flow

A first-time user signs up, lands on `/dashboard`, and currently sees a welcome placeholder. Replace this with a guided 3-step setup.

### Trigger

- A new client-side flag, stored in localStorage, called `onboarding_complete`.
- On `/dashboard` load: if the flag is unset **and** the user has zero upload batches, render the onboarding component instead of the normal dashboard.
- "Dismiss / skip" button on every step writes `onboarding_complete=true` and reveals the normal dashboard.

### The three steps

#### Step 1 — Welcome and explain the pipeline

A full-width card:

> **Welcome to ReviewMaster, [first part of email].**
>
> Here's how it works in three steps:
>
> 1. Upload your Amazon order export.
> 2. We find your repeat buyers automatically.
> 3. Request reviews from them — manually, by link, or via SP-API.
>
> [Get started] [Skip tour]

#### Step 2 — Upload nudge

Take the user to `/dashboard/uploads` with a translucent overlay/coach-mark pointing at the upload dropzone:

> "Drop your `配送信息_*.xlsx` here. We'll do the rest."

The overlay is dismissible. Once the user successfully uploads a file, advance to step 3.

#### Step 3 — Tour the repeat-orders page

After the first upload completes, redirect to `/dashboard/repeat-orders` with a brief tour:
- Highlight the KPI cards: "Here's what we found."
- Highlight the first row with a green-dot annotation: "Click here to request a review."
- Highlight the shop switcher: "Switch between your marketplaces here."

Use a small library like `react-joyride` **only if needed** — try first with a lightweight custom implementation (3 positioned `<div>`s with arrow SVGs). The full library is acceptable if the custom approach gets ugly, but keep dependency count low. **If react-joyride is chosen, install it in this stage and add it to `package.json`; do not assume it's already present.**

After step 3, set `onboarding_complete=true`.

### Re-entry

Settings page gets a small link: "Replay tour" — resets the flag and starts again.

## 2. Empty states with personality

Every list page already uses the `EmptyState` component (from Stage Design). Audit each one and make sure the copy and illustration feel inviting, not clinical.

| Page | Empty when | Copy |
|---|---|---|
| `/dashboard/uploads` (no uploads) | first-time user | "Drop your first order file to see what's hiding in your data." + sample illustration |
| `/dashboard/repeat-orders` (no repeats found) | uploaded but everyone's a one-timer | "No repeat buyers yet — but everyone starts somewhere. Try a looser grain in Settings." |
| `/dashboard/repeat-orders` (filters too tight) | filters return zero rows | "No matches for these filters. Reset filters?" with a reset button |
| `/dashboard/review-requests` (no requests sent) | first-time user | "You haven't requested any reviews yet. Find some good candidates in Repeat orders." |
| `/dashboard/review-requests` (filtered to zero) | tight filters | similar reset pattern |

Illustrations: use simple inline SVG line art (envelopes, magnifying glasses, empty boxes). Do not pull from an illustration library — too heavy. Three or four ~120px SVGs in `components/illustrations/` is enough.

## 3. Loading skeletons

Replace remaining `<Spinner>` / `Loading…` text with skeletons that match the layout that will appear.

- `/dashboard/uploads` history table: 5 placeholder rows with shimmering bars.
- `/dashboard/repeat-orders` table: 10 placeholder rows; KPI cards have skeleton numbers.
- `/dashboard/review-requests`: same pattern.
- Form pages stay with spinners on the submit button only.

Use shadcn's `Skeleton` primitive. Keep shimmer animation subtle (1.5s cycle, low contrast).

## 4. Mobile breakpoints

Target supported widths: 375px (iPhone SE) and up.

### Repeat-orders table at <768px

The table currently has ~10 columns. On narrow screens, collapse to a card list:

```
┌──────────────────────────────────┐
│ B0CQW5NDWJ · Purchase 2/3        │
│ NutraPep Magnesium Glycinate…    │
│ ROCHESTER, NY · $19.99           │
│ [Not requested]   [⋮]            │
└──────────────────────────────────┘
```

- Each card has a tap target for "Mark requested" via a bottom-sheet action menu (the `⋮` button).
- Row selection (for batch operations) uses long-press on mobile.

### Sidebar at <768px

Collapses into a Drawer sheet (already covered in Stage Design). Verify it actually works.

### Forms at <768px

- Inputs are full-width.
- Two-column form layouts (settings page) become single-column.

### Test matrix

Test the app at: 375×667 (iPhone SE), 414×896 (iPhone 12), 768×1024 (iPad portrait), 1280×800 (laptop), 1920×1080 (desktop). Document any known-broken combos in `frontend/MOBILE.md`.

## 5. Error boundary polish per route

The Stage Design `app/error.tsx` is generic. Add route-specific error pages where the message can be more helpful:

- `app/(dashboard)/uploads/error.tsx` — "Couldn't load uploads. The server might be busy. [Retry] [Go to dashboard]"
- `app/(dashboard)/repeat-orders/error.tsx` — "Couldn't load repeat orders. Check your shop selection?"

Each is a tiny file that renders a polished error card with friendly copy.

Also: every fetch in TanStack Query gets a sensible `onError` handler that surfaces a toast. Audit all `useQuery` and `useMutation` calls.

## 6. Keyboard shortcuts

Add a small set of unobtrusive shortcuts:

| Key | Action |
|---|---|
| `?` | Open shortcuts cheat sheet (modal) |
| `g u` | Go to Uploads |
| `g r` | Go to Repeat orders |
| `g q` | Go to Review requests |
| `g s` | Go to Settings |
| `/` | Focus the search input on the current page |
| `Escape` | Close any open modal or sheet |

Implement with a tiny custom hook or `react-hotkeys-hook`. Show the cheat sheet via the `?` key.

Make the cheat sheet discoverable: a small "⌨ Shortcuts" link in the footer of the sidebar, opens the same modal.

## 7. Toast notification audit

Walk through every user action and verify a consistent toast pattern:

- Success: green check icon, label says what happened ("Marked 12 orders as requested"), 4s auto-dismiss.
- Error: red icon, label says what failed, includes a `Retry` action if applicable, manual dismiss.
- Info: blue icon, used sparingly — e.g. "Link opened in a new tab".
- Warning: amber, used for partial successes — e.g. "10 of 12 succeeded. 2 were skipped — see details."

Failure mode to fix: avoid stacking 5 toasts at once. Cap at 3 visible; queue the rest.

## 8. Form UX

For every form in the app:

- The first input is autofocused on page load.
- `autoComplete="email"`, `autoComplete="current-password"`, `autoComplete="new-password"` set correctly.
- Validation errors show inline below the input, in red, with a small alert icon.
- Submit buttons disable + show a spinner while in-flight; the form fields stay enabled (so users can correct without re-entering).
- `Enter` submits; `Escape` closes if inside a modal.

## 9. Micro-interactions

Restrained — these are the only ones we add:

- Buttons: 100ms scale-down on click (`active:scale-[0.98]`).
- Cards (KPI, list items): subtle border-color transition on hover.
- Status badge change: 300ms fade when going from "Not requested" → "Requested · manual" after a successful action.
- Sidebar collapse: 200ms width transition.

Nothing bouncy, nothing spinning. The product should feel calm.

## 10. Accessibility audit

Run through the WCAG 2.1 AA checklist for each page. Specific things to verify and fix:

- Every form input has an associated `<label>`.
- Every icon button has `aria-label`.
- Every dialog/sheet has a focus trap and returns focus to the trigger on close (shadcn does this; verify).
- Tab order is logical on every page.
- Status colors are paired with text or icon (already required by Stage Design; verify it stuck).
- The toast system announces messages via `aria-live="polite"`.
- The skip-to-content link is the first focusable element on every page.

Test with: keyboard-only navigation (full app flow), screen reader (VoiceOver on macOS or NVDA on Windows — just smoke-test the main flow), and the axe DevTools browser extension on each page.

Fix everything axe flags as a violation. Document anything triaged as a "best practice but not a violation" in `frontend/A11Y.md`.

## 11. Performance pass

- Run Lighthouse on `/dashboard/repeat-orders` with 1500 rows. Aim for performance ≥85 on a mid-tier laptop.
- Eliminate any obvious waterfalls: ensure the table query and the KPI summary fire in parallel, not sequentially.
- Lazy-load `/dashboard/review-requests` route bundle (Next.js does this automatically with App Router; verify).
- Add `loading.tsx` for each route segment so route transitions feel instant.
- Ensure no unnecessary re-renders in the repeat-orders table by memoizing column definitions.

## Tests

- Vitest tests for the onboarding flow state machine (advance/skip/dismiss/replay).
- Vitest test for the keyboard-shortcut hook covering each binding.
- An axe-core automated test on each route via Playwright (if you have Playwright; otherwise a one-page smoke is fine).

No new backend tests in this stage.

## Acceptance checks

1. Brand-new user signs up → onboarding step 1 appears. Walks through all three steps; flag is set; refresh doesn't replay.
2. "Replay tour" in settings resets the flag and shows step 1 again.
3. Every list page has a non-clinical empty state.
4. Loading uploads / repeat orders shows skeletons, not spinners.
5. Resize to 375px width: table becomes cards, sidebar becomes drawer, no horizontal scroll, no overlap.
6. Keyboard-only: log in, navigate to repeat-orders, select 3 rows, mark them, all without the mouse.
7. `?` opens the shortcuts cheat sheet; `g r` goes to repeat-orders.
8. axe DevTools reports zero violations on `/dashboard/repeat-orders` and `/dashboard/uploads`.
9. Lighthouse performance ≥85 on the repeat-orders page.
10. No new git tag — this stage gets `v0.6-polish` only after the human reviewer has actually used the app for 10 minutes and feels it.

## Out of scope

- Dark mode.
- Animations beyond what's listed.
- Native mobile app.
- Internationalization.
- Custom illustrations from a designer.
- A11y compliance beyond WCAG 2.1 AA.
