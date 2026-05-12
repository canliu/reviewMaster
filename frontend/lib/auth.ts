// Auth wrapper. Tokens live in localStorage — acceptable for MVP but
// vulnerable to XSS. Stage 7 should consider httpOnly cookies.
import { api } from "@/lib/api";

const ACCESS_KEY = "rm.access_token";
const REFRESH_KEY = "rm.refresh_token";

export interface AuthUser {
  id: string;
  email: string;
  timezone: string;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

const isBrowser = () => typeof window !== "undefined";

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenPair): void {
  if (!isBrowser()) return;
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function setAccessToken(token: string): void {
  if (!isBrowser()) return;
  localStorage.setItem(ACCESS_KEY, token);
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

export async function register(
  email: string,
  password: string,
): Promise<AuthUser> {
  const { data } = await api.post<TokenPair>("/api/auth/register", {
    email,
    password,
  });
  setTokens(data);
  return getMe();
}

export async function login(
  email: string,
  password: string,
): Promise<AuthUser> {
  const { data } = await api.post<TokenPair>("/api/auth/login", {
    email,
    password,
  });
  setTokens(data);
  return getMe();
}

export async function logout(): Promise<void> {
  // Try to inform the server so future revocation infra has a hook, but
  // clearing tokens is the source-of-truth either way.
  try {
    await api.post("/api/auth/logout");
  } catch {
    /* ignore */
  }
  clearTokens();
}

export async function getMe(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>("/api/auth/me");
  return data;
}
