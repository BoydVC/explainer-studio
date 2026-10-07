#!/usr/bin/env python3
"""Explainer Studio CLI.

  python3 make_explainer.py <journal.md | topic words | storyboard.json> [options]

Examples
  python3 make_explainer.py storyboards/starmind.json          # render a curated storyboard
  python3 make_explainer.py /workspace/ij_2026-10-06_research.md --topic "starlink maneuvers"
  python3 make_explainer.py "terafab tsmc"                     # search all journal entries by topic
  python3 make_explainer.py "starship" --list                  # show matching journal items, render nothing

Pipeline: journal/topic -> storyboard JSON (out/<id>.storyboard.json) -> grounding check
          (out/<id>.grounding.json) -> frames (cairo) -> narration (local piper TTS, optional) +
          generated music bed -> 1080p30 H.264 MP4 + .srt captions -> contact sheet + thumbnail.
"""
import argparse, json, os, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, ROOT)

from studio import storyboard as sb  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="journal .md file, storyboard .json, or topic words")
    ap.add_argument("--topic", help="when input is a journal file: keywords to pick the item")
    ap.add_argument("--pick", type=int, default=0, help="choose the Nth best-matching item (0 = best)")
    ap.add_argument("--list", action="store_true", help="list matching journal items and exit")
    ap.add_argument("--recap", action="store_true", help="journal file -> one-minute recap of its top stories")
    ap.add_argument("--storyboard-only", action="store_true", help="write storyboard + grounding report, no video")
    ap.add_argument("--no-voice", action="store_true", help="skip piper narration (captions + music only)")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--force", action="store_true", help="render even if the grounding check fails")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--scale", type=float, default=1.0, help="0.5 = 960x540 quick preview")
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    a = ap.parse_args()

    if a.list:
        items, label = sb.pick(a.input, a.topic)
        for i, it in enumerate(items[:15]):
            print(f"[{i}] {os.path.basename(it['file'])} · {it['section'][:30]} · {(it['headline'] or it['body'])[:90]}")
        return

    if a.input.endswith(".json") and os.path.exists(a.input):
        story = json.load(open(a.input))
    elif a.recap:
        story = sb.recap_storyboard(a.input)
    else:
        story = sb.auto_storyboard(a.input, a.topic, a.pick)
    os.makedirs(a.out, exist_ok=True)
    sid = story["id"]
    sb_path = os.path.join(a.out, f"{sid}.storyboard.json")
    json.dump(story, open(sb_path, "w"), indent=2)
    print(f"[storyboard] {sb_path}  ({len(story['scenes'])} scenes) — {story['title']}")

    rep = sb.validate(story)
    json.dump(rep, open(os.path.join(a.out, f"{sid}.grounding.json"), "w"), indent=2)
    s = rep["summary"]
    print(f"[grounding] numbers {s['numbers_checked']}, evidence {s['evidence_checked']}, urls {s['urls_checked']}"
          f" -> {'PASS' if rep['ok'] else 'FAIL'}")
    for f in s["failures"]:
        print(f"   ✗ {f['kind']}: {f['item']!r} at {f['where']}")
    if not rep["ok"] and not a.force:
        sys.exit("Grounding check failed; fix the storyboard or pass --force.")
    if a.storyboard_only:
        return

    from studio import render  # heavy imports only when rendering
    mp4, timeline, total = render.render(story, a.out, voice=not a.no_voice, music=not a.no_music,
                                         workers=a.workers, scale=a.scale)
    shots = os.path.join(ROOT, "screenshots")
    os.makedirs(shots, exist_ok=True)
    os.makedirs(os.path.join(a.out, "thumbs"), exist_ok=True)
    cs = render.contact_sheet(story, timeline, total, mp4, os.path.join(shots, f"{sid}_contact.png"),
                              os.path.join(a.out, "thumbs", f"{sid}.jpg"))
    print(f"[contact] {cs}")
    if not (45 <= total <= 75):
        print(f"[warn] duration {total:.1f}s is outside the 45–75s target")


if __name__ == "__main__":
    main()
