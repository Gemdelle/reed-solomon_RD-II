/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
  },
  build: {
    // Terser gives finer-grained obfuscation control than the default esbuild minifier.
    minify: "terser",
    terserOptions: {
      compress: {
        drop_console: false, // Permitir logs para debugear
        drop_debugger: true,
        // Multiple passes shrink the output further after each round of inlining/dead-code elimination.
        passes: 3,
        // Inline small functions and constants aggressively.
        inline: 3,
        booleans_as_integers: true,
      },
      mangle: {
        // Rename top-level symbols (functions, classes, variables).
        // Properties are left alone to avoid breaking runtime lookups.
        toplevel: true,
      },
      format: {
        // Strip all comments — no source hints left in the bundle.
        comments: false,
      },
    },
  },
  test: {
    environment: "happy-dom",
    globals: true,
  },
});
