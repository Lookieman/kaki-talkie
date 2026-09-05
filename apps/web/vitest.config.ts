// v1.0 | 04-Sep-2026 | Configure deterministic simulator unit tests.

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/test/**/*.test.ts"],
  },
});
