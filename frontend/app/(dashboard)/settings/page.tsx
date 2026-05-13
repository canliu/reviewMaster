"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronsUpDown } from "lucide-react";
import { AxiosError } from "axios";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  COMMON_TIMEZONES,
  RepeatGrain,
  RepeatPreview,
  getRepeatPreview,
} from "@/lib/settings";
import { useToast } from "@/lib/toast";
import { useOnboarding } from "@/lib/use-onboarding";
import { useSettings } from "@/lib/use-settings";
import { cn } from "@/lib/utils";

const GRAIN_OPTIONS: ReadonlyArray<{
  value: RepeatGrain;
  label: string;
  description: string;
}> = [
  {
    value: "asin",
    label: "ASIN — exact variant",
    description:
      "Strictest. Two orders only count as the same product if their ASINs match.",
  },
  {
    value: "spu",
    label: "SPU — parent product",
    description:
      "Medium. Variants of the same product family (e.g. different sizes) count together.",
  },
  {
    value: "product_name",
    label: "Product name",
    description:
      "Loosest. Anything sharing the same product name counts together.",
  },
];

export default function SettingsPage() {
  const router = useRouter();
  const { settings, mutate, isLoading } = useSettings();
  const { reset: resetOnboarding } = useOnboarding();
  const toast = useToast();

  if (isLoading || !settings) {
    return (
      <>
        <PageHeader title="Settings" />
        <div className="space-y-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 w-full max-w-2xl" />
          ))}
        </div>
      </>
    );
  }

  const handleMutate = async (
    label: string,
    promise: Promise<unknown>,
  ): Promise<void> => {
    try {
      await promise;
      toast.success(`${label} saved`);
    } catch (err) {
      const detail =
        (err as AxiosError<{ detail?: string }>).response?.data?.detail ??
        "Try again.";
      toast.error(`Couldn't save ${label.toLowerCase()}`, detail);
    }
  };

  return (
    <>
      <PageHeader
        title="Settings"
        description="Configure how repeat buyers are detected and how data is shown."
      />

      <div className="grid max-w-2xl gap-6">
        {/* ---- Active shop ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Active Shop</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {settings.available_shop_sites.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Upload an Amazon order file to populate your shops, then come
                back here to pick one.
              </p>
            ) : (
              <>
                <Label htmlFor="shop-select">Selected shop</Label>
                <Select
                  value={settings.active_shop_site ?? undefined}
                  onValueChange={(value) =>
                    handleMutate(
                      "Active shop",
                      mutate({ active_shop_site: value }),
                    )
                  }
                >
                  <SelectTrigger id="shop-select" className="max-w-xs">
                    <SelectValue placeholder="Pick a shop" />
                  </SelectTrigger>
                  <SelectContent>
                    {settings.available_shop_sites.map((shop) => (
                      <SelectItem
                        key={shop}
                        value={shop}
                        className="font-mono text-sm"
                      >
                        {shop}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            )}
          </CardContent>
        </Card>

        {/* ---- Repeat grain ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Repeat Grain</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <RadioGroup
              value={settings.repeat_grain}
              onValueChange={(value) =>
                handleMutate(
                  "Repeat grain",
                  mutate({ repeat_grain: value as RepeatGrain }),
                )
              }
              className="space-y-3"
            >
              {GRAIN_OPTIONS.map((opt) => (
                <div key={opt.value} className="flex items-start gap-3">
                  <RadioGroupItem
                    value={opt.value}
                    id={`grain-${opt.value}`}
                    className="mt-1"
                  />
                  <div>
                    <Label
                      htmlFor={`grain-${opt.value}`}
                      className="font-medium"
                    >
                      {opt.label}
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      {opt.description}
                    </p>
                  </div>
                </div>
              ))}
            </RadioGroup>

            <GrainPreview grain={settings.repeat_grain} />
          </CardContent>
        </Card>

        {/* ---- Excluded order types ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Excluded Order Types</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Orders of these types will be hidden from the repeat-orders list.
              Typical exclusions: cancellations, refunds, gift returns.
            </p>
            {settings.available_order_types.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No order types yet — upload orders to populate.
              </p>
            ) : (
              <div className="space-y-2">
                {settings.available_order_types.map((type) => {
                  const checked = settings.excluded_order_types.includes(type);
                  return (
                    <label
                      key={type}
                      className="flex items-center gap-3 text-sm"
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(next) => {
                          const nextList = next
                            ? [...settings.excluded_order_types, type]
                            : settings.excluded_order_types.filter(
                                (t) => t !== type,
                              );
                          void handleMutate(
                            "Excluded types",
                            mutate({ excluded_order_types: nextList }),
                          );
                        }}
                      />
                      <span>{type}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---- Timezone ---- */}
        <Card>
          <CardHeader>
            <CardTitle>Timezone</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">
              All timestamps render in this timezone.
            </p>
            <TimezonePicker
              current={settings.timezone}
              onChange={(tz) =>
                handleMutate("Timezone", mutate({ timezone: tz }))
              }
            />
          </CardContent>
        </Card>

        {/* ---- SP-API link ---- */}
        <Card>
          <CardHeader>
            <CardTitle>SP-API connection</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-muted-foreground">
              Connect your Amazon Selling Partner API credentials to send
              review requests automatically (method: api).
            </p>
            <Button variant="outline" asChild>
              <a href="/settings/sp-api">Manage SP-API credentials →</a>
            </Button>
          </CardContent>
        </Card>

        {/* ---- Replay onboarding tour ---- */}
        <div className="pt-2 text-sm text-muted-foreground">
          <button
            type="button"
            onClick={() => {
              resetOnboarding();
              router.push("/dashboard");
            }}
            className="text-primary hover:underline"
          >
            Replay the welcome tour
          </button>
        </div>
      </div>
    </>
  );
}

function GrainPreview({ grain }: { grain: RepeatGrain }) {
  const [preview, setPreview] = useState<RepeatPreview | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getRepeatPreview(grain)
      .then((p) => {
        if (!cancelled) setPreview(p);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [grain]);

  return (
    <div className="rounded-md border border-border bg-muted/40 p-3 text-sm">
      {loading ? (
        <Skeleton className="h-4 w-56" />
      ) : preview ? (
        <span>
          <span className="font-semibold">{preview.repeat_buyer_count}</span>{" "}
          repeat buyer{preview.repeat_buyer_count === 1 ? "" : "s"},{" "}
          <span className="font-semibold">{preview.repeat_order_count}</span>{" "}
          repeat order{preview.repeat_order_count === 1 ? "" : "s"} at this
          grain.
        </span>
      ) : (
        <span className="text-muted-foreground">
          Couldn&apos;t load preview.
        </span>
      )}
    </div>
  );
}

function TimezonePicker({
  current,
  onChange,
}: {
  current: string;
  onChange: (tz: string) => void;
}) {
  const [open, setOpen] = useState(false);

  const options = useMemo(() => {
    // Add `current` to the list if it's not already there (a power user
    // might have set an unusual zone via the API directly).
    return COMMON_TIMEZONES.includes(current)
      ? COMMON_TIMEZONES
      : [current, ...COMMON_TIMEZONES];
  }, [current]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="max-w-xs justify-between"
        >
          {current}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search timezones…" />
          <CommandList>
            <CommandEmpty>No timezone found.</CommandEmpty>
            <CommandGroup>
              {options.map((tz) => (
                <CommandItem
                  key={tz}
                  value={tz}
                  onSelect={() => {
                    setOpen(false);
                    if (tz !== current) onChange(tz);
                  }}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      tz === current ? "opacity-100" : "opacity-0",
                    )}
                  />
                  {tz}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
