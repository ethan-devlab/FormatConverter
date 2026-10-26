import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
const python = resolve(
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
if (!existsSync(python)) {
  console.error("Run uv sync first.");
  process.exit(1);
}
const server = spawn(
  python,
  ["-m", "server.format_converter", "--dev", "--no-browser"],
  { stdio: "inherit" },
);
const web = spawn(
  process.execPath,
  [resolve("node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"],
  { stdio: "inherit" },
);
const close = () => {
  server.kill();
  web.kill();
};
process.on("SIGINT", close);
process.on("SIGTERM", close);
server.on("exit", (code) => {
  web.kill();
  process.exitCode = code || 0;
});
web.on("exit", (code) => {
  server.kill();
  process.exitCode = code || 0;
});
