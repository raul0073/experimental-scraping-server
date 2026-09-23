"""Work out which texel of the player model is shirt, shorts or socks.

THE TEXTURE ALONE CANNOT ANSWER THIS. The model is one mesh with one atlas
and the atlas is hundreds of small UV islands butted together with no
gutters, so a white texel might be a stripe across the shirt or it might be
a sock — and the island next door is as likely to be an elbow as a knee.
Colour keys get the yellow right and are helpless on the whites, which is
exactly the part that has to change for a shirt to be PLAIN.

So the answer comes from the GEOMETRY. Every triangle knows both its UVs and
its position, so rasterising the mesh into UV space gives, for each texel,
the HEIGHT UP THE BODY it belongs to. Height says which garment; colour says
whether it is a garment at all or skin. Between them:

    skin / hair / eyes  ->  left alone, whatever height they sit at
    below the ankle     ->  boots, left alone
    ankle to knee       ->  socks
    knee to waist       ->  shorts
    waist to neck       ->  shirt, INCLUDING its white stripes and trim

Doing it here rather than in the browser means the answer ships as a small
indexed PNG and the page does a lookup instead of rasterising fifteen
thousand triangles on every load.

Writes web/public/models/player-regions.png — R channel is the region id.

Usage: .venv/Scripts/python.exe scripts/build_kit_regions.py
"""
from __future__ import annotations

import argparse
import colorsys
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "web" / "public" / "models" / "player.glb"
OUT = ROOT / "web" / "public" / "models" / "player-regions.png"

RES = 512          # the page upsamples; garment borders do not need 1024
LEAVE, SHIRT, SHORTS, SOCKS = 0, 1, 2, 3

# Fractions of the model's own height. Read off the measured distribution
# rather than guessed — see --report, which prints where each colour of
# texel actually sits on the body.
# Measured with --report, not guessed. Height percentiles of each colour of
# texel on this model, which is also the proof that colour alone cannot do
# this job — two of the four are bimodal and the two peaks are different
# garments:
#
#   yellow     0.52 .. 0.84             one band: the shirt
#   white      0.08 .. 0.27  AND  0.79  socks, and the stripes across it
#   dark       0.01 .. 0.06  AND  0.49  boots, and the shorts
#   skin/hair  0.30 .. 0.98             bare leg, arms, hands, face
BOOT_TOP = 0.075
SOCK_TOP = 0.32
SHORT_TOP = 0.52
SHIRT_TOP = 0.88   # above this is neck and head


def chunks(raw: bytes):
    off, js, bins = 12, None, []
    while off < len(raw):
        ln, ty = struct.unpack_from("<II", raw, off)
        if ty == 0x4E4F534A:
            js = json.loads(raw[off + 8: off + 8 + ln].decode("utf8"))
        elif ty == 0x004E4942:
            bins.append(off + 8)
        off += 8 + ln
    return js, bins[0]


