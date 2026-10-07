"""Local TTS (piper, optional) and a generated soft music bed. No network, no paid APIs."""
import hashlib, os, subprocess, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTS_DIR = os.path.join(ROOT, "tts")
VOICE_DIR = os.path.join(ROOT, "assets", "voices")
VENDOR_TTS = os.path.join(ROOT, "vendor_tts")
SR = 44100


def voice_path(name):
    return os.path.join(VOICE_DIR, f"{name}.onnx")


def tts_available(name="en_US-ryan-high"):
    return os.path.exists(voice_path(name)) and os.path.isdir(os.path.join(VENDOR_TTS, "piper"))


def speakable(s):
    import re
    s = s.replace("*", "")
    rep = [(r"~\s?", "about "), (r"≈", "about "), (r"→", " to "), (r"(?<=\d)–(?=\d)", " to "), (r"—", ", "),
           (r" · ", ", "), (r"&", " and "), (r"\bTbps\b", "terabits per second"), (r"(?<=\d)\s?kg\b", " kilograms"),
           (r"\bLEO\b", "low Earth orbit"), (r"\bNET\b", "no earlier than"), (r"\ba\.m\.", "A.M."),
           (r"\bp\.m\.", "P.M."), (r"\bET\b", "Eastern"), (r"\bSpaceXAI\b", "SpaceX A.I."),
           (r"\bSpaceXSI\b", "SpaceX S.I."), (r"\bxAI\b", "x A.I."), (r"\bIPO\b", "I.P.O."), (r"\bAPI\b", "A.P.I."),
           (r"\bGPT-", "G.P.T. "), (r"\bAI\b", "A.I."), (r"\bSI\b", "S.I."), (r"\bTE\b", "tight end"),
           (r"\bQB\b", "quarterback"), (r"(?<=\d)\s?kW\b", " kilowatts"), (r"\bMRI\b", "M.R.I."), (r"(?<![\d$,.])\b20([1-9]\d)\b(?![,.]\d)", r"20 \1"), (r"\bNDA\b", "N.D.A."), (r"\bQ3\b", "Q 3"), (r"(?<=\d)T\b", " trillion"), (r"\b(\d+)x\b", r"\1 times"), (r"\bOct\.?(?= \d)", "October"), (r"\bSept?\.?(?= \d)", "September"), (r"\bV3\b", "V 3"), (r"\bIAC\b", "I.A.C."), (r"\bTSMC\b", "T.S.M.C."),
           (r"\bPSC\b", "P.S.C."), (r"\bFAA\b", "F.A.A."), (r"\bLZ-4\b", "Landing Zone 4")]
    for k, v in rep:
        s = re.sub(k, v, s)
    return " ".join(s.split())


def synth(text, voice="en_US-ryan-high", length_scale=1.0):
    """Return path to a 44.1k mono wav for this text (cached)."""
    os.makedirs(TTS_DIR, exist_ok=True)
    spoken = speakable(text)
    key = hashlib.sha1(f"{voice}|{length_scale}|{spoken}".encode()).hexdigest()[:16]
    out = os.path.join(TTS_DIR, f"{key}.wav")
    if os.path.exists(out):
        return out
    raw = out + ".raw.wav"
    env = dict(os.environ, PYTHONPATH=VENDOR_TTS)
    subprocess.run([sys.executable, "-m", "piper", "-m", voice_path(voice), "-f", raw,
                    "--length-scale", str(length_scale), "--sentence-silence", "0.25"],
                   input=spoken.encode(), env=env, check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ar", str(SR), "-ac", "1",
                    "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80,loudnorm=I=-17:TP=-2",
                    out], check=True)
    os.remove(raw)
    return out


def read_wav(path):
    with wave.open(path) as w:
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
        return data


