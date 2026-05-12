import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { CurrentUserProvider } from "@/lib/use-current-user";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <CurrentUserProvider>
      <AppShell>{children}</AppShell>
    </CurrentUserProvider>
  );
}
