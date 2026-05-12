import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/brand/Logo";

// Layout for the unauthenticated route group: /login, /register, /reset.
// Stages 1 onward add pages inside (auth)/.
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-primary-soft to-background">
      <header className="px-6 py-5">
        <Link href="/" aria-label="ReviewMaster home">
          <Logo />
        </Link>
        <p className="mt-2 text-sm text-muted-foreground">
          Turn repeat buyers into 5-star reviews.
        </p>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-8">
        <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-sm">
          {children}
        </div>
      </main>
    </div>
  );
}
