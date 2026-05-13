import type { Metadata } from "next";

import { ConfirmProvider } from "@/components/feedback/ConfirmDialog";
import { Toaster } from "@/components/feedback/Toaster";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { fontMono, fontSans } from "@/lib/fonts";
import { cn } from "@/lib/utils";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ReviewMaster",
    template: "%s · ReviewMaster",
  },
  description: "Turn repeat buyers into 5-star reviews.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={cn(fontSans.variable, fontMono.variable)}>
      <body className="font-sans antialiased">
        <QueryProvider>
          <ConfirmProvider>
            {children}
            <Toaster />
          </ConfirmProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
