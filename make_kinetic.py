#!/usr/bin/env python3
"""Build offline HTML kinetic-canvas explainers from storyboard JSON.

  python3 make_kinetic.py storyboards/foo.json
  python3 make_kinetic.py --all   # every storyboard + out/*.storyboard.json

Writes explainers/<id>.html (file:// friendly) and a small poster SVG in explainers/posters/.
"""
import argparse, html, json, os, re, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "explainers")
POSTER_DIR = os.path.join(OUT_DIR, "posters")

THEMES = {
    "space":   {"bg":"#050814","accent":"#4cc9f0","accent2":"#ff8a3d","card":"#0d1428","glow":"#1b3a7a"},
    "agents":  {"bg":"#060a12","accent":"#a78bfa","accent2":"#34d399","card":"#10182a","glow":"#3b2a6e"},
    "ravens":  {"bg":"#0a0806","accent":"#f59e0b","accent2":"#9f1239","card":"#16100c","glow":"#7c2d12"},
    "markets": {"bg":"#060b0a","accent":"#34d399","accent2":"#fbbf24","card":"#0c1614","glow":"#14532d"},
}

TOPIC_FOR = {
    "starmind": "spacex", "starship": "spacex", "spacex": "spacex", "starlink": "spacex",
    "tesla": "tesla", "fsd": "tesla", "agents": "agents", "ravens": "ravens",
    "lamar": "ravens", "jurgens": "ravens", "recap": "agents", "auto": "spacex",
}


def topic_of(story):
    if story.get("topic"):
        return story["topic"]
    blob = (story.get("id","") + " " + story.get("kicker","") + " " + story.get("title","")).lower()
    for k, v in TOPIC_FOR.items():
        if k in blob:
            return v
    th = story.get("theme", "space")
    return {"space":"spacex","agents":"agents","ravens":"ravens","markets":"tesla"}.get(th, "spacex")


def strip_marks(s):
    return re.sub(r"\*([^*]+)\*", r"\1", s or "")


def scenes_payload(story):
    scenes = []
    # synthetic title scene
    scenes.append({
        "type": "title",
        "label": story.get("kicker", ""),
        "heading": story.get("title", ""),
        "caption": story.get("title_narration") or story.get("subtitle") or story.get("title", ""),
        "data": {"subtitle": story.get("subtitle", "")},
        "duration": 4.5,
    })
    for sc in story.get("scenes", []):
        scenes.append({
            "type": sc.get("type", "kinetic"),
            "label": sc.get("label", ""),
            "heading": strip_marks(sc.get("heading", "")),
            "caption": sc.get("caption", ""),
            "data": sc.get("data", {}),
            "duration": 8.0,
        })
    scenes.append({
        "type": "end",
        "label": "Sources",
        "heading": "Grounded in Jim's Interest Journal",
        "caption": story.get("as_of", ""),
        "data": {"sources": story.get("sources", [])},
        "duration": float(story.get("end_seconds", 6)),
    })
    return scenes


