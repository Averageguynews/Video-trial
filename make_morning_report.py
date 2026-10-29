"""Build the AGN "Morning News Report" cricket video (1080x1920, 30fps).

Usage: python3 make_morning_report.py <images_dir> <part1.mov> <part2.mov> <fonts_dir> <out.mp4>

Mark's report was filmed in two clips. Part 2 is the start of the report and
part 1 carries on from it. They are joined into one take, and the repeated
"average" at the join is cut so no words are doubled:
  part 2: 0.40s -> 11.28s   ("It is the very, very, very early report ... as the average")
  part 1: 0.15s -> 22.65s   ("fan, if you woke up this morning ... see you later")

Layout follows the earlier AGN episodes: blue background, LIVE bar, two-line
headline, photo panel on the left, Mark on the right, word-by-word captions,
BREAKING ticker and AGN logo. On top of that: animated cricket ball, bat and
stumps, emoji stickers, and the scorecards.
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

IMG, PART1, PART2, FONTS, OUT = sys.argv[1:6]
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IMG_6832.png")

W, H, FPS = 1080, 1920, 30
P2_IN, P2_OUT = 0.40, 11.28
P1_IN, P1_OUT = 0.15, 22.65
JOIN = P2_OUT - P2_IN  # where the two clips meet in the finished video
D = JOIN + (P1_OUT - P1_IN)
N = int(D * FPS)

ORANGE = (255, 165, 31)
YELLOW = (255, 224, 27)
GREEN = (140, 255, 60)
WHITE = (255, 255, 255)
PURPLE = (166, 75, 244)
RED = (228, 35, 48)
NAVY = (6, 18, 63)
BALL_RED = (190, 20, 30)
WOOD = (232, 200, 140)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


ANTON = lambda s: font("anton-latin-400-normal.woff", s)
MONT9 = lambda s: font("montserrat-latin-900-normal.woff", s)
MONT7 = lambda s: font("montserrat-latin-700-normal.woff", s)
EMOJI_FONT = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x * x


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def bump(t, a, b, ramp=0.1):
    """0..1 envelope that is 1 between a and b with eased ramps."""
    if t < a or t > b + ramp:
        return 0.0
    if t < a + ramp:
        return ease_out((t - a) / ramp)
    if t > b:
        return 1 - ease_out((t - b) / ramp)
    return 1.0


def emoji(ch, size):
    im = Image.new("RGBA", (160, 136), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=EMOJI_FONT, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def text_img(parts, fnt, stroke=0, shadow=0, spacing=0.0, pad=30):
    """parts: list of (text, color). One line of text with stroke + drop shadow."""
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    space = d0.textlength(" ", font=fnt)
    widths = []
    for t, _ in parts:
        if spacing:
            widths.append(sum(d0.textlength(c, font=fnt) + spacing for c in t) - spacing)
        else:
            widths.append(d0.textlength(t, font=fnt))
    tw = int(sum(widths) + space * (len(parts) - 1))
    asc, desc = fnt.getmetrics()
    im = Image.new("RGBA", (tw + pad * 2 + stroke * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for layer in ("shadow", "main"):
        if layer == "shadow" and not shadow:
            continue
        x = pad
        for (t, col), w in zip(parts, widths):
            ox = oy = shadow if layer == "shadow" else 0
            fill = (0, 0, 0, 170) if layer == "shadow" else col
            sf = (0, 0, 0, 170) if layer == "shadow" else (0, 0, 0)
            if spacing:
                cx = x
                for c in t:
                    d.text((cx + ox, pad + oy), c, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=sf)
                    cx += d0.textlength(c, font=fnt) + spacing
            else:
                d.text((x + ox, pad + oy), t, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=sf)
            x += w + space
    return im.crop(im.getbbox())


def paste_center(base, im, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return m


def tag(im, bg, padx=16, pady=8, tri=False):
    extra = 34 if tri else 0
    box = Image.new("RGBA", (im.width + padx * 2 + extra, im.height + pady * 2), bg)
    if tri:
        ImageDraw.Draw(box).polygon([(padx, pady + 4), (padx, box.height - pady - 4), (padx + 24, box.height / 2)], fill=WHITE)
    box.alpha_composite(im, (padx + extra, pady))
    return box


# ---------------------------------------------------------------- background (same as earlier episodes)
def make_bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.42) / H) ** 2)
    t = np.clip(r / 0.75, 0, 1)[..., None]
    inner, outer = np.array([22, 62, 200]), np.array([5, 14, 52])
    img = inner * (1 - t) + outer * t
    img *= np.clip(1.15 - (y / H)[..., None] * 0.55, 0.45, 1.0)
    streak = (np.sin((x + y * 0.8) / 34.0) > 0.92) * np.clip(1 - y / (H * 0.45), 0, 1)
    img += streak[..., None] * np.array([20, 40, 90]) * 0.5
    bg = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    arcs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(arcs)
    for i, rad in enumerate((560, 700, 860)):
        d.ellipse((W / 2 - rad, 980 - rad, W / 2 + rad, 980 + rad), outline=(120, 170, 255, 40 - i * 8), width=3)
    bg.alpha_composite(arcs)
    return bg


BG = make_bg()


def draw_arc_glints(base, t):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, (rad, spd) in enumerate(((560, 22), (700, -16), (860, 12))):
        a0 = (t * spd + i * 120) % 360
        d.arc((W / 2 - rad, 980 - rad, W / 2 + rad, 980 + rad), a0, a0 + 38, fill=(150, 200, 255, 120), width=10)
    base.alpha_composite(layer)


# ---------------------------------------------------------------- AGN logo (letters block, as in earlier episodes)
def make_logo():
    src = np.array(Image.open(LOGO).convert("RGB")).astype(np.int16)
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    red = (r > 170) & (g < 90) & (b < 100)
    ys, xs = np.where(red)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    alpha = np.zeros(red.shape, np.uint8)
    for yy in range(y0, y1 + 1):
        row = np.where(red[yy, x0:x1 + 1])[0]
        if len(row):
            alpha[yy, x0 + row.min():x0 + row.max() + 1] = 255
    rgba = np.dstack([src.astype(np.uint8), alpha])[y0:y1 + 1, x0:x1 + 1]
    im = Image.fromarray(rgba, "RGBA")
    return im.resize((360, int(360 * im.height / im.width)), Image.LANCZOS)


LOGO_IM = make_logo()


def draw_logo(base, t):
    cx, cy = W // 2, 1690
    s = 1.0 + 0.03 * math.sin(t * 2.4)
    im = LOGO_IM.resize((int(LOGO_IM.width * s), int(LOGO_IM.height * s)), Image.BILINEAR)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.45)))
    base.alpha_composite(sh, (cx - im.width // 2 + 8, cy - im.height // 2 + 10))
    ph = (t % 3.5) / 0.7
    if ph < 1.0:
        arr = np.array(im).astype(np.float32)
        yy, xx = np.mgrid[0:im.height, 0:im.width]
        pos = -0.3 + ph * 1.6
        band = np.clip(1 - np.abs((xx + yy * 0.6) / (im.width * 1.3) - pos) / 0.08, 0, 1) * 0.6
        arr[..., :3] = arr[..., :3] * (1 - band[..., None]) + 255 * band[..., None]
        im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    base.alpha_composite(im, (cx - im.width // 2, cy - im.height // 2))


# ---------------------------------------------------------------- cricket props: ball, bat, stumps
def make_ball(size=96):
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, s - 4, s - 4), fill=BALL_RED + (255,), outline=(110, 8, 15, 255), width=10)
    d.ellipse((s * 0.2, s * 0.14, s * 0.48, s * 0.36), fill=(255, 120, 120, 120))  # shine
    # seam: two rows of white stitches across the middle
    for off in (-s * 0.06, s * 0.06):
        for k in range(9):
            x = s * 0.12 + k * s * 0.095
            y = s / 2 + off + 0.09 * s * math.sin(k / 8 * math.pi) * (1 if off > 0 else -1) * 0.3
            d.line((x, y - s * 0.025, x + s * 0.04, y + s * 0.025), fill=(255, 245, 230, 255), width=8)
    d.line((s * 0.08, s / 2, s * 0.92, s / 2), fill=(120, 10, 18, 255), width=6)
    return im.resize((size, size), Image.LANCZOS)


def make_bat(length=440):
    s = 3
    w, h = 120 * s, length * s
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    handle_h = int(h * 0.32)
    d.rounded_rectangle((w * 0.36, 0, w * 0.64, handle_h + 20), 20, fill=(30, 30, 30, 255))  # grip
    for k in range(10):
        y = 14 + k * handle_h / 10
        d.line((w * 0.36, y, w * 0.64, y + 18), fill=(70, 70, 70, 255), width=6)
    d.rounded_rectangle((w * 0.06, handle_h, w * 0.94, h - 4), 40, fill=WOOD + (255,), outline=(150, 110, 60, 255), width=8)
    d.rectangle((w * 0.06 + 8, handle_h + 60, w * 0.94 - 8, handle_h + 150), fill=RED + (255,))  # sticker
    d.text((w / 2, handle_h + 105), "AGN", font=ANTON(60), fill=WHITE, anchor="mm")
    d.line((w * 0.5, handle_h + 180, w * 0.5, h - 40), fill=(205, 170, 110, 255), width=6)  # spine
    return im.resize((w // s, h // s), Image.LANCZOS)


def make_stump(h=270):
    im = Image.new("RGBA", (22, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 0, 20, h - 1), 8, fill=(250, 245, 230, 255), outline=(150, 130, 100, 255), width=2)
    d.rectangle((2, 14, 20, 30), fill=RED + (255,))
    return im


def make_bail():
    im = Image.new("RGBA", (46, 14), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, 45, 13), 6, fill=(250, 240, 210, 255), outline=(150, 130, 100, 255), width=2)
    return im


BALL = make_ball()
BAT = make_bat()
STUMP = make_stump()
BAIL = make_bail()
SMALL_STUMP = make_stump(120)
BAM = {k: text_img([(k, WHITE)], ANTON(64), stroke=5, shadow=6) for k in ("BOWLED!", "OUT!", "SIX!", "FOUR!")}


def draw_ball(base, x, y, t, scale=1.0, trail=None):
    if trail:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for k, (px, py) in enumerate(trail):
            r = 38 * scale * (k + 1) / len(trail)
            d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 200, 80, int(90 * (k + 1) / len(trail))))
        base.alpha_composite(layer)
    paste_center(base, BALL, x, y, scale, 1, (t * 900) % 360)


def pivot_rotate(im, ang):
    """Rotate an upright prop about the middle of its bottom edge.
    Returns an image whose centre is that pivot point."""
    h = im.height
    canvas = Image.new("RGBA", (2 * h, 2 * h), (0, 0, 0, 0))
    canvas.alpha_composite(im, (h - im.width // 2, 0))
    return canvas.rotate(ang, resample=Image.BICUBIC) if ang else canvas


def draw_stumps(base, cx, by, hit, alpha=1.0):
    """Three stumps standing on y=by. hit: seconds since the ball struck (<0 = not yet)."""
    k = max(0.0, hit)
    for i, dx in enumerate((-34, 0, 34)):
        ang = (14, -10, -24)[i] * ease_out(k / 0.25) if hit >= 0 else 0.0
        paste_center(base, pivot_rotate(STUMP, ang), cx + dx, by, 1, alpha)
    # bails sit on top, then fly off when hit
    for j, dx in enumerate((-17, 17)):
        if hit < 0:
            paste_center(base, BAIL, cx + dx, by - STUMP.height - 4, 1, alpha)
        else:
            vx, vy = (-380, 520)[j], (-900, -760)[j]
            x = cx + dx + vx * k
            y = by - STUMP.height - 4 + vy * k + 1700 * k * k
            if y < H:
                paste_center(base, BAIL, x, y, 1, alpha, (k * (700 if j else -800)) % 360)


def bowled_anim(base, t, t0, label, side="right"):
    """Ball pitches and crashes into the stumps. Runs from t0 for ~1.6s."""
    tt = t - t0
    if tt < 0 or tt > 1.75:
        return 0.0
    fade = 1 - ease_out((tt - 1.45) / 0.3)
    sx = W - 170 if side == "right" else 170
    by = 1270
    draw_stumps(base, sx, by, tt - 0.55, fade)
    # ball path: enter from the far side, bounce at bx, hit stumps at 0.55s
    dirn = -1 if side == "right" else 1
    x0, y0 = W / 2 - dirn * 640, 640
    bx, bounce_y = W / 2 - dirn * 40, by - 10
    hx, hy = sx + dirn * 10, by - 150
    trail = []

    def pos(u):
        if u < 0.35:
            p = u / 0.35
            return x0 + (bx - x0) * p, y0 + (bounce_y - y0) * p * p
        p = min((u - 0.35) / 0.2, 1.0)
        return bx + (hx - bx) * p, bounce_y + (hy - bounce_y) * math.sin(p * math.pi / 2)

    if tt < 0.55:
        for k in range(6):
            trail.append(pos(max(0.0, tt - (6 - k) * 0.025)))
        x, y = pos(tt)
        draw_ball(base, x, y, t, 1.0, trail)
    else:
        k = tt - 0.55  # ball rebounds off the stumps
        x, y = hx - dirn * 260 * k, hy - 300 * k + 900 * k * k
        if y < H:
            draw_ball(base, x, y, t, 1.0)
        if 0 <= k < 0.25:
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            r = 40 + 260 * ease_out(k / 0.25)
            ImageDraw.Draw(ring).ellipse((hx - r, hy - r, hx + r, hy + r), outline=(255, 230, 120, int(230 * (1 - k / 0.25))), width=10)
            base.alpha_composite(ring)
        s = ease_back(k / 0.2)
        paste_center(base, BAM[label], sx - dirn * 60, by - STUMP.height - 110, s, fade, 8 * dirn)
        paste_center(base, FIRE, sx - dirn * 210, by - STUMP.height - 120, s, fade, 12 * math.sin(t * 9))
    return 1.0 if 0.55 <= tt < 0.75 else 0.0


def bat_anim(base, t, t0, label):
    """Bat swings and smacks the ball out of the ground. Runs from t0 for ~1.4s."""
    tt = t - t0
    if tt < 0 or tt > 1.5:
        return 0.0
    fade = 1 - ease_out((tt - 1.2) / 0.3)
    pivot = (300, 960)  # top of the handle
    ent = ease_back(tt / 0.25)
    if tt < 0.4:
        ang = -100 * ease_out(tt / 0.25)  # wind up (blade back)
    else:
        ang = -100 + 170 * ease_out((tt - 0.4) / 0.18)  # swing through
    bat = BAT.rotate(ang, resample=Image.BICUBIC, expand=True)
    # keep the handle top fixed at the pivot
    a = math.radians(ang)
    hx, hy = 0, -BAT.height / 2  # handle top relative to bat centre
    rx, ry = hx * math.cos(a) + hy * math.sin(a), -hx * math.sin(a) + hy * math.cos(a)
    paste_center(base, bat, pivot[0] - rx, pivot[1] - ry, ent, fade)
    # ball comes in from the right, gets hit at 0.48s, flies off up-right
    hit_t = 0.45  # blade is straight down here
    contact = (pivot[0], pivot[1] + 330)
    if tt < hit_t:
        p = tt / hit_t
        x = W + 60 + (contact[0] - W - 60) * p
        y = 1150 + (contact[1] - 1150) * p - 160 * math.sin(p * math.pi)
        draw_ball(base, x, y, t, 0.9)
        return 0.0
    k = tt - hit_t
    x, y = contact[0] + 1500 * k, contact[1] - 1700 * k + 900 * k * k
    trail = [(contact[0] + 1500 * (k - j * 0.03), contact[1] - 1700 * (k - j * 0.03) + 900 * (k - j * 0.03) ** 2)
             for j in range(6, 0, -1) if k - j * 0.03 > 0]
    if x < W + 80:
        draw_ball(base, x, y, t, 0.9 + 0.3 * k, trail)
    if k < 0.2:
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        r = 30 + 200 * ease_out(k / 0.2)
        ImageDraw.Draw(ring).ellipse((contact[0] - r, contact[1] - r, contact[0] + r, contact[1] + r),
                                     outline=(255, 230, 120, int(230 * (1 - k / 0.2))), width=10)
        base.alpha_composite(ring)
    s = ease_back(k / 0.2)
    paste_center(base, BAM[label], 760, 930, s * 1.2, fade, -8)
    paste_center(base, BAT_EMOJI, 940, 830, s, fade, 12 * math.sin(t * 9))
    return 1.0 if k < 0.2 else 0.0


def four_wickets(base, t, t0, t1):
    """'4 for 40': four little stumps get knocked over one after another."""
    if not (t0 <= t <= t1 + 0.3):
        return
    fade = 1 - ease_out((t - t1) / 0.3)
    for i in range(4):
        cx = W / 2 - 165 + i * 110
        by = 1240
        ti = t0 + 0.12 + i * 0.16
        k = t - ti
        ang = 0 if k < 0 else 80 * ease_out(k / 0.2) * (1 if i % 2 else -1)
        paste_center(base, pivot_rotate(SMALL_STUMP, ang), cx, by, 1, fade)
        if 0 <= k < 0.18:
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            r = 20 + 80 * (k / 0.18)
            ImageDraw.Draw(ring).ellipse((cx - r, by - 60 - r, cx + r, by - 60 + r), outline=(255, 230, 120, int(220 * (1 - k / 0.18))), width=6)
            base.alpha_composite(ring)


FIRE = emoji("\U0001F525", 110)
BAT_EMOJI = emoji("\U0001F3CF", 120)


# ---------------------------------------------------------------- photos and scorecards
def fit(fname, w, h, fx=0.5, fy=0.5, zoom=1.0):
    im = Image.open(os.path.join(IMG, fname)).convert("RGB")
    ar = w / h
    cw = min(im.width, im.height * ar) / zoom
    ch = cw / ar
    x0 = min(max(fx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(fy * im.height - ch / 2, 0), im.height - ch)
    return im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))


LP = dict(x=20, y=600, w=500, h=830, border=10, color=PURPLE)
RP = dict(x=516, y=588, w=544, h=852, border=8, color=WHITE)
LW, LH = LP["w"] - 2 * LP["border"], LP["h"] - 2 * LP["border"]

# left panel photo schedule: (start, file, focus x, focus y, zoom)
PHOTOS = [
    (0.00, "2fe4ff98-image.jpg", 0.50, 0.45, 1.00),   # Starc
    (4.46, "dfa0e6ea-image.jpg", 0.60, 0.42, 1.05),   # Lyon bowling
    (7.66, "0f1b2798-image.jpg", 0.45, 0.45, 1.00),   # raising the bat
    (9.16, "6315cfd9-image.jpg", 0.52, 0.50, 1.00),   # century celebration
    (10.40, "692e1ab2-image.jpg", 0.55, 0.45, 1.00),  # bowler in sunglasses
    (12.50, "72845c92-image.jpg", 0.50, 0.62, 1.00),  # bowling scorecard
    (22.92, "dfa0e6ea-image.jpg", 0.60, 0.42, 1.05),  # Lyon
    (26.96, "6315cfd9-image.jpg", 0.52, 0.50, 1.00),  # celebration
    (28.10, "2f4d0253-image.jpg", 0.50, 0.45, 1.00),  # keeper
    (31.50, "2fe4ff98-image.jpg", 0.50, 0.45, 1.00),  # Starc
]
# crop a little bigger than the panel so the photos can slowly zoom
PHOTO_IMS = [fit(f, LW, LH, fx, fy, z).resize((int(LW * 1.12), int(LH * 1.12)), Image.LANCZOS) for _, f, fx, fy, z in PHOTOS]


def photo_at(t):
    i = max(k for k, p in enumerate(PHOTOS) if p[0] <= t)
    t0 = PHOTOS[i][0]
    t1 = PHOTOS[i + 1][0] if i + 1 < len(PHOTOS) else D
    im = PHOTO_IMS[i]
    z = 1.0 + 0.1 * (t - t0) / max(t1 - t0, 0.1)  # slow push-in
    cw, ch = LW * im.width / (LW * 1.12) / z, LH * im.height / (LH * 1.12) / z
    x0, y0 = (im.width - cw) / 2, (im.height - ch) / 2
    out = im.resize((LW, LH), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
    flash = 1 - ease_out((t - t0) / 0.15) if t0 > 0 else 0
    if flash > 0:
        out.alpha_composite(Image.new("RGBA", out.size, (255, 255, 255, int(200 * flash))))
    return out


def make_score_card():
    """The stumps summary graphic, as a big card that pops over the headline."""
    im = Image.open(os.path.join(IMG, "e5559fe4-image.jpg")).convert("RGB")
    w = 960
    im = im.resize((w, int(w * im.height / im.width)), Image.LANCZOS)
    b = 10
    card = Image.new("RGBA", (im.width + 2 * b, im.height + 2 * b), (0, 0, 0, 0))
    card.paste(Image.new("RGBA", card.size, YELLOW + (255,)), (0, 0), rounded_mask(card.width, card.height, 26))
    card.paste(im, (b, b), rounded_mask(im.width, im.height, 18))
    pad = 30
    out = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sh.putalpha(rounded_mask(card.width, card.height, 26).point(lambda v: int(v * 0.6)))
    out.alpha_composite(sh, (pad + 8, pad + 14))
    out = out.filter(ImageFilter.GaussianBlur(10))
    out.alpha_composite(card, (pad, pad))
    return out


SCORE_CARD = make_score_card()
SCORE_TAG = tag(text_img([("STUMPS, DAY 3", WHITE)], ANTON(40)), RED + (255,), padx=14, pady=4)
SCORE_IN, SCORE_OUT = 12.50, 17.70


# ---------------------------------------------------------------- captions (timed from speech recognition)
WORDS = [
    (0.00, 0.74, "It"), (0.74, 0.98, "is"), (0.98, 1.18, "the"), (1.18, 1.52, "very"), (1.62, 1.84, "very"),
    (1.96, 2.38, "very"), (2.38, 2.84, "early"), (2.84, 3.26, "report"), (3.26, 3.48, "this"), (3.48, 3.74, "morning"),
    (3.74, 4.24, "because"), (4.24, 4.46, "the"), (4.46, 4.84, "Australian"), (4.84, 5.18, "cricket"),
    (5.18, 5.58, "team"), (5.70, 6.16, "they"), (6.16, 6.44, "have"), (6.44, 6.78, "learnt"), (6.78, 7.16, "how"),
    (7.16, 7.24, "to"), (7.24, 7.66, "bowl"), (7.66, 8.28, "along"), (8.28, 8.54, "with"), (8.54, 8.78, "learning"),
    (8.78, 9.00, "how"), (9.00, 9.16, "to"), (9.16, 9.60, "bat"), (10.00, 10.12, "now"), (10.12, 10.28, "as"),
    (10.28, 10.40, "the"), (10.40, 10.74, "average"), (10.74, 11.08, "fan"), (11.16, 11.22, "if"),
    (11.22, 11.34, "you"), (11.34, 11.56, "woke"), (11.56, 11.72, "up"), (11.72, 11.92, "this"),
    (11.92, 12.24, "morning"), (12.50, 12.82, "checked"), (12.82, 13.02, "the"), (13.02, 13.22, "cricket"),
    (13.22, 13.52, "score"), (13.52, 13.68, "and"), (13.68, 13.82, "you"), (13.82, 14.06, "saw"), (14.06, 14.26, "that"),
    (14.26, 14.46, "South"), (14.46, 14.78, "Africa"), (14.78, 15.02, "were"), (15.02, 15.26, "in"),
    (15.26, 15.96, "theory"), (15.96, 16.74, "four"), (16.74, 17.58, "forty"), (17.80, 18.26, "you'd"),
    (18.26, 18.38, "be"), (18.38, 18.60, "very"), (18.60, 18.82, "happy"), (19.46, 19.98, "you'd"), (19.98, 20.08, "be"),
    (20.08, 20.38, "very"), (20.38, 20.66, "happy"), (20.90, 21.14, "I"), (21.14, 21.36, "was"), (21.36, 21.66, "very"),
    (21.66, 21.94, "happy"), (21.94, 22.24, "waking"), (22.24, 22.52, "up"), (22.92, 23.32, "let's"),
    (23.32, 23.44, "see"), (23.44, 23.52, "if"), (23.52, 23.64, "we"), (23.64, 23.74, "can"), (23.74, 23.98, "actually"),
    (23.98, 24.42, "finish"), (24.42, 24.62, "it"), (24.62, 24.90, "tonight"), (24.90, 25.34, "by"),
    (25.34, 25.78, "bowling"), (25.78, 25.96, "the"), (25.96, 26.38, "Proteas"), (26.38, 26.62, "out"),
    (26.96, 27.32, "getting"), (27.32, 27.48, "the"), (27.48, 27.74, "runs"), (28.10, 28.38, "taking"),
    (28.38, 28.56, "the"), (28.56, 28.80, "series"), (28.80, 29.16, "victory"), (29.16, 29.56, "and"),
    (29.56, 29.78, "proving"), (29.78, 30.00, "why"), (30.00, 30.24, "we"), (30.24, 30.72, "are"),
    (30.72, 30.86, "number"), (30.86, 31.12, "one"), (31.12, 31.22, "in"), (31.22, 31.32, "the"),
    (31.32, 31.50, "world"), (32.28, 32.44, "see"), (32.44, 32.56, "you"), (32.56, 32.78, "later"),
]

HL, GR = YELLOW, GREEN
# (number of words, words as shown, colour per word)
PHRASES = [
    (2, "IT IS", "ww"), (2, "THE VERY,", "ww"), (1, "VERY,", "w"), (2, "VERY EARLY", "wy"), (1, "REPORT", "w"),
    (2, "THIS MORNING", "wy"), (2, "BECAUSE THE", "ww"), (1, "AUSTRALIAN", "y"), (2, "CRICKET TEAM", "yy"),
    (3, "THEY HAVE LEARNT", "www"), (3, "HOW TO BOWL!", "wwg"), (2, "ALONG WITH", "ww"), (1, "LEARNING", "w"),
    (3, "HOW TO BAT!", "wwg"), (3, "NOW AS THE", "www"), (2, "AVERAGE FAN,", "yy"), (4, "IF YOU WOKE UP", "wwww"),
    (2, "THIS MORNING,", "wy"), (2, "CHECKED THE", "ww"), (2, "CRICKET SCORE", "wy"), (4, "AND YOU SAW THAT", "wwww"),
    (2, "SOUTH AFRICA", "yy"), (1, "WERE", "w"), (2, "IN THEORY...", "ww"), (2, "4 FOR 40!", "ggg"),
    (4, "YOU'D BE VERY HAPPY", "wwwy"), (4, "YOU'D BE VERY HAPPY", "wwwy"), (4, "I WAS VERY HAPPY", "wwwy"),
    (2, "WAKING UP!", "ww"), (5, "LET'S SEE IF WE CAN", "wwwww"), (2, "ACTUALLY FINISH", "wy"), (2, "IT TONIGHT", "wy"),
    (2, "BY BOWLING", "wy"), (3, "THE PROTEAS OUT!", "wgg"), (3, "GETTING THE RUNS,", "wwy"), (3, "TAKING THE SERIES", "wwy"),
    (1, "VICTORY!", "g"), (4, "AND PROVING WHY WE", "wwww"), (3, "ARE NUMBER ONE", "wyy"), (3, "IN THE WORLD!", "wwg"),
    (3, "SEE YOU LATER!", "wwy"),
]
assert sum(p[0] for p in PHRASES) == len(WORDS), (sum(p[0] for p in PHRASES), len(WORDS))
COLS = {"w": WHITE, "y": HL, "g": GR}

CAPS = []
_i = 0
for n, text, cols in PHRASES:
    start = WORDS[_i][0]
    _i += n
    end = WORDS[_i][0] if _i < len(WORDS) else D
    if end - WORDS[_i - 1][1] > 0.5:  # don't hold a caption through a long pause
        end = WORDS[_i - 1][1] + 0.45
    CAPS.append((start, end, list(zip(text.split(), (COLS[c] for c in cols)))))


def caption_img(parts):
    im = text_img(parts, MONT9(84), stroke=9, shadow=7)
    if im.width > 1000:
        im = im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS)
    return im


CAP_IMS = [caption_img(p) for _, _, p in CAPS]

# emoji stickers: (start, end, emoji, x, y, size)
STICKERS = [
    (3.26, 4.40, "☀️", 950, 730, 140),
    (4.46, 5.70, "\U0001F1E6\U0001F1FA", 950, 740, 140),
    (10.40, 11.10, "\U0001F9CD", 950, 760, 120),
    (11.72, 12.50, "☕", 950, 760, 130),
    (14.26, 15.02, "\U0001F440", 950, 760, 140),
    (15.26, 15.96, "\U0001F914", 950, 760, 140),
    (17.80, 19.30, "\U0001F601", 950, 760, 150),
    (19.46, 20.80, "\U0001F604", 130, 760, 150),
    (20.90, 22.70, "\U0001F973", 950, 760, 150),
    (24.42, 25.20, "\U0001F319", 950, 740, 130),
    (28.56, 29.70, "\U0001F3C6", 950, 760, 160),
    (30.24, 31.20, "\U0001F947", 950, 740, 150),
    (31.12, 31.95, "\U0001F30F", 130, 760, 150),
    (32.28, D, "\U0001F44B", 950, 760, 150),
]
STICKER_IMS = {s[2]: emoji(s[2], s[5]) for s in STICKERS}

# ---------------------------------------------------------------- static text
LIVE_TXT = text_img([("LIVE", WHITE)], ANTON(36))
EP_TXT = text_img([("MORNING NEWS REPORT", (210, 220, 245))], MONT7(28), spacing=5)
FOLLOW_TXT = text_img([("FOLLOW FOR MORE", YELLOW)], MONT9(28), spacing=5)
LINE1 = text_img([("AUSSIES", WHITE)], ANTON(176), stroke=4, shadow=10)
LINE2 = text_img([("ON TOP!", ORANGE)], ANTON(196), stroke=4, shadow=10)
TAG_RED_BOX = tag(text_img([("LIVE FROM NEWLANDS", WHITE)], ANTON(34)), RED + (255,), tri=True)
CTX1 = text_img([("SA v AUS", YELLOW)], MONT9(34))
CTX2 = text_img([("3RD TEST, DAY 3", WHITE)], MONT9(30))
CTX_BOX = Image.new("RGBA", (400, 100), (0, 0, 0, 225))
CTX_BOX.alpha_composite(CTX1, (18, 12))
CTX_BOX.alpha_composite(emoji("\U0001F3CF", 40), (18 + CTX1.width + 12, 10))
CTX_BOX.alpha_composite(CTX2, (18, 58))
NAME_BOX = tag(text_img([("MARK", WHITE)], ANTON(44)), (24, 80, 220, 255), padx=14, pady=6)
ROLE_BOX = tag(text_img([("CHIEF AGN CORRESPONDENT", YELLOW)], MONT9(19), spacing=1), (0, 0, 0, 235), padx=10, pady=6)

# BREAKING ticker, with little cricket balls between the items
TICK_Y, TICK_H = 1508, 70
BREAK_TAG = tag(text_img([("BREAKING", WHITE)], ANTON(44)), RED + (255,), padx=14, pady=4)
TICK_ITEMS = ["SA 4-140 AT STUMPS", "LEAD BY JUST 40", "STARC 2-29", "LYON 1-31 OFF 14 OVERS",
              "AUSSIES LEARN TO BOWL", "AND TO BAT", "MARK 'VERY HAPPY'", "SERIES WIN ON THE CARDS"]


def make_tick_strip():
    f = MONT9(30)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    gap = 80
    width = sum(int(d0.textlength(it, font=f)) + gap for it in TICK_ITEMS)
    strip = Image.new("RGBA", (width * 2, TICK_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    ball = BALL.resize((28, 28), Image.LANCZOS)
    x = 0
    for _ in range(2):
        for it in TICK_ITEMS:
            d.text((x, TICK_H / 2), it, font=f, fill=NAVY, anchor="lm")
            x += int(d0.textlength(it, font=f)) + gap
            strip.alpha_composite(ball, (int(x - gap / 2 - 14), TICK_H // 2 - 14))
    return strip, width


TICK_STRIP, TICK_W = make_tick_strip()


def draw_ticker(base, t):
    bar = Image.new("RGBA", (W, TICK_H), WHITE + (245,))
    off = int(t * 210) % TICK_W
    bar.alpha_composite(TICK_STRIP.crop((off, 0, off + W, TICK_H)))
    ImageDraw.Draw(bar).rectangle((0, 0, W, 4), fill=RED + (255,))
    bar.alpha_composite(BREAK_TAG, (0, (TICK_H - BREAK_TAG.height) // 2))
    base.alpha_composite(bar, (0, TICK_Y))


# ---------------------------------------------------------------- Mark's video (both clips joined)
class MarkReader:
    def __init__(self, w, h):
        self.w, self.h = w, h
        vf = (f"[0:v]trim={P2_IN}:{P2_OUT},setpts=PTS-STARTPTS,fps={FPS}[a];"
              f"[1:v]trim={P1_IN}:{P1_OUT},setpts=PTS-STARTPTS,fps={FPS}[b];"
              f"[a][b]concat=n=2:v=1:a=0,scale={w}:{h},format=rgb24[v]")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", PART2, "-i", PART1, "-filter_complex", vf,
                                   "-map", "[v]", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        buf = self.p.stdout.read(self.w * self.h * 3)
        if len(buf) == self.w * self.h * 3:
            self.last = Image.fromarray(np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3))
        return self.last


def view(img, cx, cy, vw, vh, out_w, out_h):
    x0, y0 = (cx - vw / 2) * img.width, (cy - vh / 2) * img.height
    return img.resize((out_w, out_h), Image.BICUBIC, box=(x0, y0, x0 + vw * img.width, y0 + vh * img.height))


def build_panel(content, p):
    b = p["border"]
    frame = Image.new("RGBA", (p["w"], p["h"]), (0, 0, 0, 0))
    frame.paste(Image.new("RGBA", frame.size, p["color"] + (255,)), (0, 0), rounded_mask(p["w"], p["h"], 26))
    inner = content.convert("RGBA")
    frame.paste(inner, (b, b), rounded_mask(inner.width, inner.height, 18))
    return frame


PUNCHES = [(16.0, 17.6), (28.8, 29.5), (30.72, 31.5)]  # zoom-ins on Mark for the big lines


def main():
    rw, rh = RP["w"] - 2 * RP["border"], RP["h"] - 2 * RP["border"]
    mark = MarkReader(720, 1280)
    enc = None if os.environ.get("PREVIEW") else subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", PART2, "-i", PART1,
         "-filter_complex",
         f"[1:a]atrim={P2_IN}:{P2_OUT},asetpts=PTS-STARTPTS,aresample=48000[a0];"
         f"[2:a]atrim={P1_IN}:{P1_OUT},asetpts=PTS-STARTPTS,aresample=48000[a1];"
         f"[a0][a1]concat=n=2:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,"
         f"afade=t=in:d=0.05,afade=t=out:st={D - 0.3}:d=0.3[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{D:.3f}", OUT],
        stdin=subprocess.PIPE)
    rng = random.Random(7)
    preview = [float(x) for x in os.environ.get("PREVIEW", "").split(",") if x]

    for i in range(N):
        t = i / FPS
        if preview:
            img = mark.next()
            if not any(abs(t - p) < 0.5 / FPS for p in preview):
                continue
        fr = BG.copy()
        draw_arc_glints(fr, t)

        # --- top bar: LIVE + show name (switches to a follow prompt near the end)
        blink = 1.0 if int(t * 2) % 2 == 0 else 0.55
        live = tag(LIVE_TXT, RED + (255,), padx=34, pady=8)
        ImageDraw.Draw(live).ellipse((10, live.height / 2 - 8, 26, live.height / 2 + 8), fill=(255, 255, 255, int(255 * blink)))
        fr.alpha_composite(live, (50, 168))
        lbl = FOLLOW_TXT if t > 31.5 else EP_TXT
        fr.alpha_composite(lbl, (50 + live.width + 34, 168 + (live.height - lbl.height) // 2))
        if t > 31.5:
            x = 50 + live.width + 34 + lbl.width + 16
            yc = 168 + live.height // 2
            nudge = 6 * math.sin(t * 10)
            ImageDraw.Draw(fr).polygon([(x + nudge, yc - 12), (x + nudge, yc + 12), (x + 18 + nudge, yc)], fill=YELLOW)

        # --- screen shake on the big moments
        shake = (bump(t, 15.96, 16.3, 0.05) + bump(t, 28.8, 29.1, 0.05) + 0.7 * bump(t, 30.72, 31.0, 0.05)
                 + 0.6 * bump(t, 7.8, 8.0, 0.04) + 0.6 * bump(t, 25.9, 26.1, 0.04))
        sx, sy = (rng.uniform(-9, 9) * shake, rng.uniform(-9, 9) * shake) if shake else (0, 0)

        # --- left panel: photos and scorecard
        lc = photo_at(t)
        cs = ease_out((t - 0.25) / 0.3)
        if cs > 0:
            lc.alpha_composite(TAG_RED_BOX, (int(-TAG_RED_BOX.width + (TAG_RED_BOX.width + 16) * cs), 20))
        lc.alpha_composite(CTX_BOX, (16, 20 + TAG_RED_BOX.height + 8))
        left = build_panel(lc, LP)

        # --- right panel: Mark, with punch-in zooms (and a quick punch to hide the join)
        if not preview:
            img = mark.next()
        zr = 1.0 + 0.04 * (t % 6) / 6
        for a, b in PUNCHES:
            zr += 0.16 * bump(t, a, b, 0.08)
        zr += 0.12 * bump(t, JOIN - 0.02, JOIN + 0.3, 0.06)
        vw = 1 / zr
        vh = (rh / rw) * (720 / 1280) / zr
        tcx = min(max(0.5, vw / 2), 1 - vw / 2)
        tcy = min(max(0.42 - 0.06 * (zr - 1), vh / 2), 1 - vh / 2)
        rc = view(img, tcx, tcy, vw, vh, rw, rh).convert("RGBA")
        nm = ease_out((t - 0.35) / 0.3) * (1 - ease_out((t - 4.2) / 0.3))
        if nm > 0:
            off = int((1 - nm) * -300)
            rc.alpha_composite(NAME_BOX, (18 + off, 18))
            rc.alpha_composite(ROLE_BOX, (18 + off, 18 + NAME_BOX.height))
        right = build_panel(rc, RP)

        si = ease_out(t / 0.3)
        fr.alpha_composite(left, (int(LP["x"] - (1 - si) * 560 + sx), int(LP["y"] + sy)))
        fr.alpha_composite(right, (int(RP["x"] + (1 - si) * 600 + sx), int(RP["y"] + sy)))

        # --- headline, swapped for the stumps scorecard while Mark talks about the score
        sc = bump(t, SCORE_IN, SCORE_OUT, 0.25)
        hl_a = 1 - sc
        s1 = 1 + 0.9 * (1 - ease_out(t / 0.28))
        paste_center(fr, LINE1, W / 2, 352, s1, min(1, t / 0.12) * hl_a)
        t2 = t - 0.18
        if t2 > 0:
            pulse = 0.03 * math.sin(t * 6) * (t > 0.6) + 0.1 * bump(t, 30.72, 31.1, 0.08)
            s2 = 1 + 1.0 * (1 - ease_out(t2 / 0.28)) + pulse
            paste_center(fr, LINE2, W / 2 + sx, 500 + sy, s2, min(1, t2 / 0.12) * hl_a)
        ul = ease_out((t - 0.4) / 0.35) * hl_a
        if ul > 0:
            ImageDraw.Draw(fr).rectangle((W / 2 - 400 * ul, 580, W / 2 + 400 * ul, 585), fill=ORANGE + (int(255 * ul),))
        if sc > 0:
            k = ease_back((t - SCORE_IN) / 0.35) if t < SCORE_OUT else 1.0
            ang = -2 + 2 * math.sin(t * 1.5)
            paste_center(fr, SCORE_CARD, W / 2 + sx, 400 + sy, k * (1 + 0.04 * bump(t, 15.96, 16.5, 0.1)), sc, ang)
            paste_center(fr, SCORE_TAG, 905 + sx, 205 + sy, k, sc, 4)

        # --- cricket animations
        hit = 0.0
        hit += bowled_anim(fr, t, 7.0, "BOWLED!")
        hit += bat_anim(fr, t, 8.75, "SIX!")
        hit += bowled_anim(fr, t, 25.4, "OUT!", side="left")
        hit += bat_anim(fr, t, 26.85, "FOUR!")
        four_wickets(fr, t, 15.96, 17.7)

        # --- emoji stickers
        for a, b, ch, x, y, sz in STICKERS:
            if a <= t <= b:
                k = ease_back((t - a) / 0.25) * (1 - ease_out((t - b + 0.12) / 0.12))
                paste_center(fr, STICKER_IMS[ch], x + sx, y + sy, k, 1, 10 * math.sin(t * 8))

        # --- captions
        for (a, b, _), im in zip(CAPS, CAP_IMS):
            if a <= t < b:
                pop = 1 + 0.35 * (1 - ease_back((t - a) / 0.14))
                paste_center(fr, im, W / 2 + sx, 1385 + sy, max(pop, 0.6))
                break

        draw_ticker(fr, t)
        draw_logo(fr, t)

        # quick white flash at the start and at the join between the two clips
        fl = 0.0
        if t < 0.12:
            fl = 1 - t / 0.12
        if JOIN - 0.03 <= t < JOIN + 0.12:
            fl = max(fl, 0.6 * (1 - abs(t - JOIN) / 0.12))
        if fl > 0:
            fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * fl))))

        if preview:
            fr.convert("RGB").save(f"{OUT}_{t:05.2f}.jpg")
            continue
        enc.stdin.write(fr.convert("RGB").tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{N}", flush=True)

    if enc:
        enc.stdin.close()
        enc.wait()
    print("done", OUT)


if __name__ == "__main__":
    main()
