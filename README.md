# Explainer Studio

Turns Jim's **Interest Journal** entries (`/workspace/ij_*_research.md`, `ij_*_x.md`, `ij_*_content.md`,
`ij_*_bookmarks.md`) into short animated explainer videos: 1080p30 H.264 MP4, 45–75 s, with a title card,
4–6 animated scenes (kinetic type, vector diagrams, charts), burned-in captions, a local TTS voiceover,
a soft generated music bed, and a sources end card.

Built by TokenMax (idea #6 in `../SHORTLIST.md`). Everything runs locally on the box: no paid APIs and no network calls at render time.

## Quick start

```bash
cd /workspace/tokenmax/explainer-studio

# 1) Render a curated storyboard
python3 make_explainer.py storyboards/starmind.json

# 2) Auto-explainer from a topic (searches all journal entries, newest first)
python3 make_explainer.py "starlink maneuvers"

# 3) Auto-explainer from one journal file (best item, or steer with --topic / --pick N)
python3 make_explainer.py /workspace/ij_2026-10-06_research.md --topic "crew-12"

# 4) One-minute daily recap of a journal file (top story from each section)
python3 make_explainer.py /workspace/ij_2026-10-06_research.md --recap

# Useful flags
python3 make_explainer.py "starship" --list          # show matching journal items, render nothing
python3 make_explainer.py <input> --storyboard-only  # write storyboard + grounding report only
python3 make_explainer.py <input> --no-voice         # captions + music only
python3 make_explainer.py <input> --scale 0.5        # quick 960x540 preview

python3 build_gallery.py                             # rebuild index.html from everything in out/
```

Open `index.html` in a browser to watch everything (works offline from `file://`). `build_gallery.py` also writes
`dist/explainer-studio-snapshot.html`, an offline copy with the posters embedded that plays videos from `../out/`. Contact sheets (3×3 frame grids) are in `screenshots/`.

## Pipeline

```
journal .md / topic ──► storyboard JSON ──► grounding check ──► narration (piper, cached) ──► timeline
                         out/<id>.storyboard.json   out/<id>.grounding.json        │
                                                                                   ▼
            frames (cairo, 1920x1080, parallel per scene) ──► ffmpeg x264 segments ──► concat
            + music bed (numpy) ducked under voice ──► AAC ──► out/<id>.mp4 + .srt + .timing.json
            ──► screenshots/<id>_contact.png + out/thumbs/<id>.jpg
```

* **Storyboards.** Curated storyboards live in `storyboards/*.json`. Auto storyboards come from `studio/storyboard.py`.
  It parses the journal bullets (bold headline, body, markdown links) and splits the body into sentences. Each
  scene gets a type: stat cards for sentences with numbers, a quote card for quoted speech, kinetic text for
  everything else. Every caption is a verbatim journal sentence. If a story has fewer than 4 scenes, it's
  topped up with related journal items.
* **Grounding check** (`studio/storyboard.validate`). Runs before every render and blocks it on failure (`--force` overrides). It checks that:
  * every digit-bearing number in any title, heading, caption, narration or chart value appears in the cited
    journal files ("1 million" and "11k" are understood);
  * every scene's `evidence` snippets appear verbatim in those files (whitespace- and markdown-normalised);
  * every end-card URL appears in those files.
* **Rendering** (`studio/gfx.py`, `studio/scenes.py`, `studio/render.py`). Uses cairo (via the vendored
  `cairocffi`) with the box's Google fonts: Unbounded for titles, Inter Tight for headings, Inter for body text and
  JetBrains Mono for labels. Scene types: `title`, `kinetic`, `bignumber`, `cards`, `bars`, `line`, `timeline`,
  `quote`, `dots` (to-scale dot grid), `cluster` (satellite cluster with animated links), `flow`, `trajectory`
  (launch arc over a planet limb), and `end` (sources). Each topic gets a consistent brand: dark gradient, drifting
  glow, starfield, grid, header, progress bar, scene dots and caption band. There are 4 colour themes (space,
  agents, ravens, markets).
* **Audio** (`studio/audio.py`). Narration uses piper TTS (`en_US-ryan-high`, local ONNX model in
  `assets/voices/`). Text is normalised before speaking (e.g. "Tbps" → "terabits per second", "NET Oct 19" →
  "no earlier than October 19"), and clips are cached in `tts/`. Scene length follows the narration. The music bed
  is synthesised (soft chord pad, sub and sparse plucks) and ducked under the voice.

## Layout

```
make_explainer.py      CLI
build_gallery.py       index.html builder
index.html             gallery (videos, thumbnails, scenes, sources, grounding status, links)
storyboards/           curated storyboards (hand-written, grounded in journal text)
studio/                engine (gfx, scenes, render, audio, storyboard)
out/                   <id>.mp4, .srt/.vtt, .storyboard.json, .grounding.json, .timing.json, thumbs/
screenshots/           <id>_contact.png 3x3 contact sheets
assets/voices/         piper voices (ryan-high used; lessac-high also downloaded)
vendor/, vendor_tts/   pip --target installs (cairocffi; piper-tts + onnxruntime). No system changes.
tts/                   narration cache
```

## Adding a curated explainer

Copy a file in `storyboards/` and edit it. Each scene needs `type`, `caption` (spoken and captioned),
`evidence` (exact journal snippets) and `data` for the scene type. You can add `narration` to override what's
spoken, for example "6 and 11" for a "6-11" record. Wrap words in `*asterisks*` to highlight them. Run with
`--storyboard-only` first to see the grounding report.

## Known gaps

* **Voice quality.** I checked narration with an offline speech recogniser (vosk small), not by ear. It scored
  ~80% word match: common words come through clearly, but some proper nouns are shaky ("Starmind", "Nicolls").
  If it grates, use `--no-voice`.
* **The grounding check is mechanical.** It proves numbers, quotes and URLs come from the journal. It can't judge
  whether a paraphrase keeps the meaning, so the curated storyboards were checked by hand. A few on-screen labels
  are interpretive, e.g. "Before / Now" for the Ironclad time-per-attempt bars.
* **Auto storyboards are heuristic** (there's no LLM on the box). They're accurate because they're verbatim, but
  they look plainer than the curated ones, which use bespoke diagrams. Topic search is keyword matching.
* Visuals are vector only: no photos, logos or footage. The music is simple synthesis.
* Facts are as of each journal date (e.g. Flight 15 "NET Oct 19" is unofficial), so the videos don't update themselves.

## Fixes made on Oct 7 (evening finishing pass)

* **Render stall.** The ducking envelope in `audio.mix` used `np.convolve` with a 0.4 s kernel, about 50 GFLOP per
  minute of audio. On a busy box it stalled a render for more than 15 minutes after the video was done. It now uses
  an O(n) cumulative-sum moving average (`moving_average_same`) that gives the same result (max difference ~3e-8),
  and the mix takes about 2 s.
* **Gallery cleanup.** `build_gallery.py` used to delete every `out/.work_*`, including renders still in progress.
  It now removes a scratch dir only when that video's MP4 exists and is newer than the scratch dir.
* **Captions.** Long sentences now split at a comma near the middle, or at a balanced word break. They no longer
  break after "No.", "a.m." or other abbreviations, or inside "Thu Oct 8" or "within 4 hours", and a short lead
  like "Football:" gets merged into the next chunk.
* **Highlight markup.** `*14*).` and `*Tuesday*'s` now render as highlights, where before a stray asterisk was drawn.
* **Recap length.** Each recap scene speaks either the headline or the lead sentence (both only when the pair is
  short), so a 5-story recap runs about 57 s instead of 79 s.
* **Tesla FSD storyboard** added. In the SpaceX stock storyboard, the heading "biggest day since the summer" became
  "Highest close since mid-June" (the journal's words). The unordered midday point was dropped from the line chart.
  The auto Starlink storyboard's card labels were cleaned up by hand; its captions are still verbatim.

## What's new (Sat Oct 10 afternoon remaster)

Deep remaster for TokenMax daily-usage-check — substantial gallery polish + two new Oct 7 explainers.

### Gallery UI
* Darker cinematic look (film-grain overlay, multi-glow background, gradient title).
* Poster grid with playable kinetic cards, sticky topic filters (**All / Latest / SpaceX·Starlink / Ravens / Agents·xAI / Tesla**).
* **Latest strip** at the top for today's ships; topic pills + sources badges on every card.
* Still works offline from `file://`. Snapshot at `dist/explainer-studio-snapshot.html`.

### New explainers (from `ij_2026-10-07_research.md`)
1. **`ravens-jurgens-trade-oct-7`** — Cam Jurgens trade (biggest since Roquan) + Lamar's unconventional ankle sprain + ATL -3 Sunday night. Kinetic canvas + 960×540 preview MP4 (70s, captions, no voice).
2. **`starlink-mobile-fcc-oct-7`** — FCC green-lights 15,000 Starlink Mobile D2D sats, EchoStar/T-Mobile spectrum, 150 Mbps promise, 2032/2035 deadlines. Kinetic canvas + 960×540 preview MP4 (58s).

Both storyboards pass the grounding check (numbers / evidence / URLs). Curated JSON lives in `storyboards/`; kinetic players in `explainers/`; MP4s + thumbs in `out/`.

### Kinetic canvas pipeline
* New `make_kinetic.py` turns any storyboard into an offline HTML canvas player (`explainers/<id>.html`) with play/scrub, scene dots, captions, and source panel. Regenerated for all 9 curated titles so older MP4-less entries still play in-browser.
* `build_gallery.py` now indexes MP4s, kinetic pages, contact sheets, and storyboards together.

### Screenshots / port
* Fresh home shots in `screenshots/00-best-home.png` (+ a couple more). Gallery served on **port 4274**.

```bash
cd /workspace/tokenmax/explainer-studio
python3 make_kinetic.py storyboards/ravens-jurgens-trade.json
python3 make_explainer.py storyboards/ravens-jurgens-trade.json --scale 0.5 --no-voice
python3 build_gallery.py
python3 -m http.server 4274 --bind 127.0.0.1
```

## What's new (Sat Oct 10 ~1:35 PM — batch-2 explainers)

Three more curated explainers from Jim journals (grounding PASS; kinetic + 960×540 preview MP4, captions+music, no voice):

1. **`grok-bot-model-agnostic-oct-7`** — Musk: Grok Bot / SpaceX bots will use best backend (Claude Opus 5.5, MidJourney, Suno); Grok 4.8 path; changelog to v0.68.1.
2. **`harvey-lexis-mtd-oct-7`** — Harvey + LexisNexis Motion to Dismiss agent (plan → approve → Shepardized research → draft); KPD-relevant pattern.
3. **`starlink-leo-risk-oct-6`** — Starlink: undisclosed maneuvers = biggest LEO risk; 11k+ sats, ~650 encounters, 164,000 near-misses; V3 deploy video from Flight 14.

Gallery rebuilt (12 explainers). Port **4274**. Snapshot `dist/explainer-studio-snapshot.html`. Fresh `screenshots/00-best-home.png`.



---
## Repo notes
- **Built:** 2026-10-06, by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** Open `index.html` in a browser.
- Imported from `/workspace/tokenmax/explainer-studio` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.
