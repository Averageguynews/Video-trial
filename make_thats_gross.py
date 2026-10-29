"""Builds the "That's Gross" AGN social video (1080x1920, 9:16).

Left panel: plane/foot clip (muted). Right panel: Mark talking (audio kept).
Usage: python3 make_thats_gross.py <fonts_dir> <out.mp4>
"""
import math
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS, OUT = sys.argv[1], sys.argv[2]
TALK = "IMG_6836.mov"
FOOT = [f for f in __import__("os").listdir(".") if f.startswith("SnapInsta")][0]
LOGO = "IMG_6832.png"

W, H, FPS, D = 1080, 1920, 30, 10.6
N = int(D * FPS)
FOOT_SPEED = D / 10.19  # stretch the 10.2s plane clip to fill the video

ORANGE = (255, 165, 31)
YELLOW = (255, 224, 27)
GREEN = (140, 255, 60)
WHITE = (255, 255, 255)
PURPLE = (166, 75, 244)
RED = (228, 35, 48)
NAVY = (6, 18, 63)


def font(name, size):
    return ImageFont.truetype(f"{FONTS}/{name}", size)


ANTON = lambda s: font("anton-latin-400-normal.ttf", s)
MONT9 = lambda s: font("montserrat-latin-900-normal.ttf", s)
MONT7 = lambda s: font("montserrat-latin-700-normal.ttf", s)
EMOJI_FONT = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def emoji(ch, size):
    im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=EMOJI_FONT, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def text_img(parts, fnt, stroke=0, shadow=0, spacing=0.0, pad=30):
    """parts: list of (text, color). Renders one line as RGBA with stroke + drop shadow."""
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
    im = Image.new("RGBA", (tw + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for layer in ("shadow", "main"):
        x = pad
        for (t, col), w in zip(parts, widths):
            ox, oy = (shadow, shadow) if layer == "shadow" else (0, 0)
            if layer == "shadow" and not shadow:
                break
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
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return m


# ---------------------------------------------------------------- background
def make_bg():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.42) / H) ** 2)
    t = np.clip(r / 0.75, 0, 1)[..., None]
    inner, outer = np.array([22, 62, 200]), np.array([5, 14, 52])
    img = inner * (1 - t) + outer * t
    img *= np.clip(1.15 - (y / H)[..., None] * 0.55, 0.45, 1.0)  # darker toward bottom
    # soft diagonal streaks in the top half
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


# ---------------------------------------------------------------- AGN logo (letters only, no circle)
def make_logo():
    src = np.array(Image.open(LOGO).convert("RGB")).astype(np.int16)
    r, g, b = src[..., 0], src[..., 1], src[..., 2]
    red = (r > 170) & (g < 90) & (b < 100)
    ys, xs = np.where(red)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    alpha = np.zeros(red.shape, np.uint8)
    for yy in range(y0, y1 + 1):  # fill the slanted red block row by row (keeps the white letters)
        row = np.where(red[yy, x0:x1 + 1])[0]
        if len(row):
            alpha[yy, x0 + row.min():x0 + row.max() + 1] = 255
    rgba = np.dstack([src.astype(np.uint8), alpha])[y0:y1 + 1, x0:x1 + 1]
    im = Image.fromarray(rgba, "RGBA")
    return im.resize((420, int(420 * im.height / im.width)), Image.LANCZOS)


LOGO_IM = make_logo()


