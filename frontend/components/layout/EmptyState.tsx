import { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-card p-12 text-center"
    >
      {icon ? (
        <div
          aria-hidden="true"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-soft text-primary"
        >
          {icon}
        </div>
      ) : null}
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {description ? (
          <p className="max-w-md text-sm text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
