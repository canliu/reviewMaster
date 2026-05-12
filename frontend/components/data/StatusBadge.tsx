import { cn } from "@/lib/utils";

export type ReviewRequestStatus = "pending" | "sent" | "failed" | null;
export type ReviewRequestMethod = "manual" | "link" | "api" | null;

interface BadgeDefinition {
  label: string;
  /** Tailwind classes for background + text colour. */
  classes: string;
}

// Color/label mapping is exported so other components (filters, legends) can
// introspect the same source of truth.
export const STATUS_BADGE_MAP = {
  sent_manual: {
    label: "Requested · manual",
    classes: "bg-info-soft text-info",
  },
  sent_link: {
    label: "Requested · link",
    classes: "bg-info-soft text-info",
  },
  sent_api: {
    label: "Requested · API",
    classes: "bg-success-soft text-success",
  },
  pending: {
    label: "Pending",
    classes: "bg-warning-soft text-warning",
  },
  failed: {
    label: "Failed",
    classes: "bg-danger-soft text-danger",
  },
  empty: {
    label: "Not requested",
    classes: "bg-muted text-muted-foreground",
  },
} satisfies Record<string, BadgeDefinition>;

interface StatusBadgeProps {
  status: ReviewRequestStatus;
  method?: ReviewRequestMethod;
  /** When true, the null/unrequested case renders a slate "Not requested"
   *  badge instead of returning null. Useful on detail pages; off by default
   *  in tables to avoid visual noise on the unrequested-row majority. */
  showEmpty?: boolean;
}

function resolveDefinition(
  status: ReviewRequestStatus,
  method: ReviewRequestMethod,
): BadgeDefinition | null {
  if (status === "sent") {
    if (method === "api") return STATUS_BADGE_MAP.sent_api;
    if (method === "link") return STATUS_BADGE_MAP.sent_link;
    return STATUS_BADGE_MAP.sent_manual;
  }
  if (status === "pending") return STATUS_BADGE_MAP.pending;
  if (status === "failed") return STATUS_BADGE_MAP.failed;
  return null;
}

export function StatusBadge({
  status,
  method = null,
  showEmpty = false,
}: StatusBadgeProps) {
  const def = resolveDefinition(status, method);
  if (!def) {
    if (!showEmpty) return null;
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
          STATUS_BADGE_MAP.empty.classes,
        )}
      >
        {STATUS_BADGE_MAP.empty.label}
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        def.classes,
      )}
    >
      {def.label}
    </span>
  );
}
