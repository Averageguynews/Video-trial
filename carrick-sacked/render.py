#!/usr/bin/env python3
"""FAFO News breaking-news video: "Michael Carrick sacked".

Recreates the FAFO News layout (blue studio background, LIVE tag, two-line
title, photo panel + presenter panel, word-by-word captions, BREAKING ticker)
from three raw selfie takes and one still graphic.

Usage:
  python3 render.py --takes A.mov B.mov C.mov --photos clap.jpg nose.jpg sacked.jpg \
      --fonts FONT_DIR --out out.mp4 [--music song.mp4 --music-start 3.4]

--photos: clap (looking up, clapping), nose (hand over face), sacked ("SACKED" poster).
--music: intro track (audio is taken from any audio/video file). It plays loud
over the intro and continues as a quiet background bed under the talking.
Without it a short generated news sting is used.
"""
import argparse, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SR = 48000

ap = argparse.ArgumentParser()
ap.add_argument("--takes", nargs=3, required=True)
ap.add_argument("--photos", nargs=3, required=True)
ap.add_argument("--fonts", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--music")
ap.add_argument("--music-start", type=float, default=3.4)
ap.add_argument("--bed", type=float, default=0.2, help="background music level under talking")
ap.add_argument("--work", default="/tmp/fafo_work")
args = ap.parse_args()
os.makedirs(args.work, exist_ok=True)

F = args.fonts
def anton(s): return ImageFont.truetype(f"{F}/fontsource-anton/files/anton-latin-400-normal.woff", s)
def mont(s, w=900): return ImageFont.truetype(f"{F}/fontsource-montserrat/files/montserrat-latin-{w}-normal.woff", s)

# ---------------------------------------------------------------- timeline
INTRO = 6.4
# intro picture cuts (start, photo key) - timed to the chant: na-na / hey hey hey / goodbye
INTRO_CUTS = [(0.0, "nose"), (1.9, "clap"), (3.7, "sacked")]
# (file index, trim start, trim end)
CLIPS = [(0, 0.0, 7.6), (1, 0.45, 8.0), (2, 0.0, 9.5)]
clip_starts, t = [], INTRO
for _, a, b in CLIPS:
    clip_starts.append(t); t += b - a
TOTAL = t + 0.4
NFR = int(TOTAL * FPS)

# Captions: (clip, start, end, word, colour). Times are within the raw take.
Y, WH, RD = (255, 228, 0), (255, 255, 255), (255, 60, 60)
CAPS = {
 0: [(0.0,0.94,"IT'S",Y),(0.94,1.12,"OFFICIAL",Y),(1.12,1.82,"MICHAEL",WH),(1.82,2.28,"CARRICK",WH),
     (2.28,2.5,"HE'S",Y),(2.5,2.8,"GONE",RD),(2.8,3.36,"AS",Y),(3.36,3.54,"THE",Y),(3.54,3.9,"MANAGER",Y),
     (3.9,4.14,"OF",WH),(4.14,4.32,"MANCHESTER",WH),(4.32,4.94,"UNITED",WH),(4.94,5.48,"AFTER",Y),
     (5.48,6.02,"BASICALLY",Y),(6.02,6.62,"SUCKING",RD),(6.62,7.02,"ALL",Y),(7.02,7.6,"YEAR!",Y)],
 1: [(0.61,0.86,"IF",Y),(0.86,1.06,"MANCHESTER",WH),(1.06,1.62,"UNITED",WH),(1.62,2.5,"ACTUALLY",Y),
     (2.5,2.96,"GET",Y),(2.96,3.18,"DROPPED",RD),(3.18,3.44,"FROM",Y),(3.44,3.5,"THE",Y),(3.5,3.66,"PREMIER",WH),
     (3.66,4.3,"LEAGUE",WH),(4.4,4.42,"I",Y),(4.42,4.68,"BELIEVE",Y),(4.68,5.0,"THAT'S",Y),(5.0,5.1,"THE",Y),
     (5.1,5.34,"FIRST",Y),(5.34,5.64,"SIGN",Y),(5.64,5.84,"THAT",Y),(5.84,5.9,"THE",WH),(5.9,6.14,"FOUR",WH),
     (6.14,6.54,"HORSEMEN",WH),(6.54,6.66,"OF",WH),(6.66,6.76,"THE",WH),(6.76,8.0,"APOCALYPSE...",RD)],
 2: [(0.0,0.48,"SO",Y),(0.48,0.66,"BY",Y),(0.66,0.78,"AT",Y),(0.78,0.92,"LEAST",Y),(0.92,1.26,"FIRING",RD),
     (1.26,1.62,"THIS",Y),(1.62,2.2,"MANAGER",Y),(2.38,2.94,"THERE'S",Y),(2.94,3.06,"ONLY",Y),(3.06,3.32,"ONE",WH),
     (3.32,3.58,"WAY",WH),(3.58,3.68,"TO",WH),(3.68,4.3,"GO",WH),(4.46,5.16,"STRAIGHT",Y),(5.16,5.48,"UP",Y),
     (5.48,5.64,"TO",Y),(5.64,5.72,"THE",Y),(5.72,5.88,"TOP",WH),(5.88,6.0,"OF",WH),(6.0,6.06,"THE",WH),
     (6.06,6.9,"LADDER!",WH),(7.12,7.6,"OR",Y),(7.6,7.82,"LIKE",Y),(7.82,8.4,"TENTH.",RD),(8.52,8.7,"LET'S",Y),
     (8.7,8.84,"HOPE",Y),(8.84,9.0,"FOR",Y),(9.0,9.5,"TENTH.",RD)],
}
TICKER = ["CARRICK OUT AT OLD TRAFFORD", "MAN UTD HUNT FOR ANOTHER NEW BOSS",
          "FOUR HORSEMEN SPOTTED IN MANCHESTER", "TARGET: TENTH PLACE"]
# Photo panel moves (crop boxes in the source photo, x0,y0,x1,y1) + label
PHOTO_SHOTS = [  # (start time in video, photo, crop box start, crop box end, tag)
 (INTRO,          "clap",   (90, 0, 560, 791),   (190, 40, 500, 560),  "IT'S OFFICIAL"),
 (INTRO+4.0,      "sacked", (120, 60, 620, 840), (220, 120, 520, 650), "SACKED"),
 (clip_starts[1], "nose",   (300, 0, 760, 736),  (380, 60, 680, 560),  "RELEGATION WATCH"),
 (clip_starts[2], "sacked", (250, 180, 500, 600), (130, 30, 580, 790),  "NEXT STOP: 10TH?"),
]

# ---------------------------------------------------------------- layout
LP = (18, 598, 525, 1432)        # left panel outer
LV = (38, 618, 510, 1412)        # left photo area
RP = (525, 585, 1057, 1447)      # right panel border
RV = (532, 592, 1050, 1440)      # presenter video area
RVW, RVH = RV[2]-RV[0], RV[3]-RV[1]
LVW, LVH = LV[2]-LV[0], LV[3]-LV[1]

def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w-1, h-1), r, fill=255); return m