TYPES = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def read(js, base, raw, idx):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    n = COUNTS[acc["type"]]
    dt = np.dtype("<" + TYPES[acc["componentType"]])
    start = base + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * dt.itemsize
    out = np.empty((acc["count"], n), dtype=dt)
    for i in range(acc["count"]):
        out[i] = np.frombuffer(raw, dtype=dt, count=n, offset=start + i * stride)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print where each colour of texel sits on the body")
    args = ap.parse_args()

    raw = MODEL.read_bytes()
    js, base = chunks(raw)
    prim = js["meshes"][0]["primitives"][0]
    pos = read(js, base, raw, prim["attributes"]["POSITION"]).astype(np.float32)
    uv = read(js, base, raw, prim["attributes"]["TEXCOORD_0"]).astype(np.float32)
    tri = read(js, base, raw, prim["indices"]).astype(np.int64).reshape(-1, 3)

    lo, hi = pos[:, 1].min(), pos[:, 1].max()
    height = (pos[:, 1] - lo) / max(1e-6, hi - lo)

    # UV -> pixel. glTF UV origin is top-left, which is the same as an
    # image's, so v does NOT get flipped here; the texture is authored with
    # flipY off for exactly that reason.
    px = np.clip(uv[:, 0] * RES, 0, RES - 1)
    py = np.clip(uv[:, 1] * RES, 0, RES - 1)

    field = np.full((RES, RES), -1.0, dtype=np.float32)
    for a, b, c in tri:
        x = np.array([px[a], px[b], px[c]])
        y = np.array([py[a], py[b], py[c]])
        h = np.array([height[a], height[b], height[c]])
        x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max()))
        y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max()))
        if x1 <= x0 or y1 <= y0:
            # a triangle thinner than a texel still owns the texel it is on,
            # and dropping it leaves pinholes along every island edge
            field[int(y[0]), int(x[0])] = h.mean()
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        gx = np.clip(gx, 0, RES - 1)
        gy = np.clip(gy, 0, RES - 1)
        d = ((y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2]))
        if abs(d) < 1e-9:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        # a small negative tolerance closes the seams between triangles that
        # a strict inside test leaves as single-texel gaps
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        field[gy[inside], gx[inside]] = (
            w0[inside] * h[0] + w1[inside] * h[1] + w2[inside] * h[2])

    covered = (field >= 0).mean()

    # the albedo, at the same resolution, to tell garment from skin
    # A WebP texture hangs its image off EXT_texture_webp rather than the
    # plain `source` — which is the cost of the optimise step and is easy to
    # miss, because every glTF written before it has `source`.
    tex = js["textures"][js["materials"][0]["pbrMetallicRoughness"]
                         ["baseColorTexture"]["index"]]
    i = tex.get("source")
    if i is None:
        for ext in (tex.get("extensions") or {}).values():
            if isinstance(ext, dict) and "source" in ext:
                i = ext["source"]
                break
    if i is None:
        raise SystemExit("no image behind the base colour texture")
    bv = js["bufferViews"][js["images"][i]["bufferView"]]
    img = Image.open(io.BytesIO(
        raw[base + bv["byteOffset"]: base + bv["byteOffset"] + bv["byteLength"]]
    )).convert("RGB").resize((RES, RES), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32) / 255
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    hue = np.zeros_like(mx)
    d = mx - mn
    ok = d > 1e-6
    hue = np.where(ok & (mx == r), ((g - b) / np.maximum(d, 1e-6)) % 6, hue)
    hue = np.where(ok & (mx == g), (b - r) / np.maximum(d, 1e-6) + 2, hue)
    hue = np.where(ok & (mx == b), (r - g) / np.maximum(d, 1e-6) + 4, hue)
    hue = (hue * 60) % 360
    # skin and hair: warm, never as saturated as the kit
    skin = (hue >= 3) & (hue <= 42) & (sat >= 0.12) & (sat <= 0.62) & (mx > 0.22)

    if args.report:
        print(f"UV coverage {100 * covered:.1f}%")
        for name, m in (("yellow (shirt)", (hue > 25) & (hue < 75) & (sat > 0.55)),
                        ("white", (sat < 0.15) & (mx > 0.7)),
                        ("dark", (mx < 0.25)),
                        ("skin/hair", skin)):
            h = field[(field >= 0) & m]
            if h.size:
                q = np.percentile(h, [5, 25, 50, 75, 95])
                print(f"  {name:<16} n={h.size:>7}  height p5..p95 "
                      f"{q[0]:.2f} {q[1]:.2f} {q[2]:.2f} {q[3]:.2f} {q[4]:.2f}")
        return 0

    region = np.full((RES, RES), LEAVE, dtype=np.uint8)
    body = field >= 0
    garment = body & ~skin
    region[garment & (field > BOOT_TOP) & (field <= SOCK_TOP)] = SOCKS
    region[garment & (field > SOCK_TOP) & (field <= SHORT_TOP)] = SHORTS
    region[garment & (field > SHORT_TOP) & (field <= SHIRT_TOP)] = SHIRT

    out = np.zeros((RES, RES, 3), dtype=np.uint8)
    out[:, :, 0] = region
    out[:, :, 1] = region * 80        # visible when opened by a human
    Image.fromarray(out).save(OUT)
    n = region.size
    print(f"UV coverage {100 * covered:.1f}%")
    for name, v in (("shirt", SHIRT), ("shorts", SHORTS), ("socks", SOCKS)):
        print(f"  {name:<8} {100 * (region == v).sum() / n:5.1f}% of the atlas")
    print(f"-> {OUT}  ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
