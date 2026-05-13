import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";

import { ShortcutsProvider, useShortcuts } from "@/lib/use-shortcuts";
import { ShortcutsDialog } from "@/components/feedback/ShortcutsDialog";

// next/navigation's useRouter needs a stub for these tests.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

function Probe() {
  const { bindings } = useShortcuts();
  return (
    <ul data-testid="bindings">
      {bindings.map((b) => (
        <li key={b.combo}>{b.combo}</li>
      ))}
    </ul>
  );
}

describe("useShortcuts", () => {
  it("exposes the expected binding set", () => {
    render(
      <ShortcutsProvider>
        <Probe />
        <ShortcutsDialog />
      </ShortcutsProvider>,
    );
    const ul = screen.getByTestId("bindings");
    const combos = Array.from(ul.querySelectorAll("li")).map((li) =>
      li.textContent?.trim(),
    );
    expect(combos).toEqual(
      expect.arrayContaining(["?", "g u", "g r", "g q", "g s", "/"]),
    );
  });

  it("opens the cheat sheet via context", () => {
    // Hotkey integration with react-hotkeys-hook is exercised by hand in dev;
    // here we just verify the state machine: flipping the context value
    // mounts the dialog content.
    function Toggle() {
      const { setCheatsheetOpen } = useShortcuts();
      return (
        <button type="button" onClick={() => setCheatsheetOpen(true)}>
          open
        </button>
      );
    }

    render(
      <ShortcutsProvider>
        <Toggle />
        <ShortcutsDialog />
      </ShortcutsProvider>,
    );

    expect(screen.queryByText(/Keyboard shortcuts/i)).toBeNull();
    act(() => {
      fireEvent.click(screen.getByText("open"));
    });
    expect(screen.getByText(/Keyboard shortcuts/i)).toBeInTheDocument();
  });
});