def stroked(draw, xy, text, font, fill, stroke=6, sc=(10, 10, 30), anchor="mm"):
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=sc, anchor=anchor)

def make_background():
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    top = np.array([10, 30, 110]); mid = np.array([22, 58, 190]); bot = np.array([4, 12, 50])
    k = np.clip(1 - np.abs(y - 0.42) * 2.2, 0, 1)[..., None]
    base = (mid * k + np.where(y[..., None] < 0.42, top, bot) * (1 - k))
    base = base + (x[..., None] * 18)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    for i, r in enumerate(range(500, 1700, 170)):   # studio arcs
        g.ellipse((W*0.55-r, 1000-r*0.55, W*0.55+r, 1000+r*0.55), outline=(90, 150, 255, 70 - i*6), width=4)
    for i in range(7):                               # diagonal light streaks
        x0 = 380 + i * 110
        g.polygon([(x0, 0), (x0+40, 0), (x0-560, H*0.55), (x0-600, H*0.55)], fill=(120, 170, 255, 14))
    glow = glow.filter(ImageFilter.GaussianBlur(3))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    return img

def make_ticker_strip():
    f = mont(36, 900)
    parts = []
    for s in TICKER: parts += [s, "*"]
    widths = [f.getlength(p) if p != "*" else 60 for p in parts]
    gap = 50
    one = int(sum(widths) + gap * len(parts))
    strip = Image.new("RGBA", (one * 3, 88), (0, 0, 0, 0)); d = ImageDraw.Draw(strip)
    x = 0
    for rep in range(3):
        for p, w in zip(parts, widths):
            if p == "*":
                cx, cy, R = x + 30, 44, 20
                pts = [(cx + (R if j % 2 == 0 else R*0.42) * math.sin(j*math.pi/5), cy - (R if j % 2 == 0 else R*0.42) * math.cos(j*math.pi/5)) for j in range(10)]
                d.polygon(pts, fill=(20, 40, 120))
            else:
                d.text((x, 44), p, font=f, fill=(20, 40, 120), anchor="lm")
            x += w + gap
    return strip, one

