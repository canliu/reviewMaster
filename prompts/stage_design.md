# Stage Design — Design System, Brand, Component Library, Global Layout

> Runs **after** `stage_0_skeleton.md` and **before** `stage_1_auth.md`. Sets the visual foundation every subsequent page will build on.

## Goal

Establish the brand and design system, build a reusable component library, and create the global layout shell. After this stage, the project has zero business pages, but every page built in stages 1–5 inherits a consistent, polished look without further design work.

## Scope

- Brand decisions (colors, typography, voice)
- Design tokens (Tailwind config)
- Reusable shadcn/ui-based components
- Global app layout (sidebar + header)
- Logo (placeholder)
- Error pages (404, 500)
- Loading skeleton primitives
- Toast notification system
- Empty-state primitive

**No business pages** are built in this stage. Stage 1 onward consumes the components produced here.

## Brand decisions

### Product name

`ReviewMaster` — already chosen. Use this exact casing in all UI text.

### Tagline (for login/register pages and 404 page)

`Turn repeat buyers into 5-star reviews.`

### Color palette

Primary brand color is **indigo**, conveying trust and professionalism without being a cliché SaaS blue.

| Token | Hex | Use |
|---|---|---|
| `primary` | `#4F46E5` (indigo-600) | buttons, links, active states |
| `primary-hover` | `#4338CA` (indigo-700) | hover on primary |
| `primary-soft` | `#EEF2FF` (indigo-50) | subtle backgrounds, badges |
| `success` | `#10B981` (emerald-500) | sent / completed |
| `warning` | `#F59E0B` (amber-500) | pending / in window |
| `danger` | `#EF4444` (red-500) | failed / errors |
| `info` | `#3B82F6` (blue-500) | manual / link methods |
| `neutral-50…900` | Tailwind slate | text, borders, surfaces |

Dark mode is **out of scope** for MVP. Light mode only. Note this clearly in `tailwind.config.ts` with a comment.

### Typography

- Primary font: **Inter** (variable). Load via `next/font/google` for performance.
- Monospace (for order IDs, ASINs, code): **JetBrains Mono** via `next/font/google`.
- Type scale (use Tailwind defaults):
  - Display: `text-4xl font-bold` (32px) — page H1
  - Heading: `text-2xl font-semibold` (24px) — section H2
  - Title: `text-lg font-semibold` (18px) — card titles
  - Body: `text-sm` (14px) — default
  - Caption: `text-xs text-slate-500` (12px) — secondary info

### Spacing and radii

- Stick to Tailwind's default spacing scale (multiples of 4px).
- Default radius: `rounded-lg` (8px) for cards, `rounded-md` (6px) for inputs, `rounded-full` for avatars and badges.
- Shadow scale: `shadow-sm` on cards, `shadow-md` on dropdowns, `shadow-lg` on modals.

### Voice (microcopy)

- Direct, action-oriented, no marketing fluff. "Upload orders" not "Get started with your order data".
- Honest about limits: "Amazon allows review requests 5–30 days after delivery." not "Premium scheduling magic".
- Empty states are encouraging, not preachy: "No repeat buyers yet — upload your latest orders to find them." not "It looks like you don't have any data".

## Files to produce

### `frontend/tailwind.config.ts`

- Extend the default theme with the color tokens above as CSS variables, so future dark-mode work is one-line away.
- Pull the brand colors into `theme.extend.colors` so utility classes like `bg-primary` work.
- Configure `content` paths for `app/`, `components/`, and `lib/`.

### `frontend/app/globals.css`

- Tailwind directives.
- CSS variables for the brand palette, defined under `:root`.
- Smooth scrolling, anti-aliasing, default body color (`slate-900` on `slate-50`).

### `frontend/lib/fonts.ts`

- Export configured `Inter` and `JetBrainsMono` from `next/font/google`.
- Applied in the root layout's `<body>` class.

### `frontend/components/ui/`

This is where shadcn primitives live. Install via shadcn CLI:

```bash
npx shadcn@latest add button input label form card dialog dropdown-menu \
  select checkbox radio-group switch textarea badge tooltip toast \
  separator sheet table tabs avatar skeleton popover command
```