PLAYER_JS = r"""
const S = window.__STORY__;
const T = window.__THEME__;
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1280, H = 720;
canvas.width = W; canvas.height = H;

let playing = false, t0 = 0, elapsed = 0, sceneIdx = 0, raf = 0;
const total = S.scenes.reduce((a,s)=>a+s.duration,0);

function ease(p){ return p<0.5 ? 2*p*p : 1-Math.pow(-2*p+2,2)/2; }
function clamp(x,a,b){ return Math.max(a,Math.min(b,x)); }
function hex(c,a=1){
  if(c.length===7){
    const r=parseInt(c.slice(1,3),16),g=parseInt(c.slice(3,5),16),b=parseInt(c.slice(5,7),16);
    return `rgba(${r},${g},${b},${a})`;
  }
  return c;
}

function stars(seed){
  const pts=[]; let s=seed|0;
  for(let i=0;i<120;i++){ s=(s*1103515245+12345)&0x7fffffff; pts.push({x:(s%W), y:((s>>8)%H), r:0.4+((s>>16)%10)/10}); }
  return pts;
}
const STAR = stars(S.seed||42);

function bg(t){
  const g = ctx.createRadialGradient(W*0.75, -40, 40, W*0.5, H*0.3, W*0.9);
  g.addColorStop(0, hex(T.glow, 0.55));
  g.addColorStop(1, T.bg);
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);
  ctx.fillStyle = hex('#fff', 0.35);
  for(const p of STAR){ ctx.beginPath(); ctx.arc((p.x + t*8)%W, p.y, p.r, 0, 6.28); ctx.fill(); }
  // header bar
  ctx.fillStyle = hex('#fff', 0.04); ctx.fillRect(0,0,W,54);
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, ui-monospace, monospace';
  ctx.fillText((S.kicker||'EXPLAINER').toUpperCase(), 36, 34);
  // progress
  const prog = elapsed / total;
  ctx.fillStyle = hex('#fff', 0.08); ctx.fillRect(0, H-6, W, 6);
  ctx.fillStyle = T.accent; ctx.fillRect(0, H-6, W*prog, 6);
  // scene dots
  const n = S.scenes.length;
  for(let i=0;i<n;i++){
    ctx.beginPath();
    ctx.fillStyle = i===sceneIdx ? T.accent : hex('#fff', 0.25);
    ctx.arc(W - 28 - (n-1-i)*16, 28, i===sceneIdx?4.5:3, 0, 6.28); ctx.fill();
  }
}

function caption(text){
  if(!text) return;
  const band = 110;
  ctx.fillStyle = hex('#000', 0.55); ctx.fillRect(0, H-band-6, W, band);
  ctx.fillStyle = '#eef2ff'; ctx.font = '500 20px Inter, system-ui, sans-serif';
  wrap(text, 48, H-band+36, W-96, 26);
}

function wrap(text, x, y, maxW, lh){
  const words = String(text).split(/\s+/); let line='', yy=y;
  for(const w of words){
    const test = line ? line+' '+w : w;
    if(ctx.measureText(test).width > maxW && line){ ctx.fillText(line, x, yy); line=w; yy+=lh; }
    else line=test;
  }
  if(line) ctx.fillText(line, x, yy);
}

function drawTitle(sc, local){
  const p = ease(clamp(local/1.2,0,1));
  ctx.save(); ctx.globalAlpha = p;
  ctx.fillStyle = T.accent; ctx.font = '600 14px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 140);
  ctx.fillStyle = '#fff'; ctx.font = '800 48px Unbounded, Inter, sans-serif';
  wrap(sc.heading, 64, 210, W-280, 56);
  ctx.fillStyle = hex('#c7d2fe', 0.85); ctx.font = '400 22px Inter, sans-serif';
  wrap((sc.data&&sc.data.subtitle)||'', 64, 360, W-320, 30);
  // ring motif
  const cx=W-220, cy=H/2-20, R=150;
  ctx.strokeStyle = hex(T.accent, 0.35); ctx.lineWidth=2;
  ctx.beginPath(); ctx.arc(cx,cy,R,-Math.PI/2,-Math.PI/2+Math.PI*2*p); ctx.stroke();
  ctx.beginPath(); ctx.arc(cx,cy,R*0.72,-Math.PI/2+1,-Math.PI/2+1+Math.PI*2*p); ctx.stroke();
  ctx.restore();
}

function drawKinetic(sc, local){
  const p = ease(clamp(local/0.9,0,1));
  ctx.save(); ctx.globalAlpha = p;
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 130);
  ctx.fillStyle = '#fff'; ctx.font = '700 36px Inter, sans-serif';
  wrap(sc.heading, 64, 190, W-120, 44);
  const lines = (sc.data&&sc.data.lines)||[];
  ctx.font = '500 26px Inter, sans-serif';
  lines.forEach((ln,i)=>{
    const lp = ease(clamp((local-0.4-i*0.25)/0.6,0,1));
    ctx.globalAlpha = lp;
    ctx.fillStyle = hex('#e2e8f0', 0.95);
    ctx.fillText(String(ln).replace(/\*/g,''), 64, 300 + i*48);
  });
  ctx.restore();
}

function drawCards(sc, local){
  const cards = (sc.data&&sc.data.cards)||[];
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 120);
  ctx.fillStyle = '#fff'; ctx.font = '700 30px Inter, sans-serif';
  wrap(sc.heading, 64, 170, W-120, 38);
  const n = cards.length || 1;
  const gap = 24, cw = (W - 128 - gap*(n-1)) / n;
  cards.forEach((c,i)=>{
    const p = ease(clamp((local-0.2-i*0.15)/0.7,0,1));
    const x = 64 + i*(cw+gap), y = 240;
    ctx.save(); ctx.globalAlpha = p;
    ctx.fillStyle = hex(c.alt ? T.accent2 : T.card, c.alt ? 0.85 : 0.95);
    roundRect(x, y, cw, 220, 18); ctx.fill();
    ctx.fillStyle = c.alt ? '#fff' : T.accent;
    ctx.font = '800 36px Unbounded, Inter, sans-serif';
    wrap(String(c.big||''), x+22, y+70, cw-44, 40);
    ctx.fillStyle = c.alt ? hex('#fff',0.9) : hex('#cbd5e1',0.95);
    ctx.font = '500 16px Inter, sans-serif';
    wrap(String(c.label||''), x+22, y+150, cw-44, 22);
    ctx.restore();
  });
}

function drawBars(sc, local){
  const items = (sc.data&&sc.data.items)||[];
  const max = (sc.data&&sc.data.max) || Math.max(...items.map(i=>i.value),1);
  const suffix = (sc.data&&sc.data.suffix)||'';
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 120);
  ctx.fillStyle = '#fff'; ctx.font = '700 30px Inter, sans-serif';
  wrap(sc.heading, 64, 170, W-120, 38);
  items.forEach((it,i)=>{
    const p = ease(clamp((local-0.25-i*0.2)/0.8,0,1));
    const y = 250 + i*90;
    ctx.fillStyle = hex('#fff',0.7); ctx.font = '500 18px Inter, sans-serif';
    ctx.fillText(it.label, 64, y);
    ctx.fillStyle = hex('#fff',0.08); roundRect(64, y+12, W-200, 28, 8); ctx.fill();
    ctx.fillStyle = it.highlight ? T.accent2 : T.accent;
    roundRect(64, y+12, (W-200)*p*(it.value/max), 28, 8); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.font = '700 18px JetBrains Mono, monospace';
    ctx.fillText(it.value + suffix, W-120, y+34);
  });
}

function drawBig(sc, local){
  const p = ease(clamp(local/1.0,0,1));
  const d = sc.data||{};
  const num = d.display || d.number || (d.value!=null ? String(d.value) : '');
  const unit = d.unit || d.pre || '';
  const sub = d.label || d.sub || sc.heading || '';
  ctx.save(); ctx.globalAlpha = p;
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 130);
  ctx.fillStyle = '#fff'; ctx.font = '800 96px Unbounded, Inter, sans-serif';
  ctx.fillText(String(num), 64, 280);
  ctx.fillStyle = T.accent2; ctx.font = '600 28px Inter, sans-serif';
  ctx.fillText(String(unit), 64, 340);
  ctx.fillStyle = hex('#cbd5e1',0.9); ctx.font = '400 20px Inter, sans-serif';
  wrap(String(sub), 64, 400, W-160, 28);
  ctx.restore();
}

function drawQuote(sc, local){
  const p = ease(clamp(local/0.9,0,1));
  const q = (sc.data&&(sc.data.text||sc.data.quote))||'';
  const attr = (sc.data&&(sc.data.who||sc.data.attr))||'';
  ctx.save(); ctx.globalAlpha = p;
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 130);
  ctx.fillStyle = hex(T.accent, 0.35); ctx.font = '800 120px Georgia, serif';
  ctx.fillText('"', 48, 250);
  ctx.fillStyle = '#fff'; ctx.font = '500 28px Inter, sans-serif';
  wrap(q, 100, 240, W-220, 38);
  ctx.fillStyle = T.accent2; ctx.font = '600 18px Inter, sans-serif';
  ctx.fillText('— ' + attr, 100, 480);
  ctx.restore();
}

function drawTimeline(sc, local){
  const raw = (sc.data&&(sc.data.events||sc.data.items))||[];
  const items = raw.map(it => ({when: it.when||it.date||'', what: it.what||it.label||''}));
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText((sc.label||'').toUpperCase(), 64, 120);
  ctx.fillStyle = '#fff'; ctx.font = '700 30px Inter, sans-serif';
  wrap(sc.heading, 64, 170, W-120, 38);
  const x0=100, x1=W-100, y=360;
  ctx.strokeStyle = hex('#fff',0.2); ctx.lineWidth=3;
  ctx.beginPath(); ctx.moveTo(x0,y); ctx.lineTo(x1,y); ctx.stroke();
  items.forEach((it,i)=>{
    const p = ease(clamp((local-0.2-i*0.2)/0.7,0,1));
    const x = x0 + (x1-x0)*(i/(Math.max(items.length-1,1)));
    ctx.save(); ctx.globalAlpha = p;
    ctx.fillStyle = T.accent; ctx.beginPath(); ctx.arc(x,y,10,0,6.28); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.font = '700 16px JetBrains Mono, monospace';
    ctx.textAlign='center'; ctx.fillText(it.when, x, y-28);
    ctx.fillStyle = hex('#cbd5e1',0.95); ctx.font = '500 15px Inter, sans-serif';
    wrap(it.what, x-110, y+40, 220, 20);
    ctx.textAlign='left';
    ctx.restore();
  });
}

function drawEnd(sc, local){
  const p = ease(clamp(local/0.8,0,1));
  ctx.save(); ctx.globalAlpha = p;
  ctx.fillStyle = T.accent; ctx.font = '600 13px JetBrains Mono, monospace';
  ctx.fillText('SOURCES', 64, 140);
  ctx.fillStyle = '#fff'; ctx.font = '700 34px Inter, sans-serif';
  ctx.fillText(sc.heading||'Sources', 64, 200);
  const srcs = (sc.data&&sc.data.sources)||[];
  ctx.font = '500 18px Inter, sans-serif';
  srcs.slice(0,6).forEach((s,i)=>{
    ctx.fillStyle = T.accent2;
    ctx.fillText('→  ' + (s.label||s.url||''), 64, 270 + i*36);
  });
  ctx.restore();
}

function roundRect(x,y,w,h,r){
  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath();
}

function drawScene(sc, local){
  bg(elapsed);
  const t = sc.type;
  if(t==='title') drawTitle(sc, local);
  else if(t==='cards') drawCards(sc, local);
  else if(t==='bars') drawBars(sc, local);
  else if(t==='bignumber') drawBig(sc, local);
  else if(t==='quote') drawQuote(sc, local);
  else if(t==='timeline') drawTimeline(sc, local);
  else if(t==='end') drawEnd(sc, local);
  else drawKinetic(sc, local);
  if(t!=='end') caption(sc.caption);
}

function sceneAt(e){
  let acc=0;
  for(let i=0;i<S.scenes.length;i++){
    if(e < acc + S.scenes[i].duration) return [i, e-acc];
    acc += S.scenes[i].duration;
  }
  return [S.scenes.length-1, S.scenes[S.scenes.length-1].duration];
}

function frame(now){
  if(playing){
    elapsed = (now - t0) / 1000;
    if(elapsed >= total){ elapsed = total; playing=false; updateUI(); }
  }
  const [idx, local] = sceneAt(elapsed);
  sceneIdx = idx;
  drawScene(S.scenes[idx], local);
  document.getElementById('clock').textContent = fmt(elapsed) + ' / ' + fmt(total);
  document.getElementById('scenelabel').textContent = (S.scenes[idx].label || S.scenes[idx].type || '');
  if(playing) raf = requestAnimationFrame(frame);
}

function fmt(s){ const m=Math.floor(s/60), ss=Math.floor(s%60); return m+':'+String(ss).padStart(2,'0'); }

function updateUI(){
  document.getElementById('play').textContent = playing ? 'Pause' : (elapsed>=total ? 'Replay' : 'Play');
}

document.getElementById('play').onclick = ()=>{
  if(elapsed>=total){ elapsed=0; }
  playing = !playing;
  if(playing){ t0 = performance.now() - elapsed*1000; raf = requestAnimationFrame(frame); }
  else cancelAnimationFrame(raf);
  updateUI();
};
document.getElementById('prev').onclick = ()=>{
  const [idx] = sceneAt(elapsed);
  let acc=0; for(let i=0;i<Math.max(0,idx-1);i++) acc+=S.scenes[i].duration;
  elapsed = acc; t0 = performance.now() - elapsed*1000; frame(performance.now());
};
document.getElementById('next').onclick = ()=>{
  const [idx] = sceneAt(elapsed);
  let acc=0; for(let i=0;i<=Math.min(S.scenes.length-1,idx);i++) acc+=S.scenes[i].duration;
  elapsed = Math.min(acc, total-0.05); t0 = performance.now() - elapsed*1000; frame(performance.now());
};
document.getElementById('scrub').oninput = (e)=>{
  elapsed = (+e.target.value/1000)*total; t0 = performance.now() - elapsed*1000; frame(performance.now());
};
// first paint — nudge into the title beat so posters/screenshots aren't blank
elapsed = 0.85; t0 = performance.now() - elapsed*1000;
document.getElementById('scrub').value = Math.round(1000*elapsed/total);
frame(performance.now());
"""


