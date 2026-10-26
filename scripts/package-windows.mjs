import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { cpSync, mkdirSync, readdirSync, rmSync } from "node:fs";

if (process.platform !== "win32")
  throw new Error("Build this package on Windows x64.");
const root = resolve(import.meta.dirname, "..");
const python = resolve(root, ".venv/Scripts/python.exe");
function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
if (!process.argv.includes("--skip-build"))
  run(process.execPath, [
    process.env.npm_execpath,
    "build",
    "--logLevel",
    "warn",
  ]);
run(python, ["scripts/windows-assets.py"]);
run(python, [
  "-m",
  "PyInstaller",
  "--noconfirm",
  "--distpath",
  "build/default-package",
  "--workpath",
  "build/portable",
  "scripts/FormatConverter.spec",
]);
// Keep the delivery directory itself: Explorer or a terminal may hold it open.
const target = resolve(root, "release/FormatConverter");
mkdirSync(target, { recursive: true });
for (const name of readdirSync(target)) rmSync(resolve(target, name), { recursive: true, force: true });
cpSync(resolve(root, "build/default-package/FormatConverter"), target, { recursive: true });
run(process.execPath, ["scripts/finalize-delivery.mjs"]);
