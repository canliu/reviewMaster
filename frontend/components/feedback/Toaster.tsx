"use client";

import { Toaster as SonnerToaster } from "sonner";

// Single toast surface for the whole app. Mount once in root layout.
// Wiring callers to Sonner directly is fine, but most code should go through
// `useToast()` in `lib/toast.ts` for vocabulary consistency.
export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: "rounded-lg border border-border shadow-md",
        },
      }}
    />
  );
}
