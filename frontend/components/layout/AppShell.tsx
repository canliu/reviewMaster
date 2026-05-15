"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ListChecks,
  LogOut,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { logout } from "@/lib/auth";
import { useCurrentUser } from "@/lib/use-current-user";
import { useSettings } from "@/lib/use-settings";
import { useShortcuts } from "@/lib/use-shortcuts";
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
        <main
          id="main-content"
          className="flex-1 px-4 py-6 md:px-8 md:py-8"
        >
          {children}
        </main>
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
      <SidebarFooter />
    </div>
  );
}

function SidebarFooter() {
  const { setCheatsheetOpen } = useShortcuts();
  return (
    <div className="border-t border-border p-3 text-xs text-muted-foreground">
      <button
        type="button"
        onClick={() => setCheatsheetOpen(true)}
        className="flex items-center gap-1.5 hover:text-foreground"
      >
        <span aria-hidden="true">⌨</span>
        Shortcuts
        <span className="ml-1 rounded border border-border px-1 font-mono">?</span>
      </button>
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
        <ShopSwitcher />
        <UserMenuStub />
      </div>
    </header>
  );
}

function ShopSwitcher() {
  const { settings, mutate, isLoading } = useSettings();

  if (isLoading || !settings) {
    return (
      <span className="text-xs text-muted-foreground">Loading…</span>
    );
  }

  const scopes = settings.available_scopes ?? [];
  if (scopes.length === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        Upload an order file to start.
      </span>
    );
  }

  return (
    <Select
      value={settings.active_shop_site ?? undefined}
      onValueChange={(value) => {
        void mutate({ active_shop_site: value });
      }}
    >
      <SelectTrigger className="h-9 w-52" aria-label="Active shop or scope">
        <SelectValue placeholder="Pick a scope" />
      </SelectTrigger>
      <SelectContent align="end">
        {scopes.map((scope) => (
          <SelectItem
            key={scope.value}
            value={scope.value}
            className={
              scope.type === "marketplace"
                ? "text-xs font-medium"
                : "font-mono text-xs"
            }
          >
            {scope.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function UserMenuStub() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const initial = user?.email[0]?.toUpperCase() ?? "U";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

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
            {initial}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="font-normal">
          <div className="text-xs text-muted-foreground">Signed in as</div>
          <div className="truncate font-mono text-sm">
            {user?.email ?? "—"}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleLogout} className="gap-2">
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Re-export for tests / external use of the icon to keep tree-shaking honest.
export { X as _Close };
