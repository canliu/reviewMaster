import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { CurrentUserProvider } from "@/lib/use-current-user";
import { SettingsProvider } from "@/lib/use-settings";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <CurrentUserProvider>
      <SettingsProvider>
        <AppShell>{children}</AppShell>
      </SettingsProvider>
    </CurrentUserProvider>
  );
}