Verify each component imports cleanly and uses the design tokens (you may need to lightly edit a few to use `bg-primary` instead of `bg-slate-900`).

### `frontend/components/layout/`

Three core layout components — these will be the most-reused pieces of the app.

#### `AppShell.tsx`

The wrapping layout for all `/dashboard/*` routes. Two-column on `md+`, single-column drawer on mobile.

```
┌─────────────────────────────────────────────────────────┐
│  ┌──── Sidebar ────┐  ┌──── Topbar ──────────────────┐  │
│  │ Logo            │  │ Shop switcher | User menu    │  │
│  │                 │  └──────────────────────────────┘  │
│  │ Uploads         │  ┌──────────────────────────────┐  │
│  │ Repeat Orders   │  │                              │  │
│  │ Review Requests │  │      page content            │  │
│  │ Settings        │  │      (children)              │  │
│  │                 │  │                              │  │
│  └─────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

- Sidebar width: 240px. Collapses to icon-only at 768–1024px. Hidden behind a hamburger drawer below 768px.
- Active route highlighted with `bg-primary-soft text-primary` and a 3px left border.
- The shop switcher and user menu in Topbar are stubs in this stage (they render but are wired in Stage 3 and Stage 1 respectively).

#### `PageHeader.tsx`

Standard header for every business page:

```tsx
<PageHeader
  title="Repeat orders"
  description="Customers who purchased a product more than once."
  actions={<Button>Export CSV</Button>}
/>
```

#### `EmptyState.tsx`

Reusable empty-state component:

```tsx
<EmptyState
  icon={<UploadCloud />}
  title="No orders yet"
  description="Upload an Amazon order export to get started."
  action={<Button>Upload file</Button>}
/>
```

Icon comes from lucide-react. Includes a soft circular background behind the icon (`bg-primary-soft`).

### `frontend/components/data/`

Specialized components used heavily by stages 2–5.

#### `StatCard.tsx`

KPI card for dashboards:

```tsx
<StatCard
  label="Repeat orders"
  value="1,518"
  hint="across 432 buyers"
  icon={<Repeat />}
/>
```

#### `StatusBadge.tsx`

Centralized badge for review-request status. Drives the color scheme for the whole app:

```tsx
<StatusBadge
  status="sent"
  method="manual"
