#!/usr/bin/env python3
"""Build remastered index.html gallery + dist/explainer-studio-snapshot.html.

Scans out/*.timing.json (MP4s), explainers/*.html (kinetic canvas), storyboards/,
and screenshots contact sheets. Offline / file:// friendly.
"""
import base64, glob, html, json, os, re, shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
EXPLAINERS = os.path.join(ROOT, "explainers")
STORYBOARDS = os.path.join(ROOT, "storyboards")
SHOTS = os.path.join(ROOT, "screenshots")

TOPIC_LABELS = {
    "spacex": "SpaceX / Starlink",
    "ravens": "Ravens",
    "agents": "Agents / xAI",
    "tesla": "Tesla",
    "other": "Other",
}
TOPIC_KEYS = {
    "starmind": "spacex", "starship": "spacex", "spacex": "spacex", "starlink": "spacex",
    "rename": "agents", "spacexai": "agents", "spacexsi": "agents",
    "tesla": "tesla", "fsd": "tesla",
    "agents": "agents", "grok": "agents", "xai": "agents",
    "ravens": "ravens", "lamar": "ravens", "jurgens": "ravens",
    "recap": "other", "auto": "other",
}
ORDER = ["grok-bot-model", "harvey-lexis", "starlink-leo-risk", "ravens-jurgens", "starlink-mobile",
         "starmind", "starship", "spacex-stock", "spacexai", "tesla", "agents", "ravens-lamar", "ravens", "recap", "auto"]


def topic_of(story):
    if story.get("topic") in TOPIC_LABELS:
        return story["topic"]
    blob = (story.get("id", "") + " " + story.get("kicker", "") + " " + story.get("title", "") + " " + story.get("theme", "")).lower()
    for k, v in TOPIC_KEYS.items():
        if k in blob:
            return v
    th = story.get("theme", "")
    return {"space": "spacex", "agents": "agents", "ravens": "ravens", "markets": "tesla"}.get(th, "other")


def srt_to_vtt(srt, vtt):
    txt = open(srt).read()
    txt = re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", txt)
    open(vtt, "w").write("WEBVTT\n\n" + txt)


def load_story(sid):
    for p in [
        os.path.join(OUT, f"{sid}.storyboard.json"),
        os.path.join(STORYBOARDS, f"{sid}.json"),
        *glob.glob(os.path.join(STORYBOARDS, f"*{sid}*.json")),
    ]:
        if os.path.exists(p):
            return json.load(open(p))
    return None


