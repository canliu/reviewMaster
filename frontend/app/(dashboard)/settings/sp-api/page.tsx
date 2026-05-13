"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Link2, Loader2, Plug, Plus } from "lucide-react";

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
  SpApiCredentialsMetadata,
  TestConnectionResult,
  deleteSpApiCredentials,
  listSpApiCredentials,
  saveSpApiCredentials,
  testSpApiConnection,
} from "@/lib/sp-api";
import { useToast } from "@/lib/toast";
import { useSettings } from "@/lib/use-settings";
import { cn } from "@/lib/utils";

export default function SpApiSettingsPage() {
  const router = useRouter();
  const { settings } = useSettings();

  const listQuery = useQuery({
    queryKey: ["sp-api-credentials"],
    queryFn: listSpApiCredentials,
  });

  const configured = listQuery.data?.items ?? [];
  const configuredShops = new Set(configured.map((c) => c.shop_site));

  // For the "Add new" form, pick the first unconfigured shop.
  const availableShops = settings?.available_shop_sites ?? [];
  const unconfiguredShops = availableShops.filter((s) => !configuredShops.has(s));

  if (listQuery.isLoading) {
    return (
      <>
        <PageHeader title="SP-API connections" />
        <Skeleton className="h-80 w-full max-w-2xl" />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="SP-API connections"
        description="One SP-API credential set per Amazon shop. Connect each shop you want to send review requests for."
        actions={
          <Button variant="ghost" onClick={() => router.push("/settings")}>
            ← Back to settings
          </Button>
        }
      />

      <div className="space-y-6">
        {availableShops.length === 0 ? (
          <Card className="max-w-2xl">
            <CardContent className="p-6 text-sm text-muted-foreground">
              Upload an order file first so we know which Amazon shops you
              have. Then come back here to connect them.
            </CardContent>
          </Card>
        ) : null}

        {configured.map((meta) => (
          <ShopCard
            key={meta.shop_site}
            shopSite={meta.shop_site}
            metadata={meta}
          />
        ))}

        {unconfiguredShops.length > 0 ? (
          <ShopCard
            key="new"
            shopSite={null}
            metadata={null}
            unconfiguredShops={unconfiguredShops}
          />
        ) : null}
      </div>
    </>
  );
}

function ShopCard({
  shopSite,
  metadata,
  unconfiguredShops,
}: {
  shopSite: string | null;
  metadata: SpApiCredentialsMetadata | null;
  unconfiguredShops?: string[];
}) {
  const isNew = metadata === null;
  const queryClient = useQueryClient();
  const toast = useToast();

  // For the "new" card we need a shop-picker as well.
  const [pickedShop, setPickedShop] = useState<string>(
    unconfiguredShops?.[0] ?? "",
  );
  const effectiveShop = shopSite ?? pickedShop;

  const [lwaClientId, setLwaClientId] = useState("");
  const [lwaClientSecret, setLwaClientSecret] = useState("");
  const [refreshToken, setRefreshToken] = useState("");
  const [sellingPartnerId, setSellingPartnerId] = useState("");
  const [marketplaceId, setMarketplaceId] = useState<string>(
    metadata?.marketplace_id ?? SP_API_MARKETPLACES[0]!.id,
  );

  useEffect(() => {
    if (metadata) {
      setLwaClientId(metadata.lwa_client_id_prefix ?? "");
      setSellingPartnerId(metadata.selling_partner_id ?? "");
      if (metadata.marketplace_id) setMarketplaceId(metadata.marketplace_id);
    }
  }, [metadata]);

  const saveMutation = useMutation({
    mutationFn: saveSpApiCredentials,
    onSuccess: () => {
      toast.success(`Credentials saved for ${effectiveShop}`);
      setLwaClientSecret("");
      setRefreshToken("");
      void queryClient.invalidateQueries({ queryKey: ["sp-api-credentials"] });
    },
    onError: () => toast.error("Couldn't save credentials", "Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSpApiCredentials(effectiveShop),
    onSuccess: () => {
      toast.success(`Disconnected ${effectiveShop}`);
      void queryClient.invalidateQueries({ queryKey: ["sp-api-credentials"] });
    },
    onError: () => toast.error("Couldn't disconnect", "Try again."),
  });

  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);
  const testMutation = useMutation({
    mutationFn: () => testSpApiConnection(effectiveShop),
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
    effectiveShop.length > 0 &&
    lwaClientId.trim().length > 0 &&
    sellingPartnerId.trim().length > 0 &&
    marketplaceId.length > 0 &&
    (isNew
      ? lwaClientSecret.length > 0 && refreshToken.length > 0
      : lwaClientSecret.length > 0 || refreshToken.length > 0 ||
        // allow updating non-secret fields by themselves
        true);

  function onSave() {
    if (!canSave) return;
    saveMutation.mutate({
      shop_site: effectiveShop,
      lwa_client_id: lwaClientId.trim(),
      lwa_client_secret: lwaClientSecret,
      refresh_token: refreshToken,
      selling_partner_id: sellingPartnerId.trim(),
      marketplace_id: marketplaceId,
    });
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Plug className="h-4 w-4" aria-hidden="true" />
          {isNew ? (
            <>
              <Plus className="h-4 w-4" /> Connect a new shop
            </>
          ) : (
            <>
              <span className="font-mono">{shopSite}</span>
              <span className="inline-flex items-center gap-1 text-success">
                <CheckCircle2 className="h-4 w-4" /> Connected
              </span>
            </>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isNew && unconfiguredShops && unconfiguredShops.length > 0 ? (
          <div>
            <Label>Shop</Label>
            <Select value={pickedShop} onValueChange={setPickedShop}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {unconfiguredShops.map((s) => (
                  <SelectItem key={s} value={s} className="font-mono text-xs">
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        <div>
          <Label>LWA Client ID</Label>
          <Input
            value={lwaClientId}
            onChange={(e) => setLwaClientId(e.target.value)}
            placeholder="amzn1.application-oa2-client.xxxx"
            className="font-mono text-xs"
          />
        </div>
        <div>
          <Label>LWA Client Secret</Label>
          <Input
            type="password"
            value={lwaClientSecret}
            onChange={(e) => setLwaClientSecret(e.target.value)}
            placeholder={
              isNew ? "amzn1.oa2-cs.v1.xxxx" : "•••• saved — type to replace"
            }
            className="font-mono text-xs"
            autoComplete="off"
          />
        </div>
        <div>
          <Label>Refresh Token</Label>
          <Input
            type="password"
            value={refreshToken}
            onChange={(e) => setRefreshToken(e.target.value)}
            placeholder={isNew ? "Atzr|..." : "•••• saved — type to replace"}
            className="font-mono text-xs"
            autoComplete="off"
          />
        </div>
        <div>
          <Label>Selling Partner ID</Label>
          <Input
            value={sellingPartnerId}
            onChange={(e) => setSellingPartnerId(e.target.value)}
            placeholder="A1B2C3..."
            className="font-mono text-xs"
          />
        </div>
        <div>
          <Label>Marketplace</Label>
          <Select value={marketplaceId} onValueChange={setMarketplaceId}>
            <SelectTrigger>
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
            {testResult.ok
              ? `✓ Authorized for ${testResult.marketplaces.length} marketplace(s) — ${testResult.elapsed_ms}ms`
              : `✗ ${testResult.error_code}: ${testResult.message}`}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
          {!isNew ? (
            <>
              <Button
                variant="outline"
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
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
                disabled={deleteMutation.isPending}
              >
                Disconnect
              </Button>
            </>
          ) : null}
          <Button onClick={onSave} disabled={!canSave || saveMutation.isPending}>
            {saveMutation.isPending ? "Saving…" : isNew ? "Connect" : "Save"}
          </Button>
        </div>

        {isNew ? null : (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <AlertCircle className="h-3 w-3" />
            Leave the two secret fields blank to keep the existing ones.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
