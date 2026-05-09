/**
 * Build a release ZIP from dist/ — no external deps, uses the built-in
 * deflate to write a minimal ZIP file (PKZIP 2.0 spec, store + deflate).
 */
import { readdir, readFile, writeFile, stat } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateRawSync } from "node:zlib";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { version } = require("../package.json");

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const distDir = join(root, "dist");

async function listFiles(dir) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listFiles(p)));
    else out.push(p);
  }
  return out;
}

function crc32(buf) {
  let c;
  if (!crc32.table) {
    crc32.table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      c = n;
      for (let k = 0; k < 8; k++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      crc32.table[n] = c >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = (crc >>> 8) ^ crc32.table[(crc ^ buf[i]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function dosTime(d) {
  return ((d.getHours() & 0x1f) << 11) | ((d.getMinutes() & 0x3f) << 5) | ((Math.floor(d.getSeconds() / 2)) & 0x1f);
}
function dosDate(d) {
  return (((d.getFullYear() - 1980) & 0x7f) << 9) | (((d.getMonth() + 1) & 0xf) << 5) | (d.getDate() & 0x1f);
}

const files = await listFiles(distDir);
if (files.length === 0) {
  console.error("[zip] dist/ is empty — run npm run build first");
  process.exit(1);
}

const localChunks = [];
const central = [];
let offset = 0;
const now = new Date();
const dt = dosTime(now);
const dd = dosDate(now);

for (const file of files) {
  const data = await readFile(file);
  const compressed = deflateRawSync(data);
  const useCompressed = compressed.length < data.length;
  const payload = useCompressed ? compressed : data;
  const method = useCompressed ? 8 : 0;
  const name = relative(distDir, file).split("\\").join("/");
  const nameBuf = Buffer.from(name, "utf-8");
  const crc = crc32(data);

  const localHeader = Buffer.alloc(30 + nameBuf.length);
  localHeader.writeUInt32LE(0x04034b50, 0);
  localHeader.writeUInt16LE(20, 4); // version
  localHeader.writeUInt16LE(0, 6); // flags
  localHeader.writeUInt16LE(method, 8);
  localHeader.writeUInt16LE(dt, 10);
  localHeader.writeUInt16LE(dd, 12);
  localHeader.writeUInt32LE(crc, 14);
  localHeader.writeUInt32LE(payload.length, 18);
  localHeader.writeUInt32LE(data.length, 22);
  localHeader.writeUInt16LE(nameBuf.length, 26);
  localHeader.writeUInt16LE(0, 28); // extra
  nameBuf.copy(localHeader, 30);

  localChunks.push(localHeader, payload);

  const cd = Buffer.alloc(46 + nameBuf.length);
  cd.writeUInt32LE(0x02014b50, 0);
  cd.writeUInt16LE(20, 4); // version made by
  cd.writeUInt16LE(20, 6); // version needed
  cd.writeUInt16LE(0, 8);
  cd.writeUInt16LE(method, 10);
  cd.writeUInt16LE(dt, 12);
  cd.writeUInt16LE(dd, 14);
  cd.writeUInt32LE(crc, 16);
  cd.writeUInt32LE(payload.length, 20);
  cd.writeUInt32LE(data.length, 24);
  cd.writeUInt16LE(nameBuf.length, 28);
  cd.writeUInt16LE(0, 30); // extra len
  cd.writeUInt16LE(0, 32); // comment len
  cd.writeUInt16LE(0, 34); // disk
  cd.writeUInt16LE(0, 36); // internal attrs
  cd.writeUInt32LE(0, 38); // external attrs
  cd.writeUInt32LE(offset, 42);
  nameBuf.copy(cd, 46);
  central.push(cd);

  offset += localHeader.length + payload.length;
}

const cdStart = offset;
const cdBuf = Buffer.concat(central);
const eocd = Buffer.alloc(22);
eocd.writeUInt32LE(0x06054b50, 0);
eocd.writeUInt16LE(0, 4);
eocd.writeUInt16LE(0, 6);
eocd.writeUInt16LE(files.length, 8);
eocd.writeUInt16LE(files.length, 10);
eocd.writeUInt32LE(cdBuf.length, 12);
eocd.writeUInt32LE(cdStart, 16);
eocd.writeUInt16LE(0, 20);

const zip = Buffer.concat([...localChunks, cdBuf, eocd]);
const outPath = join(root, `propcheck-extension-${version}.zip`);
await writeFile(outPath, zip);
console.log(`[zip] wrote ${outPath} (${(zip.length / 1024).toFixed(1)} KB, ${files.length} files)`);
