"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { useHotkeys } from "react-hotkeys-hook";

// Shape of a single binding; the cheat-sheet dialog reads this map so we
// don't have to declare each key twice.
export interface ShortcutBinding {
  combo: string;
  description: string;
  action: () => void;
}

interface ShortcutsContextValue {
  cheatsheetOpen: boolean;
  setCheatsheetOpen: (open: boolean) => void;
  bindings: ShortcutBinding[];
}

const ShortcutsContext = createContext<ShortcutsContextValue | null>(null);

export function ShortcutsProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [cheatsheetOpen, setCheatsheetOpen] = useState(false);

  const focusPageSearch = useCallback(() => {
    // Convention: the page's primary search input is the first <input> with
    // id ending in "-filter" or placeholder mentioning "search".
    const candidate =
      document.querySelector<HTMLInputElement>('input[id$="-filter"]') ??
      document.querySelector<HTMLInputElement>(
        'input[placeholder*="search" i]',
      );
    candidate?.focus();
    candidate?.select();
  }, []);

  const bindings: ShortcutBinding[] = [
    {
      combo: "?",
      description: "Open this shortcuts list",
      action: () => setCheatsheetOpen(true),
    },
    {
      combo: "g u",
      description: "Go to Uploads",
      action: () => router.push("/uploads"),
    },
    {
      combo: "g r",
      description: "Go to Repeat orders",
      action: () => router.push("/repeat-orders"),
    },
    {
      combo: "g q",
      description: "Go to Review requests",
      action: () => router.push("/review-requests"),
    },
    {
      combo: "g s",
      description: "Go to Settings",
      action: () => router.push("/settings"),
    },
    {
      combo: "/",
      description: "Focus search on this page",
      action: focusPageSearch,
    },
  ];

  // Mount each binding through useHotkeys. The library scopes by key; if the
  // user is typing into an input, useHotkeys ignores by default for plain
  // letter keys.
  useHotkeys("shift+slash", () => setCheatsheetOpen((open) => !open), {
    preventDefault: true,
  });
  useHotkeys(
    "/",
    (e) => {
      e.preventDefault();
      focusPageSearch();
    },
  );
  useHotkeys("g+u", () => router.push("/uploads"));
  useHotkeys("g+r", () => router.push("/repeat-orders"));
  useHotkeys("g+q", () => router.push("/review-requests"));
  useHotkeys("g+s", () => router.push("/settings"));

  // Escape: shadcn Dialog/Sheet handle their own closes; we just close the
  // cheat sheet here in case nothing else owned it.
  useEffect(() => {
    if (!cheatsheetOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCheatsheetOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cheatsheetOpen]);

  return (
    <ShortcutsContext.Provider
      value={{ cheatsheetOpen, setCheatsheetOpen, bindings }}
    >
      {children}
    </ShortcutsContext.Provider>
  );
}

export function useShortcuts(): ShortcutsContextValue {
  const ctx = useContext(ShortcutsContext);
  if (!ctx) {
    throw new Error("useShortcuts must be used inside <ShortcutsProvider>");
  }
  return ctx;
}
