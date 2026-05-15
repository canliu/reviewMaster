import { api } from "@/lib/api";

export type RepeatGrain = "asin" | "spu" | "product_name";

export interface ScopeEntry {
  value: string;
  label: string;
  type: "shop" | "marketplace";
  marketplace: string | null;
}

export interface Settings {
  active_shop_site: string | null;
  repeat_grain: RepeatGrain;
  excluded_order_types: string[];
  timezone: string;
  available_shop_sites: string[];
  available_order_types: string[];
  available_scopes: ScopeEntry[];
}

export interface SettingsPatch {
  active_shop_site?: string | null;
  repeat_grain?: RepeatGrain;
  excluded_order_types?: string[];
  timezone?: string;
}

export interface RepeatPreview {
  repeat_buyer_count: number;
  repeat_order_count: number;
}

export async function getSettings(): Promise<Settings> {
  const { data } = await api.get<Settings>("/api/settings");
  return data;
}

export async function patchSettings(body: SettingsPatch): Promise<Settings> {
  const { data } = await api.patch<Settings>("/api/settings", body);
  return data;
}

export async function getRepeatPreview(
  grain: RepeatGrain,
): Promise<RepeatPreview> {
  const { data } = await api.get<RepeatPreview>("/api/repeat-orders/preview", {
    params: { grain },
  });
  return data;
}

// Hand-curated list of common IANA zones — full DB is ~600 entries.
export const COMMON_TIMEZONES: ReadonlyArray<string> = [
  "UTC",
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Toronto",
  "America/Mexico_City",
  "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires",
  "Europe/London",
  "Europe/Dublin",
  "Europe/Lisbon",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Amsterdam",
  "Europe/Madrid",
  "Europe/Rome",
  "Europe/Stockholm",
  "Europe/Warsaw",
  "Europe/Athens",
  "Europe/Istanbul",
  "Europe/Moscow",
  "Africa/Cairo",
  "Africa/Lagos",
  "Africa/Johannesburg",
  "Asia/Jerusalem",
  "Asia/Dubai",
  "Asia/Karachi",
  "Asia/Kolkata",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Taipei",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Perth",
  "Australia/Adelaide",
  "Australia/Sydney",
  "Pacific/Auckland",
];
