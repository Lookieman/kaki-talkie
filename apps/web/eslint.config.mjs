// v1.4 | 04-Sep-2026 | Resolve the config directory on all supported Node versions.
// v1.3 | 04-Sep-2026 | Name the exported configuration for clean lint output.
// v1.2 | 04-Sep-2026 | Adapt the Next.js legacy presets to ESLint flat config.
// v1.1 | 04-Sep-2026 | Use explicit ESM entry-point suffixes.
// v1.0 | 04-Sep-2026 | Apply the Next.js Core Web Vitals and TypeScript rules.

import { FlatCompat } from "@eslint/eslintrc"; //v1.2
import { dirname } from "node:path"; //v1.4
import { fileURLToPath } from "node:url"; //v1.4

const configDirectory = dirname(fileURLToPath(import.meta.url)); //v1.4
const compatibility = new FlatCompat({ baseDirectory: configDirectory }); //v1.4

const eslintConfig = [ //v1.3
  ...compatibility.extends("next/core-web-vitals", "next/typescript"), //v1.2
  { ignores: [".next/**", "coverage/**", "next-env.d.ts"] }, //v1.2
];

export default eslintConfig; //v1.3
