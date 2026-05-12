"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Logo } from "@/components/brand/Logo";
import { isAuthenticated } from "@/lib/auth";

// `/` is just a redirect surface. Auth check happens on the client because
// tokens live in localStorage and aren't readable from server / middleware.
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(isAuthenticated() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gradient-to-b from-primary-soft to-background px-4 py-12">
      <Logo />
      <p className="text-sm text-muted-foreground">Loading…</p>
    </main>
  );
}