def build_html(story):
    theme = THEMES.get(story.get("theme", "space"), THEMES["space"])
    scenes = scenes_payload(story)
    payload = {
        "id": story["id"],
        "title": story.get("title", ""),
        "kicker": story.get("kicker", ""),
        "subtitle": story.get("subtitle", ""),
        "seed": story.get("seed", 42),
        "topic": topic_of(story),
        "scenes": scenes,
        "sources": story.get("sources", []),
        "as_of": story.get("as_of", ""),
    }
    src_lis = "".join(
        f'<li><a href="{html.escape(s.get("url",""))}" target="_blank" rel="noopener">{html.escape(s.get("label", s.get("url","")))}</a></li>'
        for s in story.get("sources", [])
    )
    dur = sum(s["duration"] for s in scenes)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(story.get('title',''))} · Explainer Studio</title>
<style>
  :root {{ --bg:{theme['bg']}; --accent:{theme['accent']}; --accent2:{theme['accent2']}; --card:{theme['card']}; --text:#eef2ff; --muted:#93a0bf; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background: radial-gradient(900px 480px at 85% -5%, {theme['glow']}88, transparent), var(--bg); color:var(--text);
         font:16px/1.5 Inter, system-ui, sans-serif; min-height:100vh; }}
  .wrap {{ max-width:1280px; margin:0 auto; padding:28px 20px 64px; }}
  .back {{ color:var(--accent); text-decoration:none; font:600 13px JetBrains Mono, monospace; letter-spacing:.08em; text-transform:uppercase; }}
  h1 {{ font:800 34px/1.15 Unbounded, Inter, sans-serif; margin:12px 0 6px; }}
  .sub {{ color:var(--muted); margin:0 0 18px; max-width:820px; }}
  .stage-wrap {{ background:#000; border:1px solid #1d2745; border-radius:18px; overflow:hidden; box-shadow:0 30px 80px #000a; }}
  canvas {{ width:100%; height:auto; display:block; background:#000; aspect-ratio:16/9; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; padding:14px 16px; background:var(--card); border-top:1px solid #1d2745; }}
  .controls button {{ background:var(--accent); color:#041018; border:0; border-radius:999px; padding:8px 16px; font:700 13px Inter,sans-serif; cursor:pointer; }}
  .controls button.ghost {{ background:#ffffff12; color:var(--text); }}
  .controls input[type=range] {{ flex:1; min-width:140px; }}
  .meta {{ color:var(--muted); font:600 12px JetBrains Mono, monospace; }}
  .panel {{ margin-top:28px; display:grid; grid-template-columns:1.2fr .8fr; gap:24px; }}
  @media (max-width:860px){{ .panel {{ grid-template-columns:1fr; }} }}
  .panel h2 {{ font-size:15px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent); margin:0 0 10px; }}
  .panel ul {{ margin:0; padding-left:18px; color:var(--muted); }}
  .panel a {{ color:var(--accent2); }}
  .pill {{ display:inline-block; padding:3px 10px; border-radius:999px; background:#ffffff12; color:var(--muted); font-size:12px; margin-right:6px; }}
</style>
</head><body>
<div class="wrap">
  <a class="back" href="../index.html">← Explainer Studio</a>
  <h1>{html.escape(story.get('title',''))}</h1>
  <p class="sub">{html.escape(story.get('subtitle',''))}</p>
  <div>
    <span class="pill">{html.escape(topic_of(story))}</span>
    <span class="pill">kinetic canvas · ~{dur:.0f}s</span>
    <span class="pill">offline / file://</span>
  </div>
  <div class="stage-wrap" style="margin-top:16px">
    <canvas id="stage" width="1280" height="720"></canvas>
    <div class="controls">
      <button class="ghost" id="prev">Prev</button>
      <button id="play">Play</button>
      <button class="ghost" id="next">Next</button>
      <input id="scrub" type="range" min="0" max="1000" value="0">
      <span class="meta" id="clock">0:00</span>
      <span class="meta" id="scenelabel"></span>
    </div>
  </div>
  <div class="panel">
    <div>
      <h2>About</h2>
      <p style="color:var(--muted);margin:0">{html.escape(story.get('as_of',''))}</p>
      <p style="color:var(--muted);margin:12px 0 0">Every number and quote is checked against Jim's Interest Journal before ship. This page is a browser-playable kinetic explainer (canvas + captions) — no network APIs.</p>
    </div>
    <div>
      <h2>Sources ({len(story.get('sources',[]))})</h2>
      <ul>{src_lis or '<li>None listed</li>'}</ul>
    </div>
  </div>
</div>
<script>
window.__THEME__ = {json.dumps(theme)};
window.__STORY__ = {json.dumps(payload)};
{PLAYER_JS}
</script>
</body></html>
"""


def write_poster_svg(story, path):
    theme = THEMES.get(story.get("theme", "space"), THEMES["space"])
    title = html.escape(story.get("title", "")[:80])
    kicker = html.escape((story.get("kicker") or topic_of(story)).upper())
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <radialGradient id="g" cx="80%" cy="0%" r="80%">
      <stop offset="0%" stop-color="{theme['glow']}" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="{theme['bg']}"/>
    </radialGradient>
  </defs>
  <rect width="1280" height="720" fill="url(#g)"/>
  <text x="64" y="90" fill="{theme['accent']}" font-family="ui-monospace,monospace" font-size="18" font-weight="700" letter-spacing="3">{kicker}</text>
  <foreignObject x="64" y="140" width="1000" height="280">
    <div xmlns="http://www.w3.org/1999/xhtml" style="color:#fff;font:800 44px/1.15 Inter,system-ui,sans-serif">{title}</div>
  </foreignObject>
  <circle cx="1080" cy="360" r="140" fill="none" stroke="{theme['accent']}" stroke-opacity="0.4" stroke-width="2"/>
  <circle cx="1080" cy="360" r="100" fill="none" stroke="{theme['accent2']}" stroke-opacity="0.35" stroke-width="2"/>
  <text x="64" y="660" fill="#93a0bf" font-family="Inter,system-ui,sans-serif" font-size="20">Explainer Studio · kinetic canvas</text>
</svg>
"""
    open(path, "w").write(svg)


def process(path):
    story = json.load(open(path))
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(POSTER_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"{story['id']}.html")
    open(html_path, "w").write(build_html(story))
    write_poster_svg(story, os.path.join(POSTER_DIR, f"{story['id']}.svg"))
    # also copy storyboard into out/ if missing
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    sb_out = os.path.join(ROOT, "out", f"{story['id']}.storyboard.json")
    if not os.path.exists(sb_out):
        json.dump(story, open(sb_out, "w"), indent=2)
    print(f"[kinetic] {html_path}")
    return html_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    paths = []
    if a.all:
        paths += sorted(glob.glob(os.path.join(ROOT, "storyboards", "*.json")))
        paths += sorted(glob.glob(os.path.join(ROOT, "out", "*.storyboard.json")))
    paths += a.inputs
    seen = set()
    for p in paths:
        sid = json.load(open(p)).get("id")
        if sid in seen:
            continue
        seen.add(sid)
        process(p)


if __name__ == "__main__":
    main()