def make_static_overlay():
    """Everything that never moves (except title/header which animate)."""
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(o)
    d.rounded_rectangle(LP, 34, fill=(190, 70, 230)); d.rounded_rectangle((LP[0]+10, LP[1]+10, LP[2]-10, LP[3]-10), 26, fill=(60, 30, 110))
    d.rounded_rectangle(RP, 30, fill=(245, 245, 250))
    # ticker bar
    d.rectangle((0, 1470, W, 1478), fill=(250, 180, 30))
    d.rectangle((0, 1478, W, 1560), fill=(248, 248, 252))
    # FAFO NEWS logo
    d.rounded_rectangle((40, 1590, 330, 1660), 10, fill=(30, 70, 220))
    for i in range(3):
        for j in range(3):
            d.ellipse((58+i*13, 1606+j*13, 68+i*13, 1616+j*13), fill="white")
    d.text((110, 1625), "FAFO", font=anton(54), fill="white", anchor="lm")
    d.text((222, 1625), "NEWS", font=mont(28, 900), fill=(255, 200, 40), anchor="lm")
    return o

def breaking_block():
    b = Image.new("RGBA", (290, 100), (0, 0, 0, 0)); d = ImageDraw.Draw(b)
    d.polygon([(0, 0), (275, 0), (250, 92), (0, 92)], fill=(225, 30, 40))
    d.rectangle((0, 88, 220, 98), fill=(250, 200, 30))
    d.text((130, 46), "BREAKING", font=anton(62), fill="white", anchor="mm")
    return b

