"""
Slide renderer for @wealth.wave.fm.

Each brand has SIX different looks. The look is chosen from the slideshow's id,
so every post gets its own, it stays consistent across that post's six slides,
and it never drifts off brand.

  neurofusion   dark and cosmic
  meaffirmation warm paper, gold, quiet
"""
import os, math, textwrap, hashlib, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get("FONTS_DIR", os.path.join(HERE, "fonts"))
W, H = 1080, 1920

THEMES = {
    "neurofusion": {
        "bg": (7, 6, 18), "text": (238, 236, 255), "accent": (95, 225, 215),
        "accent2": (160, 115, 255), "muted": (150, 145, 190),
    },
    "meaffirmation": {
        "bg": (251, 248, 241), "text": (46, 38, 26), "accent": (184, 145, 58),
        "accent2": (214, 190, 130), "muted": (140, 120, 85),
    },
}


def font(name, size):
    files = {"bold": "Poppins-Bold.ttf", "medium": "Poppins-Medium.ttf",
             "serif": "Lora-Variable.ttf", "serif_i": "Lora-Italic-Variable.ttf"}
    return ImageFont.truetype(os.path.join(FONTS, files[name]), size)


def glow_layer(img, layer, blur=8):
    b = layer.filter(ImageFilter.GaussianBlur(blur))
    img.paste(b, (0, 0), b)
    img.paste(layer, (0, 0), layer)
    return img


def stars(img, rnd, n=90, top=H - 600, colour=(200, 200, 235)):
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y, r = rnd.randint(0, W), rnd.randint(0, top), rnd.choice([1, 1, 2])
        d.ellipse((x, y, x + r, y + r), fill=colour)
    return img


def vertical_glow(t, spots):
    img = Image.new("RGB", (W, H), t["bg"])
    g = Image.new("RGB", (W, H), t["bg"])
    gd = ImageDraw.Draw(g)
    for box, colour in spots:
        gd.ellipse(box, fill=colour)
    return Image.blend(img, g.filter(ImageFilter.GaussianBlur(220)), 0.8)


# ======================= NEUROFUSION LOOKS =======================
def nf_waves(t, rnd):
    img = vertical_glow(t, [((-200, 1250, W + 200, H + 500), (40, 20, 90)),
                            ((200, -500, W + 400, 500), (10, 50, 70))])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y0 = H - 470

    def wave(x0, x1, freq, amp, colour, fade):
        prev = None
        for x in range(int(x0), int(x1) + 1, 3):
            y = y0 + amp * math.sin(2 * math.pi * freq * x / W)
            a = int(230 * fade(x))
            if prev and a > 0:
                d.line([prev, (x, y)], fill=colour + (a,), width=4)
            prev = (x, y)

    mid = W / 2
    wave(0, mid, 10, 48, t["accent"], lambda x: max(0.0, 1 - x / mid) ** 0.6)
    wave(mid, W, 12, 48, t["accent2"], lambda x: max(0.0, (x - mid) / mid) ** 0.6)
    wave(W * 0.2, W * 0.8, 3, 38, (255, 255, 255),
         lambda x: max(0.0, 1 - abs(x - mid) / (W * 0.3)))
    return stars(glow_layer(img, layer, 6), rnd)


def nf_orb(t, rnd):
    img = vertical_glow(t, [((60, 1020, W - 60, 2000), (35, 25, 85)),
                            ((240, 980, 840, 1580), (15, 60, 80))])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H * 0.72
    for i in range(16):
        r = 120 + i * 34
        a = int(150 * (1 - i / 16) ** 1.4) + 20
        col = t["accent"] if i % 2 == 0 else t["accent2"]
        squash = 0.55 + 0.03 * i
        d.ellipse((cx - r, cy - r * squash, cx + r, cy + r * squash), outline=col + (a,), width=3)
    d.ellipse((cx - 70, cy - 40, cx + 70, cy + 40), fill=(255, 255, 255, 110))
    return stars(glow_layer(img, layer, 10), rnd, n=120, top=H - 780)


