"""Sound design + mix : voix off, musique synthétique, SFX (whoosh, impacts, pops...)."""
import json, wave, sys
import numpy as np

SR = 44100
rng = np.random.default_rng(7)

# ---- timeline partagée avec la vidéo ----
LINE_START = [0.3, 3.2, 5.1, 7.9, 12.3, 17.2, 23.6, 27.3]
TOTAL = 33.5


def sec(x):
    return int(round(x * SR))


def add(buf, sig, t, gain=1.0):
    i = sec(t)
    if i >= len(buf):
        return
    n = min(len(sig), len(buf) - i)
    buf[i:i + n] += sig[:n] * gain


def env_exp(n, k):
    return np.exp(-np.arange(n) / SR * k)


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    # filtre 1 pôle vectorisé via lfilter manuel (rapide avec cumsum n'est pas stable) -> boucle numpy par blocs
    y = np.empty_like(x)
    s = 0.0
    for i in range(len(x)):
        s = (1 - a) * x[i] + a * s
        y[i] = s
    return y


def fast_lp(x, fc):
    """Passe-bas par FFT (rapide)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x))


def fast_hp(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 - 1 / (1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x))


def band(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / (1 + (f / hi) ** 4)) * (1 - 1 / (1 + (f / lo) ** 4))
    return np.fft.irfft(X, len(x))


# ---------- sons ----------
def kick(power=1.0):
    n = sec(0.35)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) * power


def hat(open_=False):
    n = sec(0.25 if open_ else 0.07)
    x = fast_hp(rng.standard_normal(n), 7000)
    return x * env_exp(n, 14 if open_ else 55) * 0.5


def clap():
    n = sec(0.22)
    x = band(rng.standard_normal(n), 1200, 5500)
    e = env_exp(n, 22)
    for d in (0, 0.012, 0.024):
        e[sec(d):] += 0  # (grain d'attaque)
    return x * e * 0.9


def bass(freq, dur=0.22):
    n = sec(dur)
    t = np.arange(n) / SR
    saw = 2 * ((t * freq) % 1) - 1
    sq = np.sign(np.sin(2 * np.pi * freq * t))
    x = fast_lp(0.6 * saw + 0.4 * sq, 420)
    return x * np.minimum(1, t * 200) * np.exp(-t * 6) * 0.9


def whoosh(dur=0.7, up=True):
    n = sec(dur)
    t = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    # balayage de bande : on mixe 3 bandes avec enveloppes décalées
    lo = fast_lp(x, 500)
    mid = band(x, 600, 3000)
    hi = fast_hp(x, 3500)
    env = (np.sin(np.pi * t) ** 2)
    sweep = t if up else 1 - t
    y = lo * (1 - sweep) * 1.2 + mid * 1.0 + hi * sweep * 0.8
    return y * env * 0.7


def impact(dur=1.2, power=1.0):
    n = sec(dur)
    t = np.arange(n) / SR
    f = 38 + 130 * np.exp(-t * 18)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    crack = fast_hp(rng.standard_normal(n), 900) * np.exp(-t * 28) * 0.8
    tail = fast_lp(rng.standard_normal(n), 300) * np.exp(-t * 2.5) * 0.35
    return (boom + crack + tail) * power


def pop():
    n = sec(0.12)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (380 + 900 * np.exp(-t * 60)) * t) * np.exp(-t * 38) * 0.9


def ding(f=1318):
    n = sec(0.6)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.01 * t) + 0.2 * np.sin(2 * np.pi * f * 3.02 * t)
    return x * np.exp(-t * 7) * np.minimum(1, t * 800) * 0.5


def riser(dur=1.0):
    n = sec(dur)
    t = np.linspace(0, 1, n)
    f = 200 + 2600 * t ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35
    noise = fast_hp(rng.standard_normal(n), 2500) * 0.5
    return (tone + noise) * t ** 1.6


def tick():
    n = sec(0.04)
    return fast_hp(rng.standard_normal(n), 3000) * env_exp(n, 90) * 0.7


def pad(dur, freqs):
    n = sec(dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in freqs:
        for det in (-0.4, 0.4):
            x += np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6))
    x *= 0.12 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t))
    return fast_lp(x, 1800) * np.minimum(1, t * 1.5) * np.minimum(1, (dur - t) * 3)


def build(S):
    info = json.load(open(f"{S}/vo/info.json"))
    N = sec(TOTAL + 0.5)
    # ---------- voix ----------
    voice = np.zeros(N)
    for i, ((d, sr), ts) in enumerate(zip(info, LINE_START)):
        w = wave.open(f"{S}/vo/{i}.wav")
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
        w.close()
        # rééchantillonnage 22.05k -> 44.1k (interp linéaire)
        xi = np.interp(np.arange(0, len(x) - 1, sr / SR), np.arange(len(x)), x)
        xi = fast_hp(xi, 70)
        xi *= 1.0 / (np.max(np.abs(xi)) + 1e-9) * 0.85
        add(voice, xi, ts)
    # compression douce + présence
    voice = np.tanh(voice * 1.6) / np.tanh(1.6) * 0.95
    voice = voice + 0.25 * fast_hp(voice, 2500)  # un peu d'air

    # ---------- musique ----------
    music = np.zeros(N)
    bpm = 124
    beat = 60 / bpm
    notes = [55.0, 55.0, 65.41, 55.0, 82.41, 73.42, 65.41, 49.0]  # A1.. motif basse (Am)
    k = kick(1.0)
    h = hat(False)
    ho = hat(True)
    cl = clap()
    t = 0.0
    bi = 0
    DROP = 3.2
    END = 29.2
    while t < TOTAL:
        full = DROP <= t < END
        if t < DROP:
            if bi % 4 == 0:
                add(music, kick(0.8), t, 0.55)
            if bi % 2 == 1:
                add(music, tick(), t, 0.5)
        elif t < END:
            add(music, k, t, 0.95)
            add(music, ho, t + beat / 2, 0.55)
            if bi % 2 == 1:
                add(music, cl, t, 0.55)
            for j in range(2):
                add(music, h, t + beat * j / 2 + beat / 4, 0.4)
            for j in range(2):
                nf = notes[(bi * 2 + j) % len(notes)]
                add(music, bass(nf, 0.2), t + beat * j / 2, 0.55)
        t += beat
        bi += 1
    add(music, pad(TOTAL, [110, 130.81, 164.81, 220]), 0, 0.7)
    add(music, pad(TOTAL - DROP, [110, 164.81, 196, 261.6]), DROP, 0.5)
    # ducking sous la voix
    env = np.abs(voice)
    k_ = sec(0.06)
    env = np.convolve(env, np.ones(k_) / k_, mode="same")
    env = np.convolve(env, np.ones(sec(0.15)) / sec(0.15), mode="same")
    env = np.clip(env / 0.25, 0, 1)
    music *= (1 - 0.6 * env) * 0.55

    # ---------- SFX ----------
    sfx = np.zeros(N)
    scene_starts = [0.6, 1.2, 1.8, 2.5, 3.2, 5.1, 7.9, 12.3, 17.2, 23.6, 27.3, 29.2]
    for s in scene_starts:
        add(sfx, whoosh(0.55, up=True), s - 0.35, 0.55)
        add(sfx, tick(), s, 0.8)
    add(sfx, impact(1.4, 1.0), 0.0, 0.9)
    add(sfx, riser(1.0), 2.2, 0.55)
    for s, p in [(3.2, 1.0), (3.6, 0.6), (4.1, 0.8), (5.1, 0.6), (15.9, 1.0), (23.6, 0.8), (27.3, 0.9), (28.2, 1.1), (29.4, 1.0)]:
        add(sfx, impact(1.1, p), s, 0.8)
    for s in [5.3, 6.3, 6.7, 7.1, 8.5, 9.7, 10.5, 11.1, 12.4, 13.1, 13.7, 14.2, 17.8, 19.6, 21.0, 31.0]:
        add(sfx, pop(), s, 0.75)
    for s in [21.4, 22.0, 22.6, 24.2, 25.2, 26.0]:
        add(sfx, ding(1046 if s < 23 else 1318), s, 0.7)
    add(sfx, riser(0.9), 10.2, 0.4)
    add(sfx, riser(1.0), 26.3, 0.4)
    add(sfx, riser(0.9), 15.0, 0.4)
    # petits tick de compteur (<1 sec)
    for i in range(8):
        add(sfx, tick(), 15.2 + i * 0.09, 0.6)

    mix = voice * 1.0 + music * 0.9 + sfx * 0.55
    # fade out
    fo = np.ones(N)
    n_fo = sec(0.8)
    i0 = sec(TOTAL) - n_fo
    fo[i0:sec(TOTAL)] = np.linspace(1, 0, n_fo)
    fo[sec(TOTAL):] = 0
    mix *= fo
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix /= np.max(np.abs(mix)) / 0.93
    mix = mix[: sec(TOTAL)]
    st = np.stack([mix, mix], axis=1)
    out = f"{S}/mix.wav"
    w = wave.open(out, "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype("<i2").tobytes())
    w.close()
    print("audio ok", len(mix) / SR)


if __name__ == "__main__":
    build(sys.argv[1])
