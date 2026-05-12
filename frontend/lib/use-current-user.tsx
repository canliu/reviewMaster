"use client";

import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { AuthUser, clearTokens, getAccessToken, getMe } from "@/lib/auth";

interface CurrentUserContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = async () => {
    if (!getAccessToken()) {
      setUser(null);
      setIsLoading(false);
      router.replace("/login");
      return;
    }
    try {
      const fetched = await getMe();
      setUser(fetched);
    } catch {
      // /me failed even after the axios interceptor's refresh attempt; bounce.
      clearTokens();
      setUser(null);
      router.replace("/login");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <CurrentUserContext.Provider value={{ user, isLoading, refresh: load }}>
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser(): CurrentUserContextValue {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error(
      "useCurrentUser must be used inside <CurrentUserProvider>",
    );
  }
  return ctx;
}
