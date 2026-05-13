"use client";

import Link from "next/link";
import { ArrowRight, Repeat, Send, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { OnboardingStep } from "@/lib/use-onboarding";

interface OnboardingCardProps {
  step: OnboardingStep;
  emailHint: string;
  onNext: () => void;
  onSkip: () => void;
}

export function OnboardingCard({
  step,
  emailHint,
  onNext,
  onSkip,
}: OnboardingCardProps) {
  return (
    <Card className="max-w-2xl">
      <CardContent className="p-8">
        <div className="mb-6 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Step {step} of 3
        </div>
        {step === 1 ? (
          <Step1 emailHint={emailHint} onNext={onNext} onSkip={onSkip} />
        ) : step === 2 ? (
          <Step2 onNext={onNext} onSkip={onSkip} />
        ) : (
          <Step3 onNext={onNext} onSkip={onSkip} />
        )}
      </CardContent>
    </Card>
  );
}

function Step1({
  emailHint,
  onNext,
  onSkip,
}: {
  emailHint: string;
  onNext: () => void;
  onSkip: () => void;
}) {
  return (
    <>
      <h1 className="mb-3 text-2xl font-semibold tracking-tight">
        Welcome to ReviewMaster, {emailHint}.
      </h1>
      <p className="text-muted-foreground">Here&apos;s how it works:</p>
      <ol className="my-6 space-y-3 text-sm">
        <li className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Upload className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>Upload your Amazon order export (.xlsx).</span>
        </li>
        <li className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Repeat className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>We find your repeat buyers automatically.</span>
        </li>
        <li className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
            <Send className="h-4 w-4" aria-hidden="true" />
          </span>
          <span>Request reviews from them — manual, link, or API.</span>
        </li>
      </ol>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" onClick={onSkip}>
          Skip tour
        </Button>
        <Button onClick={onNext} className="gap-2">
          Get started
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </>
  );
}

function Step2({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <>
      <h1 className="mb-3 text-2xl font-semibold tracking-tight">
        Upload your order export
      </h1>
      <p className="text-muted-foreground">
        Open <span className="font-medium">Uploads</span> in the sidebar and
        drop your <code className="rounded bg-muted px-1.5 py-0.5 text-xs">配送信息_*.xlsx</code>{" "}
        file onto the dropzone. We&apos;ll parse it and tell you what we found.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" onClick={onSkip}>
          Skip tour
        </Button>
        <Button asChild>
          <Link href="/uploads" onClick={onNext} className="gap-2">
            Open uploads
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </>
  );
}

function Step3({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <>
      <h1 className="mb-3 text-2xl font-semibold tracking-tight">
        Find your repeat buyers
      </h1>
      <p className="text-muted-foreground">
        Once your file is processed, head to{" "}
        <span className="font-medium">Repeat orders</span> to see the buyers
        worth asking. Use the KPI cards up top, filters below, and the
        per-row actions to send a review request.
      </p>
      <ul className="my-6 space-y-2 text-sm text-muted-foreground">
        <li>• KPI cards summarise the active shop at a glance.</li>
        <li>
          • Use the shop switcher in the header to pivot to another marketplace.
        </li>
        <li>
          • Tap a row for buyer history; tap the icons on the right to request.
        </li>
      </ul>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="ghost" onClick={onSkip}>
          Close
        </Button>
        <Button asChild>
          <Link href="/repeat-orders" onClick={onNext} className="gap-2">
            See repeat orders
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </>
  );
}
