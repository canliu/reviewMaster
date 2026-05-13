"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useShortcuts } from "@/lib/use-shortcuts";

export function ShortcutsDialog() {
  const { cheatsheetOpen, setCheatsheetOpen, bindings } = useShortcuts();
  return (
    <Dialog open={cheatsheetOpen} onOpenChange={setCheatsheetOpen}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
        </DialogHeader>
        <dl className="space-y-2">
          {bindings.map((b) => (
            <div
              key={b.combo}
              className="flex items-center justify-between gap-4 py-1.5 text-sm"
            >
              <dt className="text-muted-foreground">{b.description}</dt>
              <dd className="font-mono text-xs">
                {b.combo.split(" ").map((piece, i) => (
                  <span
                    key={i}
                    className="ml-1 rounded border border-border bg-muted px-1.5 py-0.5"
                  >
                    {piece}
                  </span>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
