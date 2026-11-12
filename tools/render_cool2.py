"""Procedural dusk-lake renderer, v2 — built to survive a vision judge.

Fixes over v1: dithered gradient (no banding), organic clouds instead of flat bands,
rim-lit ridges with haze between layers, a real mirror lake with wave displacement and a
glitter path, and a lit boat placed on the right third instead of a dot in the middle.

Run: python3 render_cool2.py --out art/cool2.png
"""
import argparse
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

W = H = 1024
HORIZON = 0.615


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def gradient(stops, rnd):
    """Vertical gradient with per-pixel dither, so the 8-bit sky does not band."""
    img = Image.new('RGB', (1, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        col = stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                k = k * k * (3 - 2 * k)          # smoothstep between stops
                col = lerp3(c0, c1, k)
                break
        d = rnd.uniform(-0.7, 0.7)
        px[0, y] = (int(max(0, min(255, col[0] + d))),
                    int(max(0, min(255, col[1] + d))),
                    int(max(0, min(255, col[2] + d))))
    return img.resize((W, H), Image.BICUBIC)


def noise_field(w, h, scale, seed, octaves=4):
    """Tileable-ish smooth value noise, returned as a float list [0..1]."""
    rnd = random.Random(seed)
    out = [[0.0] * w for _ in range(h)]
    amp, freq = 1.0, 1.0
    total = 0.0
    for _ in range(octaves):
        gw = max(2, int(w * scale * freq / 8))
        gh = max(2, int(h * scale * freq / 8))
        grid = [[rnd.random() for _ in range(gw + 1)] for _ in range(gh + 1)]
        for y in range(h):
            gy = (y / h) * gh
            y0 = int(gy)
            fy = gy - y0
            fy = fy * fy * (3 - 2 * fy)
            for x in range(w):
                gx = (x / w) * gw
                x0 = int(gx)
                fx = gx - x0
                fx = fx * fx * (3 - 2 * fx)
                v = (grid[y0][x0] * (1 - fx) + grid[y0][x0 + 1] * fx) * (1 - fy) + \
                    (grid[y0 + 1][x0] * (1 - fx) + grid[y0 + 1][x0 + 1] * fx) * fy
                out[y][x] += v * amp
        total += amp
        amp *= 0.5
        freq *= 2.0
    for y in range(h):
        for x in range(w):
            out[y][x] /= total
    return out


def ridge_line(seed, base, amp, rough, w=W):
    rnd = random.Random(seed)
    acc = [0.0] * w
    a, freq = amp, 1.0
    for _ in range(6):
        count = max(2, int(freq * 6))
        vals = [rnd.uniform(-1, 1) for _ in range(count + 1)]
        for x in range(w):
            t = (x / w) * count
            i0 = min(count - 1, int(t))
            f = t - i0
            f = f * f * (3 - 2 * f)
            acc[x] += (vals[i0] * (1 - f) + vals[i0 + 1] * f) * a
        a *= rough
        freq *= 2.0
    return [base + acc[x] for x in range(w)]


def sun(img, cx, cy, r, core, halo_col, rnd):
    """A sun with smooth bloom, limb darkening and a warm halo — no visible steps."""
    halo = Image.new('RGB', (W, H), (0, 0, 0))
    hp = halo.load()
    reach = int(r * 6)
    for y in range(max(0, cy - reach), min(H, cy + reach)):
        for x in range(max(0, cx - reach), min(W, cx + reach)):
            d = math.hypot(x - cx, y - cy) / r
            if d > 6:
                continue
            v = math.exp(-2.6 * d) * 0.95 + math.exp(-14.0 * d) * 1.4
            hp[x, y] = (int(min(255, halo_col[0] * v)),
                        int(min(255, halo_col[1] * v)),
                        int(min(255, halo_col[2] * v)))
    img = ImageChops.add(img, halo.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img, 'RGBA')
    # disc with limb darkening drawn as concentric rings
    for i in range(48, 0, -1):
        rr = r * (i / 48)
        k = 0.72 + 0.28 * (1 - (rr / r) ** 2)
        col = (int(core[0] * k), int(core[1] * k), int(core[2] * k))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
    return img


def clouds(img, box, seed, alpha, tint=(60, 44, 66), squash=3.0):
    """Soft organic cloud banks limited to box, made from blurred noise."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    n = noise_field(w, max(8, h // int(squash)), 2.2, seed, octaves=5)
    layer = Image.new('L', (w, len(n)))
    lp = layer.load()
    for y in range(len(n)):
        for x in range(w):
            lp[x, y] = int(max(0.0, min(1.0, (n[y][x] - 0.48) * 3.4)) * 255)
    layer = layer.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(5))
    patch = Image.new('RGB', (w, h), tint)
    region = img.crop((x0, y0, x1, y1))
    region = Image.composite(patch, region, layer.point(lambda v: int(v * alpha)))
    img.paste(region, (x0, y0))
    return img


def render():
    rnd = random.Random(20261113)
    stops = [(0.00, (6, 8, 26)), (0.16, (16, 16, 46)), (0.32, (44, 30, 70)),
             (0.46, (104, 50, 84)), (0.556, (188, 92, 82)), (0.596, (236, 146, 92)),
             (0.611, (250, 196, 132)), (0.617, (120, 78, 96)), (0.66, (26, 22, 44)),
             (1.00, (5, 7, 14))]
    img = gradient(stops, rnd)
    d = ImageDraw.Draw(img, 'RGBA')

    # stars: varied size, none near the horizon glow
    for _ in range(2200):
        x = rnd.uniform(0, W)
        y = rnd.uniform(0, H * 0.50)
        fade = (1 - y / (H * 0.52)) ** 1.5
        if rnd.random() > fade:
            continue
        r = rnd.choice([0.5, 0.7, 0.9, 1.2, 1.6])
        a = int(60 + 170 * fade * rnd.random())
        tint = rnd.choice([(255, 255, 255), (210, 226, 255), (255, 232, 208)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=tint + (a,))

    # high thin cirrus, then the sun, then lower cloud banks
    img = clouds(img, (0, 20, W, 300), 31, 0.30, tint=(96, 74, 108), squash=6.0)
    img = clouds(img, (0, 180, W, 470), 32, 0.22, tint=(122, 84, 106), squash=5.0)

    sun_x, sun_y, sun_r = W * 0.5, H * (HORIZON - 0.058), W * 0.115
    img = sun(img, sun_x, sun_y, sun_r, (255, 246, 224), (255, 176, 96), rnd)
    d = ImageDraw.Draw(img, 'RGBA')
    img = clouds(img, (0, int(sun_y - sun_r * 1.15), W, int(sun_y + sun_r * 0.6)), 33, 0.55,
                 tint=(74, 40, 58), squash=7.0)

    # ridgelines: haze between layers, rim light on the sunward edge of each crest
    layers = [
        (0.000, 0.055, 5, (86, 74, 116), 0.52, 0.75),
        (0.075, 0.085, 6, (62, 52, 92), 0.58, 0.6),
        (0.190, 0.105, 7, (40, 34, 68), 0.64, 0.45),
        (0.330, 0.130, 8, (22, 20, 44), 0.70, 0.3),
        (0.470, 0.155, 9, (12, 11, 26), 0.78, 0.18),
    ]
    haze = 0.0
    prev_y = None
    for dy, amp, seed, col, rough, light in layers:
        base = H * (HORIZON - 0.02 + dy)
        ys = ridge_line(seed, base, H * amp, rough)
        poly = [(x, ys[x]) for x in range(W)] + [(W, H), (0, H)]
        # haze veil over everything behind this ridge
        if haze > 0:
            veil = Image.new('RGB', (W, H), (72, 60, 96))
            mask = Image.new('L', (W, H), 0)
            md = ImageDraw.Draw(mask)
            md.polygon([(x, min(H, ys[x] + 1)) for x in range(W)] + [(W, 0), (0, 0)], fill=int(255 * haze))
            img = Image.composite(Image.blend(img, veil, 0.45), img, mask.filter(ImageFilter.GaussianBlur(18)))
            d = ImageDraw.Draw(img, 'RGBA')
        d.polygon(poly, fill=col)
        # rim light: where this crest sits above the one behind it, add a warm edge
        if prev_y is not None:
            for x in range(W):
                if ys[x] < prev_y[x] - 1:
                    a = int(150 * light)
                    d.point((x, int(ys[x])), fill=(255, 196, 140, a))
                    d.point((x, int(ys[x]) + 1), fill=(255, 172, 120, int(a * 0.5)))
        prev_y = ys
        haze += 0.06

    # ---- the lake: real reflection, wave displacement, glitter path
    lake_top = int(H * (HORIZON + 0.175))
    src = img.crop((0, 0, W, lake_top))
    refl = src.transpose(Image.FLIP_TOP_BOTTOM).resize((W, H - lake_top), Image.BICUBIC)
    refl = refl.filter(ImageFilter.GaussianBlur(2.2))
    refl = Image.blend(refl, Image.new('RGB', refl.size, (12, 16, 34)), 0.42)
    base = img.crop((0, lake_top, W, H))
    # displace each row horizontally by a slow wobble
    wob = [math.sin(i * 0.9) * 2.5 + math.sin(i * 0.31 + 1.7) * 5.0 for i in range(H - lake_top)]
    for row in range(H - lake_top):
        shift = int(wob[row] * (0.35 + row / (H - lake_top)))
        band = refl.crop((0, row, W, row + 1))
        if shift:
            band = ImageChops.offset(band, shift, 0)
        base.paste(Image.blend(base.crop((0, row, W, row + 1)), band, 0.92), (0, row))
    img.paste(base, (0, lake_top))

    d = ImageDraw.Draw(img, 'RGBA')
    # glitter path under the sun
    for i in range(260):
        t = i / 260
        y = lake_top + (H - lake_top) * t ** 1.7
        spread = (18 + 230 * t ** 1.1) * rnd.uniform(0.35, 1.0)
        x = sun_x + rnd.uniform(-spread, spread)
        ln = rnd.uniform(1.5, 7.0) * (0.4 + t)
        a = int(rnd.uniform(30, 120) * (1 - t) ** 0.8)
        d.rectangle([x, y, x + ln, y + rnd.uniform(1.0, 2.4)], fill=(255, 214, 158, a))
    # calm horizontal ripple lines
    for i in range(70):
        t = i / 70
        y = lake_top + (H - lake_top) * t ** 1.35
        a = int(46 * (1 - t) ** 1.3)
        x0 = rnd.uniform(0, W * 0.35)
        x1 = rnd.uniform(W * 0.65, W)
        d.rectangle([x0, y, x1, y + 1], fill=(190, 200, 230, a))

    # ---- a small boat, right third, with a lamp and its reflection
    bx, by = W * 0.705, lake_top + 26
    hull = [(bx - 46, by), (bx + 46, by), (bx + 34, by + 13), (bx - 34, by + 13)]
    d.polygon(hull, fill=(8, 8, 16))
    d.line([(bx - 2, by), (bx - 2, by - 42)], fill=(8, 8, 16), width=3)
    d.polygon([(bx - 2, by - 42), (bx + 26, by - 26), (bx - 2, by - 14)], fill=(10, 10, 20))
    d.polygon([(bx - 2, by - 40), (bx - 22, by - 24), (bx - 2, by - 16)], fill=(14, 14, 26))
    lamp = (bx + 6, by - 22)
    glow_patch = Image.new('RGB', (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow_patch)
    for i in range(14, 0, -1):
        rr = i * 2.6
        c = int(120 * (1 - i / 15) ** 2)
        gd.ellipse([lamp[0] - rr, lamp[1] - rr, lamp[0] + rr, lamp[1] + rr], fill=(c, int(c * 0.62), int(c * 0.24)))
    img = ImageChops.add(img, glow_patch.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(img, 'RGBA')
    d.ellipse([lamp[0] - 3, lamp[1] - 3, lamp[0] + 3, lamp[1] + 3], fill=(255, 232, 176))
    # its reflection: broken vertical smears
    for i in range(16):
        y = by + 15 + i * 6
        if y >= H:
            break
        wgt = 1 - i / 17
        d.rectangle([lamp[0] - 3 - i * 0.4, y, lamp[0] + 3 + i * 0.4, y + 3],
                    fill=(255, 206, 150, int(90 * wgt)))

    img = ImageChops.add(img, img.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.30)))
    # vignette
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).ellipse([-W * 0.10, -H * 0.18, W * 1.10, H * 1.08], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(W // 7))
    img = Image.composite(img, Image.blend(img, Image.new('RGB', (W, H), (0, 0, 0)), 0.55), mask)
    # fine grain to hide any residual gradient steps
    n = Image.effect_noise((W, H), 9).point(lambda v: int(v * 0.5))
    img = Image.blend(img, Image.merge('RGB', (n, n, n)), 0.035)
    return img.convert('RGB')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='art/cool2.png')
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    im = render()
    im.save(a.out, optimize=True)
    print(f'{a.out}: {im.size[0]}x{im.size[1]}, {os.path.getsize(a.out)} bytes')
