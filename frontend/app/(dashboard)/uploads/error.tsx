"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function UploadsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex flex-col items-center gap-4 rounded-lg border border-border bg-card p-12 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft text-danger">
        <AlertTriangle className="h-7 w-7" aria-hidden="true" />
      </div>
      <h2 className="text-lg font-semibold">Couldn&apos;t load uploads</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        The server might be busy or unreachable. Try again, or head back to
        the dashboard.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={reset}>Retry</Button>
        <Button variant="outline" asChild>
          <Link href="/dashboard">Go to dashboard</Link>
        </Button>
      </div>
    </main>
  );
}
