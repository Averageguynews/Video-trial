"""AGN breaking news tribute: "We will miss you Sir Patrick" (1080x1920, 30fps, 15s).

Usage: python3 make_sir_patrick_tribute.py <photos_dir> <music_clip> <fonts_dir> <out.mp4>

0-3s   the 3-second AGN intro, photos removed: logo in the middle,
       "BREAKING NEWS" above, "It's a sad day for movie lovers" below.
3-15s  photo collage that pops in one card at a time under the title
       "We will miss you Sir Patrick", ending on the memorial card.
Music is taken from <music_clip> and runs under the whole video.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PHOTOS, MUSIC, FONTS, OUT = sys.argv[1:5]
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IMG_6832.png")

W, H, FPS, D = 1080, 1920, 30, 15.0
N = int(D * FPS)
INTRO = 3.0

RED = (227, 37, 50)
GOLD = (232, 196, 120)
WHITE = (255, 255, 255)


def font(path, size):
    return ImageFont.truetype(os.path.join(FONTS, path), size)


ANTON = lambda s: font("anton-latin-400-normal.woff", s)
MONT9 = lambda s: font("montserrat-latin-900-normal.woff", s)
MONT7 = lambda s: font("montserrat-latin-700-normal.woff", s)
PLAY7 = lambda s: font("playfair-display-latin-700-normal.woff", s)
PLAY4 = lambda s: font("playfair-display-latin-400-normal.woff", s)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_back(x, c=1.4):
    x = clamp01(x)
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def with_alpha(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def paste_center(base, im, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    im = with_alpha(im, alpha)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def text_img(txt, fnt, fill, spacing=0, shadow=True):
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    widths = [d0.textlength(c, font=fnt) for c in txt]
    tw = int(sum(widths) + spacing * (len(txt) - 1))
    asc, desc = fnt.getmetrics()
    pad = 30
    im = Image.new("RGBA", (tw + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for c, w in zip(txt, widths):
        d.text((x, pad), c, font=fnt, fill=fill)
        x += w + spacing
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.6)))
        sh = sh.filter(ImageFilter.GaussianBlur(9))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(sh, (0, 6))
        out.alpha_composite(im)
        return out
    return im


# ------------------------------------------------------------------ backgrounds
def radial_bg(inner, outer, streaks=True):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.5) / H) ** 2)
    t = np.clip(r / 0.75, 0, 1)[..., None]
    img = np.array(inner) * (1 - t) + np.array(outer) * t
    if streaks:
        streak = (np.sin((x + y * 0.8) / 34.0) > 0.92) * 0.5
        img += streak[..., None] * np.array([20, 40, 90]) * 0.35
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


# same look as the usual intro, a touch darker for a sad story
INTRO_BG = radial_bg((16, 46, 150), (4, 10, 38))
COLLAGE_BG = radial_bg((24, 34, 66), (3, 5, 14), streaks=False)


def draw_rings(base, t, alpha=1.0):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H / 2
    for i, rad in enumerate((470, 620, 790)):
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(120, 170, 255, int((40 - i * 10) * alpha)), width=3)
    for i, (rad, spd) in enumerate(((470, 60), (620, -40), (790, 30))):  # slower than usual
        a0 = (t * spd + i * 120) % 360
        d.arc((cx - rad, cy - rad, cx + rad, cy + rad), a0, a0 + 40, fill=(150, 200, 255, int(120 * alpha)), width=8)
    base.alpha_composite(layer)


# ------------------------------------------------------------------ logo (as in the usual intro)
def make_logo(size=600):
    src = Image.open(LOGO).convert("RGBA")
    s = src.width
    mask = Image.new("L", (s * 2, s * 2), 0)
    rad = s * 0.488
    ImageDraw.Draw(mask).ellipse((s - rad * 2, s - rad * 2, s + rad * 2, s + rad * 2), fill=255)
    src.putalpha(mask.resize((s, s), Image.LANCZOS))
    logo = src.resize((size, size), Image.LANCZOS)
    pad = 80
    out = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    g = Image.new("RGBA", (size, size), (70, 140, 255, 0))
    g.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.8)))
    out.alpha_composite(g, (pad, pad))
    out = out.filter(ImageFilter.GaussianBlur(28))
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.55)))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (pad + 6, pad + 14))
    out.alpha_composite(logo, (pad, pad))
    return out


LOGO_IM = make_logo()


def make_breaking():
    txt = text_img("BREAKING NEWS", ANTON(118), WHITE, spacing=6, shadow=False)
    bw, bh = txt.width + 40, 170
    im = Image.new("RGBA", (bw + 60, bh + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sk = 22  # slanted bar, like the logo
    d.polygon([(30 + sk, 30), (30 + bw, 30), (30 + bw - sk, 30 + bh), (30, 30 + bh)], fill=RED + (255,))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.5)))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), (0, 10))
    out.alpha_composite(im)
    out.alpha_composite(txt, ((out.width - txt.width) // 2, (out.height - txt.height) // 2 - 4))
    return out


BREAKING = make_breaking()
SAD1 = text_img("IT'S A SAD DAY", MONT9(84), WHITE, spacing=3)
SAD2 = text_img("FOR MOVIE LOVERS", MONT9(84), WHITE, spacing=3)


def intro_frame(t):
    fr = INTRO_BG.copy()
    draw_rings(fr, t)

    # logo eases in and breathes gently
    ls = ease_back(t / 0.45, 1.0) * (1 + 0.012 * math.sin(t * 3))
    paste_center(fr, LOGO_IM, W / 2, H / 2, ls)

    # BREAKING NEWS drops in above, with a soft pulse
    p = (t - 0.25) / 0.4
    if p > 0:
        pulse = 1 + 0.02 * math.sin(max(0, t - 0.65) * 6)
        paste_center(fr, BREAKING, W / 2, 400 - 60 * (1 - ease_out(p)), pulse, alpha=clamp01(p * 2))

    # "It's a sad day for movie lovers" fades up below
    for img, t0, y in ((SAD1, 0.9, 1490), (SAD2, 1.25, 1590)):
        p = (t - t0) / 0.6
        if p > 0:
            paste_center(fr, img, W / 2, y + 30 * (1 - ease_out(p)), alpha=ease_out(p))

    # slow dip to black into the tribute (no white flash on a sad one)
    if t > 2.6:
        fr = Image.blend(fr, Image.new("RGBA", (W, H), (0, 0, 0, 255)), ease_out((t - 2.6) / 0.4))
    return fr


# ------------------------------------------------------------------ collage
TITLE1 = text_img("We will miss you", PLAY4(92), WHITE, spacing=1)
TITLE2 = text_img("SIR PATRICK", PLAY7(126), GOLD, spacing=6)
DATES = text_img("1940  –  2026", MONT7(40), (200, 205, 220), spacing=8)

CARD_W, CARD_H, BORDER = 450, 340, 12

# (file, focus x, focus y, zoom, centre x, centre y, rotation)
CARDS = [
    ("f941adea-image.jpg", 0.50, 0.40, 1.00, 300, 660, -5),  # Captain Picard
    ("4669bde4-image.jpg", 0.50, 0.24, 1.00, 790, 720, 5),  # Professor X, X-Men
    ("e6c27d9d-image.jpg", 0.50, 0.30, 1.00, 290, 1000, 4),  # knighthood
    ("4d3e62ad-image.jpg", 0.45, 0.45, 1.00, 800, 1060, -4),  # Logan, with Hugh Jackman
    ("18d79299-image.jpg", 0.50, 0.33, 1.00, 300, 1350, -3),  # Peabody Award
    ("8b07c930-image.jpg", 0.50, 0.40, 1.00, 790, 1400, 6),  # Cerebro
    ("d7fa2959-image.jpg", 0.40, 0.42, 1.00, 300, 1690, 5),  # Logan
    ("1b8cc40a-image.jpg", 0.50, 0.50, 1.00, 790, 1730, -5),  # The Emoji Movie
]
MEMORIAL = "97fc5c8d-image.jpg"

T_TITLE = 3.25
T_CARD0, CARD_GAP = 4.0, 0.8
T_MEM = 11.0
T_FADE = 14.0


def rounded_card(photo, border, r_out=20, r_in=12):
    pw, ph = photo.size
    cw, ch = pw + border * 2, ph + border * 2
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), r_out, fill=255)
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    card.paste(Image.new("RGBA", (cw, ch), (250, 248, 242, 255)), (0, 0), m)
    pm = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(pm).rounded_rectangle((0, 0, pw - 1, ph - 1), r_in, fill=255)
    card.paste(photo, (border, border), pm)
    pad = 44
    out = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sh.putalpha(m.point(lambda v: int(v * 0.7)))
    out.alpha_composite(sh, (pad + 10, pad + 18))
    out = out.filter(ImageFilter.GaussianBlur(16))
    out.alpha_composite(card, (pad, pad))
    return out


def make_card(fname, fx, fy, zoom):
    im = Image.open(os.path.join(PHOTOS, fname)).convert("RGB")
    ar = CARD_W / CARD_H
    cw = min(im.width, im.height * ar) / zoom
    ch = cw / ar
    x0 = min(max(fx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(fy * im.height - ch / 2, 0), im.height - ch)
    photo = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((CARD_W, CARD_H), Image.LANCZOS)
    return rounded_card(photo, BORDER)


CARD_IMS = [make_card(*c[:4]) for c in CARDS]
mem = Image.open(os.path.join(PHOTOS, MEMORIAL)).convert("RGB")
mem = mem.resize((940, int(940 * mem.height / mem.width)), Image.LANCZOS)
MEM_IM = rounded_card(mem, 14)

# soft floating light specks
_rng = np.random.default_rng(3)
SPECKS = [(_rng.uniform(0, W), _rng.uniform(0, H), _rng.uniform(3, 9), _rng.uniform(15, 45), _rng.uniform(0, 6.28))
          for _ in range(40)]


def draw_specks(base, t):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x, y, r, spd, ph in SPECKS:
        yy = (y - spd * t) % H
        xx = x + 18 * math.sin(t * 0.6 + ph)
        a = int(70 + 50 * math.sin(t * 1.3 + ph))
        d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=(255, 230, 180, a))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3)))


def collage_frame(t):
    fr = COLLAGE_BG.copy()
    draw_specks(fr, t)
    tc = t - INTRO

    # whole collage drifts in slowly (gentle Ken Burns)
    push = 1 + 0.03 * clamp01(tc / (D - INTRO))
    dim = 1 - 0.65 * ease_out((t - T_MEM) / 0.8)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, ((f, fx, fy, z, cx, cy, rot), im) in enumerate(zip(CARDS, CARD_IMS)):
        t0 = T_CARD0 + i * CARD_GAP
        if t < t0:
            continue
        p = (t - t0) / 0.5
        s = 0.92 * ease_back(p, 1.2) * (1 + 0.01 * (t - t0))
        wob = rot + (1 - ease_out(p)) * rot * 1.5
        px = W / 2 + (cx - W / 2) * push
        py = H / 2 + (cy - H / 2) * push + 40 * (1 - ease_out(p))
        paste_center(layer, im, px, py, s * push, wob, clamp01(p * 2))
    if dim < 1:
        layer = with_alpha(layer, dim)
    fr.alpha_composite(layer)

    # title
    p = (t - T_TITLE) / 0.9
    if p > 0:
        a = ease_out(p)
        paste_center(fr, TITLE1, W / 2, 170 + 20 * (1 - a), alpha=a)
    p = (t - T_TITLE - 0.35) / 1.0
    if p > 0:
        a = ease_out(p)
        paste_center(fr, TITLE2, W / 2, 300, 0.94 + 0.06 * a, alpha=a)
        # thin gold rule either side of the dates
        ImageDraw.Draw(fr).line((W / 2 - 330 * a, 418, W / 2 - 190, 418), fill=GOLD + (int(200 * a),), width=2)
        ImageDraw.Draw(fr).line((W / 2 + 190, 418, W / 2 + 330 * a, 418), fill=GOLD + (int(200 * a),), width=2)
        paste_center(fr, DATES, W / 2, 418, alpha=a)

    # memorial card rises to the centre at the end
    p = (t - T_MEM) / 1.0
    if p > 0:
        s = (0.85 + 0.15 * ease_out(p)) * (1 + 0.012 * (t - T_MEM))
        paste_center(fr, MEM_IM, W / 2, 1150 + 80 * (1 - ease_out(p)), s, 0, ease_out(p))

    # fade in from the intro, fade out at the end
    k = max(1 - ease_out(tc / 0.5), ease_out((t - T_FADE) / (D - T_FADE)))
    if k > 0:
        fr = Image.blend(fr, Image.new("RGBA", (W, H), (0, 0, 0, 255)), k)
    return fr


def frame(t):
    return (intro_frame(t) if t < INTRO else collage_frame(t)).convert("RGB")


def main():
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", MUSIC,
         "-filter_complex",
         f"[1:a]atrim=0:{D},asetpts=PTS-STARTPTS,aresample=48000,"
         f"afade=t=in:st=0:d=0.3,afade=t=out:st={D - 2.0}:d=2.0,apad,atrim=0:{D}[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(D), OUT],
        stdin=subprocess.PIPE)
    for i in range(N):
        ff.stdin.write(frame(i / FPS).tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
