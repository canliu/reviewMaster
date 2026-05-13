# Mobile / responsive status

We target 375px (iPhone SE) and up. Last verified after stage_polish.

## Verified working

- Sidebar collapses into a drawer at `<768px` (hamburger in the top bar).
- Forms (login, register, settings) reflow to single-column.
- Toaster (Sonner) positions correctly on narrow viewports.
- Skip-to-content link appears on focus and lands on `#main-content`.

## Known gaps (deferred)

- **Repeat-orders table at `<768px`** — still uses horizontal scroll, not
  the card list described in `prompts/stage_polish.md` §4. Scope was
  deliberately punted; converting the table to a card layout is a sizable
  rewrite. The page is usable but cramped.
- **Long shop_site strings** can overflow the top-bar shop switcher trigger
  on the smallest viewports. Text truncates with ellipsis; acceptable but
  not pretty.

## Test matrix

| Viewport | Sidebar | Tables | Forms | Notes |
|---|---|---|---|---|
| 375×667 (iPhone SE) | drawer ✓ | scrolls | ✓ | table is cramped |
| 414×896 (iPhone 12) | drawer ✓ | scrolls | ✓ | OK |
| 768×1024 (iPad) | sidebar visible ✓ | OK | ✓ | OK |
| 1280×800 | ✓ | ✓ | ✓ | OK |
| 1920×1080 | ✓ | ✓ | ✓ | OK |
