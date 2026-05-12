import { cn } from "@/lib/utils";

interface LogoProps {
  iconOnly?: boolean;
  className?: string;
}

// Placeholder wordmark. Single inline SVG so swapping in a real logo later is
// one file change with no asset pipeline involved.
export function Logo({ iconOnly = false, className }: LogoProps) {
  if (iconOnly) {
    return (
      <svg
        viewBox="0 0 24 24"
        width="24"
        height="24"
        role="img"
        aria-label="ReviewMaster"
        className={cn("text-primary", className)}
      >
        <rect width="24" height="24" rx="6" fill="currentColor" />
        <path
          d="M6.5 12.5l3.2 3.2 7.8-7.8"
          stroke="white"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-primary",
        className,
      )}
      aria-label="ReviewMaster"
    >
      <svg
        viewBox="0 0 24 24"
        width="28"
        height="28"
        aria-hidden="true"
      >
        <rect width="24" height="24" rx="6" fill="currentColor" />
        <path
          d="M6.5 12.5l3.2 3.2 7.8-7.8"
          stroke="white"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      <span className="text-xl font-semibold tracking-tight">
        ReviewMaster
      </span>
    </span>
  );
}
