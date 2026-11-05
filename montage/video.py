"""Rendu vidéo 1080x1920 @30fps : clips + motion design + sous-titres animés."""
import math, subprocess, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
TOTAL = 33.5
Y = (255, 214, 10)
R = (255, 59, 48)
WH = (255, 255, 255)
K = (10, 10, 14)
FD = "/usr/share/fonts/opentype/inter/InterDisplay-%s.otf"

LINE_START = [0.3, 3.2, 5.1, 7.9, 12.3, 17.2, 23.6, 27.3]
LINES = ["Tu veux devenir plus fort ? Plus explosif ?",
         "Arrête de zapper l'arraché !",
         "C'est le mouvement le plus technique de l'haltérophilie.",
         "Il développe ta puissance : de la force, multipliée par la vitesse.",
         "Jambes, hanches, dos, épaules : tout travaille ensemble, en moins d'une seconde.",
         "Tu reçois la barre bras tendus, au-dessus de la tête, en squat profond. Mobilité. Stabilité. Contrôle.",
         "Résultat : tu sautes plus haut, tu cours plus vite, tu soulèves plus lourd.",
         "Alors charge la barre, et arrache !"]
NO_CAPTION = {0, 1, 7}

# (t0, t1, clip, start_src, speed, punch)
SCENES = [
    (0.0, 0.6, "1123", 1.2, 1.0, True),
    (0.6, 1.2, "1124", 2.4, 1.0, True),
    (1.2, 1.8, "1125", 2.5, 1.0, True),
    (1.8, 2.5, "1127", 2.2, 1.0, True),
    (2.5, 3.2, "1117", 11.8, 1.0, True),
    (3.2, 5.1, "1117", 5.55, 0.5, True),
    (5.1, 7.9, "1124", 2.0, 1.0, True),
    (7.9, 12.3, "1127", 2.2, 1.0, True),
    (12.3, 17.2, "1123", 1.0, 1.0, True),
    (17.2, 23.6, "1117", 12.3, 0.8, True),
    (23.6, 27.3, "1125", 12.0, 1.0, True),
    (27.3, 29.2, "1124", 8.3, 1.0, True),
    (29.2, 33.5, "1117", 5.8, 0.5, False),
]
CUT_T = [s[0] for s in SCENES][1:]
IMPACTS = [0.0, 3.2, 3.6, 4.1, 5.1, 15.9, 23.6, 27.3, 28.2, 29.4, 11.1, 9.7, 8.5]

_f = {}
def font(size, w="Black"):
    k = (size, w)
    if k not in _f:
        _f[k] = ImageFont.truetype(FD % w, size)
    return _f[k]

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ease_out_back(x):
    x = clamp(x); c1 = 1.9; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def ease_out(x):
    x = clamp(x); return 1 - (1 - x) ** 3

# ---------- lecture clips ----------
class Reader:
    def __init__(self, S, clip, ss, speed, dur):
        src_dur = dur * speed + 0.2
        vf = "eq=contrast=1.1:saturation=1.25:brightness=-0.03"
        if speed != 1.0:
            vf = f"setpts=PTS/{speed},minterpolate=fps=30:mi_mode=blend," + vf
        vf = f"{vf},fps=30"
        cmd = ["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(src_dur), "-i", f"{S}/src/{clip}.mp4",
               "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.last = None
    def frame(self):
        b = self.p.stdout.read(W * H * 3)
        if len(b) == W * H * 3:
            self.last = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        return self.last
    def close(self):
        try:
            self.p.kill(); self.p.stdout.close(); self.p.wait()
        except Exception:
            pass

# ---------- helpers texte ----------
_tc = {}
def T(txt, size, fill=WH, w="Black", stroke=0, shadow=True, pad=None):
    if pad is None:
        pad = 40 if shadow else 0
    k = (txt, size, fill, w, stroke, shadow, pad)
    if k in _tc:
        return _tc[k]
    f = font(size, w)
    bb = f.getbbox(txt, stroke_width=stroke)
    wd, ht = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    im = Image.new("RGBA", (wd, ht), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (wd, ht), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - bb[0] + 0, pad - bb[1] + 8), txt, font=f, fill=(0, 0, 0, 200), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        im.alpha_composite(sh)
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), txt, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    _tc[k] = im
    return im

