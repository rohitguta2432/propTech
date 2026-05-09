import * as esbuild from "esbuild";
import { mkdir, copyFile, readdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = __dirname;
const distDir = join(root, "dist");
const watch = process.argv.includes("--watch");

/** Recursively copy a directory tree, creating parents as needed. */
async function copyDir(src, dest) {
  if (!existsSync(src)) return;
  await mkdir(dest, { recursive: true });
  const entries = await readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else if (entry.isFile()) {
      await copyFile(srcPath, destPath);
    }
  }
}

async function copyStaticAssets() {
  // Copy public/ → dist/ (icons, popup.html, etc.)
  await copyDir(join(root, "public"), distDir);
  // Copy manifest.json → dist/manifest.json
  await copyFile(join(root, "manifest.json"), join(distDir, "manifest.json"));
}

/** Common esbuild options. */
const baseOpts = {
  bundle: true,
  target: ["chrome120"],
  platform: "browser",
  sourcemap: false, // CWS prefers no sourcemaps in shipped extensions
  minify: true,
  legalComments: "none",
  logLevel: "info",
};

const entries = [
  // Service worker — Manifest V3 supports ESM service workers
  {
    entryPoints: [join(root, "src/background/worker.ts")],
    outfile: join(distDir, "background/worker.js"),
    format: "esm",
  },
  // Popup script — runs in a normal page context, IIFE is fine
  {
    entryPoints: [join(root, "src/popup/popup.ts")],
    outfile: join(distDir, "popup.js"),
    format: "iife",
  },
  // Content scripts must be IIFE; Chrome cannot reliably load ESM as content scripts.
  {
    entryPoints: [join(root, "src/content/magicbricks.ts")],
    outfile: join(distDir, "content/magicbricks.js"),
    format: "iife",
  },
  {
    entryPoints: [join(root, "src/content/acres99.ts")],
    outfile: join(distDir, "content/acres99.js"),
    format: "iife",
  },
  {
    entryPoints: [join(root, "src/content/housing.ts")],
    outfile: join(distDir, "content/housing.js"),
    format: "iife",
  },
  {
    entryPoints: [join(root, "src/content/nobroker.ts")],
    outfile: join(distDir, "content/nobroker.js"),
    format: "iife",
  },
];

async function buildOnce() {
  await mkdir(distDir, { recursive: true });
  for (const e of entries) {
    await esbuild.build({ ...baseOpts, ...e });
  }
  await copyStaticAssets();
  // Sanity log: list dist tree size summary
  const files = await listFiles(distDir);
  console.log(`[esbuild] wrote ${files.length} files to dist/`);
}

async function listFiles(dir) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listFiles(p)));
    else out.push(relative(distDir, p));
  }
  return out;
}

async function watchMode() {
  await mkdir(distDir, { recursive: true });
  await copyStaticAssets();
  for (const e of entries) {
    const ctx = await esbuild.context({ ...baseOpts, ...e });
    await ctx.watch();
  }
  console.log("[esbuild] watching for changes... (Ctrl+C to stop)");
}

if (watch) {
  await watchMode();
} else {
  await buildOnce();
}
