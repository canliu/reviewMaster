import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReviewMaster",
  description: "Find Amazon repeat buyers and request reviews.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