/>
// renders: blue "Requested · manual"
```

Logic:
- `sent` + `manual` → blue, label "Requested · manual"
- `sent` + `link` → blue, label "Requested · link"
- `sent` + `api` → green, label "Requested · API"
- `pending` → amber, label "Pending"
- `failed` → red, label "Failed"
- null → **renders nothing** (returns `null`). Rationale: in a table where 90% of rows are unrequested, showing a "Not requested" badge on every row creates visual noise. The absence of a badge is the signal.

Export the color/label mapping as a separate const so other components can introspect it. Provide an opt-in `showEmpty` prop for cases (like a detail page) where the explicit "Not requested" badge is helpful — when set, the null case renders slate with the label.

#### `DataTableShell.tsx`

A wrapper around TanStack Table that the repeat-orders and review-requests pages will use. Provides:
- A consistent toolbar slot
- Skeleton loading state
- Empty-state fallback
- Pagination controls in a consistent location

The shell takes `columns`, `data`, `isLoading`, `emptyState`, `toolbar`, and `pagination` as props. Do not bake any business logic in here.

### `frontend/components/feedback/`

#### `Toaster.tsx`

Wraps shadcn's toast system. Mounted once in the root layout. Expose a `useToast` hook from `lib/toast.ts` with `success`, `error`, `info`, `warning` shortcuts.

#### `ConfirmDialog.tsx`

Modal confirmation primitive. Used by destructive or escalating actions:

```tsx
const confirmed = await confirm({
  title: "Mark 12 orders as requested?",
  description: "This cannot be undone.",
  confirmLabel: "Mark all",
  destructive: false,
});
```

Implement as a context provider + hook so any component can call `confirm()` without passing props through layers.

### `frontend/components/brand/`

#### `Logo.tsx`

Placeholder logo: a simple SVG wordmark `ReviewMaster` in the primary color with a small checkmark glyph. Two variants:
- `<Logo />` — full wordmark, ~32px tall
- `<Logo iconOnly />` — just the glyph, 24×24, for the collapsed sidebar

Use inline SVG, no external assets. Future replacement is one file.

### `frontend/app/layout.tsx`

Root layout: fonts, `<Toaster />`, theme provider (light only for now), error boundary fallback.

### `frontend/app/(auth)/layout.tsx`

A second layout group for unauthenticated routes (`/login`, `/register`). Centered card on a soft gradient background. Logo top-left, tagline below.

### `frontend/app/(dashboard)/layout.tsx`

Wraps `AppShell` around all authenticated routes.

### `frontend/app/not-found.tsx`

404 page. Friendly empty-state-style design: large icon, "We can't find that page.", link back to dashboard or login depending on auth state.

### `frontend/app/error.tsx`

500 / runtime error page. Apologetic copy, a "Try again" button (uses Next's `reset` prop), and a small "If this keeps happening, contact support." line.

### `frontend/app/(dashboard)/page.tsx`

A placeholder dashboard home. Just renders `<PageHeader title="Welcome to ReviewMaster" description="Pick a section from the sidebar to get started." />`. Stages 1–5 will replace or extend this.

### `frontend/lib/format.ts`

Centralized formatters that every page should use:
- `formatCurrency(amount, currency, locale?)` — uses `Intl.NumberFormat`
- `formatDateTime(iso, timezone?)` — uses `Intl.DateTimeFormat`; timezone defaults to user setting from context (wired in Stage 3)
- `formatRelative(iso)` — "2 hours ago" using a tiny inline helper, no extra dep
- `truncate(text, max)` — ellipsis truncation

## Storybook? — No

We do **not** add Storybook in this stage. It's overhead for MVP. Components are exercised in real pages from Stage 1 onward. Reconsider post-launch.

## Accessibility baseline

- Every interactive element has a visible focus ring (`focus-visible:ring-2 focus-visible:ring-primary`).
- All icons inside buttons have `aria-hidden="true"`; the button itself has an accessible label (visible text or `aria-label`).
- Color is never the only differentiator — status badges include text labels in addition to color.
- Minimum contrast: body text 4.5:1, large text 3:1. The chosen palette meets this on `slate-50` background.

Document these rules in `frontend/CONTRIBUTING.md` (create it if not present) so later stages don't drift.

## Tests

Only smoke tests in this stage — no business logic to verify.

- `frontend/components/__tests__/StatusBadge.test.tsx`: renders the right label and color class for each (status, method) combination.
- `frontend/components/__tests__/EmptyState.test.tsx`: renders title, description, and the action button if provided.

Use Vitest + Testing Library for frontend tests. Configure in `package.json` if not already.

## Acceptance checks

1. `npm run dev` boots and `/` redirects (eventually) to `/login` — for now, `/` can show a holding page that links to `/login` and `/dashboard`.
2. `/dashboard` (you'll need to visit it directly since auth isn't wired yet) shows the AppShell with sidebar, topbar, and the welcome placeholder.
3. Sidebar collapses to icon-only between 768–1024px; below 768px, a hamburger button opens a drawer.
4. `/some-bad-route` renders the 404 page with the correct copy and a working link back.
5. Throwing in any page (temporarily) shows `app/error.tsx` with the Try again button.
6. The shadcn primitives use the brand color — primary buttons are indigo-600, not the default slate.
7. Inter font is rendered (inspect with devtools); JetBrains Mono renders on a sample `<code>` element.
8. `npm run lint` is clean.
9. The component smoke tests pass: `npm test`.

## Out of scope

- Dark mode (post-MVP).
- Real logo design (we use a placeholder wordmark).
- Mobile-first redesign — we target desktop primary with reasonable mobile fallback. Detailed responsive polish happens in `stage_polish`.
- Internationalization. UI is English only.
- Storybook.
- Animations beyond standard shadcn transitions (covered in stage_polish if at all).
