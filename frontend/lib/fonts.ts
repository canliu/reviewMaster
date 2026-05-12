import { Inter, JetBrains_Mono } from "next/font/google";

// Inter for UI text. `variable` exports a CSS custom property the Tailwind
// config picks up via `font-sans`.
export const fontSans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// JetBrains Mono for order IDs, ASINs, and other technical strings.
export const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});
