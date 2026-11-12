"""Procedural art renderer for make.fun's art bounties (PIL only, deterministic).

Two modes:
  cool   - a dusk scene: huge low sun with bloom, layered ridgelines with atmospheric
           perspective, a mirror lake, stars, one tiny figure for scale, film grain
  cute   - a round fluffy creature with big glossy eyes in a pastel bokeh field

Run:  python3 render.py --mode cool --out art/cool.png
"""
import argparse
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W = H = 1024


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def vgrad(size, stops):
    """Vertical gradient from [(pos0..1, colour), ...]."""
    w, h = size
    img = Image.new('RGB', (1, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                px[0, y] = lerp(c0, c1, k)
                break
        else:
            px[0, y] = stops[-1][1]
    return img.resize(size, Image.BICUBIC)


def smooth_noise(n, seed):
    """Deterministic 1-D value noise in [0,1], smooth over n samples."""
    rnd = random.Random(seed)
    pts = [rnd.random() for _ in range(n + 2)]
    out = []
    for i in range(n):
        t = i / 1.0
        i0 = int(math.floor(t)) % (n + 1)
        f = t - math.floor(t)
        f = f * f * (3 - 2 * f)
        out.append(pts[i0] * (1 - f) + pts[(i0 + 1) % (n + 2)] * f)
    return out


def ridge(width, seed, base, amp, octaves=4, roughness=0.55):
    """Fractal ridgeline y(x) as a list of heights."""
    rnd = random.Random(seed)
    accum = [0.0] * width
    a = amp
    freq = 1.0
    for o in range(octaves):
        pts = []
        count = max(2, int(freq * 8))
        vals = [rnd.uniform(-1, 1) for _ in range(count + 1)]
        for x in range(width):
            t = (x / width) * count
            i0 = int(t)
            f = t - i0
            f = f * f * (3 - 2 * f)
            pts.append(vals[i0] * (1 - f) + vals[i0 + 1] * f)
        for x in range(width):
            accum[x] += pts[x] * a
        a *= roughness
        freq *= 2.0
    return [base - accum[x] for x in range(width)]


def glow(img, radius, strength=1.0, bright=1.0):
    """Screen-blended bloom from the bright parts of img."""
    small = img.resize((img.width // 4, img.height // 4), Image.BILINEAR)
    b = small.filter(ImageFilter.GaussianBlur(radius))
    b = b.point(lambda v: min(255, int(v * bright)))
    b = b.resize(img.size, Image.BICUBIC)
    return ImageChops.screen(img, Image.eval(b, lambda v: int(v * strength)))


def grain(img, amount=6, seed=7):
    rnd = random.Random(seed)
    noise = Image.new('L', (img.width, img.height))
    px = noise.load()
    for y in range(img.height):
        for x in range(img.width):
            px[x, y] = 128 + rnd.randint(-amount, amount)
    return Image.blend(img, Image.merge('RGB', (noise, noise, noise)), 0.06)


def vignette(img, strength=0.55):
    w, h = img.size
    mask = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w * 0.15, -h * 0.25, w * 1.15, h * 1.15], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w // 6))
    dark = Image.new('RGB', (w, h), (0, 0, 0))
    return Image.composite(img, Image.blend(img, dark, strength), mask)


def render_cool():
    horizon = 0.62
    sky = vgrad((W, H),
                [(0.0, (8, 10, 28)), (0.25, (26, 22, 58)), (0.45, (86, 44, 82)),
                 (0.58, (196, 96, 74)), (0.615, (245, 176, 96)), (0.625, (255, 214, 150)),
                 (0.64, (28, 20, 34)), (1.0, (6, 8, 16))])
    img = sky.copy()
    d = ImageDraw.Draw(img, 'RGBA')

    # stars, denser and brighter higher up
    rnd = random.Random(11)
    for _ in range(1500):
        x = rnd.uniform(0, W)
        y = rnd.uniform(0, H * horizon * 0.92)
        fall = 1.0 - (y / (H * horizon))
        if rnd.random() > fall ** 1.6:
            continue
        r = rnd.choice([0.6, 0.8, 1.0, 1.3])
        a = int(90 + 150 * fall * rnd.random())
        d.ellipse([x - r, y - r, x + r, y + r], fill=(235, 240, 255, a))

    # the sun: a huge low disc just above the horizon
    sun_y = H * (horizon - 0.075)
    sun_r = W * 0.135
    halo = Image.new('RGB', (W, H), (0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for i in range(26, 0, -1):
        rr = sun_r * (1 + i * 0.16)
        c = int(52 * (1 - i / 27) ** 2)
        hd.ellipse([W / 2 - rr, sun_y - rr, W / 2 + rr, sun_y + rr], fill=(c, int(c * 0.62), int(c * 0.3)))
    img = ImageChops.add(img, halo.filter(ImageFilter.GaussianBlur(W // 40)))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(18, 0, -1):
        rr = sun_r * (1 + i * 0.045)
        k = 1 - i / 19
        d.ellipse([W / 2 - rr, sun_y - rr, W / 2 + rr, sun_y + rr],
                  fill=(int(250 * k), int(150 * k), int(84 * k), 26))
    d.ellipse([W / 2 - sun_r, sun_y - sun_r, W / 2 + sun_r, sun_y + sun_r], fill=(255, 238, 206))

    # thin cloud bands crossing the disc
    for i, (yy, hh, al) in enumerate([(sun_y - sun_r * 0.45, 10, 90), (sun_y - sun_r * 0.05, 16, 70),
                                      (sun_y + sun_r * 0.42, 22, 60), (sun_y + sun_r * 0.78, 12, 46)]):
        wob = smooth_noise(W, 100 + i)
        for x in range(W):
            y = yy + (wob[x] - 0.5) * 26
            d.rectangle([x, y, x + 1, y + hh], fill=(52, 30, 46, al))

    # ridgelines, far to near, each darker and sharper
    layers = [(0.0, 0.075, 46, (74, 62, 104), 0.52), (0.10, 0.10, 33, (52, 44, 78), 0.60),
              (0.28, 0.13, 22, (32, 28, 54), 0.68), (0.46, 0.16, 14, (18, 16, 34), 0.78)]
    for i, (dy, amp, seed, col, rough) in enumerate(layers):
        base = H * (horizon - 0.055 + dy)
        ys = ridge(W, 300 + seed, base, H * amp, octaves=5, roughness=rough)
        poly = [(x, ys[x]) for x in range(W)] + [(W, H), (0, H)]
        d.polygon(poly, fill=col)

    # the lake: mirrored sun plus horizontal banding
    lake_top = int(H * (horizon + 0.16))
    lake = img.crop((0, lake_top, W, H)).transpose(Image.FLIP_TOP_BOTTOM)
    lake = lake.filter(ImageFilter.GaussianBlur(3))
    lake = Image.blend(lake, Image.new('RGB', lake.size, (10, 14, 30)), 0.55)
    img.paste(lake, (0, lake_top))
    d = ImageDraw.Draw(img, 'RGBA')
    for i in range(90):
        y = lake_top + (H - lake_top) * (i / 90) ** 1.6
        wob = smooth_noise(W // 8, 700 + i)
        width_scale = 0.10 + 0.9 * (i / 90)
        for x in range(0, W, 8):
            xx = x / 8
            off = (wob[int(xx) % (W // 8)] - 0.5) * 22 * width_scale
            a = int(60 * (1 - i / 90) ** 1.4)
            d.rectangle([x + off, y, x + 8 + off, y + 2], fill=(255, 214, 160, a))

    # a lone figure on the shore for scale
    fx, fy = W * 0.5, H * (horizon + 0.145)
    d.ellipse([fx - 4, fy - 34, fx + 4, fy - 26], fill=(6, 6, 12))
    d.polygon([(fx - 7, fy), (fx + 7, fy), (fx + 4, fy - 26), (fx - 4, fy - 26)], fill=(6, 6, 12))

    img = glow(img, 6, strength=0.55, bright=0.9)
    img = vignette(img, 0.5)
    img = grain(img, 5, seed=3)
    return img


def render_cute():
    img = vgrad((W, H), [(0.0, (255, 226, 238)), (0.45, (252, 214, 226)),
                         (0.75, (250, 226, 240)), (1.0, (255, 240, 246))])
    d = ImageDraw.Draw(img, 'RGBA')
    # soft bokeh field
    rnd = random.Random(21)
    for _ in range(90):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.uniform(18, 88)
        c = rnd.choice([(255, 255, 255), (255, 208, 226), (214, 236, 255), (255, 232, 196)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (rnd.randint(18, 44),))
    img = img.filter(ImageFilter.GaussianBlur(9))
    d = ImageDraw.Draw(img, 'RGBA')

    cx, cy = W * 0.5, H * 0.55
    # body
    for i in range(30, 0, -1):
        r = 210 + i * 3.2
        d.ellipse([cx - r, cy - r * 0.92, cx + r, cy + r * 0.92],
                  fill=(255, 236, 244, 5))
    d.ellipse([cx - 212, cy - 196, cx + 212, cy + 196], fill=(255, 250, 252))
    # ears
    for sx in (-1, 1):
        d.ellipse([cx + sx * 150 - 62, cy - 250 - 40, cx + sx * 150 + 62, cy - 250 + 96],
                  fill=(255, 250, 252))
        d.ellipse([cx + sx * 150 - 34, cy - 236 - 26, cx + sx * 150 + 34, cy - 236 + 58],
                  fill=(255, 206, 222))
    # cheeks
    for sx in (-1, 1):
        d.ellipse([cx + sx * 132 - 56, cy + 16 - 30, cx + sx * 132 + 56, cy + 16 + 30],
                  fill=(255, 176, 200, 130))
    # eyes: big, glossy, with two highlights each
    for sx in (-1, 1):
        ex = cx + sx * 84
        ey = cy - 26
        d.ellipse([ex - 62, ey - 72, ex + 62, ey + 72], fill=(38, 30, 52))
        d.ellipse([ex - 44, ey - 54, ex + 44, ey + 56], fill=(78, 62, 104))
        d.ellipse([ex - 34, ey - 40, ex + 10, ey - 6], fill=(255, 255, 255, 240))
        d.ellipse([ex + 6, ey + 14, ex + 30, ey + 38], fill=(255, 255, 255, 150))
    # nose and mouth
    d.ellipse([cx - 12, cy + 32, cx + 12, cy + 48], fill=(255, 168, 196))
    d.arc([cx - 34, cy + 44, cx, cy + 84], 10, 170, fill=(140, 96, 120), width=6)
    d.arc([cx, cy + 44, cx + 34, cy + 84], 10, 170, fill=(140, 96, 120), width=6)
    # little paws
    for sx in (-1, 1):
        d.ellipse([cx + sx * 96 - 46, cy + 150 - 34, cx + sx * 96 + 46, cy + 150 + 40],
                  fill=(255, 250, 252))
    img = glow(img, 10, strength=0.35, bright=1.0)
    img = vignette(img, 0.22)
    return img


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['cool', 'cute'], default='cool')
    ap.add_argument('--out', default='art/out.png')
    a = ap.parse_args()
    import os
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    img = render_cool() if a.mode == 'cool' else render_cute()
    img = img.convert('RGB')
    img.save(a.out, optimize=True)
    print(f'{a.out}: {img.size[0]}x{img.size[1]}, {os.path.getsize(a.out)} bytes')
