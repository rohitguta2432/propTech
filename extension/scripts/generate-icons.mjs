/**
 * Generates the three brand icons as real PNGs via a tiny hand-rolled encoder.
 *
 * Why hand-rolled? `canvas` is a large native dep and `sharp` adds platform
 * binaries — overkill for three flat-color icons. The PNG format with all
 * pixels in a single IDAT chunk + DEFLATE-stored (no compression) is short
 * enough to write directly. ~150 lines, zero deps, deterministic output,
 * runs in Node and ships real PNG files (not placeholders).
 *
 * Each icon: dark ink #141413 rounded square + centered orange #d97757
 * checkmark-in-circle (mirrors the SVG used in web/components/Nav.tsx).
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outDir = join(root, "public", "icons");

const INK = [0x14, 0x14, 0x13, 0xff];
const ORANGE = [0xd9, 0x77, 0x57, 0xff];
const TRANSPARENT = [0, 0, 0, 0];

/** Build raw RGBA pixel buffer for a single icon. */
function rasterize(size) {
  const stride = size * 4;
  const pixels = new Uint8Array(size * stride);

  // Geometry — fractions of icon size
  const radius = size * 0.22; // rounded square corner radius
  const ringR = size * 0.30; // checkmark circle radius
  const ringWidth = Math.max(1, size * 0.09);
  const cx = size / 2;
  const cy = size / 2;

  // Checkmark vertices (relative to center)
  // Original SVG: M 9 12 L 11 14 L 15 10 in a 24-unit viewBox
  const u = size / 24;
  const v1 = { x: cx - 3 * u, y: cy };
  const v2 = { x: cx - 1 * u, y: cy + 2 * u };
  const v3 = { x: cx + 3 * u, y: cy - 2 * u };
  const strokeR = Math.max(1, size * 0.07);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = y * stride + x * 4;
      let color = TRANSPARENT;

      // 1. Rounded square in ink
      if (insideRoundedSquare(x + 0.5, y + 0.5, size, radius)) {
        color = INK;
      }

      // 2. Orange ring (circle outline, only inside the rounded square)
      if (color === INK) {
        const d = dist(x + 0.5, y + 0.5, cx, cy);
        if (Math.abs(d - ringR) <= ringWidth / 2) {
          color = ORANGE;
        }
      }

      // 3. Orange checkmark stroke (two segments)
      if (color === INK) {
        const d1 = distToSegment(x + 0.5, y + 0.5, v1, v2);
        const d2 = distToSegment(x + 0.5, y + 0.5, v2, v3);
        if (Math.min(d1, d2) <= strokeR) {
          color = ORANGE;
        }
      }

      pixels[idx] = color[0];
      pixels[idx + 1] = color[1];
      pixels[idx + 2] = color[2];
      pixels[idx + 3] = color[3];
    }
  }
  return pixels;
}

function dist(ax, ay, bx, by) {
  const dx = ax - bx;
  const dy = ay - by;
  return Math.sqrt(dx * dx + dy * dy);
}

function distToSegment(px, py, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return dist(px, py, a.x, a.y);
  let t = ((px - a.x) * dx + (py - a.y) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return dist(px, py, a.x + t * dx, a.y + t * dy);
}

function insideRoundedSquare(x, y, size, r) {
  if (x < 0 || y < 0 || x > size || y > size) return false;
  // Distance to nearest corner — clamp to inner rectangle then circle test
  const cx = Math.min(Math.max(x, r), size - r);
  const cy = Math.min(Math.max(y, r), size - r);
  return dist(x, y, cx, cy) <= r;
}

// ---------- minimal PNG encoder (RGBA, filter type 0) ----------

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

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, "ascii");
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

function encodePng(width, height, rgba) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type RGBA
  ihdr[10] = 0; // compression
  ihdr[11] = 0; // filter
  ihdr[12] = 0; // interlace

  const stride = width * 4;
  const filtered = Buffer.alloc(height * (stride + 1));
  for (let y = 0; y < height; y++) {
    filtered[y * (stride + 1)] = 0; // filter type none
    rgba.subarray(y * stride, (y + 1) * stride).forEach((b, i) => {
      filtered[y * (stride + 1) + 1 + i] = b;
    });
  }
  const idat = deflateSync(filtered);
  return Buffer.concat([
    sig,
    chunk("IHDR", ihdr),
    chunk("IDAT", idat),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function generate(size) {
  const rgba = rasterize(size);
  const png = encodePng(size, size, Buffer.from(rgba));
  const out = join(outDir, `icon-${size}.png`);
  await writeFile(out, png);
  console.log(`[icons] wrote ${out} (${png.length} bytes)`);
}

await mkdir(outDir, { recursive: true });
await generate(16);
await generate(48);
await generate(128);