def nf_interference(t, rnd):
    img = vertical_glow(t, [((-300, 1100, 700, 2100), (20, 55, 80)),
                            ((380, 1100, W + 300, 2100), (45, 22, 95))])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for cx, col in [(W * 0.26, t["accent"]), (W * 0.74, t["accent2"])]:
        for i in range(14):
            r = 60 + i * 62
            a = int(130 * (1 - i / 14) ** 1.2) + 15
            d.ellipse((cx - r, H * 0.78 - r, cx + r, H * 0.78 + r), outline=col + (a,), width=3)
    return stars(glow_layer(img, layer, 7), rnd, n=70, top=H - 900)


def nf_spectrum(t, rnd):
    img = vertical_glow(t, [((-200, 1300, W + 200, H + 400), (30, 18, 80)),
                            ((100, 900, 900, 1500), (12, 55, 75))])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    base, n = H - 300, 34
    bw = W / n
    for i in range(n):
        s = i / (n - 1)
        h = (math.sin(s * math.pi) ** 1.6) * 330 * (0.55 + 0.45 * rnd.random())
        col = tuple(int(t["accent"][k] * (1 - s) + t["accent2"][k] * s) for k in range(3))
        x = i * bw + 6
        d.rounded_rectangle((x, base - h, x + bw - 12, base), radius=8, fill=col + (190,))
    return stars(glow_layer(img, layer, 9), rnd, n=80, top=H - 800)


def nf_constellation(t, rnd):
    img = vertical_glow(t, [((-150, 1150, W + 150, H + 300), (26, 20, 78)),
                            ((250, 850, 950, 1450), (14, 52, 72))])
    pts = [(rnd.randint(70, W - 70), rnd.randint(int(H * 0.56), H - 260)) for _ in range(26)]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, p in enumerate(pts):
        for q in pts[i + 1:]:
            dist = math.hypot(p[0] - q[0], p[1] - q[1])
            if dist < 290:
                a = int(120 * (1 - dist / 290))
                d.line([p, q], fill=t["accent"] + (a,), width=2)
    for p in pts:
        r = rnd.choice([4, 5, 7])
        col = t["accent"] if rnd.random() < 0.6 else t["accent2"]
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col + (230,))
    return stars(glow_layer(img, layer, 8), rnd, n=100, top=int(H * 0.5))


def nf_horizon(t, rnd):
    img = vertical_glow(t, [((-400, 1500, W + 400, H + 900), (18, 60, 85)),
                            ((150, 1150, 930, 1750), (48, 24, 100))])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = W / 2, H + 520, 900
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(10, 9, 26, 255))
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=t["accent"] + (220,), width=5)
    for i, a in enumerate([90, 60, 40]):
        rr = r + 26 + i * 22
        d.arc((cx - rr, cy - rr, cx + rr, cy + rr), 205, 335, fill=t["accent"] + (a,), width=3)
    return stars(glow_layer(img, layer, 9), rnd, n=150, top=int(H * 0.62))


# ======================= MEAFFIRMATION LOOKS =======================
def leaf(d, cx, cy, length, angle, colour, width=2):
    pts = []
    for i in range(0, 41):
        s = i / 40
        w = math.sin(math.pi * s) * length * 0.28
        pts.append((s * length, w))
    pts += [(x, -y) for x, y in reversed(pts)]
    a = math.radians(angle)
    rot = [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]
    d.polygon(rot, outline=colour, width=width)
    d.line([rot[0], rot[40]], fill=colour, width=1)


def paper(t, rnd, speckle=900):
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    for _ in range(speckle):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        shade = rnd.randint(232, 246)
        d.point((x, y), fill=(shade, shade - 6, shade - 18))
    return img


