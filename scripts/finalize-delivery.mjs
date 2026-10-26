import { spawnSync } from "node:child_process";
import { copyFileSync, cpSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const python = resolve(root, ".venv/Scripts/python.exe");
const target = resolve(root, "release/FormatConverter");
for (const file of ["LICENSE", "README.md", "THIRD_PARTY_NOTICES.md", "DESIGN.md"])
  copyFileSync(resolve(root, file), resolve(target, file));
// Replace this owned document directory so removed historical files do not
// survive a document-only refresh of an existing portable folder.
rmSync(resolve(target, "docs"), { recursive: true, force: true });
cpSync(resolve(root, "docs"), resolve(target, "docs"), { recursive: true });
copyFileSync(resolve(root, "resources/tessdata/manifest.json"),
  resolve(target, "_internal/resources/tessdata/manifest.json"));
for (const args of [
  ["scripts/collect-notices.py", target],
  ["scripts/source-bundle.py", resolve(target, "application-source.zip")],
  ["scripts/archive-portable.py"],
  ["scripts/verify-delivery.py"],
]) {
  const result = spawnSync(python, args, { cwd: root, stdio: "inherit", windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
