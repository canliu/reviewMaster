"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronDown,
  ListChecks,
  Menu,
  Repeat,
  Settings,
  Upload,
  X,
} from "lucide-react";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

// URLs match the future stage routes inside the (dashboard) route group:
//   stage 2 → /uploads, stage 4 → /repeat-orders, stage 5 → /review-requests,
//   stage 3 → /settings. The (dashboard) group doesn't appear in the URL.
const NAV_ITEMS = [
  { href: "/uploads", label: "Uploads", icon: Upload },
  { href: "/repeat-orders", label: "Repeat orders", icon: Repeat },
  { href: "/review-requests", label: "Review requests", icon: ListChecks },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-border bg-card md:flex md:flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-60 p-0">
          <SidebarContent onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center border-b border-border px-5">
        <Link
          href="/dashboard"
          className="flex items-center"
          onClick={onNavigate}
        >
          <Logo />
        </Link>
      </div>
      <nav className="flex-1 space-y-1 p-3" aria-label="Main">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-md border-l-[3px] px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "border-primary bg-primary-soft text-primary"
                  : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon aria-hidden="true" className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-4 md:px-8">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenuClick}
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </Button>

      <div className="ml-auto flex items-center gap-2">
        <ShopSwitcherStub />
        <UserMenuStub />
      </div>
    </header>
  );
}

/* These two stubs render shape only — wiring lands in Stage 3 (shop) and
 * Stage 1 (user). They exist now so the shell looks complete on screenshot
 * and Stage 1/3 only have to swap state, not introduce new layout. */

function ShopSwitcherStub() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <span className="font-mono text-xs">No shop selected</span>
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Shop</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          Upload orders to populate shops
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenuStub() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="User menu"
          className="rounded-full"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary">
            U
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Account</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>Sign out (Stage 1)</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Re-export for tests / external use of the icon to keep tree-shaking honest.
export { X as _Close };
