"""Timeline planning, frame rendering (parallel per scene), audio mix, mux, contact sheets."""
import json, math, os, subprocess, sys, time
from multiprocessing import Pool

import cairocffi as cairo

from . import audio
from .gfx import *
from .scenes import DRAW, CX0

FPS = 30
LEAD = 0.55     # narration starts this long after a scene begins
TAIL = 0.75     # breathing room after narration ends


# ------------------------------------------------------------------ planning
def _split_long(s, maxlen):
    """Split one sentence into <= maxlen pieces, preferring a comma near the middle, else balanced word breaks
    (so a caption never ends on a dangling 'and doesn't' with a two-word tail on the next card)."""
    import math, re
    s = s.strip()
    if len(s) <= maxlen:
        return [s] if s else []
    n = math.ceil(len(s) / maxlen)
    target = len(s) / n
    best = None
    for m in re.finditer(r"[,;—]\s+", s):
        cut = m.end()
        if cut <= maxlen and len(s) - cut >= 18 and abs(cut - target) < target * 0.45 and not s[cut:cut + 1].isdigit():
            if best is None or abs(cut - target) < abs(best - target):
                best = cut
    if best is None:
        words, cut, best = s.split(" "), 0, None
        glue = re.compile(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec|No\.|"
                          r"at|of|the|a|an|to|by|in|on|about|than|within|from|and|or|\$?[\d.,]+)$")
        for i, w in enumerate(words[:-1]):
            cut += len(w) + 1
            if cut > maxlen:
                break
            if glue.match(w) or words[i + 1][:1].isdigit():   # keep "Thu Oct 8", "within 4 hours" together
                continue
            if best is None or abs(cut - target) < abs(best - target):
                best = cut
    if not best:
        return [s]
    return [s[:best].strip()] + _split_long(s[best:], maxlen)


def caption_chunks(textv, maxlen=86):
    """Split a caption into readable chunks (<= ~2 lines) on sentence/clause boundaries."""
    import re
    textv = strip_markup(textv)
    sents = []
    for piece in re.split(r"(?<=[.!?;:])\s+", textv.strip()):
        # don't break after abbreviations like "No. 5", "8:49 a.m. EDT", "vs.", "St."
        if sents and re.search(r"(?:\b(?:No|vs|St|Mr|Ms|Dr|Jr|Sr|[ap]\.m|[A-Z])\.)$", sents[-1]):
            sents[-1] += " " + piece
        else:
            sents.append(piece)
    chunks = []
    for s in sents:
        chunks += _split_long(s, maxlen)
    # merge tiny tails
    out = []
    for c in chunks:
        if out and (len(c) < 18 or len(out[-1]) < 18) and len(out[-1]) + len(c) < maxlen + 20:
            out[-1] += " " + c
        else:
            out.append(c)
    return out


def plan(story, voice=True, voice_name="en_US-ryan-high"):
    """Compute per-scene durations, narration clips and caption timings."""
    scenes = [{"type": "title", "caption": story.get("title_narration", ""), "min": 4.5}] + story["scenes"] + \
             [{"type": "end", "caption": "", "min": story.get("end_seconds", 7.0)}]
    use_voice = voice and audio.tts_available(voice_name)
    t = 0.0
    timeline = []
    for i, sc in enumerate(scenes):
        cap = sc.get("caption", "")
        narr = sc.get("narration", cap)
        clip, vlen = None, 0.0
        if use_voice and narr:
            clip = audio.synth(narr, voice_name, story.get("length_scale", 1.0))
            vlen = audio.wav_len(clip)
        if clip:
            d = max(sc.get("min", 6.0), LEAD + vlen + TAIL)
        else:
            words = len(strip_markup(cap).split())
            d = max(sc.get("min", 6.0), 1.0 + words / 2.7)   # comfortable caption reading speed
        d = round(d * FPS) / FPS
        chunks = []
        if cap and sc["type"] not in ("title", "end"):
            cs = caption_chunks(cap)
            tot = sum(len(c) for c in cs)
            a0, a1 = (LEAD, LEAD + vlen) if clip else (0.4, d - 0.5)
            acc = a0
            for c in cs:
                dur = (a1 - a0) * len(c) / tot
                chunks.append((c, acc, acc + dur))
                acc += dur
        timeline.append(dict(scene=sc, start=t, dur=d, clip=clip, vlen=vlen, chunks=chunks, index=i))
        t += d
    return timeline, t, use_voice