def ma_botanical(t, rnd):
    img = paper(t, rnd)
    d = ImageDraw.Draw(img)
    soft = (232, 219, 188)
    for cx, cy, ln, ang in [(-40, 180, 260, 30), (60, 320, 200, -15), (980, 120, 240, 150),
                            (1040, 330, 180, 200), (-30, 1650, 260, -30), (90, 1790, 190, 20),
                            (990, 1640, 250, 210), (1060, 1820, 170, 160)]:
        leaf(d, cx, cy, ln, ang, soft)
    d.rectangle((60, 60, W - 60, H - 60), outline=t["accent"], width=2)
    d.rectangle((74, 74, W - 74, H - 74), outline=(226, 206, 160), width=1)
    return img


def ma_journal(t, rnd):
    img = paper(t, rnd, 700)
    d = ImageDraw.Draw(img)
    for y in range(300, H - 220, 78):
        d.line((150, y, W - 90, y), fill=(226, 217, 196), width=2)
    d.line((150, 180, 150, H - 160), fill=(220, 175, 170), width=3)
    for cy in [260, 470, 680]:
        d.ellipse((92, cy - 16, 124, cy + 16), outline=(214, 200, 172), width=3)
    leaf(d, 980, 1700, 210, 205, (230, 216, 184))
    leaf(d, 1035, 1810, 150, 170, (235, 224, 198))
    return img


def ma_arch(t, rnd):
    img = paper(t, rnd, 500)
    glow = Image.new("RGB", (W, H), t["bg"])
    g = ImageDraw.Draw(glow)
    g.ellipse((80, 240, W - 80, 1500), fill=(244, 229, 200))
    g.ellipse((240, 560, W - 240, 1320), fill=(240, 216, 176))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(150)), 0.75)
    d = ImageDraw.Draw(img)
    d.arc((150, 250, W - 150, 1250), 180, 360, fill=t["accent"], width=3)
    d.line((150, 750, 150, H - 300), fill=t["accent"], width=3)
    d.line((W - 150, 750, W - 150, H - 300), fill=t["accent"], width=3)
    d.line((150, H - 300, W - 150, H - 300), fill=t["accent"], width=3)
    return img


def ma_ribbon(t, rnd):
    img = paper(t, rnd, 600)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for off, a, wdt in [(0, 90, 7), (46, 55, 5), (-52, 40, 4)]:
        prev = None
        for x in range(-40, W + 40, 6):
            y = H * 0.70 + off + 120 * math.sin(2 * math.pi * x / (W * 1.5))
            if prev:
                d.line([prev, (x, y)], fill=t["accent"] + (a,), width=wdt)
            prev = (x, y)
    img = glow_layer(img, layer, 5)
    d2 = ImageDraw.Draw(img)
    d2.rectangle((64, 64, W - 64, H - 64), outline=(226, 206, 160), width=2)
    return img


def ma_frame(t, rnd):
    img = paper(t, rnd, 800)
    d = ImageDraw.Draw(img)
    d.rectangle((86, 140, W - 86, H - 200), outline=t["accent"], width=3)
    d.rectangle((104, 158, W - 104, H - 218), outline=(228, 210, 168), width=1)
    for cx, cy, ang in [(86, 140, 45), (W - 86, 140, 135), (86, H - 200, -45), (W - 86, H - 200, -135)]:
        leaf(d, cx, cy, 130, ang, t["accent2"])
        leaf(d, cx, cy, 90, ang + 38, (230, 216, 184))
    return img


def ma_sunrise(t, rnd):
    img = paper(t, rnd, 500)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W / 2, H - 250
    for i in range(18):
        ang = math.radians(180 + i * (180 / 17))
        x, y = cx + 1500 * math.cos(ang), cy + 1500 * math.sin(ang)
        a = 40 if i % 2 else 68
        d.line([(cx, cy), (x, y)], fill=t["accent2"] + (a,), width=26)
    img = glow_layer(img, layer, 26)
    d2 = ImageDraw.Draw(img)
    for r, wdt, col in [(190, 3, t["accent"]), (250, 2, (228, 210, 168))]:
        d2.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=col, width=wdt)
    d2.rectangle((64, 64, W - 64, H - 64), outline=(230, 214, 176), width=2)
    return img


