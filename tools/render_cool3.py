"""Layered paper-cut (kirigami) dusk scene — a style procedural drawing can do cleanly.

Each ridge is a filled polygon with a soft drop shadow onto the layer behind, a warm rim light
on the sun-facing edge, and a fine paper grain. Composition is deliberately off-centre: the sun
sits on the left third, a lone pine on the right, the valley opening between them.
Rendered at 2x and reduced with LANCZOS so the edges are crisp, not aliased.
"""
import argparse
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

SS = 2
S = 1024 * SS


def gradient(stops, rnd):
    img = Image.new('RGB', (1, S))
    px = img.load()
    for y in range(S):
        t = y / (S - 1)
        col = stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0)
                k = k * k * (3 - 2 * k)
                col = tuple(c0[j] + (c1[j] - c0[j]) * k for j in range(3))
                break
        d = rnd.uniform(-0.6, 0.6)
        px[0, y] = tuple(int(max(0, min(255, c + d))) for c in col)
    return img.resize((S, S), Image.BICUBIC)


def ridge(seed, base, amp, rough, w=S, octaves=5):
    rnd = random.Random(seed)
    acc = [0.0] * w
    a, freq = amp, 1.0
    for _ in range(octaves):
        count = max(2, int(freq * 5))
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


def pine(d, x, y, h, col, width_frac=0.34):
    """A simple layered conifer silhouette."""
    tiers = 5
    for i in range(tiers):
        t = i / tiers
        w = h * width_frac * (1 - t * 0.72)
        y0 = y - h * (1 - t)
        d.polygon([(x - w, y0), (x + w, y0), (x, y0 - h * 0.34)], fill=col)
    d.rectangle([x - h * 0.028, y - h * 0.10, x + h * 0.028, y], fill=col)


def render(seed=20261113):
    rnd = random.Random(seed)
    stops = [(0.00, (18, 20, 52)), (0.18, (36, 34, 82)), (0.34, (74, 48, 104)),
             (0.47, (146, 70, 106)), (0.545, (214, 110, 92)), (0.585, (248, 168, 104)),
             (0.605, (255, 214, 150)), (0.612, (120, 78, 96)), (0.70, (44, 34, 62)),
             (1.00, (18, 16, 34))]
    img = gradient(stops, rnd)
    d = ImageDraw.Draw(img, 'RGBA')

    # stars
    for _ in range(1600):
        x, y = rnd.uniform(0, S), rnd.uniform(0, S * 0.42)
        fade = (1 - y / (S * 0.45)) ** 1.4
        if rnd.random() > fade:
            continue
        r = rnd.choice([0.8, 1.2, 1.6, 2.2]) * SS / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, int(70 + 160 * fade)))

    # the sun, off-centre left, with a layered halo
    sx, sy, sr = S * 0.335, S * 0.567, S * 0.098
    halo = Image.new('RGB', (S, S), (0, 0, 0))
    hp = halo.load()
    reach = int(sr * 5)
    for y in range(max(0, int(sy - reach)), min(S, int(sy + reach))):
        for x in range(max(0, int(sx - reach)), min(S, int(sx + reach))):
            dd = math.hypot(x - sx, y - sy) / sr
            if dd > 5:
                continue
            v = math.exp(-2.2 * dd) * 0.85 + math.exp(-12.0 * dd) * 1.2
            hp[x, y] = (int(min(255, 255 * v)), int(min(255, 186 * v)), int(min(255, 116 * v)))
    img = ImageChops.add(img, halo.filter(ImageFilter.GaussianBlur(4 * SS)))
    d = ImageDraw.Draw(img, 'RGBA')
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 246, 216))
    d.ellipse([sx - sr * 0.72, sy - sr * 0.72, sx + sr * 0.72, sy + sr * 0.72], fill=(255, 252, 236))

    # paper-cut layers: far -> near, each with a drop shadow and a lit edge
    layers = [
        (0.000, 0.048, 11, (122, 96, 138), 0.50, 3.0),
        (0.070, 0.070, 12, (98, 74, 118), 0.55, 4.0),
        (0.160, 0.092, 13, (74, 56, 100), 0.60, 5.0),
        (0.270, 0.110, 14, (54, 42, 80), 0.65, 6.5),
        (0.400, 0.130, 15, (36, 30, 60), 0.70, 8.0),
        (0.545, 0.150, 16, (22, 20, 42), 0.76, 9.5),
    ]
    for dy, amp, sd, col, rough, blur in layers:
        base = S * (0.615 - 0.02 + dy)
        ys = ridge(sd, base, S * amp, rough)
        poly = [(x, ys[x]) for x in range(S)] + [(S, S), (0, S)]
        # shadow cast onto the layer behind
        sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon([(x, y + blur * 1.5) for x, y in poly], fill=(10, 8, 22, 130))
        img = Image.alpha_composite(img.convert('RGBA'),
                                    sh.filter(ImageFilter.GaussianBlur(blur))).convert('RGB')
        d = ImageDraw.Draw(img, 'RGBA')
        d.polygon(poly, fill=col)
        # rim light on the sun-facing edge, only where the crest faces the sun
        for x in range(S):
            y = int(ys[x])
            dx = (x - sx) / S
            lit = max(0.0, 1.0 - abs(dx) * 1.7)
            if lit <= 0.02:
                continue
            a = int(120 * lit)
            d.point((x, y), fill=(255, 206, 158, a))
            d.point((x, y + 1), fill=(255, 188, 140, int(a * 0.55)))

    # a lone pine on the right, and a smaller one near the valley
    d = ImageDraw.Draw(img, 'RGBA')
    pine(d, S * 0.775, S * 0.735, S * 0.20, (14, 13, 28))
    pine(d, S * 0.845, S * 0.760, S * 0.125, (20, 18, 36))
    pine(d, S * 0.560, S * 0.706, S * 0.070, (16, 15, 30))

    # thin mist bands between the near layers
    mist = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    md = ImageDraw.Draw(mist)
    for i, (yy, hh, al) in enumerate([(0.66, 0.030, 60), (0.72, 0.022, 45), (0.80, 0.016, 30)]):
        md.rectangle([0, S * yy, S, S * (yy + hh)], fill=(214, 186, 206, al))
    img = Image.alpha_composite(img.convert('RGBA'),
                                mist.filter(ImageFilter.GaussianBlur(26 * SS))).convert('RGB')

    # paper grain: fine, uniform, low amplitude
    n = Image.effect_noise((S, S), 14)
    img = Image.blend(img, Image.merge('RGB', (n, n, n)), 0.030)

    # gentle warm bloom and a soft vignette
    img = ImageChops.add(img, img.filter(ImageFilter.GaussianBlur(18 * SS)).point(lambda v: int(v * 0.22)))
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).ellipse([-S * 0.06, -S * 0.10, S * 1.06, S * 1.06], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(S // 10))
    img = Image.composite(img, Image.blend(img, Image.new('RGB', (S, S), (0, 0, 0)), 0.45), mask)
    return img.resize((1024, 1024), Image.LANCZOS).convert('RGB')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='art/cool3.png')
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    im = render()
    im.save(a.out, optimize=True)
    print(f'{a.out}: {im.size[0]}x{im.size[1]}, {os.path.getsize(a.out)} bytes')
