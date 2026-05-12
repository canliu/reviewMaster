import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";

const ACCESS_KEY = "rm.access_token";
const REFRESH_KEY = "rm.refresh_token";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8088",
  headers: { "Content-Type": "application/json" },
});

const isBrowser = () => typeof window !== "undefined";

// ---- Request: attach the access token ----
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (isBrowser()) {
    const token = localStorage.getItem(ACCESS_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ---- Response: single-attempt refresh-on-401 ----
//
// Tag we add to retried requests so we don't loop if the refresh itself 401s.
interface RetryConfig extends AxiosRequestConfig {
  _retried?: boolean;
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!isBrowser()) return null;
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    // Bare axios call (not `api`) so we don't recurse through the interceptor.
    const { data } = await axios.post<{ access_token: string }>(
      `${api.defaults.baseURL}/api/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { "Content-Type": "application/json" } },
    );
    localStorage.setItem(ACCESS_KEY, data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    const status = error.response?.status;

    // Don't refresh on /api/auth/* paths — login/register failures are not
    // session-expiry signals, and refreshing the refresh endpoint is silly.
    const isAuthRoute = original?.url?.startsWith("/api/auth/") ?? false;

    if (status === 401 && original && !original._retried && !isAuthRoute) {
      original._retried = true;
      refreshInFlight = refreshInFlight ?? refreshAccessToken();
      const newToken = await refreshInFlight;
      refreshInFlight = null;

      if (newToken) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization =
          `Bearer ${newToken}`;
        return api(original);
      }

      // Refresh failed — clear tokens and bounce to /login. Avoid the bounce
      // if we're already on an auth page so error toasts can render.
      if (isBrowser()) {
        localStorage.removeItem(ACCESS_KEY);
        localStorage.removeItem(REFRESH_KEY);
        const onAuthPage =
          window.location.pathname.startsWith("/login") ||
          window.location.pathname.startsWith("/register");
        if (!onAuthPage) {
          window.location.href = "/login";
        }
      }
    }

    return Promise.reject(error);
  },
);