def draw_logo(base, t):
    cx, cy = W // 2, 1600
    s = 1.0 + 0.03 * math.sin(t * 2.4)
    im = LOGO_IM.resize((int(LOGO_IM.width * s), int(LOGO_IM.height * s)), Image.BILINEAR)
    # drop shadow
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.45)))
    base.alpha_composite(sh, (cx - im.width // 2 + 8, cy - im.height // 2 + 10))
    # shine sweep every 3.5s
    ph = (t % 3.5) / 0.7
    if ph < 1.0:
        arr = np.array(im).astype(np.float32)
        yy, xx = np.mgrid[0:im.height, 0:im.width]
        pos = -0.3 + ph * 1.6
        band = np.clip(1 - np.abs((xx + yy * 0.6) / (im.width * 1.3) - pos) / 0.08, 0, 1) * 0.6
        arr[..., :3] = arr[..., :3] * (1 - band[..., None]) + 255 * band[..., None]
        im = Image.fromarray(arr.astype(np.uint8), "RGBA")
    base.alpha_composite(im, (cx - im.width // 2, cy - im.height // 2))


# ---------------------------------------------------------------- video readers
class Reader:
    def __init__(self, path, vf, w, h, ss=0.0):
        self.w, self.h = w, h
        self.p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", str(ss), "-i", path, "-an", "-vf", vf + ",format=rgb24",
             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        buf = self.p.stdout.read(self.w * self.h * 3)
        if len(buf) == self.w * self.h * 3:
            self.last = Image.fromarray(np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3))
        return self.last


def hide_caption(img):
    """Blur out the plane clip's own small caption (our context bar replaces it)."""
    box = (int(0.12 * img.width), int(0.12 * img.height), int(0.88 * img.width), int(0.235 * img.height))
    img = img.copy()
    img.paste(img.crop(box).filter(ImageFilter.GaussianBlur(40)), box[:2])
    return img


def view(img, cx, cy, vw, vh, out_w, out_h):
    """Crop a normalised window (centre cx,cy; size vw,vh) and resize to out size."""
    x0, y0 = (cx - vw / 2) * img.width, (cy - vh / 2) * img.height
    box = (x0, y0, x0 + vw * img.width, y0 + vh * img.height)
    return img.resize((out_w, out_h), Image.BICUBIC, box=box)


# panel geometry (matches the previous episode's layout)
LP = dict(x=20, y=600, w=500, h=830, border=10, color=PURPLE)
RP = dict(x=516, y=588, w=544, h=852, border=8, color=WHITE)


def clamp_view(cx, cy, vw, vh):
    cx = min(max(cx, vw / 2), 1 - vw / 2)
    cy = min(max(cy, vh / 2), 1 - vh / 2)
    return cx, cy


def bump(t, a, b, ramp=0.1):
    """0..1 envelope that is 1 between a and b with eased ramps."""
    if t < a or t > b + ramp:
        return 0.0
    if t < a + ramp:
        return ease_out((t - a) / ramp)
    if t > b:
        return 1 - ease_out((t - b) / ramp)
    return 1.0


# foot position keyframes, in source-clip seconds -> normalised (x, y) in the source frame
FOOT_KEYS = [(1.45, 0.15, 0.66), (2.2, 0.16, 0.70), (3.0, 0.16, 0.71),
             (5.55, 0.12, 0.70), (6.0, 0.12, 0.70), (6.8, 0.15, 0.71), (7.05, 0.16, 0.71)]
FOOT_SHOWS = [(1.5, 3.0, "THE FOOT"), (5.6, 7.0, "IT'S BACK")]  # source seconds


def foot_pos(st):
    ks = FOOT_KEYS
    for (t0, x0, y0), (t1, x1, y1) in zip(ks, ks[1:]):
        if t0 <= st <= t1:
            k = (st - t0) / (t1 - t0)
            return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
    return (ks[-1][1], ks[-1][2]) if st > ks[-1][0] else (ks[0][1], ks[0][2])


# ---------------------------------------------------------------- captions (word timings from speech recognition)
HL, GR = YELLOW, GREEN
CAPS = [
    (0.00, 0.88, [("I", WHITE), ("THINK", WHITE)]),
    (0.88, 1.44, [("THE", WHITE), ("ONLY", WHITE)]),
    (1.44, 2.00, [("APPROPRIATE", HL)]),
    (2.00, 2.56, [("RESPONSE", WHITE)]),
    (2.56, 3.28, [("RIGHT", WHITE), ("THERE", WHITE)]),
    (3.28, 3.92, [("YOU", WHITE), ("GOT", WHITE), ("TO", WHITE)]),
    (3.92, 4.52, [("PRETEND", HL), ("TO", WHITE)]),
    (4.52, 5.05, [("COUGH", HL)]),
    (5.05, 5.52, [("*COUGH*", GR)]),
    (5.52, 6.08, [("AND", WHITE), ("AT", WHITE)]),
    (6.08, 6.92, [("THE", WHITE), ("SAME", WHITE), ("TIME", WHITE)]),
    (6.92, 7.16, [("LIKE", WHITE)]),
    (7.16, 7.92, [("POUR", WHITE), ("WATER", HL)]),
    (7.92, 8.32, [("OR", WHITE), ("JUST", WHITE)]),
    (8.32, 8.64, [("SPIT", HL)]),
    (8.64, 9.28, [("ON", WHITE), ("THE", WHITE), ("FOOT", HL)]),
    (9.28, D, [("DISGUSTING!", GR)]),
]
CAP_IMS = [text_img(p, MONT9(118 if p[0][0] == "DISGUSTING!" else 84), stroke=9, shadow=7) for _, _, p in CAPS]

STICKERS = [  # (start, end, emoji, x, y, size)
    (4.52, 5.6, "\U0001F637", 960, 760, 150),   # mask face for the cough
    (7.16, 7.95, "\U0001F4A6", 960, 1150, 140),  # sweat drops for "pour water"
    (8.64, 9.3, "\U0001F9B6", 960, 1150, 140),   # foot
]
STICKER_IMS = {s[2]: emoji(s[2], s[5]) for s in STICKERS}
SICK = emoji("\U0001F922", 150)

# ---------------------------------------------------------------- static text
LIVE_TXT = text_img([("LIVE", WHITE)], ANTON(36))
EP_TXT = text_img([("THIS WEEK'S EPISODE", (210, 220, 245))], MONT7(28), spacing=5)
FOLLOW_TXT = text_img([("FOLLOW FOR MORE", YELLOW)], MONT9(28), spacing=5)
LINE1 = text_img([("THAT'S", WHITE)], ANTON(176), stroke=4, shadow=10)
LINE2 = text_img([("GROSS!", ORANGE)], ANTON(196), stroke=4, shadow=10)
TAG_RED = text_img([("MID-FLIGHT", WHITE)], ANTON(40))
CTX1 = text_img([("SOMEONE'S FOOT", YELLOW)], MONT9(36))
CTX2 = text_img([("ON A PLANE", WHITE)], MONT9(36))
PLANE = emoji("✈️", 44)
NAME = text_img([("MARK", WHITE)], ANTON(44))
ROLE = text_img([("CHIEF AGN CORRESPONDENT", YELLOW)], MONT9(19), spacing=1)
FOOT_LBL = {lbl: text_img([(lbl, WHITE)], ANTON(40)) for _, _, lbl in FOOT_SHOWS}


def tag(im, bg, padx=16, pady=8, tri=False):
    extra = 34 if tri else 0
    box = Image.new("RGBA", (im.width + padx * 2 + extra, im.height + pady * 2), bg)
    if tri:
        ImageDraw.Draw(box).polygon([(padx, pady + 4), (padx, box.height - pady - 4), (padx + 24, box.height / 2)], fill=WHITE)
    box.alpha_composite(im, (padx + extra, pady))
    return box


TAG_RED_BOX = tag(TAG_RED, RED + (255,), tri=True)
CTX_BOX = Image.new("RGBA", (420, 108), (0, 0, 0, 225))
CTX_BOX.alpha_composite(CTX1, (18, 12))
CTX_BOX.alpha_composite(CTX2, (18, 60))
CTX_BOX.alpha_composite(PLANE, (18 + CTX2.width + 14, 58))
NAME_BOX = tag(NAME, (24, 80, 220, 255), padx=14, pady=6)
ROLE_BOX = tag(ROLE, (0, 0, 0, 235), padx=10, pady=6)
FOOT_TAGS = {k: tag(v, RED + (255,), padx=12, pady=4) for k, v in FOOT_LBL.items()}


# ---------------------------------------------------------------- frame builder
def build_panel(content, p):
    b = p["border"]
    frame = Image.new("RGBA", (p["w"], p["h"]), (0, 0, 0, 0))
    frame.paste(Image.new("RGBA", frame.size, p["color"] + (255,)), (0, 0), rounded_mask(p["w"], p["h"], 26))
    inner = content.convert("RGBA")
    frame.paste(inner, (b, b), rounded_mask(inner.width, inner.height, 18))
    return frame


def main():
    lw, lh = LP["w"] - 2 * LP["border"], LP["h"] - 2 * LP["border"]
    rw, rh = RP["w"] - 2 * RP["border"], RP["h"] - 2 * RP["border"]
    foot = Reader(FOOT, f"setpts=PTS*{FOOT_SPEED:.5f},fps={FPS},scale=720:1280", 720, 1280)
    talk = Reader(TALK, f"fps={FPS},scale=720:1280", 720, 1280)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-t", str(D), "-i", TALK, "-map", "0:v", "-map", "1:a",
         "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.05,afade=t=out:st={D - 0.35}:d=0.35",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", OUT],
        stdin=subprocess.PIPE)
    rng = random.Random(7)

    for i in range(N):
        t = i / FPS
        st = t / FOOT_SPEED  # time in the original plane clip
        fr = BG.copy()
        draw_arc_glints(fr, t)

        # --- top bar: LIVE + episode label (switches to a follow prompt near the end)
        blink = 1.0 if int(t * 2) % 2 == 0 else 0.55
        live = tag(LIVE_TXT, RED + (255,), padx=34, pady=8)
        ImageDraw.Draw(live).ellipse((10, live.height / 2 - 8, 26, live.height / 2 + 8), fill=(255, 255, 255, int(255 * blink)))
        fr.alpha_composite(live, (50, 168))
        lbl = FOLLOW_TXT if t > 8.3 else EP_TXT
        fr.alpha_composite(lbl, (50 + live.width + 34, 168 + (live.height - lbl.height) // 2))
        if t > 8.3:
            x = 50 + live.width + 34 + lbl.width + 16
            yc = 168 + live.height // 2
            nudge = 6 * math.sin(t * 10)
            ImageDraw.Draw(fr).polygon([(x + nudge, yc - 12), (x + nudge, yc + 12), (x + 18 + nudge, yc)], fill=YELLOW)

        # --- shake on the cough and on "disgusting"
        shake = bump(t, 9.28, 9.7, 0.05) + 0.6 * bump(t, 5.05, 5.35, 0.05)
        sx, sy = (rng.uniform(-9, 9) * shake, rng.uniform(-9, 9) * shake) if shake else (0, 0)

        # --- left panel: plane clip (muted) with zoom on the foot
        fimg = hide_caption(foot.next())
        zl = 1.0 + 0.04 * t / D
        fcx, fcy = 0.5, 0.5
        show = next(((a, b, l) for a, b, l in FOOT_SHOWS if a - 0.1 <= st <= b + 0.15), None)
        fx, fy = foot_pos(st)
        if show:
            k = bump(st, show[0], show[1], 0.25)
            zl += 0.22 * k
            fcx, fcy = 0.5 + (fx - 0.5) * k, 0.5 + (fy - 0.5) * k * 0.6
        vh = (lh / lw) * (720 / 1280) / zl
        vw = 1 / zl
        if vh > 1:
            vh, vw = 1, (lw / lh) * (1280 / 720)
        fcx, fcy = clamp_view(fcx, fcy, vw, vh)
        lc = view(fimg, fcx, fcy, vw, vh, lw, lh).convert("RGBA")
        d = ImageDraw.Draw(lc)
        if show:
            k = bump(st, show[0], show[1], 0.15)
            px = (fx - (fcx - vw / 2)) / vw * lw
            py = (fy - (fcy - vh / 2)) / vh * lh
            rad = 105 * ease_back(min(1, (st - show[0] + 0.1) / 0.3)) if k else 0
            if k > 0 and rad > 5:
                d.ellipse((px - rad, py - rad, px + rad, py + rad), outline=RED + (int(255 * k),), width=9)
                ft = FOOT_TAGS[show[2]]
                tx = int(min(max(px - ft.width / 2, 10), lw - ft.width - 10))
                ty = int(py - rad - ft.height - 26)
                lc.alpha_composite(ft, (tx, ty))
                ImageDraw.Draw(lc).polygon([(px - 14, ty + ft.height), (px + 14, ty + ft.height), (px, ty + ft.height + 18)], fill=RED)
        # context bar covers the clip's original small caption
        cs = ease_out((t - 0.25) / 0.3)
        if cs > 0:
            lc.alpha_composite(TAG_RED_BOX, (int(-TAG_RED_BOX.width + (TAG_RED_BOX.width + 16) * cs), 20))
        lc.alpha_composite(CTX_BOX, ((lw - CTX_BOX.width) // 2, 78))
        left = build_panel(lc, LP)

        # --- right panel: Mark, with punch-in zooms on key words
        timg = talk.next()
        zr = 1.0 + 0.05 * t / D + 0.16 * bump(t, 4.52, 5.5, 0.08) + 0.24 * bump(t, 9.28, D, 0.1) + 0.08 * bump(t, 8.32, 8.64, 0.06)
        vw = 1 / zr
        vh = (rh / rw) * (720 / 1280) / zr
        tcx, tcy = clamp_view(0.5, 0.44 - 0.08 * (zr - 1), vw, vh)
        rc = view(timg, tcx, tcy, vw, vh, rw, rh).convert("RGBA")
        nm = ease_out((t - 0.35) / 0.3) * (1 - ease_out((t - 3.2) / 0.3))
        if nm > 0:
            off = int((1 - nm) * -300)
            rc.alpha_composite(NAME_BOX, (18 + off, 18))
            rc.alpha_composite(ROLE_BOX, (18 + off, 18 + NAME_BOX.height))
        right = build_panel(rc, RP)

        # panels slide in during the first 0.3s
        si = ease_out(t / 0.3)
        fr.alpha_composite(left, (int(LP["x"] - (1 - si) * 560 + sx), int(LP["y"] + sy)))
        fr.alpha_composite(right, (int(RP["x"] + (1 - si) * 600 + sx), int(RP["y"] + sy)))

        # --- headline "THAT'S / GROSS!" slams in, pulses on "disgusting"
        s1 = 1 + 0.9 * (1 - ease_out(t / 0.28))
        a1 = min(1, t / 0.12)
        paste_center(fr, LINE1, W / 2, 352, s1, a1)
        t2 = t - 0.18
        if t2 > 0:
            pulse = 0.1 * bump(t, 9.28, 9.6, 0.08) + 0.03 * math.sin(t * 6) * (t > 0.6)
            s2 = 1 + 1.0 * (1 - ease_out(t2 / 0.28)) + pulse
            ang = 3 * math.sin(t * 40) * bump(t, 9.28, 9.7, 0.05)
            paste_center(fr, LINE2, W / 2 + sx, 500 + sy, s2, min(1, t2 / 0.12), ang)
        ul = ease_out((t - 0.4) / 0.35)
        if ul > 0:
            ImageDraw.Draw(fr).rectangle((W / 2 - 400 * ul, 580, W / 2 + 400 * ul, 585), fill=ORANGE)
        if t >= 9.28:
            k = ease_back((t - 9.28) / 0.3)
            paste_center(fr, SICK, 930 + sx, 470 + sy, k, 1, 12 * math.sin(t * 9))

        # --- emoji stickers
        for a, b, ch, x, y, sz in STICKERS:
            if a <= t <= b:
                k = ease_back((t - a) / 0.25) * (1 - ease_out((t - b + 0.12) / 0.12))
                paste_center(fr, STICKER_IMS[ch], x + sx, y + sy, k, 1, 10 * math.sin(t * 8))

        # --- captions
        for (a, b, _), im in zip(CAPS, CAP_IMS):
            if a <= t < b:
                pop = 1 + 0.35 * (1 - ease_back((t - a) / 0.14))
                paste_center(fr, im, W / 2 + sx, 1335 + sy, max(pop, 0.6))
                break

        draw_logo(fr, t)

        # quick white flash at the very start
        if t < 0.12:
            fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * (1 - t / 0.12)))))

        enc.stdin.write(fr.convert("RGB").tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{N}", flush=True)

    enc.stdin.close()
    enc.wait()
    print("done", OUT)


if __name__ == "__main__":
    main()
