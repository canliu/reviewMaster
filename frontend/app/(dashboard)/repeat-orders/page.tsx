"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AxiosError } from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckSquare,
  Download,
  ExternalLink,
  ListChecks,
  Repeat,
  Send,
  Square,
  Users,
} from "lucide-react";

import { LinkConfirmDialog } from "@/components/feedback/LinkConfirmDialog";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/data/StatCard";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatCurrency, formatDateTime } from "@/lib/format";
import {
  RepeatOrderItem,
  RepeatSort,
  fetchDetail,
  fetchList,
  fetchSummary,
} from "@/lib/repeat-orders";
import {
  CreateResult,
  confirmAsManual,
  confirmRequest,
  createReviewRequests,
  downloadCsv,
} from "@/lib/review-requests";
import { listSpApiCredentials } from "@/lib/sp-api";
import { useToast } from "@/lib/toast";
import { useDebounce } from "@/lib/use-debounce";
import { useSettings } from "@/lib/use-settings";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

interface UrlFilters {
  page: number;
  asin: string;
  product_search: string;
  has_review_request: "" | "true" | "false";
  in_window: "" | "true" | "false";
  min_purchases: number;
  sort: RepeatSort;
}

const DEFAULT_FILTERS: UrlFilters = {
  page: 1,
  asin: "",
  product_search: "",
  has_review_request: "",
  in_window: "",
  min_purchases: 2,
  sort: "last_order_desc",
};

function parseFilters(params: URLSearchParams): UrlFilters {
  const get = (k: keyof UrlFilters) => params.get(k as string) ?? "";
  const hr = get("has_review_request");
  const iw = get("in_window");
  const sort = get("sort") as RepeatSort;
  return {
    page: Number(params.get("page")) || 1,
    asin: get("asin"),
    product_search: get("product_search"),
    has_review_request:
      hr === "true" ? "true" : hr === "false" ? "false" : "",
    in_window: iw === "true" ? "true" : iw === "false" ? "false" : "",
    min_purchases: Number(params.get("min_purchases")) || 2,
    sort: ["last_order_desc", "purchase_count_desc", "delivery_asc"].includes(
      sort,
    )
      ? sort
      : "last_order_desc",
  };
}