# look, how high the words sit, hook font, and whether the words need a
# soft panel behind them so a busy background stays readable
LOOKS = {
    "neurofusion": [
        (nf_waves, 0.42, "bold", False), (nf_orb, 0.30, "bold", False),
        (nf_interference, 0.34, "serif", False), (nf_spectrum, 0.40, "bold", False),
        (nf_constellation, 0.30, "bold", True), (nf_horizon, 0.34, "serif", False),
    ],
    "meaffirmation": [
        (ma_botanical, 0.47, "serif", False), (ma_journal, 0.44, "serif", True),
        (ma_arch, 0.42, "bold", False), (ma_ribbon, 0.40, "serif", False),
        (ma_frame, 0.46, "bold", False), (ma_sunrise, 0.38, "serif", False),
    ],
}


def panel(img, t, top, bottom, dark):
    """A soft band behind the words, so busy backgrounds stay readable."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = (9, 8, 22, 205) if dark else (252, 250, 245, 215)
    d.rounded_rectangle((52, top - 46, W - 52, bottom + 46), radius=40, fill=col)
    lay = lay.filter(ImageFilter.GaussianBlur(3))
    img.paste(lay, (0, 0), lay)
    return img


def pick_look(theme_name, show_id):
    looks = LOOKS[theme_name]
    n = int(hashlib.sha1(str(show_id).encode()).hexdigest(), 16)
    return looks[n % len(looks)], n


# ---------- text helpers ----------
def centred(d, text, fnt, fill, y, width, gap=1.25):
    for line in textwrap.wrap(text, width=width):
        d.text(((W - d.textlength(line, font=fnt)) / 2, y), line, font=fnt, fill=fill)
        y += int(fnt.size * gap)
    return y


def height(text, fnt, width, gap=1.25):
    return len(textwrap.wrap(text, width=width)) * int(fnt.size * gap)


# ---------- the "how it works" diagram (NeuroFusion) ----------
def state_name(hz):
    if hz < 4:
        return "DELTA", "deep sleep"
    if hz < 8:
        return "THETA", "dreamlike, visualisation, the void"
    if hz < 13:
        return "ALPHA", "calm, relaxed focus"
    return "BETA", "alert, switched on"


def ear_wave(d, x0, x1, yc, cycles, amp, colour, alpha=235, width=5):
    prev = None
    for x in range(int(x0), int(x1) + 1, 3):
        y = yc + amp * math.sin(2 * math.pi * cycles * (x - x0) / (x1 - x0))
        if prev:
            d.line([prev, (x, y)], fill=colour + (alpha,), width=width)
        prev = (x, y)


def draw_diagram(img, t, slide):
    """Left ear tone, right ear tone, the brain creates the third beat."""
    left, right = int(slide["left"]), int(slide["right"])
    beat = abs(right - left)
    name, feel = state_name(beat)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fl, fn, fs = font("medium", 36), font("bold", 64), font("serif", 44)

    title = slide.get("title", "How it works").upper()
    ft = font("medium", 44)
    d.text(((W - d.textlength(title, font=ft)) / 2, 150), title, font=ft, fill=t["accent"] + (255,))
    d.line((W / 2 - 60, 228, W / 2 + 60, 228), fill=t["accent"] + (255,), width=3)

    # two ears, two tones
    for cx, hz, col, lab in [(W * 0.25, left, t["accent"], "LEFT EAR"),
                             (W * 0.75, right, t["accent2"], "RIGHT EAR")]:
        d.ellipse((cx - 70, 300, cx + 70, 440), outline=col + (255,), width=5)
        d.arc((cx - 40, 330, cx + 40, 410), 100, 260 if cx < W / 2 else 440, fill=col + (200,), width=4)
        d.text((cx - d.textlength(lab, font=fl) / 2, 460), lab, font=fl, fill=t["muted"] + (255,))
        txt = f"{hz} Hz"
        d.text((cx - d.textlength(txt, font=fn) / 2, 510), txt, font=fn, fill=col + (255,))
        ear_wave(d, cx - 190, cx + 190, 660, 9 if cx < W / 2 else 10, 34, col)

    # arrows into the brain
    for sx in (W * 0.25, W * 0.75):
        d.line([(sx, 730), (W / 2, 850)], fill=t["muted"] + (200,), width=4)
    d.polygon([(W / 2 - 16, 836), (W / 2 + 16, 836), (W / 2, 862)], fill=t["muted"] + (220,))

    # the brain: two hemispheres moving together
    cx, cy = W / 2, 1000
    d.ellipse((cx - 230, cy - 130, cx - 6, cy + 130), outline=t["accent"] + (255,), width=5)
    d.ellipse((cx + 6, cy - 130, cx + 230, cy + 130), outline=t["accent2"] + (255,), width=5)
    for k in range(3):
        yy = cy - 60 + k * 60
        d.arc((cx - 200, yy - 30, cx - 40, yy + 30), 200, 340, fill=t["accent"] + (150,), width=3)
        d.arc((cx + 40, yy - 30, cx + 200, yy + 30), 200, 340, fill=t["accent2"] + (150,), width=3)

    # the third beat
    ear_wave(d, 140, W - 140, 1230, 3, 46, (255, 255, 255), 240, 6)
    txt = f"{beat} Hz"
    fb = font("bold", 96)
    d.text(((W - d.textlength(txt, font=fb)) / 2, 1300), txt, font=fb, fill=(255, 255, 255, 255))
    sub = "the beat your brain creates"
    d.text(((W - d.textlength(sub, font=fs)) / 2, 1420), sub, font=fs, fill=t["text"] + (255,))
    st = f"{name}  ·  {feel}"
    d.text(((W - d.textlength(st, font=fl)) / 2, 1500), st, font=fl, fill=t["accent"] + (255,))
    if slide.get("text"):
        centred(d, slide["text"], font("serif", 40), t["text"] + (255,), 1590, 34, 1.3)
    return glow_layer(img, layer, 5)


def render_slide(slide, idx, total, brand, show_id="x"):
    theme_name = brand["theme"]
    t = THEMES[theme_name]
    (bg_fn, band, hook_font, needs_panel), seed = pick_look(theme_name, show_id)
    rnd = random.Random(seed + idx)          # same look, small natural variation per slide
    img = bg_fn(t, rnd)
    d = ImageDraw.Draw(img)

    if slide["type"] == "diagram":
        img = vertical_glow(t, [((-200, 900, W + 200, H + 300), (30, 18, 80)),
                                ((150, 150, 930, 900), (12, 50, 70))])
        img = draw_diagram(stars(img, rnd, n=60, top=H), t, slide)
        d = ImageDraw.Draw(img)
    elif slide["type"] == "hook":
        f = font(hook_font, 82 if hook_font == "bold" else 76)
        wrap = 19 if hook_font == "bold" else 21
        h = height(slide["text"], f, wrap, 1.2)
        if needs_panel:
            img = panel(img, t, H * band - h / 2, H * band + h / 2 + 140, theme_name == "neurofusion")
            d = ImageDraw.Draw(img)
        centred(d, slide["text"], f, t["text"], H * band - h / 2, wrap, 1.2)
        fs = font("serif_i", 40)
        s = "swipe  >>"
        d.text(((W - d.textlength(s, font=fs)) / 2, H * band + h / 2 + 80), s, font=fs, fill=t["accent"])
    elif slide["type"] == "body":
        ft, fb = font("medium", 44), font("serif", 60)
        title = slide["title"].upper()
        hb = height(slide["text"], fb, 25, 1.35)
        y = H * band - (hb + 140) / 2
        if needs_panel:
            img = panel(img, t, y, y + hb + 150, theme_name == "neurofusion")
            d = ImageDraw.Draw(img)
        d.text(((W - d.textlength(title, font=ft)) / 2, y), title, font=ft, fill=t["accent"])
        d.line((W / 2 - 60, y + 78, W / 2 + 60, y + 78), fill=t["accent"], width=3)
        centred(d, slide["text"], fb, t["text"], y + 135, 25, 1.35)
    else:  # cta
        f1, f2, f3, fu = font("serif_i", 56), font("bold", 110), font("medium", 38), font("bold", 44)
        y = H * band - 300
        if needs_panel:
            img = panel(img, t, y, y + 520, theme_name == "neurofusion")
            d = ImageDraw.Draw(img)
        y = centred(d, brand["cta_line"], f1, t["text"], y, 26, 1.3) + 30
        y = centred(d, brand["cta_name"], f2, t["accent"], y, 14, 1.1) + 40
        y = centred(d, brand["cta_sub"], f3, t["text"], y, 34) + 10
        d.text(((W - d.textlength(brand["cta_url"], font=fu)) / 2, y), brand["cta_url"],
               font=fu, fill=t["accent"])

    fl = font("medium", 30)
    label = f'{brand["label"]}  ·  {idx}/{total}'
    d.text(((W - d.textlength(label, font=fl)) / 2, H - 150), label, font=fl, fill=t["accent"])
    fh = font("medium", 26)
    d.text(((W - d.textlength(brand["handle"], font=fh)) / 2, H - 110), brand["handle"],
           font=fh, fill=t["muted"])
    return img


def render_show(show, brand):
    out = os.path.join(HERE, "output", show["id"])
    os.makedirs(out, exist_ok=True)
    total = len(show["slides"])
    for i, s in enumerate(show["slides"], 1):
        render_slide(s, i, total, brand, show["id"]).convert("RGB").save(
            os.path.join(out, f"slide_{i}.jpg"), "JPEG", quality=92)
    with open(os.path.join(out, "caption.txt"), "w") as fh:
        fh.write(show["caption"] + "\n\n" + " ".join(brand["hashtags"]) + "\n")
    return out


# ---------- slideshow -> video with a binaural beat underneath (NeuroFusion) ----------
import subprocess


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def make_short(images, out_path, seconds_each=4.5, beat=6.0, carrier=200.0):
    """Slow push-in on each slide, soft fades between them, and a binaural bed underneath:
    carrier Hz in the left ear, carrier+beat Hz in the right, with a soft brown-noise pad.
    Same recipe as the quote-of-the-day videos."""
    fps = 30
    frames = int(seconds_each * fps)
    total = seconds_each * len(images)
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
    for p in images:
        cmd += ["-i", p]
    cmd += ["-f", "lavfi", "-t", str(total), "-i", f"sine=frequency={carrier}:sample_rate=44100",
            "-f", "lavfi", "-t", str(total), "-i", f"sine=frequency={carrier + beat}:sample_rate=44100",
            "-f", "lavfi", "-t", str(total), "-i", "anoisesrc=color=brown:amplitude=0.25:sample_rate=44100"]
    parts = []
    for i in range(len(images)):
        parts.append(
            f"[{i}:v]scale=1620:2880,zoompan=z='min(1+on*0.0007,1.08)':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
            f"fade=t=in:st=0:d=0.35,fade=t=out:st={seconds_each - 0.35}:d=0.35,setsar=1[v{i}]")
    n = len(images)
    parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p[v]")
    parts.append(f"[{n}:a][{n + 1}:a]join=inputs=2:channel_layout=stereo,volume=0.12[bin]")
    parts.append(f"[{n + 2}:a]lowpass=f=400,volume=0.06,aformat=channel_layouts=stereo[pad]")
    parts.append(f"[bin][pad]amix=inputs=2:normalize=0,afade=t=in:d=1.5,"
                 f"afade=t=out:st={max(total - 2, 0)}:d=2[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_path]
    subprocess.run(cmd, check=True)
    return out_path
