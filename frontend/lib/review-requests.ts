import { api } from "@/lib/api";

export type RequestMethod = "manual" | "link" | "api";
export type RequestStatus = "pending" | "sent" | "failed";

export interface CreateResult {
  created: Array<{
    id: string;
    order_uuid: string;
    method: RequestMethod;
    status: RequestStatus;
    redirect_url: string | null;
  }>;
  skipped: Array<{ order_uuid: string; reason: string }>;
  errors: Array<{ order_uuid: string; code: string; reason: string }>;
}

export interface ReviewRequestListItem {
  id: string;
  order_uuid: string;
  method: RequestMethod;
  status: RequestStatus;
  requested_at: string;
  api_response: Record<string, unknown> | null;
  order_id: string;
  shop_site: string;
  asin: string | null;
  product_name: string | null;
  buyer_email: string | null;
  notes_count: number;
}

export interface ReviewRequestList {
  items: ReviewRequestListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface Note {
  id: string;
  order_uuid: string;
  review_request_id: string | null;
  note: string;
  kind: "user" | "system";
  created_at: string;
}

export interface ReviewRequestDetail {
  request: ReviewRequestListItem;
  notes: Note[];
}

export interface ListFilters {
  page?: number;
  page_size?: number;
  method?: RequestMethod;
  status?: RequestStatus;
  shop_site?: string;
  from_date?: string;
  to_date?: string;
}

export async function createReviewRequests(body: {
  order_uuids: string[];
  method: "manual" | "link";
  note?: string;
}): Promise<CreateResult> {
  const { data } = await api.post<CreateResult>("/api/review-requests", body);
  return data;
}

export async function confirmRequest(id: string): Promise<ReviewRequestListItem> {
  const { data } = await api.patch<ReviewRequestListItem>(
    `/api/review-requests/${id}/confirm`,
  );
  return data;
}

export async function confirmAsManual(
  id: string,
): Promise<ReviewRequestListItem> {
  const { data } = await api.patch<ReviewRequestListItem>(
    `/api/review-requests/${id}/confirm-as-manual`,
  );
  return data;
}

export async function listReviewRequests(
  filters: ListFilters,
): Promise<ReviewRequestList> {
  const { data } = await api.get<ReviewRequestList>("/api/review-requests", {
    params: filters,
  });
  return data;
}

export async function getReviewRequest(
  id: string,
): Promise<ReviewRequestDetail> {
  const { data } = await api.get<ReviewRequestDetail>(
    `/api/review-requests/${id}`,
  );
  return data;
}

export async function listNotes(orderUuid: string): Promise<Note[]> {
  const { data } = await api.get<Note[]>(`/api/orders/${orderUuid}/notes`);
  return data;
}

export async function addNote(
  orderUuid: string,
  note: string,
): Promise<Note> {
  const { data } = await api.post<Note>(`/api/orders/${orderUuid}/notes`, {
    note,
  });
  return data;
}

export function buildExportUrl(
  base: "repeat-orders" | "review-requests",
  filters: Record<string, string | number | boolean | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  }
  const apiBase =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8088";
  // The export.csv endpoint requires Authorization, so the browser can't
  // navigate to the URL directly. Callers should fetch with the api client
  // and trigger a blob download instead. This helper just returns the URL
  // for diagnostic/debug use.
  return `${apiBase}/api/${base}/export.csv?${params.toString()}`;
}

/** Trigger a CSV download in the browser by fetching with auth then saving
 *  the resulting blob. The browser's native download flow doesn't carry the
 *  Authorization header, so a plain anchor href wouldn't work. */
export async function downloadCsv(
  base: "repeat-orders" | "review-requests",
  filters: Record<string, string | number | boolean | undefined>,
  filename: string,
): Promise<void> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  }
  const response = await api.get(`/api/${base}/export.csv`, {
    params,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
