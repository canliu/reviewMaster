"use client";

import { useRouter } from "next/navigation";
import { LogOut, Mail } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { logout } from "@/lib/auth";
import { useCurrentUser } from "@/lib/use-current-user";

export default function DashboardHome() {
  const router = useRouter();
  const { user, isLoading } = useCurrentUser();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <>
      <PageHeader
        title="Welcome to ReviewMaster"
        description="Pick a section from the sidebar to get started."
      />

      <Card className="max-w-lg">
        <CardContent className="space-y-4 p-6">
          <div className="flex items-center gap-3 text-sm">
            <Mail className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            {isLoading || !user ? (
              <Skeleton className="h-4 w-48" />
            ) : (
              <span className="font-mono">{user.email}</span>
            )}
          </div>
          <Button
            variant="outline"
            onClick={handleLogout}
            disabled={isLoading}
            className="gap-2"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Sign out
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