# ------------------------------------------------------------------ chrome
def draw_chrome(ctx, story, th, item, t, gt, total, n_scenes):
    sc = item["scene"]
    font(ctx, MONO, 22, True)
    rgba(ctx, th["muted"], 0.9)
    text(ctx, "JIM'S INTEREST JOURNAL  ·  EXPLAINER", CX0, 92)
    rgba(ctx, th["accent"])
    circle(ctx, CX0 - 22, 84, 7)
    ctx.fill()
    if sc["type"] not in ("title",):
        rgba(ctx, th["muted"], 0.9)
        text(ctx, story.get("kicker", "").upper(), 1800, 92, "right")
    # progress bar
    rgba(ctx, th["text"], 0.08)
    ctx.rectangle(0, 0, W, 6)
    ctx.fill()
    rgba(ctx, th["accent"])
    ctx.rectangle(0, 0, W * gt / total, 6)
    ctx.fill()
    # scene dots
    if 0 < item["index"] < n_scenes - 1:
        k = n_scenes - 2
        for j in range(k):
            x = W / 2 - (k - 1) * 14 + j * 28
            rgba(ctx, th["accent"] if j == item["index"] - 1 else th["muted"], 1 if j == item["index"] - 1 else 0.4)
            circle(ctx, x, 86, 6 if j == item["index"] - 1 else 4)
            ctx.fill()


def draw_caption(ctx, th, item, t):
    for c, a, b in item["chunks"]:
        if a - 0.05 <= t < b + 0.05 or (c == item["chunks"][-1][0] and b <= t < item["dur"] - 0.3):
            fa = clamp(prog(t, a - 0.05, 0.15)) * (1 - prog(t, item["dur"] - 0.45, 0.3))
            font(ctx, BODY, 38, False)
            lines = wrap(ctx, c, 1500)[:2]
            lw = max(tw(ctx, ln) for ln in lines)
            bh = 30 + 52 * len(lines)
            by = 1040 - bh
            rgba(ctx, (0, 0, 0), 0.55 * fa)
            rrect(ctx, W / 2 - lw / 2 - 36, by, lw + 72, bh, 18)
            ctx.fill()
            rgba(ctx, th["accent"], 0.9 * fa)
            rrect(ctx, W / 2 - lw / 2 - 36, by, 6, bh, 3)
            ctx.fill()
            rgba(ctx, (1, 1, 1), fa)
            for j, ln in enumerate(lines):
                text(ctx, ln, W / 2, by + 52 + j * 52, "center")
            break


# ------------------------------------------------------------------ frame rendering
_G = {}


def render_frame(ctx, story, th, bg, item, t, total, n):
    gt = item["start"] + t
    bg.draw(ctx, gt)
    d = item["dur"]
    sc = item["scene"]
    ca = clamp(prog(t, 0, 0.35)) * (1 - prog(t, d - 0.35, 0.35))
    ctx.push_group()
    DRAW[sc["type"]](ctx, sc, t, d, th, story)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(ca)
    draw_chrome(ctx, story, th, item, t, gt, total, n)
    draw_caption(ctx, th, item, t)
    # global fade in / out
    fo = max(1 - prog(gt, 0, 0.6), prog(gt, total - 0.8, 0.8))
    if fo > 0:
        ctx.set_source_rgba(0, 0, 0, fo)
        ctx.paint()