def place(layer, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BILINEAR, expand=True)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy(); im.putalpha(a)
    layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

def pop_text(layer, t, ts, txt, size, cx, cy, fill=WH, te=None, rot=0.0, stroke=0, w="Black"):
    if t < ts or (te is not None and t > te + 0.2):
        return
    s = ease_out_back((t - ts) / 0.32)
    a = clamp((t - ts) / 0.08)
    if te is not None and t > te:
        a *= clamp(1 - (t - te) / 0.2)
    im = T(txt, size, fill, w, stroke)
    fit = min(1.0, 930 / max(1, im.width - 80))
    place(layer, im, cx, cy, s * fit, a, rot)

def card(layer, x0, y0, x1, y1, a=0.62, accent=None, r=26):
    ov = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), r, fill=(12, 12, 18, int(255 * a)))
    if accent:
        d.rounded_rectangle((0, 0, 14, y1 - y0 - 1), 7, fill=accent + (255,))
    layer.alpha_composite(ov, (x0, y0))

def pop_card(layer, t, ts, x, y, wd, ht, txt, size, accent=Y, fill=WH, te=None, icon=None):
    if t < ts or (te is not None and t > te + 0.2):
        return
    s = ease_out_back((t - ts) / 0.3)
    a = clamp((t - ts) / 0.08)
    if te is not None and t > te:
        a *= clamp(1 - (t - te) / 0.2)
    im = Image.new("RGBA", (wd, ht), (0, 0, 0, 0))
    card(im, 0, 0, wd, ht, 0.72, accent)
    tx = T(txt, size, fill, "ExtraBold", 0, False)
    im.alpha_composite(tx, (40 + (0 if not icon else 0), (ht - tx.height) // 2))
    place(layer, im, x + wd / 2, y + ht / 2, s, a)

def arrow_up(d, cx, cy, s, fill):
    d.polygon([(cx, cy - s), (cx + s * 0.9, cy), (cx + s * 0.38, cy), (cx + s * 0.38, cy + s), (cx - s * 0.38, cy + s), (cx - s * 0.38, cy), (cx - s * 0.9, cy)], fill=fill)

def check(d, cx, cy, s, fill):
    d.line([(cx - s, cy), (cx - s * 0.25, cy + s * 0.7), (cx + s, cy - s * 0.7)], fill=fill, width=int(s * 0.5), joint="curve")

# ---------- captions ----------
def caption_data():
    out = []
    for i, line in enumerate(LINES):
        words = line.upper().split()
        groups, cur = [], []
        f_ = font(78, "Black")
        for w_ in words:
            if cur and f_.getlength(" ".join(cur + [w_]) + " ") > 880:
                groups.append(cur); cur = []
            cur.append(w_)
            if w_[-1] in ":?!." or f_.getlength(" ".join(cur) + " ") > 520:
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        out.append(groups)
    return out
CAPS = caption_data()
INFO = None

def caption(layer, t):
    for i, ts in enumerate(LINE_START):
        d = INFO[i][0]
        if i in NO_CAPTION or not (ts <= t <= ts + d + 0.15):
            continue
        words = [w_ for g in CAPS[i] for w_ in g]
        total = sum(len(w_) + 1 for w_ in words)
        p = clamp((t - ts) / d)
        acc, idx_global, cum = 0, 0, 0
        for gi, g in enumerate(CAPS[i]):
            n = sum(len(w_) + 1 for w_ in g)
            if p * total <= cum + n or gi == len(CAPS[i]) - 1:
                # groupe courant
                loc = p * total - cum
                c = 0
                cw = len(g) - 1
                for wi, w_ in enumerate(g):
                    c += len(w_) + 1
                    if loc < c:
                        cw = wi; break
                f = font(78, "Black")
                full = " ".join(g)
                widths = [f.getlength(w_ + " ") for w_ in g]
                tw = sum(widths)
                x = (W - tw) / 2
                im = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
                dr = ImageDraw.Draw(im)
                for wi, w_ in enumerate(g):
                    col = Y if wi == cw else WH
                    dr.text((x, 40), w_, font=f, fill=col + (255,), stroke_width=9, stroke_fill=(0, 0, 0, 255))
                    x += widths[wi]
                age = (t - ts) if False else 1
                layer.alpha_composite(im, (0, 1390))
                return
            cum += n

# ---------- overlays par scène ----------
def overlays(layer, t):
    # barre de progression
    x0, x1, yb = 60, W - 60, 215
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, yb, x1, yb + 10), 5, fill=(255, 255, 255, 70))
    d.rounded_rectangle((x0, yb, x0 + (x1 - x0) * clamp(t / TOTAL), yb + 10), 5, fill=Y + (255,))

    # ===== HOOK =====
    if t < 1.65:
        pop_text(layer, t, 0.0, "TU VEUX", 130, W / 2, 380, WH, te=1.55)
        pop_text(layer, t, 0.12, "DEVENIR", 130, W / 2, 500, WH, te=1.55)
        pop_text(layer, t, 0.3, "PLUS FORT ?", 190, W / 2, 680, Y, te=1.55, rot=-3)
    elif t < 3.2:
        pop_text(layer, t, 1.7, "PLUS", 150, W / 2, 440, WH, te=3.1)
        pop_text(layer, t, 1.8, "EXPLOSIF ?", 200, W / 2, 640, R, te=3.1, rot=3)
    # ===== ARRÊTE DE ZAPPER =====
    elif t < 5.1:
        pop_text(layer, t, 3.2, "ARRÊTE", 220, W / 2, 400, R, te=5.0, rot=-4)
        pop_text(layer, t, 3.6, "DE ZAPPER", 130, W / 2, 590, WH, te=5.0)
        if t > 4.0:
            p = ease_out((t - 4.0) / 0.12)
            ImageDraw.Draw(layer).line([(180, 600), (180 + 720 * p, 600)], fill=R + (255,), width=14)
        pop_text(layer, t, 4.1, "L'ARRACHÉ", 190, W / 2, 790, Y, te=5.0, rot=2)
    # ===== TECHNIQUE =====
    elif t < 7.9:
        pop_text(layer, t, 5.15, "ARRACHÉ", 170, W / 2, 340, Y, te=7.8)
        pop_text(layer, t, 5.4, "SNATCH", 70, W / 2, 445, WH, te=7.8, w="Bold")
        bars = [("TECHNIQUE", 6.3, 1.0), ("VITESSE", 6.7, 0.95), ("COORDINATION", 7.1, 0.9)]
        for j, (lab, ts, v) in enumerate(bars):
            if t < ts: continue
            a = clamp((t - ts) / 0.15)
            yy = 560 + j * 112
            s = ease_out((t - ts) / 0.5)
            im = Image.new("RGBA", (W, 110), (0, 0, 0, 0))
            card(im, 60, 0, W - 60, 92, 0.7, Y)
            dd = ImageDraw.Draw(im)
            _t = T(lab, 44, WH, "ExtraBold", 0, False); im.alpha_composite(_t, (80, (92 - _t.height) // 2))
            dd.rounded_rectangle((520, 34, 1000, 58), 12, fill=(255, 255, 255, 50))
            dd.rounded_rectangle((520, 34, 520 + 480 * v * s, 58), 12, fill=Y + (255,))
            a_ = im.getchannel("A").point(lambda q: int(q * a)); im.putalpha(a_)
            layer.alpha_composite(im, (0, yy))
    # ===== PUISSANCE = FORCE x VITESSE =====
    elif t < 12.3:
        pop_text(layer, t, 8.5, "PUISSANCE", 170, W / 2, 340, Y, te=12.2)
        pop_text(layer, t, 9.7, "FORCE", 130, W / 2, 485, WH, te=12.2)
        pop_text(layer, t, 10.5, "×", 110, W / 2, 585, R, te=12.2)
        pop_text(layer, t, 11.1, "VITESSE", 130, W / 2, 690, WH, te=12.2)
        if t > 11.1:
            p = ease_out((t - 11.1) / 0.35)
            ImageDraw.Draw(layer).rounded_rectangle((W / 2 - 400 * p, 775, W / 2 + 400 * p, 793), 9, fill=Y + (255,))
    # ===== MUSCLES + <1s =====
    elif t < 17.2:
        chips = [("JAMBES", 12.4, 60, 330), ("HANCHES", 13.1, 560, 330), ("DOS", 13.7, 60, 450), ("ÉPAULES", 14.2, 560, 450)]
        for lab, ts, x, y in chips:
            pop_card(layer, t, ts, x, y, 460, 100, lab, 54, Y, WH, te=16.9)
        if t > 15.9:
            pop_text(layer, t, 15.9, "< 1 SEC", 230, W / 2, 700, Y, te=17.1, rot=-3)
        if t > 15.1 and t < 15.9:
            v = int((t - 15.1) / 0.8 * 99)
            pop_text(layer, t, 15.1, "TOUT EN MÊME TEMPS", 70, W / 2, 640, WH, te=15.85)
    # ===== RÉCEPTION =====
    elif t < 23.6:
        tags = [("BRAS TENDUS", 17.8, 19.5), ("BARRE AU-DESSUS DE LA TÊTE", 19.6, 20.95), ("SQUAT PROFOND", 21.0, 21.3)]
        for lab, ts, te in tags:
            sz = 80 if len(lab) < 20 else 54
            pop_text(layer, t, ts, lab, sz, W / 2, 420, Y if "SQUAT" in lab else WH, te=te)
        if t >= 17.3 and t < 17.8:
            pop_text(layer, t, 17.3, "LA RÉCEPTION", 110, W / 2, 420, WH, te=17.75)
        words = [("MOBILITÉ", 21.4), ("STABILITÉ", 22.0), ("CONTRÔLE", 22.6)]
        for j, (lab, ts) in enumerate(words):
            if t < ts: continue
            s = ease_out_back((t - ts) / 0.3)
            im = Image.new("RGBA", (860, 120), (0, 0, 0, 0))
            card(im, 0, 0, 860, 110, 0.72, Y)
            dd = ImageDraw.Draw(im)
            check(dd, 90, 56, 28, Y + (255,))
            _t = T(lab, 66, WH, "Black", 0, False); im.alpha_composite(_t, (150, (110 - _t.height) // 2))
            place(layer, im, W / 2, 330 + j * 135, s, clamp((t - ts) / 0.1))
    # ===== RÉSULTAT =====
    elif t < 27.3:
        pop_text(layer, t, 23.65, "RÉSULTAT", 150, W / 2, 300, Y, te=27.2, rot=-2)
        stats = [("SAUT", 24.2), ("VITESSE", 25.2), ("FORCE", 26.0)]
        for j, (lab, ts) in enumerate(stats):
            if t < ts: continue
            s = ease_out_back((t - ts) / 0.3)
            im = Image.new("RGBA", (900, 130), (0, 0, 0, 0))
            card(im, 0, 0, 900, 120, 0.74, Y)
            dd = ImageDraw.Draw(im)
            _t = T(lab, 62, WH, "Black", 0, False); im.alpha_composite(_t, (50, (120 - _t.height) // 2))
            p = ease_out((t - ts) / 0.6)
            dd.rounded_rectangle((420, 48, 740, 72), 12, fill=(255, 255, 255, 50))
            dd.rounded_rectangle((420, 48, 420 + 320 * p, 72), 12, fill=Y + (255,))
            arrow_up(dd, 820, 60, 34 * (0.7 + 0.3 * p), (60, 220, 110, 255))
            place(layer, im, W / 2, 440 + j * 150, s, clamp((t - ts) / 0.1))
    # ===== CHARGE LA BARRE / ARRACHE =====
    elif t < 29.2:
        pop_text(layer, t, 27.3, "CHARGE", 150, W / 2, 400, WH, te=29.1)
        pop_text(layer, t, 27.55, "LA BARRE.", 150, W / 2, 540, WH, te=29.1)
        pop_text(layer, t, 28.2, "ARRACHE !", 220, W / 2, 740, Y, te=29.1, rot=-3)
    # ===== OUTRO =====
    else:
        pop_text(layer, t, 29.4, "L'ARRACHÉ", 200, W / 2, 430, Y)
        pop_text(layer, t, 29.8, "FORCE", 120, W / 2, 600, WH)
        pop_text(layer, t, 30.1, "VITESSE", 120, W / 2, 725, WH)
        pop_text(layer, t, 30.4, "TECHNIQUE", 120, W / 2, 850, WH)
        if t > 31.0:
            s = ease_out_back((t - 31.0) / 0.35) * (1 + 0.04 * math.sin((t - 31) * 8))
            im = Image.new("RGBA", (860, 130), (0, 0, 0, 0))
            ImageDraw.Draw(im).rounded_rectangle((0, 0, 859, 129), 65, fill=Y + (255,))
            tx = T("ENTRAÎNE-TOI. ARRACHE.", 56, K, "Black", 0, False)
            im.alpha_composite(tx, ((860 - tx.width) // 2, (130 - tx.height) // 2))
            place(layer, im, W / 2, 1060, s, clamp((t - 31.0) / 0.1))
        if t > 31.5:
            pop_text(layer, t, 31.5, "ENREGISTRE & PARTAGE", 56, W / 2, 1200, WH, w="ExtraBold")

    caption(layer, t)

# ---------- effets image ----------
def shake_offset(t):
    ox = oy = 0.0
    for ti in IMPACTS:
        dt = t - ti
        if 0 <= dt < 0.45:
            a = 26 * math.exp(-dt * 9)
            ox += a * math.sin(dt * 90 + ti)
            oy += a * math.cos(dt * 80 + ti * 2)
    return ox, oy

GRAD = None
def make_grad():
    g = np.zeros((H, W, 4), np.uint8)
    y = np.arange(H)[:, None]
    top = np.clip(1 - y / 900, 0, 1) ** 1.5 * 170
    bot = np.clip((y - 1100) / 820, 0, 1) ** 1.5 * 190
    g[..., 3] = (top + bot).astype(np.uint8)[:, 0:1].repeat(W, 1)
    return Image.fromarray(g, "RGBA")

def compose(frame, t, scene, ts_scene):
    t0, t1, clip, ss, speed, punch = scene
    lt = t - t0
    # zoom : punch d'entrée + lent push-in
    z = 1.15 + 0.05 * (lt / (t1 - t0))
    if punch:
        z += 0.14 * math.exp(-lt * 11)
    ox, oy = shake_offset(t)
    img = Image.fromarray(frame)
    if True:
        nw, nh = int(W * z), int(H * z)
        img = img.resize((nw, nh), Image.BILINEAR)
        left = (nw - W) - int(ox); top = (nh - H) - int(oy)
        left = max(0, min(nw - W, left)); top = max(0, min(nh - H, top))
        img = img.crop((left, top, left + W, top + H))
    img = img.convert("RGBA")
    # outro : assombrir
    if t >= 29.2:
        d = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * 0.62 * clamp((t - 29.2) / 0.3))))
        img.alpha_composite(d)
    img.alpha_composite(GRAD)
    # glitch RGB sur hook
    if t < 3.2 and any(0 <= t - c < 0.12 for c in [0.0, 1.7]):
        a = np.array(img)
        a[..., 0] = np.roll(a[..., 0], 18, axis=1)
        a[..., 2] = np.roll(a[..., 2], -18, axis=1)
        img = Image.fromarray(a, "RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlays(layer, t)
    img.alpha_composite(layer)
    # flash blanc aux coupes
    for c in CUT_T + [0.0]:
        dt = t - c
        if 0 <= dt < 0.12:
            f = Image.new("RGBA", (W, H), (255, 255, 255, int(190 * (1 - dt / 0.12))))
            img.alpha_composite(f)
    # fondu de sortie
    if t > TOTAL - 0.6:
        f = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * clamp((t - (TOTAL - 0.6)) / 0.6))))
        img.alpha_composite(f)
    return img.convert("RGB")

def main(S, out, limit=None):
    global GRAD, INFO
    GRAD = make_grad()
    INFO = json.load(open(f"{S}/vo/info.json"))
    n_frames = int(round(TOTAL * FPS))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    reader, cur = None, -1
    for i in range(n_frames if not limit else limit):
        t = i / FPS
        si = max(k for k, s in enumerate(SCENES) if s[0] <= t + 1e-6)
        if si != cur:
            if reader: reader.close()
            s = SCENES[si]
            reader = Reader(S, s[2], s[3], s[4], s[1] - s[0]); cur = si
        fr = reader.frame()
        if fr is None:
            fr = np.zeros((H, W, 3), np.uint8)
        im = compose(fr, t, SCENES[si], si)
        enc.stdin.write(im.tobytes())
        if i % 90 == 0:
            print("frame", i, "/", n_frames, flush=True)
    enc.stdin.close(); enc.wait()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
