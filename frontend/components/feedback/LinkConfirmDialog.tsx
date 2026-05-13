"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface LinkConfirmDialogProps {
  open: boolean;
  redirectUrl: string | null;
  onConfirmClicked: () => void;
  onConfirmAsManual: () => void;
  onCancel: () => void;
}

export function LinkConfirmDialog({
  open,
  redirectUrl,
  onConfirmClicked,
  onConfirmAsManual,
  onCancel,
}: LinkConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Did you click &ldquo;Request a Review&rdquo;?</DialogTitle>
          <DialogDescription>
            Amazon&apos;s order page is open in a new tab. Click the{" "}
            <span className="font-semibold">Request a Review</span> button
            there, then come back and confirm below.
          </DialogDescription>
        </DialogHeader>
        {redirectUrl ? (
          <a
            href={redirectUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            Reopen the Seller Central page
          </a>
        ) : null}
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="outline" onClick={onConfirmAsManual}>
            I marked it manually
          </Button>
          <Button onClick={onConfirmClicked}>I clicked it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
