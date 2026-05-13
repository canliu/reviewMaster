import type { ReactNode } from "react";

import { ShortcutsDialog } from "@/components/feedback/ShortcutsDialog";
import { AppShell } from "@/components/layout/AppShell";
import { CurrentUserProvider } from "@/lib/use-current-user";
import { SettingsProvider } from "@/lib/use-settings";
import { ShortcutsProvider } from "@/lib/use-shortcuts";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <CurrentUserProvider>
      <SettingsProvider>
        <ShortcutsProvider>
          {/* Skip-to-content link — first focusable element for keyboard users. */}
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
          >
            Skip to main content
          </a>
          <AppShell>{children}</AppShell>
          <ShortcutsDialog />
        </ShortcutsProvider>
      </SettingsProvider>
    </CurrentUserProvider>
  );
}
