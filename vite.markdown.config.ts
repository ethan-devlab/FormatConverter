import { defineConfig } from "vite";

export default defineConfig({
  plugins: [{
    name: "katex-woff2-only",
    enforce: "pre",
    transform(code, id) {
      if (!id.includes("katex") || !id.endsWith(".css")) return;
      return code.replace(/,\s*url\([^)]*\.(?:woff|ttf)["']?\)\s*format\(["'][^"']+["']\)/g, "");
    },
  }],
  build: {
    outDir: "dist/markdown", sourcemap: false,
    lib: { entry: "src/markdown-renderer.ts", formats: ["es"], fileName: () => "render.js", cssFileName: "render" },
  },
});
