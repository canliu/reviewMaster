# Frontend contributing guide

This guide covers conventions that only apply to the `frontend/` workspace.
For repo-wide rules (branching, commits, stage workflow) see the root
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Design tokens, not raw colors

Use the brand tokens defined in `tailwind.config.ts` / `app/globals.css`:

- `bg-primary`, `text-primary`, `bg-primary-soft` — brand indigo
- `bg-success`, `bg-warning`, `bg-danger`, `bg-info` — status palette
- `text-foreground`, `text-muted-foreground` — body and secondary text
- `border-border` — default border

Do **not** reach into Tailwind's raw palette (`bg-indigo-600`, `text-slate-500`)
inside components. If a needed shade isn't in the token map yet, extend the
token map first.

## Accessibility baseline

These rules apply to every interactive element. Stage `polish` adds the
formal a11y audit but the foundation is set here.

1. **Visible focus**: every focusable element shows a focus ring. The global
   `:focus-visible` rule in `globals.css` provides this for free — don't add
   `outline-none` without replacing the ring.
2. **Icon-only buttons** have an `aria-label` so screen readers announce
   them. The icon itself is `aria-hidden="true"`.
3. **Color is never the only signal**: status badges include both color and
   a text label. Tables show "Failed" not just a red dot.
4. **Contrast**: body text 4.5:1, large text 3:1. The chosen palette meets
   this on `slate-50` background. Don't introduce off-palette text colors
   without checking with a contrast tool.
5. **Keyboard navigation**: every clickable element must be reachable with
   Tab. If you write a custom interactive element (rather than using a
   shadcn primitive), set `role` and key handlers explicitly.

## Formatters

All currency, date, and time values flow through `lib/format.ts`. Do not
inline `toLocaleString` calls — locale and timezone handling must stay in
one file so the user-settings work in Stage 3 can wire a single seam.

## Toasts

Call `useToast()` from `lib/toast.ts` for `success / error / info / warning`.
Don't import `sonner` directly so the toast library can be swapped later
without touching call sites.

## Confirmation dialogs

For "are you sure?" interactions, use `useConfirm()` from
`components/feedback/ConfirmDialog.tsx`. Avoid `window.confirm` (it's an
OS-level modal and doesn't match the design system).

## Testing

- Vitest + Testing Library — see `vitest.config.ts`. Run with
  `docker compose exec frontend npm test`.
- Smoke tests live next to features under `components/**/__tests__/`.
- Only add a test when the component has logic worth pinning down
  (e.g. `StatusBadge`'s status×method matrix). Visual-only components
  don't need unit tests; rely on `npm run build` + manual click-through.