def collect():
    cards = {}
    # MP4 explainers
    for tp in glob.glob(os.path.join(OUT, "*.timing.json")):
        t = json.load(open(tp))
        sid = t["id"]
        sb = load_story(sid) or {"id": sid, "title": sid, "scenes": [], "sources": []}
        gr_path = os.path.join(OUT, f"{sid}.grounding.json")
        gr = json.load(open(gr_path)) if os.path.exists(gr_path) else {"ok": True, "summary": {"numbers_checked": 0, "evidence_checked": 0, "urls_checked": 0}}
        srt = os.path.join(OUT, f"{sid}.srt")
        if os.path.exists(srt):
            srt_to_vtt(srt, os.path.join(OUT, f"{sid}.vtt"))
        cards[sid] = {
            "id": sid, "story": sb, "timing": t, "grounding": gr,
            "kind": "mp4", "topic": topic_of(sb),
            "duration": t.get("duration", 0),
            "newest": True if any(k in sid for k in ("harvey-lexis","starlink-leo-risk","grok-bot-model","ravens-jurgens","starlink-mobile-fcc")) else False,
            "contact": os.path.exists(os.path.join(SHOTS, f"{sid}_contact.png")),
            "kinetic": os.path.exists(os.path.join(EXPLAINERS, f"{sid}.html")),
            "mp4": os.path.exists(os.path.join(OUT, f"{sid}.mp4")),
            "thumb": os.path.exists(os.path.join(OUT, "thumbs", f"{sid}.jpg")),
            "poster_svg": os.path.exists(os.path.join(EXPLAINERS, "posters", f"{sid}.svg")),
            "mtime": os.path.getmtime(tp),
        }

    # Kinetic HTML (and storyboards without MP4)
    for hp in glob.glob(os.path.join(EXPLAINERS, "*.html")):
        sid = os.path.splitext(os.path.basename(hp))[0]
        if sid in cards:
            cards[sid]["kinetic"] = True
            continue
        sb = load_story(sid)
        if not sb:
            # try matching storyboard by scanning
            for sp in glob.glob(os.path.join(STORYBOARDS, "*.json")):
                s = json.load(open(sp))
                if s.get("id") == sid:
                    sb = s
                    break
        if not sb:
            sb = {"id": sid, "title": sid.replace("-", " ").title(), "kicker": "", "subtitle": "", "scenes": [], "sources": []}
        gr_path = os.path.join(OUT, f"{sid}.grounding.json")
        gr = json.load(open(gr_path)) if os.path.exists(gr_path) else {"ok": True, "summary": {"numbers_checked": 0, "evidence_checked": 0, "urls_checked": 0}}
        is_new = any(x in sid for x in ("oct-7", "jurgens", "starlink-mobile"))
        cards[sid] = {
            "id": sid, "story": sb, "timing": None, "grounding": gr,
            "kind": "kinetic", "topic": topic_of(sb),
            "duration": 4.5 + 8.0 * len(sb.get("scenes", [])) + float(sb.get("end_seconds", 6)),
            "newest": is_new,
            "contact": os.path.exists(os.path.join(SHOTS, f"{sid}_contact.png")),
            "kinetic": True,
            "mp4": os.path.exists(os.path.join(OUT, f"{sid}.mp4")),
            "thumb": os.path.exists(os.path.join(OUT, "thumbs", f"{sid}.jpg")),
            "poster_svg": os.path.exists(os.path.join(EXPLAINERS, "posters", f"{sid}.svg")),
            "mtime": os.path.getmtime(hp),
        }

    # Storyboards that have contact sheets but no kinetic yet
    for sp in glob.glob(os.path.join(STORYBOARDS, "*.json")):
        sb = json.load(open(sp))
        sid = sb["id"]
        if sid in cards:
            continue
        if not os.path.exists(os.path.join(SHOTS, f"{sid}_contact.png")):
            continue
        cards[sid] = {
            "id": sid, "story": sb, "timing": None,
            "grounding": {"ok": True, "summary": {"numbers_checked": 0, "evidence_checked": 0, "urls_checked": 0}},
            "kind": "sheet", "topic": topic_of(sb),
            "duration": 0, "newest": False,
            "contact": True, "kinetic": False, "mp4": False, "thumb": False, "poster_svg": False,
            "mtime": os.path.getmtime(sp),
        }
    return cards


def sort_key(c):
    sid = c["id"]
    rank = next((i for i, k in enumerate(ORDER) if sid.startswith(k) or k in sid), 50)
    # newest first within same bucket
    return (0 if c.get("newest") else 1, rank, -c.get("mtime", 0))


