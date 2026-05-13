"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ListChecks, MessageSquare } from "lucide-react";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime } from "@/lib/format";
import {
  RequestMethod,
  RequestStatus,
  ReviewRequestListItem,
  addNote,
  downloadCsv,
  getReviewRequest,
  listReviewRequests,
} from "@/lib/review-requests";
import { useToast } from "@/lib/toast";
import { useSettings } from "@/lib/use-settings";

const PAGE_SIZE = 50;

interface UrlFilters {
  page: number;
  method: RequestMethod | "";
  status: RequestStatus | "";
  shop_site: string;
  from_date: string;
  to_date: string;
}

function parseFilters(params: URLSearchParams): UrlFilters {
  return {
    page: Number(params.get("page")) || 1,
    method: (params.get("method") as RequestMethod) || "",
    status: (params.get("status") as RequestStatus) || "",
    shop_site: params.get("shop_site") ?? "",
    from_date: params.get("from_date") ?? "",
    to_date: params.get("to_date") ?? "",
  };
}

function ReviewRequestsPageInner() {
  const router = useRouter();
  const search = useSearchParams();
  const { settings } = useSettings();
  const toast = useToast();

  const urlFilters = useMemo(() => parseFilters(search), [search]);
  const [detailId, setDetailId] = useState<string | null>(null);

  function updateParam(key: keyof UrlFilters, value: string | number) {
    const next = new URLSearchParams(search);
    if (value === "" || value === null || value === undefined) {
      next.delete(key);
    } else {
      next.set(key, String(value));
    }
    if (key !== "page") next.delete("page");
    router.replace(`/review-requests?${next.toString()}`, { scroll: false });
  }

  const apiFilters = useMemo(
    () => ({
      page: urlFilters.page,
      page_size: PAGE_SIZE,
      method: urlFilters.method || undefined,
      status: urlFilters.status || undefined,
      shop_site: urlFilters.shop_site || undefined,
      from_date: urlFilters.from_date || undefined,
      to_date: urlFilters.to_date || undefined,
    }),
    [urlFilters],
  );

  const listQuery = useQuery({
    queryKey: ["review-requests", apiFilters],
    queryFn: () => listReviewRequests(apiFilters),
    placeholderData: (prev) => prev,
  });

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const pageCount = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;

  async function handleExport() {
    try {
      await downloadCsv(
        "review-requests",
        apiFilters as Record<string, string | number | boolean | undefined>,
        `review-requests-${new Date().toISOString().slice(0, 10)}.csv`,
      );
    } catch {
      toast.error("Export failed", "Try again.");
    }
  }

  return (
    <>
      <PageHeader
        title="Review requests"
        description="Every review request you've created, with notes and audit trail."
      />

      {/* ---- Filter bar ---- */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <div>
          <Label className="text-xs">Method</Label>
          <Select
            value={urlFilters.method || "any"}
            onValueChange={(v) =>
              updateParam("method", v === "any" ? "" : v)
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="manual">Manual</SelectItem>
              <SelectItem value="link">Link</SelectItem>
              <SelectItem value="api">API</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Status</Label>
          <Select
            value={urlFilters.status || "any"}
            onValueChange={(v) =>
              updateParam("status", v === "any" ? "" : v)
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Shop</Label>
          <Input
            value={urlFilters.shop_site}
            onChange={(e) => updateParam("shop_site", e.target.value)}
            placeholder="p3:US"
            className="font-mono text-xs"
          />
        </div>
        <div>
          <Label className="text-xs">From</Label>
          <Input
            type="date"
            value={urlFilters.from_date}
            onChange={(e) => updateParam("from_date", e.target.value)}
          />
        </div>
        <div>
          <Label className="text-xs">To</Label>
          <Input
            type="date"
            value={urlFilters.to_date}
            onChange={(e) => updateParam("to_date", e.target.value)}
          />
        </div>
      </div>

      <div className="mb-3 flex items-center justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          className="gap-2"
        >
          <Download className="h-4 w-4" aria-hidden="true" />
          Export CSV
        </Button>
      </div>

      {/* ---- Table ---- */}
      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Order</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Buyer</TableHead>
              <TableHead>Shop</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Requested</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 8 }).map((__, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 p-0">
                  <EmptyState
                    icon={<ListChecks />}
                    title="No review requests yet"
                    description="Use the actions on the Repeat Orders page to create some."
                  />
                </TableCell>
              </TableRow>
            ) : (
              items.map((req) => (
                <TableRow
                  key={req.id}
                  className="cursor-pointer"
                  onClick={() => setDetailId(req.id)}
                >
                  <TableCell className="font-mono text-xs">
                    {req.order_id}
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate text-sm">
                    {req.product_name ?? "—"}
                  </TableCell>
                  <TableCell className="max-w-[180px] truncate text-xs">
                    {req.buyer_email ?? (
                      <span className="text-muted-foreground">— no email —</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {req.shop_site}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="rounded-full">
                      {req.method}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={req.status} method={req.method} showEmpty />
                  </TableCell>
                  <TableCell className="text-xs">
                    {formatDateTime(req.requested_at, settings?.timezone)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="rounded-full">
                      <MessageSquare
                        aria-hidden="true"
                        className="mr-1 h-3 w-3"
                      />
                      {req.notes_count}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

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

      <DetailPanel
        requestId={detailId}
        onClose={() => setDetailId(null)}
        timezone={settings?.timezone}
      />
    </>
  );
}

function DetailPanel({
  requestId,
  onClose,
  timezone,
}: {
  requestId: string | null;
  onClose: () => void;
  timezone: string | undefined;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [noteDraft, setNoteDraft] = useState("");

  const query = useQuery({
    queryKey: ["review-request-detail", requestId],
    queryFn: () => getReviewRequest(requestId as string),
    enabled: requestId !== null,
  });

  const addNoteMutation = useMutation({
    mutationFn: (note: string) => {
      const orderUuid = query.data?.request.order_uuid;
      if (!orderUuid) throw new Error("no order_uuid");
      return addNote(orderUuid, note);
    },
    onSuccess: () => {
      setNoteDraft("");
      toast.success("Note added");
      void queryClient.invalidateQueries({
        queryKey: ["review-request-detail", requestId],
      });
      void queryClient.invalidateQueries({ queryKey: ["review-requests"] });
    },
    onError: () => toast.error("Couldn't save note", "Try again."),
  });

  const detail = query.data;

  return (
    <Sheet
      open={requestId !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent
        side="right"
        className="w-full max-w-lg overflow-y-auto sm:max-w-lg"
      >
        <SheetHeader>
          <SheetTitle>Review request</SheetTitle>
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
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Order
              </div>
              <div className="font-mono text-sm">{detail.request.order_id}</div>
              <div className="text-xs text-muted-foreground">
                {detail.request.product_name ?? "—"}
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Status
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge
                  status={detail.request.status}
                  method={detail.request.method}
                  showEmpty
                />
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(detail.request.requested_at, timezone)}
                </span>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Notes ({detail.notes.length})
                </span>
              </div>
              {detail.notes.length === 0 ? (
                <p className="text-xs text-muted-foreground">No notes yet.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.notes.map((n) => (
                    <li
                      key={n.id}
                      className="rounded-md border border-border p-2 text-xs"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-muted-foreground">
                          {n.kind === "system" ? "system" : "you"}
                        </span>
                        <span className="text-muted-foreground">
                          {formatDateTime(n.created_at, timezone)}
                        </span>
                      </div>
                      <p className="mt-1">{n.note}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="add-note">Add a note</Label>
              <Textarea
                id="add-note"
                value={noteDraft}
                onChange={(e) => setNoteDraft(e.target.value)}
                placeholder="Correction, follow-up, context…"
                maxLength={500}
                rows={3}
              />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{noteDraft.length} / 500</span>
                <Button
                  size="sm"
                  disabled={
                    noteDraft.trim().length === 0 || addNoteMutation.isPending
                  }
                  onClick={() => addNoteMutation.mutate(noteDraft.trim())}
                >
                  Save note
                </Button>
              </div>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function ReviewRequestsPage() {
  return (
    <Suspense fallback={<PageHeader title="" />}>
      <ReviewRequestsPageInner />
    </Suspense>
  );
}
