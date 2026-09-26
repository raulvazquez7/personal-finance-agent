import { defineConfig } from "vitest/config";

// Pure helpers only (src/lib). Components are checked in the browser with agent-browser, so
// jsdom and React Testing Library from the Next.js guide are left out.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // Review Focus 2: every helper test runs west of UTC, set before any module loads.
    env: { TZ: "America/Los_Angeles" },
  },
});
