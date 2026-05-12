import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// We avoid vite-tsconfig-paths here (ESM-only; doesn't load in the CJS
// vitest.config). Mapping `@/*` to the frontend root by hand matches
// what's in tsconfig.json.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    include: ["components/**/__tests__/**/*.test.{ts,tsx}", "lib/**/*.test.ts"],
  },
});
