"""
Slide renderer for @wealth.wave.fm - two looks:
  neurofusion   dark, cosmic, two sound waves meeting in the middle
  meaffirmation white and gold, soft botanicals, like a private journal
"""
import os, math, textwrap
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


# ---------- backgrounds ----------
def bg_neurofusion(t):
    img = Image.new("RGB", (W, H), t["bg"])
    glow = Image.new("RGB", (W, H), t["bg"])
    g = ImageDraw.Draw(glow)
    g.ellipse((-200, 1250, W + 200, H + 500), fill=(40, 20, 90))
    g.ellipse((200, -500, W + 400, 500), fill=(10, 50, 70))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(220)), 0.8)
    # two waves: left ear (teal) and right ear (violet) merging into one in the centre
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y0 = H - 470

    def wave(x0, x1, freq, amp, colour, fade):
        # draw short segments so each can have its own transparency
        prev = None
        for x in range(int(x0), int(x1) + 1, 3):
            y = y0 + amp * math.sin(2 * math.pi * freq * x / W)
            a = int(230 * fade(x))
            if prev and a > 0:
                d.line([prev, (x, y)], fill=colour + (a,), width=4)
            prev = (x, y)

    mid = W / 2
    # left ear (teal) fades out as it reaches the centre
    wave(0, mid, 10, 48, t["accent"], lambda x: max(0.0, 1 - x / mid) ** 0.6)
    # right ear (violet) fades out as it reaches the centre
    wave(mid, W, 12, 48, t["accent2"], lambda x: max(0.0, (x - mid) / mid) ** 0.6)
    # the new third tone, born in the middle
    wave(W * 0.2, W * 0.8, 3, 38, (255, 255, 255), lambda x: max(0.0, 1 - abs(x - mid) / (W * 0.3)))
    blurred = layer.filter(ImageFilter.GaussianBlur(6))
    img.paste(blurred, (0, 0), blurred)
    img.paste(layer, (0, 0), layer)
    # stars
    d2 = ImageDraw.Draw(img)
    import random
    rnd = random.Random(7)
    for _ in range(90):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H - 600), rnd.choice([1, 1, 2])
        d2.ellipse((x, y, x + r, y + r), fill=(200, 200, 235))
    return img


def leaf(d, cx, cy, length, angle, colour):
    pts = []
    for i in range(0, 41):
        s = i / 40
        w = math.sin(math.pi * s) * length * 0.28
        pts.append((s * length, w))
    pts += [(x, -y) for x, y in reversed(pts)]
    a = math.radians(angle)
    rot = [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]
    d.polygon(rot, outline=colour, width=2)
    d.line([rot[0], rot[40]], fill=colour, width=1)


def bg_meaffirmation(t):
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    soft = (232, 219, 188)
    for cx, cy, ln, ang in [(-40, 180, 260, 30), (60, 320, 200, -15), (980, 120, 240, 150),
                            (1040, 330, 180, 200), (-30, 1650, 260, -30), (90, 1790, 190, 20),
                            (990, 1640, 250, 210), (1060, 1820, 170, 160)]:
        leaf(d, cx, cy, ln, ang, soft)
    d.rectangle((60, 60, W - 60, H - 60), outline=t["accent"], width=2)
    d.rectangle((74, 74, W - 74, H - 74), outline=(226, 206, 160), width=1)
    return img


BACKGROUNDS = {"neurofusion": bg_neurofusion, "meaffirmation": bg_meaffirmation}


# ---------- text helpers ----------
def centred(d, text, fnt, fill, y, width, gap=1.25):
    for line in textwrap.wrap(text, width=width):
        d.text(((W - d.textlength(line, font=fnt)) / 2, y), line, font=fnt, fill=fill)
        y += int(fnt.size * gap)
    return y


def height(text, fnt, width, gap=1.25):
    return len(textwrap.wrap(text, width=width)) * int(fnt.size * gap)


def render_slide(slide, idx, total, brand):
    theme_name = brand["theme"]
    t = THEMES[theme_name]
    img = BACKGROUNDS[theme_name](t)
    d = ImageDraw.Draw(img)
    top_band = 0.42 if theme_name == "neurofusion" else 0.47   # keep text above the waves

    if slide["type"] == "hook":
        f = font("bold", 82)
        h = height(slide["text"], f, 19, 1.2)
        centred(d, slide["text"], f, t["text"], H * top_band - h / 2, 19, 1.2)
        fs = font("serif_i", 40)
        s = "swipe  >>"
        d.text(((W - d.textlength(s, font=fs)) / 2, H * top_band + h / 2 + 80), s, font=fs, fill=t["accent"])
    elif slide["type"] == "body":
        ft, fb = font("medium", 44), font("serif", 60)
        title = slide["title"].upper()
        hb = height(slide["text"], fb, 25, 1.35)
        y = H * top_band - (hb + 140) / 2
        d.text(((W - d.textlength(title, font=ft)) / 2, y), title, font=ft, fill=t["accent"])
        d.line((W / 2 - 60, y + 78, W / 2 + 60, y + 78), fill=t["accent"], width=3)
        centred(d, slide["text"], fb, t["text"], y + 135, 25, 1.35)
    else:  # cta
        f1, f2, f3, fu = font("serif_i", 56), font("bold", 110), font("medium", 38), font("bold", 44)
        y = H * top_band - 300
        y = centred(d, brand["cta_line"], f1, t["text"], y, 26, 1.3) + 30
        y = centred(d, brand["cta_name"], f2, t["accent"], y, 14, 1.1) + 40
        y = centred(d, brand["cta_sub"], f3, t["text"], y, 34) + 10
        url = brand["cta_url"]
        d.text(((W - d.textlength(url, font=fu)) / 2, y), url, font=fu, fill=t["accent"])

    fl = font("medium", 30)
    label = f'{brand["label"]}  ·  {idx}/{total}'
    d.text(((W - d.textlength(label, font=fl)) / 2, H - 150), label, font=fl, fill=t["accent"])
    fh = font("medium", 26)
    d.text(((W - d.textlength(brand["handle"], font=fh)) / 2, H - 110), brand["handle"], font=fh, fill=t["muted"])
    return img


def render_show(show, brand):
    out = os.path.join(HERE, "output", show["id"])
    os.makedirs(out, exist_ok=True)
    total = len(show["slides"])
    for i, s in enumerate(show["slides"], 1):
        render_slide(s, i, total, brand).convert("RGB").save(
            os.path.join(out, f"slide_{i}.jpg"), "JPEG", quality=92)
    with open(os.path.join(out, "caption.txt"), "w") as fh:
        fh.write(show["caption"] + "\n\n" + " ".join(brand["hashtags"]) + "\n")
    return out
