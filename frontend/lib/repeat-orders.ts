import { api } from "@/lib/api";

export type RepeatSort =
  | "last_order_desc"
  | "purchase_count_desc"
  | "delivery_asc";

export interface ActiveReview {
  id: string;
  status: "sent" | "pending";
  method: "manual" | "link" | "api";
  requested_at: string;
}

export interface RepeatOrderItem {
  order_uuid: string;
  order_id: string;
  shop_site: string;
  asin: string | null;
  spu: string | null;
  product_name: string | null;
  product_title_short: string | null;
  order_type: string | null;
  buyer_email: string | null;
  buyer_key: string;
  order_time_utc: string | null;
  estimated_delivery_utc: string | null;
  item_price: number | null;
  currency: string | null;
  quantity: number | null;
  ship_city: string | null;
  ship_state: string | null;
  ship_country: string | null;
  purchase_index: number;
  total_purchases: number;
  review_request: ActiveReview | null;
  can_request_review: boolean;
  can_request_reason: string | null;
}

export interface RepeatOrderSummary {
  total_repeat_orders: number;
  total_repeat_buyers: number;
  total_repeat_products: number;
  in_review_window: number;
  already_requested: number;
}

export interface RepeatOrderList {
  total: number;
  page: number;
  page_size: number;
  items: RepeatOrderItem[];
}

export interface BuyerHistoryOrder {
  order_id: string;
  asin: string | null;
  product_name: string | null;
  order_time_utc: string | null;
  item_price: number | null;
  quantity: number | null;
  review_request_status: "sent" | "pending" | null;
}

export interface BuyerHistory {
  buyer_key: string;
  buyer_email: string | null;
  total_orders_all_products: number;
  orders_returned: number;
  has_more: boolean;
  orders: BuyerHistoryOrder[];
}

export interface RepeatOrderDetail {
  order: RepeatOrderItem;
  buyer_history: BuyerHistory;
}

export interface RepeatOrderFilters {
  page: number;
  page_size: number;
  asin?: string;
  product_search?: string;
  has_review_request?: boolean;
  in_window?: boolean;
  min_purchases?: number;
  sort: RepeatSort;
}

export async function fetchSummary(): Promise<RepeatOrderSummary> {
  const { data } = await api.get<RepeatOrderSummary>(
    "/api/repeat-orders/summary",
  );
  return data;
}

export async function fetchList(
  filters: RepeatOrderFilters,
): Promise<RepeatOrderList> {
  const params: Record<string, string | number | boolean> = {
    page: filters.page,
    page_size: filters.page_size,
    sort: filters.sort,
  };
  if (filters.asin) params.asin = filters.asin;
  if (filters.product_search) params.product_search = filters.product_search;
  if (filters.has_review_request !== undefined)
    params.has_review_request = filters.has_review_request;
  if (filters.in_window !== undefined) params.in_window = filters.in_window;
  if (filters.min_purchases !== undefined)
    params.min_purchases = filters.min_purchases;
  const { data } = await api.get<RepeatOrderList>("/api/repeat-orders", {
    params,
  });
  return data;
}

export async function fetchDetail(
  orderUuid: string,
): Promise<RepeatOrderDetail> {
  const { data } = await api.get<RepeatOrderDetail>(
    `/api/repeat-orders/${orderUuid}`,
  );
  return data;
}
