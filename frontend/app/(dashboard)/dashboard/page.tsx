"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { LogOut, Mail } from "lucide-react";

import { OnboardingCard } from "@/components/onboarding/OnboardingCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { logout } from "@/lib/auth";
import { useCurrentUser } from "@/lib/use-current-user";
import { useOnboarding } from "@/lib/use-onboarding";

export default function DashboardHome() {
  const router = useRouter();
  const { user, isLoading } = useCurrentUser();
  const { complete, step, next, skip } = useOnboarding();

  // Only call the uploads-list endpoint if we still might be onboarding.
  const uploadsQuery = useQuery({
    queryKey: ["uploads-count"],
    queryFn: async () => {
      const { data } = await api.get<{ total: number }>("/api/uploads", {
        params: { page: 1, page_size: 1 },
      });
      return data.total;
    },
    enabled: !complete,
  });

  const showOnboarding = !complete && uploadsQuery.data === 0;
  const emailHint = user?.email ? user.email.split("@")[0] : "there";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  if (showOnboarding) {
    return (
      <>
        <PageHeader title="Welcome" />
        <OnboardingCard
          step={step}
          emailHint={emailHint}
          onNext={next}
          onSkip={skip}
        />
      </>
    );
  }

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
