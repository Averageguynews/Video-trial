"""Build the ~7-second AGN "Morning News Report" intro, version 3 (1080x1920, 30fps).

Usage: python3 make_agn_intro_v3.py <images_dir> <sound_clip> <fonts_dir> <out.mp4>

Same as v2, with Australian cricketer photos and a "MORNING NEWS REPORT" title.
The sound clip can be the audio already in AGN_intro_v2.mp4 (it is used as-is).

Same look as the 3-second intro (blue background, AGN circle logo), but with
the Shane Falco speech clip as the soundtrack, a new set of champion photos,
and extra animation to fill the longer runtime:
  - photos pop in on the speech beats, each with a shockwave ring
  - a scrolling LIVE news ticker along the bottom
  - a big punch on the last beat (shake + flash)
  - as the crowd swells: photos blast off-screen, confetti falls,
    and a "THIS WEEK IN SPORT" title slams in under the logo
  - push-in and white flash to finish
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

IMG_DIR, SOUND, FONTS, OUT = sys.argv[1:5]
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IMG_6832.png")

W, H, FPS, D = 1080, 1920, 30, 6.9
N = int(D * FPS)
PUNCH = 4.30  # last spoken beat
FINALE = 5.0  # crowd swell starts

ORANGE = (255, 165, 31)
WHITE = (255, 255, 255)
RED = (228, 35, 48)
NAVY = (6, 18, 63)
BLUE = (70, 140, 255)
GOLD = (255, 206, 60)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


ANTON = lambda s: font("anton-latin-400-normal.woff", s)
MONT9 = lambda s: font("montserrat-latin-900-normal.woff", s)
MONT8 = lambda s: font("montserrat-latin-800-normal.woff", s)

# (file, focus x, focus y, crop zoom, centre x, centre y, rotation, pop time)
# Pop times land on the beats of the speech.
CARDS = [
    ("2fe4ff98-image.jpg", 0.50, 0.42, 1.00, 255, 440, -8, 0.55),  # Starc
    ("dfa0e6ea-image.jpg", 0.58, 0.33, 1.30, 825, 420, 7, 0.85),  # Lyon bowling
    ("0f1b2798-image.jpg", 0.50, 0.40, 1.00, 255, 1490, 6, 2.15),  # batter raising bat
    ("2f4d0253-image.jpg", 0.50, 0.50, 1.00, 825, 1470, -6, 2.40),  # keeper
    ("6315cfd9-image.jpg", 0.55, 0.50, 1.00, 545, 290, -3, 2.65),  # century celebration
    ("692e1ab2-image.jpg", 0.55, 0.38, 1.00, 540, 1630, 4, PUNCH),  # bowler with sunglasses
]
CARD_W, CARD_H, BORDER = 370, 462, 10


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c = 2.2
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x


# ---------------------------------------------------------------- background (same as v1)
def make_bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.5) / H) ** 2)
    t = np.clip(r / 0.75, 0, 1)[..., None]
    inner, outer = np.array([22, 62, 200]), np.array([5, 14, 52])
    img = inner * (1 - t) + outer * t
    streak = (np.sin((x + y * 0.8) / 34.0) > 0.92) * 0.5
    img += streak[..., None] * np.array([20, 40, 90]) * 0.5
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


BG = make_bg()


def draw_rings(base, t, cy):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = W / 2
    for i, rad in enumerate((470, 620, 790)):
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(120, 170, 255, 45 - i * 10), width=3)
    for i, (rad, spd) in enumerate(((470, 160), (620, -110), (790, 80))):
        a0 = (t * spd + i * 120) % 360
        d.arc((cx - rad, cy - rad, cx + rad, cy + rad), a0, a0 + 40, fill=(150, 200, 255, 140), width=10)
    base.alpha_composite(layer)


def draw_shockwaves(base, t, cy):
    """Expanding ring from the logo every time a photo lands."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hits = [c[7] for c in CARDS] + [PUNCH + 0.12, FINALE + 0.55]
    for t0 in hits:
        p = (t - t0) / 0.55
        if 0 <= p < 1:
            rad = 320 + ease_out(p) * 650
            a = int(170 * (1 - p))
            w = int(14 * (1 - p)) + 2
            d.ellipse((W / 2 - rad, cy - rad, W / 2 + rad, cy + rad), outline=(160, 210, 255, a), width=w)
    base.alpha_composite(layer)


