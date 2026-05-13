"use client";

import { useCallback, useEffect, useState } from "react";

// Client-only flag: localStorage `onboarding_complete`. The dashboard renders
// the OnboardingCard when this is unset AND the user has zero uploads.
const KEY = "onboarding_complete";

export type OnboardingStep = 1 | 2 | 3;

export function useOnboarding(): {
  complete: boolean;
  step: OnboardingStep;
  next: () => void;
  skip: () => void;
  reset: () => void;
} {
  const [complete, setComplete] = useState(true); // start as complete to avoid SSR flash
  const [step, setStep] = useState<OnboardingStep>(1);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(KEY);
    setComplete(stored === "true");
  }, []);

  const next = useCallback(() => {
    setStep((s) => {
      if (s === 3) {
        if (typeof window !== "undefined") {
          window.localStorage.setItem(KEY, "true");
        }
        setComplete(true);
        return 3;
      }
      return (s + 1) as OnboardingStep;
    });
  }, []);

  const skip = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(KEY, "true");
    }
    setComplete(true);
  }, []);

  const reset = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(KEY);
    }
    setStep(1);
    setComplete(false);
  }, []);

  return { complete, step, next, skip, reset };
}
