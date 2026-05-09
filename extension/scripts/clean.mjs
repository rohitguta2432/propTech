import { rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");

if (existsSync(dist)) {
  await rm(dist, { recursive: true, force: true });
  console.log("[clean] removed dist/");
} else {
  console.log("[clean] dist/ already absent");
}
