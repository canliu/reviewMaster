"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Link2, Loader2, Plug } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  SP_API_MARKETPLACES,
  TestConnectionResult,
  deleteSpApiCredentials,
  getSpApiCredentials,
  saveSpApiCredentials,
  testSpApiConnection,
} from "@/lib/sp-api";
import { useToast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export default function SpApiSettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();

  const metadataQuery = useQuery({
    queryKey: ["sp-api-credentials"],
    queryFn: getSpApiCredentials,
  });
  const meta = metadataQuery.data;

  const [lwaClientId, setLwaClientId] = useState("");
  const [lwaClientSecret, setLwaClientSecret] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [sellingPartnerId, setSellingPartnerId] = useState("");
  const [marketplaceId, setMarketplaceId] = useState<string>(
    SP_API_MARKETPLACES[0]!.id,
  );

  // Hydrate non-secret fields once metadata loads.
  useEffect(() => {
    if (meta?.configured) {
      setLwaClientId(meta.lwa_client_id_prefix ?? "");
      setSellingPartnerId(meta.selling_partner_id ?? "");
      if (meta.marketplace_id) setMarketplaceId(meta.marketplace_id);
    }
  }, [meta]);

  const saveMutation = useMutation({
    mutationFn: saveSpApiCredentials,
    onSuccess: () => {
      toast.success("SP-API credentials saved");
      setLwaClientSecret("");
      setRefreshToken("");
      void queryClient.invalidateQueries({ queryKey: ["sp-api-credentials"] });
    },
    onError: () => toast.error("Couldn't save credentials", "Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSpApiCredentials,
    onSuccess: () => {
      toast.success("SP-API disconnected");
      void queryClient.invalidateQueries({ queryKey: ["sp-api-credentials"] });
    },
    onError: () => toast.error("Couldn't disconnect", "Try again."),
  });

  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);
  const testMutation = useMutation({
    mutationFn: testSpApiConnection,
    onSuccess: (result) => {
      setTestResult(result);
      if (result.ok) {
        toast.success(
          "Connection OK",
          `${result.marketplaces.length} marketplace(s) authorized · ${result.elapsed_ms}ms`,
        );
      } else {
        toast.error("Connection failed", result.message);
      }
    },
    onError: () => toast.error("Couldn't test connection", "Try again."),
  });

  const canSave =
    lwaClientId.trim().length > 0 &&
    sellingPartnerId.trim().length > 0 &&
    marketplaceId.length > 0 &&
    // Need at least one fresh secret unless this is a brand-new save.
    (!meta?.configured ||
      lwaClientSecret.length > 0 ||
      refreshToken.length > 0);

  function onSave() {
    if (!canSave) return;
    saveMutation.mutate({
      lwa_client_id: lwaClientId.trim(),
      lwa_client_secret: lwaClientSecret || "•••• preserve",  // server requires non-empty
      refresh_token: refreshToken || "•••• preserve",
      selling_partner_id: sellingPartnerId.trim(),
      marketplace_id: marketplaceId,
    });
  }

  if (metadataQuery.isLoading || !meta) {
    return (
      <>
        <PageHeader title="SP-API connection" />
        <Skeleton className="h-80 w-full max-w-2xl" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="SP-API connection"
        description="Connect your Amazon Selling Partner API credentials to send review requests automatically."
        actions={
          <Button variant="ghost" onClick={() => router.push("/settings")}>
            ← Back to settings
          </Button>
        }
      />

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug className="h-4 w-4" aria-hidden="true" />
            Connection status:{" "}
            {meta.configured ? (
              <span className="inline-flex items-center gap-1 text-success">
                <CheckCircle2 className="h-4 w-4" /> Connected
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <AlertCircle className="h-4 w-4" /> Not connected
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="lwa-client-id">LWA Client ID</Label>
            <Input
              id="lwa-client-id"
              value={lwaClientId}
              onChange={(e) => setLwaClientId(e.target.value)}
              placeholder="amzn1.application-oa2-client.xxxx"
              className="font-mono text-xs"
            />
          </div>
          <div>
            <Label htmlFor="lwa-client-secret">LWA Client Secret</Label>
            <Input
              id="lwa-client-secret"
              type="password"
              value={lwaClientSecret}
              onChange={(e) => setLwaClientSecret(e.target.value)}
              placeholder={
                meta.configured
                  ? "•••• saved — type to replace"
                  : "amzn1.oa2-cs.v1.xxxx"
              }
              className="font-mono text-xs"
              autoComplete="off"
            />
          </div>
          <div>
            <Label htmlFor="refresh-token">Refresh Token</Label>
            <Input
              id="refresh-token"
              type="password"
              value={refreshToken}
              onChange={(e) => setRefreshToken(e.target.value)}
              placeholder={
                meta.configured
                  ? "•••• saved — type to replace"
                  : "Atzr|..."
              }
              className="font-mono text-xs"
              autoComplete="off"
            />
          </div>
          <div>
            <Label htmlFor="selling-partner-id">Selling Partner ID</Label>
            <Input
              id="selling-partner-id"
              value={sellingPartnerId}
              onChange={(e) => setSellingPartnerId(e.target.value)}
              placeholder="A1B2C3..."
              className="font-mono text-xs"
            />
          </div>
          <div>
            <Label htmlFor="marketplace">
              Primary marketplace
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                (used for connection testing — not a limit on which markets you can send to)
              </span>
            </Label>
            <Select value={marketplaceId} onValueChange={setMarketplaceId}>
              <SelectTrigger id="marketplace">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SP_API_MARKETPLACES.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              To request reviews in other marketplaces, ensure your Seller
              Central app is authorized there too.
            </p>
          </div>

          {testResult ? (
            <div
              className={cn(
                "rounded-md border p-3 text-sm",
                testResult.ok
                  ? "border-success/40 bg-success-soft text-success"
                  : "border-danger/40 bg-danger-soft text-danger",
              )}
            >
              {testResult.ok ? (
                <>
                  ✓ Authorized for {testResult.marketplaces.length} marketplace
                  {testResult.marketplaces.length === 1 ? "" : "s"}:{" "}
                  <span className="font-mono">
                    {testResult.marketplaces.join(", ")}
                  </span>{" "}
                  ({testResult.elapsed_ms}ms)
                </>
              ) : (
                <>
                  ✗ {testResult.error_code}: {testResult.message}
                </>
              )}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => testMutation.mutate()}
              disabled={!meta.configured || testMutation.isPending}
              className="gap-2"
            >
              {testMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Link2 className="h-4 w-4" />
              )}
              Test connection
            </Button>
            <Button
              variant="ghost"
              onClick={() => deleteMutation.mutate()}
              disabled={!meta.configured || deleteMutation.isPending}
            >
              Disconnect
            </Button>
            <Button
              onClick={onSave}
              disabled={!canSave || saveMutation.isPending}
            >
              {saveMutation.isPending ? "Saving…" : "Save"}
            </Button>
          </div>

          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer hover:text-foreground">
              How do I get these credentials?
            </summary>
            <ol className="ml-4 mt-2 list-decimal space-y-1">
              <li>Sign in to Seller Central → Apps &amp; Services → Develop Apps.</li>
              <li>Create a self-authorization app (no marketplace review needed).</li>
              <li>Generate LWA credentials (Client ID + Secret).</li>
              <li>Self-authorize the app to get a refresh token.</li>
              <li>
                Copy your Selling Partner ID from Account Info; paste the
                primary marketplace above.
              </li>
            </ol>
          </details>
        </CardContent>
      </Card>
    </>
  );
}
