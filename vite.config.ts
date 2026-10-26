import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    ...(process.env.FORMAT_CONVERTER_WOFF2 !== "0"
      ? [{
          name: "fontsource-woff2-only",
          enforce: "pre" as const,
          transform(code: string, id: string) {
            if (!id.replaceAll("\\", "/").includes("/@fontsource") || !id.endsWith(".css")) return;
            return code.replace(/,\s*url\([^)]*\.woff["']?\)\s*format\(["']woff["']\)/g, "");
          },
        }]
      : []),
  ],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { outDir: "dist", sourcemap: false },
});
