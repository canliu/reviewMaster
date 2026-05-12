"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, FileSpreadsheet, UploadCloud } from "lucide-react";
import { AxiosError } from "axios";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import { useToast } from "@/lib/toast";
import {
  UploadBatch,
  getUpload,
  listUploads,
  uploadFile,
} from "@/lib/uploads";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 2000;

export default function UploadsPage() {
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [activeBatch, setActiveBatch] = useState<UploadBatch | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const [history, setHistory] = useState<UploadBatch[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [detailBatch, setDetailBatch] = useState<UploadBatch | null>(null);

  const refreshHistory = useCallback(async () => {
    try {
      const data = await listUploads(1, 20);
      setHistory(data.items);
    } catch {
      // Silent — toasts on every poll would be noisy.
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  // Poll the active batch until it's no longer processing.
  useEffect(() => {
    if (!activeBatch || activeBatch.status !== "processing") return;
    const interval = setInterval(async () => {
      try {
        const next = await getUpload(activeBatch.id);
        setActiveBatch(next);
        if (next.status !== "processing") {
          await refreshHistory();
          if (next.status === "completed") {
            toast.success(
              "Upload complete",
              `New: ${next.new_rows}, Updated: ${next.updated_rows}, ` +
                `Duplicates: ${next.duplicate_rows}, Errors: ${next.error_rows}`,
            );
          } else {
            const reason =
              (next.error_detail?.reason as string | undefined) ??
              "The worker reported a failure.";
            toast.error("Upload failed", reason);
          }
        }
      } catch {
        /* keep polling */
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [activeBatch, refreshHistory, toast]);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      toast.error("Wrong file type", "Only .xlsx files are accepted.");
      return;
    }
    setIsUploading(true);
    try {
      const enqueued = await uploadFile(file);
      const batch = await getUpload(enqueued.batch_id);
      setActiveBatch(batch);
      await refreshHistory();
    } catch (err) {
      const detail =
        (err as AxiosError<{ detail?: string }>).response?.data?.detail ??
        "Could not start the upload.";
      toast.error("Upload failed", detail);
    } finally {
      setIsUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  return (
    <>
      <PageHeader
        title="Uploads"
        description="Upload an Amazon order export to find your repeat buyers."
      />

      {/* ---- Upload card ---- */}
      <Card className="mb-8">
        <CardContent className="p-6">
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border bg-muted/40 p-12 text-center transition-colors",
              dragging && "border-primary bg-primary-soft",
            )}
          >
            <UploadCloud
              aria-hidden="true"
              className="h-10 w-10 text-primary"
            />
            <p className="text-sm font-medium">
              Drop your .xlsx here, or{" "}
              <span className="text-primary underline">choose a file</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Up to 50 MB. We&apos;ll parse the sheet named 配送信息.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
                e.target.value = "";
              }}
            />
          </div>

          {activeBatch ? (
            <ActiveBatchStatus batch={activeBatch} />
          ) : isUploading ? (
            <p className="mt-4 text-sm text-muted-foreground">Uploading…</p>
          ) : null}
        </CardContent>
      </Card>

      {/* ---- History ---- */}
      <h2 className="mb-3 text-lg font-semibold">History</h2>
      {historyLoading ? (
        <HistorySkeleton />
      ) : history.length === 0 ? (
        <EmptyState
          icon={<FileSpreadsheet />}
          title="No uploads yet"
          description="Drop your first Amazon order export above to get started."
        />
      ) : (
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Updated</TableHead>
                <TableHead className="text-right">Dupes</TableHead>
                <TableHead className="text-right">Errors</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((batch) => (
                <TableRow
                  key={batch.id}
                  className="cursor-pointer"
                  onClick={() => setDetailBatch(batch)}
                >
                  <TableCell className="max-w-[280px] truncate font-mono text-xs">
                    {batch.filename}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={batch.status} />
                  </TableCell>
                  <TableCell className="text-right">{batch.total_rows}</TableCell>
                  <TableCell className="text-right">{batch.new_rows}</TableCell>
                  <TableCell className="text-right">{batch.updated_rows}</TableCell>
                  <TableCell className="text-right">{batch.duplicate_rows}</TableCell>
                  <TableCell className="text-right">{batch.error_rows}</TableCell>
                  <TableCell className="text-xs">
                    {formatDateTime(batch.started_at)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {batch.completed_at ? formatDateTime(batch.completed_at) : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* ---- Detail side panel ---- */}
      <Sheet
        open={detailBatch !== null}
        onOpenChange={(open) => {
          if (!open) setDetailBatch(null);
        }}
      >
        <SheetContent side="right" className="w-full max-w-md sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Upload details</SheetTitle>
          </SheetHeader>
          {detailBatch ? (
            <div className="mt-6 space-y-4 text-sm">
              <DetailLine label="File">{detailBatch.filename}</DetailLine>
              <DetailLine label="Status">
                <StatusBadge status={detailBatch.status} />
              </DetailLine>
              <DetailLine label="Total rows">{detailBatch.total_rows}</DetailLine>
              <DetailLine label="New / Updated / Dupes / Errors">
                {detailBatch.new_rows} / {detailBatch.updated_rows} /{" "}
                {detailBatch.duplicate_rows} / {detailBatch.error_rows}
              </DetailLine>
              <DetailLine label="Started">
                {formatDateTime(detailBatch.started_at)}
              </DetailLine>
              <DetailLine label="Completed">
                {detailBatch.completed_at
                  ? formatDateTime(detailBatch.completed_at)
                  : "—"}
              </DetailLine>
              {detailBatch.error_detail ? (
                <div>
                  <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Error detail
                  </div>
                  <pre className="overflow-auto rounded bg-muted p-3 text-xs">
                    {JSON.stringify(detailBatch.error_detail, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}

function ActiveBatchStatus({ batch }: { batch: UploadBatch }) {
  const pct =
    batch.total_rows > 0
      ? Math.min(100, Math.round((batch.progress / batch.total_rows) * 100))
      : 0;

  if (batch.status === "failed") {
    const reason =
      (batch.error_detail?.reason as string | undefined) ??
      "The worker reported a failure.";
    return (
      <div className="mt-6 flex items-start gap-3 rounded-md border border-danger/40 bg-danger-soft p-4 text-sm text-danger">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <div className="font-medium">Upload failed</div>
          <div className="mt-1 text-danger/80">{reason}</div>
        </div>
      </div>
    );
  }

  if (batch.status === "completed") {
    return (
      <div className="mt-6 text-sm text-muted-foreground">
        Latest upload: <span className="font-mono">{batch.filename}</span> —
        new {batch.new_rows}, updated {batch.updated_rows}, dupes{" "}
        {batch.duplicate_rows}, errors {batch.error_rows}.
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Processing…</span>
        <span className="text-muted-foreground">
          {batch.progress} / {batch.total_rows || "?"} rows
        </span>
      </div>
      <Progress value={pct} />
    </div>
  );
}

function StatusBadge({ status }: { status: UploadBatch["status"] }) {
  const map = {
    processing: { label: "Processing", classes: "bg-warning-soft text-warning" },
    completed: { label: "Completed", classes: "bg-success-soft text-success" },
    failed: { label: "Failed", classes: "bg-danger-soft text-danger" },
  } as const;
  const { label, classes } = map[status];
  return (
    <Badge className={cn("rounded-full font-medium", classes)} variant="secondary">
      {label}
    </Badge>
  );
}

function DetailLine({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div>{children}</div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