# ---------------------------------------------------------------- logo (same as v1)
def make_logo(size=620):
    src = Image.open(LOGO).convert("RGBA")
    s = src.width
    mask = Image.new("L", (s * 2, s * 2), 0)
    rad = s * 0.488
    ImageDraw.Draw(mask).ellipse((s - rad * 2, s - rad * 2, s + rad * 2, s + rad * 2), fill=255)
    mask = mask.resize((s, s), Image.LANCZOS)
    src.putalpha(mask)
    logo = src.resize((size, size), Image.LANCZOS)
    pad = 80
    glow = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    g = Image.new("RGBA", (size, size), BLUE + (0,))
    g.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.9)))
    glow.alpha_composite(g, (pad, pad))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.55)))
    glow.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (pad + 6, pad + 14))
    glow.alpha_composite(logo, (pad, pad))
    return glow, logo.getchannel("A")


LOGO_IM, LOGO_MASK = make_logo()
SHINES = (1.35, 3.40, 6.05)


def logo_with_shine(t):
    for s0 in SHINES:
        ph = (t - s0) / 0.55
        if 0 <= ph < 1:
            im = LOGO_IM.copy()
            arr = np.array(im).astype(np.float32)
            hh, ww = arr.shape[:2]
            yy, xx = np.mgrid[0:hh, 0:ww]
            pos = -0.3 + ph * 1.6
            band = np.clip(1 - np.abs((xx + yy * 0.6) / (ww * 1.3) - pos) / 0.07, 0, 1) * 0.55
            m = np.zeros((hh, ww), np.float32)
            pad = (ww - LOGO_MASK.width) // 2
            m[pad:pad + LOGO_MASK.height, pad:pad + LOGO_MASK.width] = np.array(LOGO_MASK) / 255.0
            band *= m
            arr[..., :3] = arr[..., :3] * (1 - band[..., None]) + 255 * band[..., None]
            return Image.fromarray(arr.astype(np.uint8), "RGBA")
    return LOGO_IM