def _render_segment(args):
    story, item, total, n, path, scale = args
    th = theme(story.get("theme", "space"))
    bg = Background(th, seed=story.get("seed", 7))
    w, h = int(W * scale), int(H * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    opts = cairo.FontOptions()
    opts.set_antialias(cairo.ANTIALIAS_GRAY)
    opts.set_hint_style(cairo.HINT_STYLE_NONE)
    opts.set_hint_metrics(cairo.HINT_METRICS_OFF)
    ctx.set_font_options(opts)
    nf = int(round(item["dur"] * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{w}x{h}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-r", str(FPS), path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nf):
        ctx.save()
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()
        ctx.restore()
        render_frame(ctx, story, th, bg, item, f / FPS, total, n)
        surf.flush()
        p.stdin.write(bytes(surf.get_data()))
    p.stdin.close()
    p.wait()
    return path


def render_still(story, timeline, total, t_global, path, scale=1.0):
    th = theme(story.get("theme", "space"))
    bg = Background(th, seed=story.get("seed", 7))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W * scale), int(H * scale))
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    item = next(i for i in timeline if i["start"] <= t_global < i["start"] + i["dur"])
    render_frame(ctx, story, th, bg, item, t_global - item["start"], total, len(timeline))
    surf.write_to_png(path)


def fmt_srt(s):
    h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
    return f"{h:02d}:{m:02d}:{int(sec):02d},{int((sec % 1) * 1000):03d}"


def render(story, out_dir, voice=True, music=True, workers=6, scale=1.0, log=print):
    os.makedirs(out_dir, exist_ok=True)
    sid = story["id"]
    t0 = time.time()
    timeline, total, used_voice = plan(story, voice=voice)
    log(f"[plan] {sid}: {len(timeline)} scenes, {total:.1f}s, voice={'piper' if used_voice else 'off'}")
    work = os.path.join(out_dir, f".work_{sid}")
    os.makedirs(work, exist_ok=True)
    jobs = [(story, it, total, len(timeline), os.path.join(work, f"seg_{it['index']:02d}.mp4"), scale)
            for it in timeline]
    with Pool(min(workers, len(jobs))) as pool:
        segs = pool.map(_render_segment, jobs)
    log(f"[video] segments done in {time.time() - t0:.0f}s")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    silent = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    silent], check=True)
    clips = [(it["start"] + LEAD, it["clip"]) for it in timeline if it["clip"]]
    mixed = audio.mix(total, clips, music=music and story.get("music", "pad") != "none",
                      mood=story.get("theme", "space"))
    wav = os.path.join(work, "audio.wav")
    audio.write_wav(wav, mixed)
    mp4 = os.path.join(out_dir, f"{sid}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-movflags", "+faststart", "-shortest", mp4], check=True)
    # captions sidecar
    srt = os.path.join(out_dir, f"{sid}.srt")
    k = 1
    with open(srt, "w") as f:
        for it in timeline:
            for c, a, b in it["chunks"]:
                f.write(f"{k}\n{fmt_srt(it['start'] + a)} --> {fmt_srt(it['start'] + b)}\n{c}\n\n")
                k += 1
    # timing manifest
    man = dict(id=sid, title=story["title"], duration=round(total, 2), voice=used_voice,
               scenes=[dict(type=it["scene"]["type"], start=round(it["start"], 2), dur=round(it["dur"], 2),
                            heading=strip_markup(it["scene"].get("heading", "")),
                            caption=strip_markup(it["scene"].get("caption", ""))) for it in timeline])
    json.dump(man, open(os.path.join(out_dir, f"{sid}.timing.json"), "w"), indent=2)
    log(f"[done] {mp4} ({total:.1f}s) in {time.time() - t0:.0f}s")
    return mp4, timeline, total


def contact_sheet(story, timeline, total, mp4, out_png, thumb_jpg=None):
    """3x3 grid of frames: title, each scene at ~72%, end card (filled to 9 with extra samples)."""
    from PIL import Image, ImageDraw, ImageFont
    times = []
    for it in timeline:
        frac = 0.6 if it["scene"]["type"] == "title" else 0.72
        times.append((it["start"] + it["dur"] * frac, it))
    while len(times) < 9:
        # add extra samples from the longest scenes at 40%
        cands = sorted([it for it in timeline if it["scene"]["type"] not in ("title", "end")],
                       key=lambda i: -i["dur"])
        used = {round(x[0], 2) for x in times}
        for it in cands:
            tt = it["start"] + it["dur"] * 0.42
            if round(tt, 2) not in used:
                times.append((tt, it))
                break
        else:
            break
    times = sorted(times, key=lambda x: x[0])[:9]
    tw_, th_ = 640, 360
    pad, head = 16, 96
    sheet = Image.new("RGB", (3 * tw_ + 4 * pad, head + 3 * (th_ + 44) + pad), (10, 12, 20))
    d = ImageDraw.Draw(sheet)
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf", 34)
        fs = ImageFont.truetype("/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf", 20)
    except Exception:
        fb = fs = ImageFont.load_default()
    d.text((pad, 22), f"{story['title']}  ·  {total:.0f}s", fill=(240, 244, 255), font=fb)
    d.text((pad, 64), f"{os.path.basename(mp4)}  ·  contact sheet (3x3)", fill=(140, 150, 175), font=fs)
    tmp = out_png + ".frame.png"
    for k, (tt, it) in enumerate(times):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{tt:.2f}", "-i", mp4, "-frames:v", "1",
                        "-vf", f"scale={tw_}:{th_}", tmp], check=True)
        im = Image.open(tmp).convert("RGB")
        x = pad + (k % 3) * (tw_ + pad)
        y = head + (k // 3) * (th_ + 44)
        sheet.paste(im, (x, y))
        lab = f"{int(tt // 60)}:{tt % 60:04.1f}  {it['scene']['type']}"
        hd = strip_markup(it["scene"].get("heading", "")) or ("title card" if it["scene"]["type"] == "title" else "")
        d.text((x, y + th_ + 8), (lab + "  " + hd)[:64], fill=(170, 180, 205), font=fs)
    os.remove(tmp)
    sheet.save(out_png)
    if thumb_jpg:
        tt = timeline[0]["dur"] * 0.85
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{tt:.2f}", "-i", mp4, "-frames:v", "1",
                        "-vf", "scale=960:540", "-q:v", "3", thumb_jpg], check=True)
    return out_png