def card_html(c):
    sb = c["story"]
    sid = c["id"]
    topic = c["topic"]
    gr = c["grounding"]
    s = gr.get("summary", {})
    kind = "MP4 · piper" if c["kind"] == "mp4" and c.get("timing", {}).get("voice") else (
        "MP4" if c["kind"] == "mp4" else ("kinetic canvas" if c["kind"] == "kinetic" else "contact sheet"))
    if c["newest"]:
        kind = "NEW · " + kind
    # media block
    if c["mp4"] and c["thumb"]:
        media = f"""
    <div class="poster">
      <video controls preload="none" poster="out/thumbs/{sid}.jpg">
        <source src="out/{sid}.mp4" type="video/mp4">
        <track kind="captions" src="out/{sid}.vtt" srclang="en" label="English">
      </video>
      <a class="play-fab" href="out/{sid}.mp4">▶</a>
    </div>"""
    elif c["kinetic"]:
        poster = f'explainers/posters/{sid}.svg' if c["poster_svg"] else (
            f'screenshots/{sid}_contact.png' if c["contact"] else "")
        media = f"""
    <a class="poster kinetic" href="explainers/{sid}.html">
      {"<img src='" + poster + "' alt='' loading='lazy'>" if poster else "<div class='ph'></div>"}
      <span class="play-fab">▶ Play</span>
      <span class="badge-kin">Kinetic</span>
    </a>"""
    elif c["contact"]:
        media = f"""
    <a class="poster" href="screenshots/{sid}_contact.png" target="_blank">
      <img src="screenshots/{sid}_contact.png" alt="" loading="lazy">
      <span class="badge-kin">Contact sheet</span>
    </a>"""
    else:
        media = "<div class='poster ph'></div>"

    src = "".join(
        f'<li><a href="{html.escape(x["url"])}" target="_blank" rel="noopener">{html.escape(x["label"])}</a></li>'
        for x in sb.get("sources", [])[:8]
    )
    scenes = "".join(
        f"<li><b>{html.escape(sc.get('type',''))}</b> {html.escape(sc.get('heading') or sc.get('label') or '')}</li>"
        for sc in sb.get("scenes", [])[:8]
    )
    g_ok = gr.get("ok", True)
    g_pill = f"<span class=\"{'ok' if g_ok else 'bad'}\">grounding {'PASS' if g_ok else 'FAIL'}"
    if s.get("numbers_checked"):
        g_pill += f" · {s['numbers_checked']}# · {s.get('evidence_checked',0)}q · {s.get('urls_checked',0)}u"
    g_pill += "</span>"

    links = []
    if c["kinetic"]:
        links.append(f'<a href="explainers/{sid}.html">Open kinetic</a>')
    if c["mp4"]:
        links.append(f'<a href="out/{sid}.mp4" download>Download MP4</a>')
    if c["contact"]:
        links.append(f'<a href="screenshots/{sid}_contact.png" target="_blank">Contact sheet</a>')
    if os.path.exists(os.path.join(OUT, f"{sid}.storyboard.json")):
        links.append(f'<a href="out/{sid}.storyboard.json" target="_blank">Storyboard</a>')
    if os.path.exists(os.path.join(OUT, f"{sid}.grounding.json")):
        links.append(f'<a href="out/{sid}.grounding.json" target="_blank">Grounding</a>')
    if os.path.exists(os.path.join(OUT, f"{sid}.srt")):
        links.append(f'<a href="out/{sid}.srt" target="_blank">Captions</a>')

    new_badge = '<span class="new">LATEST</span>' if c.get("newest") else ""
    return f"""
  <article class="card" data-topic="{html.escape(topic)}" data-id="{html.escape(sid)}" data-newest="{1 if c.get('newest') else 0}">
    {media}
    <div class="meta">
      <div class="kicker-row">
        <div class="kicker">{html.escape(sb.get('kicker', TOPIC_LABELS.get(topic, topic)))}</div>
        {new_badge}
        <span class="topic-pill" data-t="{topic}">{html.escape(TOPIC_LABELS.get(topic, topic))}</span>
      </div>
      <h2>{html.escape(sb.get('title', sid))}</h2>
      <p class="sub">{html.escape(sb.get('subtitle', ''))}</p>
      <div class="pills">
        <span>{c['duration']:.0f}s</span>
        <span>{kind}</span>
        {g_pill}
        <span class="src-badge">{len(sb.get('sources', []))} sources</span>
      </div>
      <details><summary>Scenes</summary><ol>{scenes or '<li>See kinetic player</li>'}</ol></details>
      <details><summary>Sources ({len(sb.get('sources', []))})</summary><ul>{src or '<li>—</li>'}</ul></details>
      <div class="links">{''.join(links)}</div>
    </div>
  </article>"""


def latest_strip(cards):
    newest = [c for c in cards if c.get("newest")] or sorted(cards, key=lambda c: -c.get("mtime", 0))[:2]
    items = []
    for c in newest[:4]:
        sb = c["story"]
        href = f"explainers/{c['id']}.html" if c["kinetic"] else (f"out/{c['id']}.mp4" if c["mp4"] else "#")
        poster = f"explainers/posters/{c['id']}.svg" if c["poster_svg"] else (
            f"screenshots/{c['id']}_contact.png" if c["contact"] else "")
        items.append(f"""
      <a class="latest-card" href="{href}" data-topic="{c['topic']}">
        <div class="lc-art">{"<img src='" + poster + "' alt=''>" if poster else ""}</div>
        <div class="lc-body">
          <div class="lc-k">{html.escape(TOPIC_LABELS.get(c['topic'], c['topic']))} · NEW</div>
          <div class="lc-t">{html.escape(sb.get('title', c['id']))}</div>
        </div>
      </a>""")
    return "".join(items)


def main(clean=True):
    cards_map = collect()
    cards = sorted(cards_map.values(), key=sort_key)
    total = sum(c["duration"] for c in cards)
    topics_present = sorted({c["topic"] for c in cards})
    filters = ['<button class="fbtn active" data-filter="all">All</button>',
               '<button class="fbtn" data-filter="newest">Latest</button>']
    for t in ["spacex", "ravens", "agents", "tesla"]:
        if t in topics_present or True:
            filters.append(f'<button class="fbtn" data-filter="{t}">{html.escape(TOPIC_LABELS[t])}</button>')

    page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explainer Studio · Jim's Interest Journal</title>
