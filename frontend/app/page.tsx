import Link from "next/link";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";

// Holding page. Stage 1 wires `/` to redirect based on auth state.
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-gradient-to-b from-primary-soft to-background px-4 py-12">
      <Logo />
      <p className="max-w-md text-center text-lg text-muted-foreground">
        Turn repeat buyers into 5-star reviews.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button asChild>
          <Link href="/dashboard">Open dashboard</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/login">Sign in</Link>
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Pre-MVP, under construction.
      </p>
    </main>
  );
}
