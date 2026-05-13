import { describe, beforeEach, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useOnboarding } from "@/lib/use-onboarding";

const KEY = "onboarding_complete";

describe("useOnboarding", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("starts at step 1 when the flag is unset", () => {
    const { result } = renderHook(() => useOnboarding());
    expect(result.current.complete).toBe(false);
    expect(result.current.step).toBe(1);
  });

  it("advances through steps 1 → 2 → 3 then marks complete", () => {
    const { result } = renderHook(() => useOnboarding());
    act(() => result.current.next());
    expect(result.current.step).toBe(2);
    act(() => result.current.next());
    expect(result.current.step).toBe(3);
    act(() => result.current.next());
    expect(result.current.complete).toBe(true);
    expect(window.localStorage.getItem(KEY)).toBe("true");
  });

  it("skip() marks complete immediately", () => {
    const { result } = renderHook(() => useOnboarding());
    act(() => result.current.skip());
    expect(result.current.complete).toBe(true);
    expect(window.localStorage.getItem(KEY)).toBe("true");
  });

  it("reset() clears the flag and returns to step 1", () => {
    window.localStorage.setItem(KEY, "true");
    const { result } = renderHook(() => useOnboarding());
    act(() => result.current.reset());
    expect(result.current.complete).toBe(false);
    expect(result.current.step).toBe(1);
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });
});
