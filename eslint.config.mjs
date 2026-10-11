import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // PF12: the SDKs and the MCP package are their own packages (Node code,
    // generated clients), not the site.
    "sdks/**",
    "packages/**",
    // PF10: the Android app (Flutter; its own analyzer in scripts/verify-mobile.ps1).
    "mobile/**",
  ]),
]);

export default eslintConfig;