def name_tag():
    t = Image.new("RGBA", (260, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    d.rectangle((0, 0, 84, 62), fill=(30, 60, 220)); d.text((42, 32), "MARK", font=anton(30), fill="white", anchor="mm")
    d.rectangle((0, 66, 248, 114), fill=(10, 10, 15)); d.text((124, 90), "CHIEF FAFO CORRESPONDENT", font=anton(19), fill=(255, 210, 40), anchor="mm")
    return t

def title_layers():
    l1 = Image.new("RGBA", (W, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(l1)
    f = anton(118)
    d.text((W//2 + 6, 92), "MICHAEL CARRICK", font=f, fill=(10, 10, 40), anchor="mm")
    stroked(d, (W//2, 86), "MICHAEL CARRICK", f, (250, 240, 225), stroke=5)
    l2 = Image.new("RGBA", (W, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(l2)
    d.text((W//2 + 6, 92), "IS SACKED!", font=f, fill=(10, 10, 40), anchor="mm")
    stroked(d, (W//2, 86), "IS SACKED!", f, (255, 150, 20), stroke=5)
    return l1, l2

def tag_img(text, red=True):
    f = anton(30); w = int(f.getlength(text)) + (64 if red else 30)
    t = Image.new("RGBA", (w, 52), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    d.rounded_rectangle((0, 0, w-1, 51), 6, fill=(225, 30, 40) if red else (20, 40, 140))
    if red: d.polygon([(16, 14), (16, 38), (36, 26)], fill="white")
    d.text((w - 14, 26), text, font=f, fill="white", anchor="rm")
    return t

def caption_img(word, col):
    f = mont(68, 900)
    img = Image.new("RGBA", (int(f.getlength(word)) + 60, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    stroked(d, (img.width//2 + 4, 64), word, f, (0, 0, 0), stroke=9, sc=(0, 0, 0))
    stroked(d, (img.width//2, 60), word, f, col, stroke=8, sc=(10, 10, 20))
    return img

# ---------------------------------------------------------------- media
PHOTOS = {k: Image.open(p).convert("RGB") for k, p in zip(("clap", "nose", "sacked"), args.photos)}

def decode_clip(path, a, b):
    vf = f"scale={RVW}:-2,crop={RVW}:{RVH}:0:'min(ih-{RVH},ih*0.06)'"
    cmd = ["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", path, "-vf", vf + f",fps={FPS}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (RVW * RVH * 3)
    return np.frombuffer(raw, np.uint8)[: n * RVW * RVH * 3].reshape(n, RVH, RVW, 3)

print("decoding takes…", file=sys.stderr)
CLIPFR = [decode_clip(args.takes[i], a, b) for i, a, b in CLIPS]

def ease(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)
def lerp_box(b0, b1, k): return tuple(b0[i] + (b1[i] - b0[i]) * k for i in range(4))

def crop_cover(img, box, w, h):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    tgt = w / h
    if bw / bh > tgt:   # too wide -> shrink width around centre
        nw = bh * tgt; cx = (x0 + x1) / 2; x0, x1 = cx - nw/2, cx + nw/2
    else:
        nh = bw / tgt; cy = (y0 + y1) / 2; y0, y1 = cy - nh/2, cy + nh/2
    return img.resize((w, h), Image.LANCZOS, box=(x0, y0, x1, y1))

# ---------------------------------------------------------------- build static assets
bg = make_background()
static = make_static_overlay()
base = Image.alpha_composite(bg, static)
lv_mask = rounded_mask(LVW, LVH, 22); rv_mask = rounded_mask(RVW, RVH, 24)
ticker, tick_period = make_ticker_strip()
brk = breaking_block(); ntag = name_tag()
T1, T2 = title_layers()
cap_cache = {}
def blur_bg(im):
    r = W / H; pw, ph = im.size
    box = (0, 0, pw, pw / r) if pw / ph < r else ((pw - ph * r) / 2, 0, (pw + ph * r) / 2, ph)
    return Image.blend(im.resize((W, H), Image.LANCZOS, box=box).filter(ImageFilter.GaussianBlur(40)),
                       Image.new("RGB", (W, H), (0, 0, 0)), 0.45).convert("RGBA")
INTRO_BG = {k: blur_bg(v) for k, v in PHOTOS.items()}
tags = {s[4]: tag_img(s[4]) for s in PHOTO_SHOTS}
live_f = anton(34); hdr_f = mont(27, 900)

def header(d, t):
    on = (int(t * 2) % 2 == 0)
    d.rectangle((50, 158, 164, 222), fill=(225, 30, 40))
    if on: d.ellipse((66, 170, 84, 188), fill="white")
    d.text((100, 191), "LIVE", font=live_f, fill="white", anchor="lm")
    txt = "FOLLOW FOR NEXT WEEK  >" if t > TOTAL - 4 else "BREAKING NEWS"
    col = (255, 210, 40) if t > TOTAL - 4 else (255, 255, 255)
    d.text((240, 194), " ".join(txt), font=hdr_f, fill=col, anchor="lm")

def intro_frame(t):
    ci = max(i for i, c in enumerate(INTRO_CUTS) if c[0] <= t)
    c0 = INTRO_CUTS[ci][0]; c1 = INTRO_CUTS[ci + 1][0] if ci + 1 < len(INTRO_CUTS) else INTRO
    key = INTRO_CUTS[ci][1]; im = PHOTOS[key]
    k = (t - c0) / (c1 - c0)
    z = 1.04 + 0.10 * ease(k)
    fr = INTRO_BG[key].copy()
    pw, ph = im.size
    fw = int(W * z); fh = int(ph * fw / pw)
    if fh > 1440: fh = int(1300 * z); fw = int(pw * fh / ph)
    fg = im.resize((fw, fh), Image.BILINEAR)
    fr.paste(fg, ((W - fw) // 2, 90 + (1400 - fh) // 2))
    d = ImageDraw.Draw(fr)
    # punchy "FAFO NEWS" bug + breaking slam
    s = ease((t - 0.25) / 0.35)
    if s > 0:
        bx = int(-300 + 300 * s)
        fr.alpha_composite(brk, (bx, 1500))
        d.rounded_rectangle((bx + 300, 1505, bx + 600, 1585), 8, fill=(30, 70, 220))
        d.text((bx + 320, 1545), "FAFO", font=anton(54), fill="white", anchor="lm")
        d.text((bx + 440, 1545), "NEWS", font=mont(28, 900), fill=(255, 200, 40), anchor="lm")
    # shake on the slam
    if 0.55 < t < 0.8 or INTRO_CUTS[-1][0] < t < INTRO_CUTS[-1][0] + 0.25:
        fr = fr.transform(fr.size, Image.AFFINE, (1, 0, 8 * math.sin(t * 90), 0, 1, 6 * math.cos(t * 70)))
    # white flash at start and into main section
    flash = max(0, 1 - (t - c0) / 0.2) + max(0, (t - (INTRO - 0.15)) / 0.15)
    if flash > 0:
        fr = Image.blend(fr, Image.new("RGBA", fr.size, (255, 255, 255, 255)), min(flash, 1) * 0.85)
    return fr

def main_frame(t):
    fr = base.copy()
    d = ImageDraw.Draw(fr)
    header(d, t)
    # title animation
    tt = t - INTRO
    k1 = ease(tt / 0.35); k2 = ease((tt - 0.3) / 0.3)
    if k1 > 0:
        l = T1 if k1 >= 1 else T1.resize((int(W * (1.6 - 0.6 * k1)), int(170 * (1.6 - 0.6 * k1))))
        fr.alpha_composite(l, ((W - l.width) // 2, 265 + (170 - l.height) // 2))
    if k2 > 0:
        fr.alpha_composite(T2, (int(-W * (1 - k2)), 420))
        d.rectangle((140, 577, 140 + int(800 * k2), 583), fill=(255, 150, 20))
    # photo panel
    shot = max([s for s in PHOTO_SHOTS if s[0] <= t], key=lambda s: s[0])
    nxt = [s[0] for s in PHOTO_SHOTS if s[0] > shot[0]]
    end = nxt[0] if nxt else TOTAL
    k = (t - shot[0]) / (end - shot[0])
    pimg = crop_cover(PHOTOS[shot[1]], lerp_box(shot[2], shot[3], k), LVW, LVH)
    fr.paste(pimg, LV[:2], lv_mask)
    tg = tags[shot[4]]
    if t - shot[0] > 0.25:
        fr.alpha_composite(tg, (LV[0] + 16, LV[1] + 18))
    # presenter
    ci = max(i for i, s in enumerate(clip_starts) if s <= t + 1e-6)
    frames = CLIPFR[ci]
    fi = min(int((t - clip_starts[ci]) * FPS), len(frames) - 1)
    fr.paste(Image.fromarray(frames[fi]), RV[:2], rv_mask)
    fr.alpha_composite(ntag, (RV[0] + 10, RV[1] + 14))
    # caption
    lt = t - clip_starts[ci] + CLIPS[ci][1]
    cur = [c for c in CAPS[ci] if c[0] <= lt < c[1] + 0.12]
    if cur:
        c = cur[-1]
        key = (c[2], c[3])
        if key not in cap_cache: cap_cache[key] = caption_img(*key)
        ci_img = cap_cache[key]
        pop = 1 + 0.18 * max(0, 1 - (lt - c[0]) / 0.1)
        if pop > 1.01:
            ci_img = ci_img.resize((int(ci_img.width * pop), int(ci_img.height * pop)))
        fr.alpha_composite(ci_img, (W // 2 - ci_img.width // 2, 1340 - ci_img.height // 2))
    # ticker
    off = int((t * 150) % tick_period)
    fr.alpha_composite(ticker.crop((off, 0, off + W - 250, 88)), (290, 1476))
    fr.alpha_composite(brk, (0, 1468))
    # flash between takes (like the original)
    for s in clip_starts[1:]:
        if 0 <= t - s < 0.18:
            fr = Image.blend(fr, Image.new("RGBA", fr.size, (255, 255, 255, 255)), 0.6 * (1 - (t - s) / 0.18))
    if t < INTRO + 0.15:
        fr = Image.blend(fr, Image.new("RGBA", fr.size, (255, 255, 255, 255)), 0.85 * (1 - (t - INTRO) / 0.15))
    return fr

# ---------------------------------------------------------------- audio
def load_audio(path, a, b):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", path, "-vn",
                          "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()

def sting(dur):
    """Original news sting: drum hits + rising synth stabs (placeholder music)."""
    n = int(dur * SR); tt = np.arange(n) / SR; out = np.zeros(n)
    def hit(t0, f0, decay, amp):
        idx = (tt >= t0); x = tt[idx] - t0
        out[idx] += amp * np.sin(2 * np.pi * f0 * x * np.exp(-x * 6)) * np.exp(-x * decay)
    rng = np.random.default_rng(1)
    for i, t0 in enumerate([0.0, 0.55, 0.85, 1.4, 1.7, 2.0, 2.25, 2.5, 2.75]):
        hit(t0, 60, 7, 0.9)
        idx = (tt >= t0) & (tt < t0 + 0.15)
        out[idx] += 0.25 * rng.standard_normal(idx.sum()) * np.exp(-(tt[idx] - t0) * 30)
    chords = [(0.0, [220, 277, 330]), (0.55, [247, 311, 370]), (1.4, [262, 330, 392]), (2.0, [294, 370, 440])]
    for t0, fs in chords:
        idx = tt >= t0; x = tt[idx] - t0
        env = np.minimum(x / 0.02, 1) * np.exp(-x * 2.2)
        for f0 in fs:
            out[idx] += 0.12 * np.sign(np.sin(2 * np.pi * f0 * x)) * env
    out = np.tanh(out * 1.2) * 0.6
    return np.stack([out, out], 1).astype(np.float32)

def whoosh(dur=0.35):
    n = int(dur * SR); x = np.arange(n) / SR
    noise = np.random.default_rng(2).standard_normal(n)
    noise = np.convolve(noise, np.ones(20) / 20, "same")
    env = np.sin(np.pi * x / dur) ** 2
    s = noise * env * 0.35
    return np.stack([s, s], 1).astype(np.float32)

print("mixing audio…", file=sys.stderr)
mix = np.zeros((int(TOTAL * SR) + SR, 2), np.float32)
def put(sig, t0, gain=1.0):
    i = int(t0 * SR); mix[i:i + len(sig)] += sig[: len(mix) - i] * gain
for (i, a, b), s in zip(CLIPS, clip_starts):
    v = load_audio(args.takes[i], a, b)
    fade = int(0.02 * SR); v[:fade] *= np.linspace(0, 1, fade)[:, None]; v[-fade:] *= np.linspace(1, 0, fade)[:, None]
    put(v, s, 1.0)
if args.music:
    m = load_audio(args.music, args.music_start, args.music_start + TOTAL)
    env = np.full(len(m), args.bed, np.float32)
    env[: int((INTRO - 0.3) * SR)] = 0.9
    fi = int(0.12 * SR); env[:fi] *= np.linspace(0, 1, fi)
    ramp = int(0.5 * SR); j = int((INTRO - 0.3) * SR)
    env[j:j + ramp] = np.linspace(0.9, args.bed, ramp)
    tail = int(1.0 * SR); env[-tail:] *= np.linspace(1, 0, tail)
    put(m * env[:, None], 0.0)
else:
    put(sting(INTRO + 0.3), 0.0, 0.9)
for s in clip_starts[1:] + [INTRO]:
    put(whoosh(), s - 0.2, 0.7)
mix = mix[: int(TOTAL * SR)]
peak = np.abs(mix).max(); mix = mix / max(peak, 1e-6) * 0.95 if peak > 0.95 else mix
wav = os.path.join(args.work, "mix.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())

# ---------------------------------------------------------------- render
print(f"rendering {NFR} frames…", file=sys.stderr)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                        "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        args.out], stdin=subprocess.PIPE)
for n in range(NFR):
    t = n / FPS
    fr = intro_frame(t) if t < INTRO else main_frame(t)
    enc.stdin.write(fr.convert("RGB").tobytes())
    if n % 150 == 0: print(f"  {n}/{NFR}", file=sys.stderr)
enc.stdin.close(); enc.wait()
print("done:", args.out, file=sys.stderr)