function RepeatOrdersPageInner() {
  const router = useRouter();
  const search = useSearchParams();
  const { settings } = useSettings();

  const urlFilters = useMemo(() => parseFilters(search), [search]);

  // ASIN and product_search debounce locally before hitting the URL.
  const [asinDraft, setAsinDraft] = useState(urlFilters.asin);
  const [searchDraft, setSearchDraft] = useState(urlFilters.product_search);
  const asinDebounced = useDebounce(asinDraft, 300);
  const searchDebounced = useDebounce(searchDraft, 300);

  useEffect(() => {
    if (asinDebounced !== urlFilters.asin) {
      updateParam("asin", asinDebounced);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asinDebounced]);
  useEffect(() => {
    if (searchDebounced !== urlFilters.product_search) {
      updateParam("product_search", searchDebounced);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDebounced]);

  function updateParam(key: string, value: string | number) {
    const next = new URLSearchParams(search);
    if (value === "" || value === null || value === undefined) {
      next.delete(key);
    } else {
      next.set(key, String(value));
    }
    // Resetting filters always resets page.
    if (key !== "page") next.delete("page");
    router.replace(`/repeat-orders?${next.toString()}`, { scroll: false });
  }

  const apiFilters = useMemo(
    () => ({
      page: urlFilters.page,
      page_size: PAGE_SIZE,
      asin: urlFilters.asin || undefined,
      product_search: urlFilters.product_search || undefined,
      has_review_request:
        urlFilters.has_review_request === ""
          ? undefined
          : urlFilters.has_review_request === "true",
      in_window:
        urlFilters.in_window === ""
          ? undefined
          : urlFilters.in_window === "true",
      min_purchases: urlFilters.min_purchases,
      sort: urlFilters.sort,
    }),
    [urlFilters],
  );

  const summaryQuery = useQuery({
    queryKey: ["repeat-orders-summary", settings?.active_shop_site, settings?.repeat_grain, settings?.excluded_order_types?.join(",")],
    queryFn: fetchSummary,
    enabled: Boolean(settings?.active_shop_site),
  });

  const listQuery = useQuery({
    queryKey: [
      "repeat-orders",
      settings?.active_shop_site,
      settings?.repeat_grain,
      settings?.excluded_order_types?.join(","),
      apiFilters,
    ],
    queryFn: () => fetchList(apiFilters),
    enabled: Boolean(settings?.active_shop_site),
    placeholderData: (prev) => prev,
    // Poll every 3s while any visible row has a pending request — off otherwise.
    refetchInterval: (q) => {
      const data = q.state.data as { items?: RepeatOrderItem[] } | undefined;
      const hasPending = (data?.items ?? []).some(
        (it: RepeatOrderItem) => it.review_request?.status === "pending",
      );
      return hasPending ? 3000 : false;
    },
  });

  // SP-API config — used to enable/disable the API-send action per row.
  const spApiQuery = useQuery({
    queryKey: ["sp-api-credentials"],
    queryFn: listSpApiCredentials,
  });
  const configuredSpApiShops = new Set(
    (spApiQuery.data?.items ?? []).map((c) => c.shop_site),
  );

  // Row selection — local state, reset on page change.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  useEffect(() => {
    setSelected(new Set());
  }, [urlFilters.page, settings?.active_shop_site]);

  const [detailUuid, setDetailUuid] = useState<string | null>(null);
  const [linkModal, setLinkModal] = useState<{
    requestId: string;
    orderUuid: string;
    redirectUrl: string | null;
  } | null>(null);

  const queryClient = useQueryClient();
  const toast = useToast();

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["repeat-orders"] });
    void queryClient.invalidateQueries({
      queryKey: ["repeat-orders-summary"],
    });
  };

  function reportResults(result: CreateResult) {
    const { created, skipped, errors } = result;
    if (created.length > 0) {
      toast.success(
        `Created ${created.length} review request${created.length === 1 ? "" : "s"}`,
        skipped.length || errors.length
          ? `Skipped ${skipped.length}, errors ${errors.length}.`
          : undefined,
      );
    } else if (skipped.length > 0 && errors.length === 0) {
      toast.info(
        "Already requested",
        `${skipped.length} order${skipped.length === 1 ? " was" : "s were"} skipped.`,
      );
    } else if (errors.length > 0) {
      toast.error(
        "Couldn't request review",
        errors.map((e) => e.reason).join("; "),
      );
    }
  }

  const manualMutation = useMutation({
    mutationFn: (orderUuids: string[]) =>
      createReviewRequests({ order_uuids: orderUuids, method: "manual" }),
    onSuccess: (result) => {
      reportResults(result);
      refresh();
      setSelected(new Set());
    },
    onError: () => {
      toast.error("Couldn't mark", "Try again.");
    },
  });

  const linkMutation = useMutation({
    mutationFn: (orderUuid: string) =>
      createReviewRequests({ order_uuids: [orderUuid], method: "link" }),
    onSuccess: (result, orderUuid) => {
      const created = result.created[0];
      if (created) {
        if (created.redirect_url) {
          window.open(created.redirect_url, "_blank", "noopener,noreferrer");
        }
        setLinkModal({
          requestId: created.id,
          orderUuid,
          redirectUrl: created.redirect_url,
        });
      }
      reportResults(result);
      refresh();
    },
    onError: (err) => {
      const detail =
        (err as AxiosError<{ detail?: string }>).response?.data?.detail ??
        "Try again.";
      toast.error("Couldn't open Amazon", detail);
    },
  });

  const confirmLink = useMutation({
    mutationFn: confirmRequest,
    onSuccess: () => {
      toast.success("Marked as requested");
      setLinkModal(null);
      refresh();
    },
    onError: () => toast.error("Couldn't confirm", "Try again."),
  });

  const apiMutation = useMutation({
    mutationFn: (orderUuids: string[]) =>
      createReviewRequests({ order_uuids: orderUuids, method: "api" }),
    onSuccess: (result) => {
      reportResults(result);
      refresh();
      setSelected(new Set());
    },
    onError: (err) => {
      const detail =
        (err as AxiosError<{ detail?: string }>).response?.data?.detail ??
        "Try again.";
      toast.error("Couldn't send via API", detail);
    },
  });

  const confirmAsManualMut = useMutation({
    mutationFn: confirmAsManual,
    onSuccess: () => {
      toast.success("Marked as manual");
      setLinkModal(null);
      refresh();
    },
    onError: () => toast.error("Couldn't confirm", "Try again."),
  });

  // ---- Export popover state ----
  const [exportShop, setExportShop] = useState<string>("");
  const [exportStatus, setExportStatus] = useState<string>("any");
  useEffect(() => {
    // Initialize the export-shop picker to the active shop once settings load.
    if (settings?.active_shop_site && !exportShop) {
      setExportShop(settings.active_shop_site);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings?.active_shop_site]);

  async function handleExport() {
    try {
      const exportFilters = {
        ...apiFilters,
        shop_site_override: exportShop || undefined,
        request_status:
          exportStatus === "any" ? undefined : exportStatus,
      };
      // The shop_site_override and request_status filters take precedence
      // over the page's active-shop / has_review_request scoping.
      const shop = exportShop || "all";
      const statusPart = exportStatus === "any" ? "any" : exportStatus;
      await downloadCsv(
        "repeat-orders",
        exportFilters as Record<string, string | number | boolean | undefined>,
        `repeat-orders-${shop.replace(":", "-")}-${statusPart}-${new Date()
          .toISOString()
          .slice(0, 10)}.csv`,
      );
    } catch {
      toast.error("Export failed", "Try again.");
    }
  }

  // ---- empty / loading shells ----
  if (settings && !settings.active_shop_site) {
    return (
      <>
        <PageHeader title="Repeat orders" />
        <EmptyState
          icon={<Repeat />}
          title="No shop selected"
          description="Upload an Amazon order file to populate your shops, then pick one in the header."
          action={
            <Button asChild>
              <Link href="/uploads">Go to uploads</Link>
            </Button>
          }
        />
      </>
    );
  }

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const pageCount = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;
  const allSelectedOnPage =
    items.length > 0 && items.every((it) => selected.has(it.order_uuid));

  return (
    <>
      <PageHeader
        title="Repeat orders"
        description="Customers who have purchased a product more than once."
      />

      {/* ---- KPI strip ---- */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard
          label="Repeat orders"
          value={summaryQuery.data?.total_repeat_orders}
          icon={<Repeat />}
          loading={summaryQuery.isLoading}
        />
        <KpiCard
          label="Repeat buyers"
          value={summaryQuery.data?.total_repeat_buyers}
          icon={<Users />}
          loading={summaryQuery.isLoading}
        />
        <KpiCard
          label="Repeat products"
          value={summaryQuery.data?.total_repeat_products}
          icon={<ListChecks />}
          loading={summaryQuery.isLoading}
        />
        <KpiCard
          label="In window"
          value={summaryQuery.data?.in_review_window}
          icon={<Send />}
          loading={summaryQuery.isLoading}
        />
        <KpiCard
          label="Already requested"
          value={summaryQuery.data?.already_requested}
          icon={<CheckSquare />}
          loading={summaryQuery.isLoading}
        />
      </div>

      {/* ---- Filter bar ---- */}
      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-6">
        <div>
          <Label htmlFor="asin-filter" className="text-xs">
            ASIN
          </Label>
          <Input
            id="asin-filter"
            value={asinDraft}
            onChange={(e) => setAsinDraft(e.target.value)}
            placeholder="B0…"
            className="font-mono text-xs"
          />
        </div>
        <div className="md:col-span-2">
          <Label htmlFor="search-filter" className="text-xs">
            Product search
          </Label>
          <Input
            id="search-filter"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="name or title contains…"
          />
        </div>
        <div>
          <Label className="text-xs">Review status</Label>
          <Select
            value={urlFilters.has_review_request || "any"}
            onValueChange={(v) =>
              updateParam("has_review_request", v === "any" ? "" : v)
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="true">Already requested</SelectItem>
              <SelectItem value="false">Not requested</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">In window</Label>
          <Select
            value={urlFilters.in_window || "any"}
            onValueChange={(v) =>
              updateParam("in_window", v === "any" ? "" : v)
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="true">In review window</SelectItem>
              <SelectItem value="false">Outside window</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Sort</Label>
          <Select
            value={urlFilters.sort}
            onValueChange={(v) => updateParam("sort", v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="last_order_desc">Latest first</SelectItem>
              <SelectItem value="purchase_count_desc">
                Most purchases
              </SelectItem>
              <SelectItem value="delivery_asc">Nearing 30-day cutoff</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* ---- Action bar ---- */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex-1">
          {selected.size > 0 ? (
            <div className="flex items-center justify-between rounded-md border border-primary/30 bg-primary-soft px-3 py-2 text-sm">
              <span>
                <span className="font-semibold">{selected.size}</span> selected
              </span>
              <Button
                size="sm"
                disabled={manualMutation.isPending}
                onClick={() =>
                  manualMutation.mutate(Array.from(selected))
                }
              >
                Mark selected as requested (manual)
              </Button>
            </div>
          ) : null}
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="h-4 w-4" aria-hidden="true" />
              Export CSV
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 space-y-3">
            <div className="text-sm font-medium">Export options</div>
            <div className="space-y-1">
              <Label className="text-xs">Shop</Label>
              <Select value={exportShop} onValueChange={setExportShop}>
                <SelectTrigger>
                  <SelectValue placeholder="Pick a shop" />
                </SelectTrigger>
                <SelectContent>
                  {(settings?.available_shop_sites ?? []).map((shop) => (
                    <SelectItem
                      key={shop}
                      value={shop}
                      className="font-mono text-xs"
                    >
                      {shop}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Review status</Label>
              <Select value={exportStatus} onValueChange={setExportStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Any status</SelectItem>
                  <SelectItem value="none">Not requested</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="sent">Sent</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-muted-foreground">
              Other filters from the page (ASIN, search, in-window, sort)
              also apply. One file per shop.
            </p>
            <Button
              size="sm"
              className="w-full gap-2"
              onClick={handleExport}
              disabled={!exportShop}
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              Download
            </Button>
          </PopoverContent>
        </Popover>
      </div>

      {/* ---- Table ---- */}
      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <Checkbox
                  checked={allSelectedOnPage}
                  onCheckedChange={(next) => {
                    setSelected((prev) => {
                      const copy = new Set(prev);
                      for (const it of items) {
                        if (next) copy.add(it.order_uuid);
                        else copy.delete(it.order_uuid);
                      }
                      return copy;
                    });
                  }}
                  aria-label="Select page"
                />
              </TableHead>
              <TableHead>Order</TableHead>
              <TableHead>Buyer</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Purchases</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Delivery ETA</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 9 }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="h-32 text-center">
                  <span className="text-sm text-muted-foreground">
                    No repeat orders match your filters. Try changing the grain
                    in Settings or relaxing your filters.
                  </span>
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <Row
                  key={item.order_uuid}
                  item={item}
                  selected={selected.has(item.order_uuid)}
                  onToggle={(checked) =>
                    setSelected((prev) => {
                      const copy = new Set(prev);
                      if (checked) copy.add(item.order_uuid);
                      else copy.delete(item.order_uuid);
                      return copy;
                    })
                  }
                  onOpenDetail={() => setDetailUuid(item.order_uuid)}
                  onManualMark={() => manualMutation.mutate([item.order_uuid])}
                  onOpenAmazon={() => linkMutation.mutate(item.order_uuid)}
                  onApiSend={() => apiMutation.mutate([item.order_uuid])}
                  onReopenPending={() => {
                    const rr = item.review_request;
                    if (rr) {
                      const url =
                        (item.review_request &&
                          (item.review_request as unknown as {
                            api_response?: { redirect_url?: string };
                          }).api_response?.redirect_url) ??
                        null;
                      setLinkModal({
                        requestId: rr.id,
                        orderUuid: item.order_uuid,
                        redirectUrl: url,
                      });
                    }
                  }}
                  spApiConfigured={configuredSpApiShops.has(item.shop_site)}
                  busy={
                    manualMutation.isPending ||
                    linkMutation.isPending ||
                    apiMutation.isPending
                  }
                />
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* ---- Pagination ---- */}
      {pageCount > 1 ? (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">
            Page {urlFilters.page} of {pageCount} ({total} total)
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={urlFilters.page <= 1}
            onClick={() => updateParam("page", urlFilters.page - 1)}
          >
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={urlFilters.page >= pageCount}
            onClick={() => updateParam("page", urlFilters.page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}

      {/* ---- Detail panel ---- */}
      <DetailPanel
        orderUuid={detailUuid}
        onClose={() => setDetailUuid(null)}
        timezone={settings?.timezone}
      />

      {/* ---- Confirm-after-Amazon dialog ---- */}
      <LinkConfirmDialog
        open={linkModal !== null}
        redirectUrl={linkModal?.redirectUrl ?? null}
        onCancel={() => setLinkModal(null)}
        onConfirmClicked={() =>
          linkModal && confirmLink.mutate(linkModal.requestId)
        }
        onConfirmAsManual={() =>
          linkModal && confirmAsManualMut.mutate(linkModal.requestId)
        }
      />
    </>
  );
}

function KpiCard({
  label,
  value,
  icon,
  loading,
}: {
  label: string;
  value?: number;
  icon: React.ReactNode;
  loading: boolean;
}) {
  return (
    <StatCard
      label={label}
      icon={icon}
      value={loading || value === undefined ? "—" : value.toLocaleString()}
    />
  );
}

function Row({
  item,
  selected,
  onToggle,
  onOpenDetail,
  onManualMark,
  onOpenAmazon,
  onApiSend,
  onReopenPending,
  spApiConfigured,
  busy,
}: {
  item: RepeatOrderItem;
  selected: boolean;
  onToggle: (checked: boolean) => void;
  onOpenDetail: () => void;
  onManualMark: () => void;
  onOpenAmazon: () => void;
  onApiSend: () => void;
  onReopenPending: () => void;
  spApiConfigured: boolean;
  busy: boolean;
}) {
  const actionsDisabled = !item.can_request_review || busy;
  const isPendingLink =
    item.review_request?.status === "pending" &&
    item.review_request?.method === "link";

  return (
    <TableRow
      className={cn(
        "cursor-pointer",
        !item.can_request_review && "opacity-60",
      )}
      onClick={onOpenDetail}
    >
      <TableCell
        className="w-8"
        onClick={(e) => e.stopPropagation()}
      >
        <Checkbox
          checked={selected}
          onCheckedChange={(next) => onToggle(Boolean(next))}
          aria-label="Select row"
        />
      </TableCell>
      <TableCell className="font-mono text-xs">{item.order_id}</TableCell>
      <TableCell className="max-w-[180px] truncate text-xs">
        {item.buyer_email ?? (
          <span className="text-muted-foreground">— no email —</span>
        )}
      </TableCell>
      <TableCell className="max-w-[260px] truncate">
        <div className="text-sm">
          {item.product_name ?? item.product_title_short ?? "—"}
        </div>
        <div className="font-mono text-[10px] text-muted-foreground">
          {item.asin ?? "—"}
        </div>
      </TableCell>
      <TableCell>
        <Badge
          variant="secondary"
          className={cn(
            "rounded-full text-xs font-medium",
            item.purchase_index === item.total_purchases
              ? "bg-muted text-muted-foreground"
              : "bg-info-soft text-info",
          )}
        >
          {item.purchase_index} / {item.total_purchases}
        </Badge>
      </TableCell>
      <TableCell>
        {formatCurrency(item.item_price ?? null, item.currency ?? null)}
      </TableCell>
      <TableCell className="text-xs">
        {formatDateTime(item.estimated_delivery_utc)}
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        {isPendingLink ? (
          <button
            type="button"
            onClick={onReopenPending}
            className="cursor-pointer rounded focus-visible:outline-none"
            aria-label="Reopen pending link request"
            title="Reopen the Seller Central tab to finish this request"
          >
            <StatusBadge
              status={item.review_request?.status ?? null}
              method={item.review_request?.method ?? null}
            />
          </button>
        ) : (
          <StatusBadge
            status={item.review_request?.status ?? null}
            method={item.review_request?.method ?? null}
          />
        )}
      </TableCell>
      <TableCell
        className="text-right"
        onClick={(e) => e.stopPropagation()}
      >
        <TooltipProvider delayDuration={200}>
          <ActionIcon
            icon={<CheckSquare className="h-4 w-4" />}
            label="Mark as requested (manual)"
            disabled={actionsDisabled}
            onClick={onManualMark}
          />
          <ActionIcon
            icon={<ExternalLink className="h-4 w-4" />}
            label="Open in Seller Central (link)"
            disabled={actionsDisabled}
            onClick={onOpenAmazon}
          />
          <ActionIcon
            icon={<Send className="h-4 w-4" />}
            label={
              spApiConfigured
                ? "Send via Amazon SP-API"
                : "Configure SP-API in Settings to use this method"
            }
            disabled={actionsDisabled || !spApiConfigured}
            onClick={onApiSend}
          />
        </TooltipProvider>
        {!item.can_request_review ? (
          <div className="mt-1 text-[10px] text-muted-foreground">
            {item.can_request_reason}
          </div>
        ) : null}
      </TableCell>
    </TableRow>
  );
}

function ActionIcon({
  icon,
  label,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          disabled={disabled}
          onClick={onClick}
          aria-label={label}
        >
          {icon}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function DetailPanel({
  orderUuid,
  onClose,
  timezone,
}: {
  orderUuid: string | null;
  onClose: () => void;
  timezone: string | undefined;
}) {
  const query = useQuery({
    queryKey: ["repeat-order-detail", orderUuid],
    queryFn: () => fetchDetail(orderUuid as string),
    enabled: orderUuid !== null,
  });

  const detail = query.data;

  return (
    <Sheet
      open={orderUuid !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent side="right" className="w-full max-w-lg overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Order detail</SheetTitle>
        </SheetHeader>

        {query.isLoading || !detail ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 space-y-6 text-sm">
            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Order
              </h3>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                <Field label="Order ID" value={detail.order.order_id} mono />
                <Field
                  label="Product"
                  value={detail.order.product_name ?? "—"}
                />
                <Field label="ASIN" value={detail.order.asin ?? "—"} mono />
                <Field
                  label="Buyer"
                  value={detail.order.buyer_email ?? "— no email —"}
                  mono
                />
                <Field
                  label="Ordered"
                  value={formatDateTime(
                    detail.order.order_time_utc,
                    timezone,
                  )}
                />
                <Field
                  label="ETA"
                  value={formatDateTime(
                    detail.order.estimated_delivery_utc,
                    timezone,
                  )}
                />
                <Field
                  label="Price"
                  value={formatCurrency(
                    detail.order.item_price,
                    detail.order.currency,
                  )}
                />
                <Field
                  label="Purchase"
                  value={`${detail.order.purchase_index} of ${detail.order.total_purchases}`}
                />
                <Field
                  label="Status"
                  value={
                    detail.order.review_request
                      ? `${detail.order.review_request.status} (${detail.order.review_request.method})`
                      : "Not requested"
                  }
                />
              </dl>
            </div>

            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Buyer history
              </h3>
              <p className="mb-3 text-xs text-muted-foreground">
                {detail.buyer_history.total_orders_all_products} order
                {detail.buyer_history.total_orders_all_products === 1
                  ? ""
                  : "s"}{" "}
                in this shop.{" "}
                {detail.buyer_history.has_more
                  ? "Showing the most recent 50."
                  : null}
              </p>
              <ul className="space-y-2">
                {detail.buyer_history.orders.map((o) => (
                  <li
                    key={o.order_id}
                    className="rounded-md border border-border p-2 text-xs"
                  >
                    <div className="flex items-baseline justify-between">
                      <span className="font-mono">{o.order_id}</span>
                      <span className="text-muted-foreground">
                        {formatDateTime(o.order_time_utc, timezone)}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-muted-foreground">
                      {o.product_name ?? o.asin ?? "—"}
                    </div>
                    <div className="mt-1 flex items-baseline justify-between">
                      <span>
                        {o.quantity ?? 1} ×{" "}
                        {formatCurrency(o.item_price ?? null, null)}
                      </span>
                      {o.review_request_status ? (
                        <Badge
                          variant="secondary"
                          className="rounded-full bg-info-soft text-info"
                        >
                          {o.review_request_status}
                        </Badge>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={cn(mono && "font-mono text-xs")}>{value}</dd>
    </>
  );
}

// Suppress unused-import warning for the icon variant; ESLint flags it
// since this file's table doesn't render bare Square (the checkbox does).
void Square;

export default function RepeatOrdersPage() {
  return (
    <Suspense fallback={<PageHeader title="" />}>
      <RepeatOrdersPageInner />
    </Suspense>
  );
}
