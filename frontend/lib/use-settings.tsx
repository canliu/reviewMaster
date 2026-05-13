"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { Settings, SettingsPatch, getSettings, patchSettings } from "@/lib/settings";

interface SettingsContextValue {
  settings: Settings | null;
  isLoading: boolean;
  mutate: (patch: SettingsPatch) => Promise<Settings>;
  refresh: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setSettings(await getSettings());
    } catch {
      // The dashboard layout's CurrentUserProvider handles redirect-on-401.
      // Anything else here is a transient failure; the UI can show stale.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const mutate = useCallback(async (patch: SettingsPatch) => {
    const next = await patchSettings(patch);
    setSettings(next);
    return next;
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, isLoading, mutate, refresh: load }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettings must be used inside <SettingsProvider>");
  }
  return ctx;
}