def wav_len(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def write_wav(path, data):
    d = np.clip(data, -1, 1)
    if d.ndim == 1:
        d = np.stack([d, d], axis=1)
    pcm = (d * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def music_bed(duration, seed=3, mood="space"):
    """Soft ambient pad + gentle plucks, generated with numpy. Returns stereo float array."""
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2), dtype=np.float32)
    progs = {
        "space": [[48, 55, 59, 64], [45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 59]],   # Cmaj7 Am Fmaj7 G
        "agents": [[50, 57, 60, 65], [46, 53, 58, 62], [43, 50, 55, 58], [45, 52, 57, 61]],
        "ravens": [[45, 52, 57, 60], [41, 48, 53, 57], [48, 55, 60, 64], [43, 50, 55, 59]],
        "markets": [[47, 54, 59, 62], [43, 50, 55, 59], [45, 52, 57, 60], [42, 49, 54, 57]],
    }
    chords = progs.get(mood, progs["space"])
    bar = 4.0
    nb = int(np.ceil(duration / bar)) + 1
    for b in range(nb):
        ch = chords[b % len(chords)]
        s0 = b * bar - 1.0
        s1 = s0 + bar + 2.0
        i0, i1 = max(0, int(s0 * SR)), min(n, int(s1 * SR))
        if i1 <= i0:
            continue
        tt = t[i0:i1] - s0
        L = s1 - s0
        env = np.clip(tt / 1.5, 0, 1) * np.clip((L - tt) / 1.8, 0, 1)
        env = env ** 1.5
        for k, note in enumerate(ch):
            f = midi(note + 12)
            for det, pan in ((0.997, 0.3), (1.003, 0.7)):
                ph = rng.uniform(0, 6.28)
                w = np.sin(2 * np.pi * f * det * tt + ph) + 0.18 * np.sin(4 * np.pi * f * det * tt + ph)
                amp = 0.05 * env * (1.0 if k else 0.8)
                out[i0:i1, 0] += (w * amp * (1 - pan)).astype(np.float32)
                out[i0:i1, 1] += (w * amp * pan).astype(np.float32)
        # sub bass
        fb = midi(ch[0] - 12 + 12)
        out[i0:i1, :] += (0.06 * env * np.sin(2 * np.pi * fb * tt))[:, None].astype(np.float32)
        # plucks (arpeggio, eighth notes, sparse)
        for step in range(8):
            if rng.random() < 0.45:
                continue
            ts = b * bar + step * bar / 8
            j0 = int(ts * SR)
            if j0 >= n or j0 < 0:
                continue
            j1 = min(n, j0 + int(1.6 * SR))
            tp = t[j0:j1] - ts
            note = ch[rng.integers(1, len(ch))] + 24
            pl = np.sin(2 * np.pi * midi(note) * tp) * np.exp(-tp * 3.2) * 0.035
            pan = rng.uniform(0.2, 0.8)
            out[j0:j1, 0] += (pl * (1 - pan)).astype(np.float32)
            out[j0:j1, 1] += (pl * pan).astype(np.float32)
    # gentle slow tremolo + fades
    out *= (0.9 + 0.1 * np.sin(2 * np.pi * 0.12 * t))[:, None]
    fade_in = np.clip(t / 2.0, 0, 1)
    fade_out = np.clip((duration - t) / 3.0, 0, 1)
    out *= (fade_in * fade_out)[:, None]
    # crude one-pole lowpass via cumulative smoothing (vectorised moving average)
    k = 9
    ker = np.ones(k) / k
    for c in range(2):
        out[:, c] = np.convolve(out[:, c], ker, mode="same")
    peak = np.abs(out).max() or 1
    return out / peak * 0.5


def moving_average_same(x, k):
    """Same result as np.convolve(x, np.ones(k)/k, mode="same") but O(n) via cumsum.
    (Direct convolution with a 0.4 s kernel is ~50 GFLOP per minute of audio and stalled renders under load.)"""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    c = np.concatenate(([0.0], np.cumsum(x)))
    off = (k - 1) // 2
    j = np.arange(n) + off            # index into the 'full' convolution
    hi = np.minimum(j + 1, n)
    lo = np.clip(j - k + 1, 0, n)
    return ((c[hi] - c[lo]) / k).astype(np.float32)


def mix(duration, voice_clips, music=True, mood="space", music_db=None):
    """voice_clips: list of (start_seconds, wav_path). Returns stereo array."""
    n = int(duration * SR) + 1
    voice = np.zeros(n, dtype=np.float32)
    active = np.zeros(n, dtype=np.float32)
    for st, p in voice_clips:
        d = read_wav(p)
        i0 = int(st * SR)
        i1 = min(n, i0 + len(d))
        voice[i0:i1] += d[: i1 - i0]
        active[i0:i1] = 1
    out = np.zeros((n, 2), dtype=np.float32)
    if music:
        m = music_bed(duration, mood=mood)[:n]
        if voice_clips:
            # duck music under narration (smoothed)
            k = int(0.4 * SR)
            sm = moving_average_same(active, k)
            gain = 10 ** ((music_db if music_db is not None else -21) / 20) * (1 - 0.45 * sm)
        else:
            gain = np.full(n, 10 ** ((music_db if music_db is not None else -14) / 20), dtype=np.float32)
        out[: len(m)] += m * gain[: len(m), None]
    out += voice[:, None] * 0.92
    return out