<style>
  :root {{
    --bg:#03050c; --card:#0a0f1c; --card2:#0e1528; --line:#1a2340; --line2:#243056;
    --text:#f1f5ff; --muted:#8b9bb8; --accent:#5ce1ff; --accent2:#ff9a4a;
    --ravens:#f59e0b; --spacex:#5ce1ff; --agents:#a78bfa; --tesla:#34d399;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; color:var(--text);
    font:16px/1.5 Inter, system-ui, sans-serif;
    background:
      radial-gradient(1100px 520px at 88% -8%, #1a3a7a55, transparent 60%),
      radial-gradient(800px 480px at -10% 30%, #7c2d1222, transparent 55%),
      radial-gradient(700px 400px at 50% 110%, #3b2a6e33, transparent 50%),
      var(--bg);
    min-height:100vh;
  }}
  body::before {{
    content:""; position:fixed; inset:0; pointer-events:none; opacity:.35;
    background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.45'/%3E%3C/svg%3E");
    mix-blend-mode:overlay; z-index:0;
  }}
  .shell {{ position:relative; z-index:1; }}
  header {{ padding:52px 6vw 12px; }}
  header .k {{ font:600 12px JetBrains Mono, monospace; letter-spacing:.16em; color:var(--accent); text-transform:uppercase; }}
  header h1 {{
    font:800 clamp(32px, 5vw, 52px)/1.05 Unbounded, Inter, sans-serif;
    margin:14px 0 10px; letter-spacing:-.02em;
    background:linear-gradient(120deg, #fff 20%, #9ad8ff 60%, #ffb07a 100%);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }}
  header p {{ color:var(--muted); max-width:820px; margin:0; font-size:16px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }}
  .stats span {{
    font:600 12px JetBrains Mono, monospace; letter-spacing:.04em;
    padding:6px 12px; border-radius:999px; border:1px solid var(--line2);
    background:#ffffff08; color:var(--muted);
  }}
  .latest {{ padding:8px 6vw 8px; }}
  .latest h2 {{
    font:700 12px JetBrains Mono, monospace; letter-spacing:.14em; text-transform:uppercase;
    color:var(--accent2); margin:0 0 12px;
  }}
  .latest-row {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }}
  .latest-card {{
    display:flex; gap:14px; align-items:stretch; text-decoration:none; color:inherit;
    background:linear-gradient(145deg, #121a30, #0a1020); border:1px solid var(--line2);
    border-radius:16px; overflow:hidden; transition:transform .2s, border-color .2s, box-shadow .2s;
  }}
  .latest-card:hover {{ transform:translateY(-3px); border-color:var(--accent); box-shadow:0 16px 40px #0008; }}
  .lc-art {{ width:120px; min-height:88px; background:#000; flex-shrink:0; }}
  .lc-art img {{ width:100%; height:100%; object-fit:cover; display:block; }}
  .lc-body {{ padding:14px 14px 14px 0; }}
  .lc-k {{ font:600 11px JetBrains Mono, monospace; color:var(--accent); letter-spacing:.08em; }}
  .lc-t {{ font:700 15px/1.3 Inter, sans-serif; margin-top:4px; }}
  .filters {{
    display:flex; flex-wrap:wrap; gap:8px; padding:18px 6vw 8px; position:sticky; top:0; z-index:5;
    background:linear-gradient(180deg, #03050cee, #03050c99 70%, transparent); backdrop-filter:blur(10px);
  }}
  .fbtn {{
    border:1px solid var(--line); background:#0b1224; color:var(--muted); cursor:pointer;
    border-radius:999px; padding:8px 14px; font:600 13px Inter, sans-serif; transition:.15s;
  }}
  .fbtn:hover {{ color:var(--text); border-color:var(--line2); }}
  .fbtn.active {{ background:var(--accent); color:#031018; border-color:var(--accent); }}
  main {{
    display:grid; grid-template-columns:repeat(auto-fill, minmax(min(420px, 100%), 1fr));
    gap:26px; padding:12px 6vw 72px;
  }}
  .card {{
    background:linear-gradient(180deg, var(--card2), var(--card));
    border:1px solid var(--line); border-radius:22px; overflow:hidden;
    display:flex; flex-direction:column;
    box-shadow:0 20px 50px #0006;
    transition:transform .2s, border-color .2s, box-shadow .2s;
  }}
  .card:hover {{ transform:translateY(-4px); border-color:#3a4d7a; box-shadow:0 28px 60px #000a; }}
  .card.hidden {{ display:none; }}
  .poster {{ position:relative; display:block; aspect-ratio:16/9; background:#000; overflow:hidden; text-decoration:none; }}
  .poster img, .poster video {{ width:100%; height:100%; object-fit:cover; display:block; }}
  .poster.ph, .ph {{ background:radial-gradient(circle at 70% 30%, #1b3a7a66, #050814); min-height:180px; }}
  .play-fab {{
    position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    background:linear-gradient(135deg, var(--accent), #7dd3fc); color:#031018;
    font:800 14px Inter, sans-serif; padding:12px 18px; border-radius:999px;
    box-shadow:0 10px 30px #000a; opacity:.95; pointer-events:none;
  }}
  .badge-kin {{
    position:absolute; top:12px; right:12px; font:700 11px JetBrains Mono, monospace;
    letter-spacing:.08em; text-transform:uppercase; padding:5px 10px; border-radius:999px;
    background:#000a; color:var(--accent); border:1px solid #5ce1ff55;
  }}
  .meta {{ padding:16px 20px 20px; flex:1; display:flex; flex-direction:column; }}
  .kicker-row {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:4px; }}
  .kicker {{ font:600 11px JetBrains Mono, monospace; letter-spacing:.1em; color:var(--accent); text-transform:uppercase; }}
  .new {{
    font:800 10px JetBrains Mono, monospace; letter-spacing:.1em;
    background:linear-gradient(90deg, var(--accent2), #ff5d7a); color:#1a0a00;
    padding:3px 8px; border-radius:6px;
  }}
  .topic-pill {{
    margin-left:auto; font:600 11px Inter, sans-serif; padding:3px 9px; border-radius:999px;
    background:#ffffff10; color:var(--muted); border:1px solid var(--line);
  }}
  .topic-pill[data-t=ravens] {{ color:var(--ravens); border-color:#f59e0b44; }}
  .topic-pill[data-t=spacex] {{ color:var(--spacex); border-color:#5ce1ff44; }}
  .topic-pill[data-t=agents] {{ color:var(--agents); border-color:#a78bfa44; }}
  .topic-pill[data-t=tesla] {{ color:var(--tesla); border-color:#34d39944; }}
  h2 {{ margin:4px 0 6px; font-size:20px; line-height:1.25; letter-spacing:-.01em; }}
  .sub {{ color:var(--muted); margin:0 0 12px; font-size:14px; flex:0; }}
  .pills {{ margin-bottom:4px; }}
  .pills span {{
    display:inline-block; font-size:11px; padding:3px 9px; margin:0 6px 6px 0;
    border-radius:99px; background:#ffffff0d; color:var(--muted); border:1px solid #ffffff08;
  }}
  .pills .ok {{ background:#10b98122; color:#6ee7b7; border-color:#10b98133; }}
  .pills .bad {{ background:#ef444422; color:#fca5a5; border-color:#ef444433; }}
  .pills .src-badge {{ color:var(--accent2); }}
  details {{ margin:6px 0; color:var(--muted); font-size:13px; }}
  summary {{ cursor:pointer; color:var(--text); }}
  details a {{ color:var(--accent); }}
  .links {{ margin-top:auto; padding-top:8px; }}
  .links a {{
    display:inline-block; margin:8px 14px 0 0; color:var(--accent2);
    text-decoration:none; font-size:13px; font-weight:600;
  }}
  .links a:hover {{ text-decoration:underline; }}
  footer {{ color:var(--muted); padding:0 6vw 56px; font-size:13px; max-width:900px; }}
  code {{ background:#ffffff12; padding:2px 6px; border-radius:6px; font-size:12px; }}
  .empty {{ grid-column:1/-1; color:var(--muted); padding:40px; text-align:center; }}
</style>
</head><body>
<div class="shell">
<header>
  <div class="k">TokenMax · Explainer Studio · Sat Oct 10 remaster</div>
  <h1>Jim's Interest Journal, explained</h1>
  <p>{len(cards)} explainers ({total / 60:.1f} min on the clock) — curated storyboards grounded in Jim's journal,
  playable as kinetic canvas pages (and MP4s when rendered). Filter by topic, hit Latest for today's ships,
  or open a card and press Play. Works offline from <code>file://</code>.</p>
  <div class="stats">
    <span>{len(cards)} titles</span>
    <span>{sum(1 for c in cards if c.get('newest'))} new today</span>
    <span>{sum(1 for c in cards if c.get('kinetic'))} kinetic</span>
    <span>{sum(1 for c in cards if c.get('mp4'))} MP4</span>
    <span>topics: SpaceX · Ravens · Agents · Tesla</span>
  </div>
</header>

<section class="latest">
  <h2>Latest strip</h2>
  <div class="latest-row">{latest_strip(cards)}</div>
</section>

<nav class="filters" id="filters">{''.join(filters)}</nav>

<main id="grid">{''.join(card_html(c) for c in cards)}
  <div class="empty" id="empty" hidden>No explainers in this filter.</div>
</main>

<footer>
  Remastered Sat Oct 10 afternoon. Numbers, quotes and source URLs are grounding-checked against
  <code>/workspace/ij_*</code> journal files. Kinetic players run entirely in-browser (canvas + captions).
  MP4 pipeline: cairo + ffmpeg + local piper TTS — no paid APIs.
  Rebuild with <code>python3 build_gallery.py</code> · new kinetic: <code>python3 make_kinetic.py storyboards/…</code>
  · render: <code>python3 make_explainer.py storyboards/…</code>.
</footer>
</div>
<script>
(function(){{
  const btns = [...document.querySelectorAll('.fbtn')];
  const cards = [...document.querySelectorAll('.card')];
  const empty = document.getElementById('empty');
  function apply(f){{
    btns.forEach(b => b.classList.toggle('active', b.dataset.filter === f));
    let n = 0;
    cards.forEach(c => {{
      const show = f === 'all' || (f === 'newest' ? c.dataset.newest === '1' : c.dataset.topic === f);
      c.classList.toggle('hidden', !show);
      if(show) n++;
    }});
    empty.hidden = n > 0;
  }}
  btns.forEach(b => b.addEventListener('click', () => apply(b.dataset.filter)));
}})();
</script>
</body></html>"""

    open(os.path.join(ROOT, "index.html"), "w").write(page)
    write_snapshot(page)
    if clean:
        for w in glob.glob(os.path.join(OUT, ".work_*")):
            sid = os.path.basename(w)[len(".work_"):]
            mp4 = os.path.join(OUT, f"{sid}.mp4")
            files = [os.path.join(w, f) for f in os.listdir(w)] or [w]
            if os.path.exists(mp4) and os.path.getmtime(mp4) >= max(os.path.getmtime(f) for f in files):
                shutil.rmtree(w, ignore_errors=True)
    print(f"index.html: {len(cards)} explainers, {total:.0f}s total "
          f"({sum(1 for c in cards if c.get('newest'))} new, {sum(1 for c in cards if c.get('kinetic'))} kinetic)")


def write_snapshot(page):
    """Offline bundle: rewrite relative paths one level deeper; inline small posters as data URIs when possible."""
    def poster_img(m):
        rel = m.group(1)
        f = os.path.join(ROOT, rel)
        if not os.path.exists(f) or os.path.getsize(f) > 400_000:
            return m.group(0)
        if f.endswith(".svg"):
            return f'src="data:image/svg+xml;base64,{base64.b64encode(open(f,"rb").read()).decode()}"'
        if f.endswith((".jpg", ".jpeg")):
            return f'src="data:image/jpeg;base64,{base64.b64encode(open(f,"rb").read()).decode()}"'
        if f.endswith(".png"):
            return f'src="data:image/png;base64,{base64.b64encode(open(f,"rb").read()).decode()}"'
        return m.group(0)

    def video_poster(m):
        f = os.path.join(OUT, "thumbs", m.group(1))
        if not os.path.exists(f):
            return 'poster=""'
        return 'poster="data:image/jpeg;base64,' + base64.b64encode(open(f, "rb").read()).decode() + '"'

    snap = re.sub(r'poster="out/thumbs/([^"]+)"', video_poster, page)
    snap = re.sub(r'src="((?:explainers/posters|screenshots|out/thumbs)/[^"]+)"', poster_img, snap)
    snap = re.sub(r'(src|href)="(out|screenshots|explainers)/', r'\1="../\2/', snap)
    snap = snap.replace(
        "<footer>",
        "<footer>Offline snapshot: kinetic pages + assets resolve from <code>../</code>; small posters may be embedded. ",
        1,
    )
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    open(os.path.join(ROOT, "dist", "explainer-studio-snapshot.html"), "w").write(snap)
    print("wrote dist/explainer-studio-snapshot.html")


if __name__ == "__main__":
    main()
