"""Build the 3-second AGN news intro (1080x1920, 30fps).

Usage: python3 make_agn_intro.py <images_dir> <quote_clip> <out.mp4>

The AGN circle logo sits in the centre while sports photos pop in on the
syllables of the "sometimes maybe good, sometimes maybe shit" voice clip,
over a soft synthesized backing pad.
"""
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

IMG_DIR, QUOTE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IMG_6832.png")

W, H, FPS, D = 1080, 1920, 30, 3.0
N = int(D * FPS)
SR = 48000
PUNCH = 2.44  # "...shit"

# (file, focus x, focus y, crop zoom, centre x, centre y, rotation, pop time)
# Pop times land on the syllable onsets of the voice clip.
CARDS = [
    ("a3e901d9-image.jpg", 0.55, 0.38, 1.00, 255, 430, -8, 0.26),  # Bellingham
    ("18d5ec0b-image.jpg", 0.45, 0.42, 1.00, 825, 1490, -6, 0.54),  # Packers kicker
    ("2c72c70f-image.jpg", 0.50, 0.33, 1.00, 825, 410, 7, 0.90),  # Starc at the SCG
    ("33bc3b3d-image.jpg", 0.45, 0.55, 1.00, 255, 1510, 6, 1.28),  # WACA beer shower
    ("fed14c18-image.jpg", 0.40, 0.42, 1.00, 545, 250, -3, 1.58),  # Brewers champagne
    ("9a433301-image.jpg", 0.45, 0.30, 1.25, 540, 1690, 4, 1.84),  # Cheesehead (crop hides IG heart)
]
CARD_W, CARD_H, BORDER = 370, 462, 10


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c = 2.2
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ---------------------------------------------------------------- background (matches the episode videos)
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


def draw_rings(base, t):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H / 2
    for i, rad in enumerate((470, 620, 790)):
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(120, 170, 255, 45 - i * 10), width=3)
    for i, (rad, spd) in enumerate(((470, 160), (620, -110), (790, 80))):
        a0 = (t * spd + i * 120) % 360
        d.arc((cx - rad, cy - rad, cx + rad, cy + rad), a0, a0 + 40, fill=(150, 200, 255, 140), width=10)
    base.alpha_composite(layer)


# ---------------------------------------------------------------- logo
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
    g = Image.new("RGBA", (size, size), (70, 140, 255, 0))
    g.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.9)))
    glow.alpha_composite(g, (pad, pad))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.55)))
    glow.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (pad + 6, pad + 14))
    glow.alpha_composite(logo, (pad, pad))
    return glow


LOGO_IM = make_logo()


# ---------------------------------------------------------------- photo cards
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
    card.paste(Image.new("RGBA", (cw2, ch2), (255, 255, 255, 255)), (0, 0), m)
    pm = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(pm).rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), 14, fill=255)
    card.paste(photo, (BORDER, BORDER), pm)
    # drop shadow baked in
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


def frame(t, rng):
    fr = BG.copy()
    draw_rings(fr, t)

    # little shake on the punchline
    sx = sy = 0
    if PUNCH <= t < PUNCH + 0.2:
        k = 1 - (t - PUNCH) / 0.2
        sx, sy = rng.integers(-14, 15) * k, rng.integers(-14, 15) * k

    # final push-in for the last 0.25s
    push = 1 + 0.18 * ease_out((t - 2.75) / 0.25) if t > 2.75 else 1.0

    for (f, fx, fy, z, cx, cy, rot, t0), im in zip(CARDS, CARD_IMS):
        if t < t0:
            continue
        p = (t - t0) / 0.28
        s = ease_back(p) * (1 + 0.04 * (t - t0))  # pop then slow zoom
        a = min(1.0, p * 2.5)
        wob = rot + (1 - ease_out(p)) * rot * 1.6
        if PUNCH <= t < PUNCH + 0.18:
            s *= 1 + 0.06 * (1 - (t - PUNCH) / 0.18)
        px = W / 2 + (cx - W / 2) * push + sx
        py = H / 2 + (cy - H / 2) * push + sy
        paste_center(fr, im, px, py, s * push, wob, a)

    # logo: pops in at the start, breathes, punches on "shit"
    ls = ease_back(t / 0.3) * (1 + 0.02 * math.sin(t * 5))
    if PUNCH <= t < PUNCH + 0.3:
        ls *= 1 + 0.14 * math.sin(math.pi * (t - PUNCH) / 0.3)
    paste_center(fr, LOGO_IM, W / 2 + sx, H / 2 + sy, ls * push)

    # flash on the punchline and white-out into the episode
    flash = 0.0
    if PUNCH <= t < PUNCH + 0.12:
        flash = 0.35 * (1 - (t - PUNCH) / 0.12)
    if t > 2.82:
        flash = max(flash, ease_out((t - 2.82) / 0.18) * 0.9)
    if flash > 0:
        fr = Image.blend(fr, Image.new("RGBA", (W, H), (255, 255, 255, 255)), flash)
    return fr.convert("RGB")


# ---------------------------------------------------------------- backing track (synthesized, royalty-free)
def backing():
    n = int(D * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    # warm pad: Dmaj9-ish, slow attack
    for f, amp in ((146.83, 1.0), (220.0, 0.8), (277.18, 0.6), (329.63, 0.5), (440.0, 0.3)):
        det = 1.003
        out += amp * (np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * det * t + 1.0))
    out *= np.clip(t / 0.5, 0, 1) * (0.6 + 0.4 * np.clip(t / D, 0, 1))
    out /= np.abs(out).max()
    out *= 0.25
    # soft pulse: muted plucks on eighth notes at 120 bpm
    notes = [293.66, 440.0, 369.99, 440.0]
    for i, st in enumerate(np.arange(0, D, 0.25)):
        idx = int(st * SR)
        L = int(0.22 * SR)
        tt = np.arange(min(L, n - idx)) / SR
        f = notes[i % 4]
        out[idx:idx + len(tt)] += 0.10 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 18)
    # sub boom at the start and on the punchline
    for st, g in ((0.0, 0.5), (PUNCH, 0.45)):
        idx = int(st * SR)
        tt = np.arange(min(int(0.6 * SR), n - idx)) / SR
        out[idx:idx + len(tt)] += g * np.sin(2 * np.pi * (55 + 30 * np.exp(-tt * 20)) * tt) * np.exp(-tt * 6)
    # filtered-noise riser into the episode
    rng = np.random.default_rng(1)
    nz = rng.standard_normal(n)
    nz = np.convolve(nz, np.ones(6) / 6, "same")
    rise = np.clip((t - 2.4) / 0.6, 0, 1) ** 2
    out += 0.12 * nz * rise
    fade = np.clip((D - t) / 0.05, 0, 1)
    return np.clip(out * fade, -1, 1)


def main():
    tmp = tempfile.mkdtemp()
    bed = os.path.join(tmp, "bed.wav")
    pcm = (np.repeat(backing()[:, None], 2, 1) * 32767).astype(np.int16)
    import wave

    with wave.open(bed, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    rng = np.random.default_rng(7)
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", QUOTE, "-i", bed,
         "-filter_complex",
         # voice up front, bed tucked well underneath
         f"[1:a]atrim=0:{D},asetpts=PTS-STARTPTS,aresample={SR},afade=t=out:st=2.9:d=0.1,volume=1.0[v];"
         f"[2:a]volume=0.45[b];"
         f"[v][b]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,atrim=0:{D}[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE)
    for i in range(N):
        ff.stdin.write(frame(i / FPS, rng).tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
