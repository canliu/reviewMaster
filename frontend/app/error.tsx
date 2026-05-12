"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Stage 7 wires Sentry. For now, keep a console breadcrumb so devs see it.
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-gradient-to-b from-primary-soft to-background px-4 py-12 text-center">
      <div
        aria-hidden="true"
        className="flex h-16 w-16 items-center justify-center rounded-full bg-danger-soft text-danger"
      >
        <AlertTriangle className="h-8 w-8" />
      </div>
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">
          Something went wrong.
        </h1>
        <p className="max-w-md text-muted-foreground">
          We&apos;ve logged the error. Try again — if this keeps happening,
          contact support.
        </p>
      </div>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