# ---------------------------------------------------------------- photo cards (same style as v1)
def make_card(fname, fx, fy, zoom):
    im = Image.open(os.path.join(IMG_DIR, fname)).convert("RGB")
    ar = CARD_W / CARD_H
    cw = min(im.width, im.height * ar) / zoom
    ch = cw / ar
    x0 = min(max(fx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(fy * im.height - ch / 2, 0), im.height - ch)
    photo = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((CARD_W, CARD_H), Image.LANCZOS)
    cw2, ch2 = CARD_W + BORDER * 2, CARD_H + BORDER * 2
    card = Image.new("RGBA", (cw2, ch2), (0, 0, 0, 0))
    m = Image.new("L", (cw2, ch2), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cw2 - 1, ch2 - 1), 22, fill=255)
    card.paste(Image.new("RGBA", (cw2, ch2), WHITE + (255,)), (0, 0), m)
    pm = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(pm).rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), 14, fill=255)
    card.paste(photo, (BORDER, BORDER), pm)
    pad = 40
    out = Image.new("RGBA", (cw2 + pad * 2, ch2 + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", (cw2, ch2), (0, 0, 0, 0))
    sh.putalpha(m.point(lambda v: int(v * 0.6)))
    out.alpha_composite(sh, (pad + 10, pad + 16))
    out = out.filter(ImageFilter.GaussianBlur(14))
    out.alpha_composite(card, (pad, pad))
    return out


CARD_IMS = [make_card(f, fx, fy, z) for f, fx, fy, z, *_ in CARDS]


def paste_center(base, im, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    im = im.resize((w, h), Image.BILINEAR)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ---------------------------------------------------------------- text
def text_img(text, fnt, fill, stroke=0, stroke_fill=NAVY, shadow=10, pad=30):
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t_, r, b = d0.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + pad * 2 + shadow, b - t_ + pad * 2 + shadow), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shadow:
        d.text((pad - l + shadow, pad - t_ + shadow), text, font=fnt, fill=(0, 0, 0, 160),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 160))
    d.text((pad - l, pad - t_), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


TITLE_1 = text_img("MORNING", ANTON(170), WHITE, stroke=6)
TITLE_2 = text_img("NEWS REPORT", ANTON(170), ORANGE, stroke=6)

# ticker
TICK_Y, TICK_H = 1838, 74
TAG = Image.new("RGBA", (190, TICK_H), RED + (255,))
_d = ImageDraw.Draw(TAG)
_d.ellipse((22, TICK_H / 2 - 10, 42, TICK_H / 2 + 10), fill=WHITE)
_d.text((54, TICK_H / 2), "LIVE", font=MONT9(36), fill=WHITE, anchor="lm")
TICK_ITEMS = ["AVERAGE GUY NEWS", "MORNING NEWS REPORT", "CRICKET", "THE SCORES", "THE HOT TAKES"]


def make_tick_strip():
    f = MONT8(32)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    gap = 70
    width = sum(int(d0.textlength(it, font=f)) + gap for it in TICK_ITEMS)
    strip = Image.new("RGBA", (width * 2, TICK_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    x = 0
    for _ in range(2):
        for it in TICK_ITEMS:
            d.text((x, TICK_H / 2), it, font=f, fill=NAVY, anchor="lm")
            x += int(d0.textlength(it, font=f)) + gap
            cx = x - gap / 2
            d.ellipse((cx - 7, TICK_H / 2 - 7, cx + 7, TICK_H / 2 + 7), fill=RED)
    return strip, width


TICK_STRIP, _tw = make_tick_strip()


def draw_ticker(base, t):
    if t < 1.0:
        return
    slide = ease_out((t - 1.0) / 0.35)
    y = int(TICK_Y + (1 - slide) * 140)
    bar = Image.new("RGBA", (W, TICK_H), WHITE + (245,))
    off = int((t - 1.0) * 230) % _tw
    bar.alpha_composite(TICK_STRIP.crop((off, 0, off + W, TICK_H)))
    bar.alpha_composite(TAG, (0, 0))
    # thin blue rule on top
    ImageDraw.Draw(bar).rectangle((0, 0, W, 4), fill=BLUE + (255,))
    base.alpha_composite(bar, (0, y))


# ---------------------------------------------------------------- confetti
CRNG = np.random.default_rng(3)
NCONF = 170
CONF = dict(
    x=CRNG.uniform(-40, W + 40, NCONF),
    y0=CRNG.uniform(-1700, -40, NCONF),
    vy=CRNG.uniform(650, 1050, NCONF),
    sway=CRNG.uniform(20, 60, NCONF),
    freq=CRNG.uniform(3, 7, NCONF),
    ph=CRNG.uniform(0, 6.28, NCONF),
    spin=CRNG.uniform(-9, 9, NCONF),
    w=CRNG.uniform(14, 26, NCONF),
    h=CRNG.uniform(7, 12, NCONF),
    col=CRNG.integers(0, 5, NCONF),
)
CONF_COLS = [RED, WHITE, BLUE, GOLD, ORANGE]


def draw_confetti(base, t):
    if t < FINALE:
        return
    tt = t - FINALE
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(NCONF):
        y = CONF["y0"][i] + CONF["vy"][i] * tt
        if y < -40 or y > H + 40:
            continue
        x = CONF["x"][i] + CONF["sway"][i] * math.sin(CONF["freq"][i] * tt + CONF["ph"][i])
        a = CONF["spin"][i] * tt + CONF["ph"][i]
        w = CONF["w"][i] * (0.35 + 0.65 * abs(math.cos(a * 1.3)))  # flutter
        h = CONF["h"][i]
        ca, sa = math.cos(a), math.sin(a)
        pts = [(x + px * ca - py * sa, y + px * sa + py * ca)
               for px, py in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        d.polygon(pts, fill=CONF_COLS[CONF["col"][i]] + (235,))
    base.alpha_composite(layer)


# ---------------------------------------------------------------- frame
def frame(t, rng):
    # finale: logo rises and grows to make room for the title
    fin = ease_out((t - FINALE) / 0.5)
    logo_cy = H / 2 - 110 * fin
    fr = BG.copy()
    draw_rings(fr, t, logo_cy)
    draw_shockwaves(fr, t, logo_cy)

    # screen shake on the last beat and on the title slam
    sx = sy = 0
    for t0, amp, dur in ((PUNCH, 18, 0.25), (FINALE + 0.55, 12, 0.2)):
        if t0 <= t < t0 + dur:
            k = 1 - (t - t0) / dur
            sx, sy = rng.integers(-amp, amp + 1) * k, rng.integers(-amp, amp + 1) * k

    # final push-in
    push = 1 + 0.2 * ease_out((t - 6.6) / 0.3) if t > 6.6 else 1.0

    for i, ((f, fx, fy, z, cx, cy, rot, t0), im) in enumerate(zip(CARDS, CARD_IMS)):
        if t < t0:
            continue
        p = (t - t0) / 0.28
        s = ease_back(p) * (1 + 0.025 * (t - t0))  # pop, then slow zoom
        a = min(1.0, p * 2.5)
        wob = rot + (1 - ease_out(p)) * rot * 1.6 + 1.5 * math.sin(t * 2.2 + i)  # gentle sway
        bob = 8 * math.sin(t * 2.6 + i * 1.7)  # float
        if PUNCH <= t < PUNCH + 0.2:
            s *= 1 + 0.07 * (1 - (t - PUNCH) / 0.2)
        # blast off-screen as the crowd swells, one after another
        out_t = FINALE + 0.07 * i
        ox = oy = 0.0
        if t > out_t:
            q = ease_in((t - out_t) / 0.55)
            dx, dy = cx - W / 2, cy - H / 2
            n = math.hypot(dx, dy)
            ox, oy = dx / n * 1500 * q, dy / n * 1500 * q
            wob += q * 70 * (1 if dx > 0 else -1)
            if q >= 1:
                continue
        px = W / 2 + (cx - W / 2) * push + sx + ox
        py = H / 2 + (cy - H / 2) * push + sy + bob + oy
        paste_center(fr, im, px, py, s * push, wob, a)

    # logo: pop in, breathe, punch on the last beat, grow for the finale
    ls = ease_back(t / 0.3) * (1 + 0.02 * math.sin(t * 5)) * (1 + 0.1 * fin)
    for t0 in (PUNCH, FINALE + 0.55):
        if t0 <= t < t0 + 0.3:
            ls *= 1 + 0.12 * math.sin(math.pi * (t - t0) / 0.3)
    paste_center(fr, logo_with_shine(t), W / 2 + sx, logo_cy + sy, ls * push)

    # title slam under the logo
    for k, (im, y, t0) in enumerate(((TITLE_1, 1360, FINALE + 0.45), (TITLE_2, 1530, FINALE + 0.55))):
        if t >= t0:
            p = (t - t0) / 0.18
            s = 2.6 - 1.6 * ease_out(p)
            paste_center(fr, im, W / 2 + sx, H / 2 + (y - H / 2) * push + sy, s * push, 0, min(1, p * 1.5))

    draw_confetti(fr, t)
    draw_ticker(fr, t)

    # flashes: last beat, title slam, white-out at the end
    flash = 0.0
    for t0, amt in ((PUNCH, 0.45), (FINALE + 0.55, 0.3)):
        if t0 <= t < t0 + 0.12:
            flash = max(flash, amt * (1 - (t - t0) / 0.12))
    if t > 6.7:
        flash = max(flash, ease_out((t - 6.7) / 0.2) * 0.92)
    if flash > 0:
        fr = Image.blend(fr, Image.new("RGBA", (W, H), WHITE + (255,)), flash)
    return fr.convert("RGB")


def main():
    rng = np.random.default_rng(7)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", SOUND,
         "-filter_complex",
         # soundtrack is the already-mixed audio from AGN_intro_v2.mp4
         f"[1:a]atrim=0:{D},asetpts=PTS-STARTPTS,aresample=48000[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(D), OUT],
        stdin=subprocess.PIPE)
    for i in range(N):
        ff.stdin.write(frame(i / FPS, rng).tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
