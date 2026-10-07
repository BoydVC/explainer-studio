"""Storyboards: grounding validator + automatic storyboard builder from Interest Journal markdown.

Grounding rules (enforced before rendering):
  * every digit-bearing number in any on-screen or spoken text must appear in the cited journal file(s);
  * every scene's `evidence` snippets must appear verbatim (whitespace/markup-normalised) in those files;
  * every source URL on the end card must appear in those files.
"""
import glob, json, os, re

JOURNAL_GLOBS = ["/workspace/ij_*_research.md", "/workspace/ij_*_x.md", "/workspace/ij_*_content.md",
                 "/workspace/ij_*_bookmarks.md"]
NON_CLAIM_KEYS = {"per_dot", "cols", "size", "at", "min", "max", "decimals", "invert", "alt", "highlight", "seed",
                  "length_scale", "end_seconds"}
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def journal_files():
    out = []
    for g in JOURNAL_GLOBS:
        out += glob.glob(g)
    return sorted(out, reverse=True)


def norm(s):
    s = s.replace("**", "").replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("*", "")
    return " ".join(s.lower().split())


MULT = {"k": 1e3, "thousand": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "b": 1e9, "trillion": 1e12, "t": 1e12}


def src_nums(s):
    """Numbers in the source, plus scaled forms ("1 million" -> 1000000, "11k" -> 11000)."""
    out = nums_in(s)
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|million|billion|trillion|[MBT])\b", s, re.I):
        v = float(m.group(1).replace(",", "")) * MULT[m.group(2).lower()]
        out.add(str(int(v)) if v.is_integer() else repr(v))
    return out


def nums_in(s):
    out = set()
    for m in NUM_RE.findall(s):
        m = m.rstrip(",.")
        v = m.replace(",", "")
        out.add(v)
        if "." in v:
            out.add(v.rstrip("0").rstrip("."))
    return out


def _collect(obj, key=None, acc=None):
    acc = [] if acc is None else acc
    if key in NON_CLAIM_KEYS:
        return acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("evidence", "sources", "source_files", "id", "theme", "music", "type"):
                continue
            _collect(v, k, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, key, acc)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        acc.append((key, (str(int(obj)) if float(obj).is_integer() else repr(abs(obj))).lstrip("-")))
    elif isinstance(obj, str):
        acc.append((key, obj))
    return acc


def validate(story):
    files = story.get("source_files", [])
    src = "\n".join(open(f).read() for f in files if os.path.exists(f))
    nsrc = norm(src)
    srcnums = src_nums(src.replace("**", ""))
    report = {"id": story.get("id"), "source_files": files, "checks": [], "ok": True}

    def add(kind, item, ok, where):
        report["checks"].append({"kind": kind, "item": item, "ok": ok, "where": where})
        if not ok:
            report["ok"] = False

    if not src:
        add("source", "no readable source files", False, "story")
    # date-like kicker words are fine; check numbers everywhere
    meta = {k: story.get(k, "") for k in ("title", "subtitle", "kicker", "title_narration")}
    for k, v in meta.items():
        for n in nums_in(v):
            add("number", n, n in srcnums, k)
    for i, sc in enumerate(story.get("scenes", [])):
        where = f"scene {i + 1} ({sc.get('type')})"
        for key, val in _collect(sc):
            for n in nums_in(val):
                add("number", n, n in srcnums, f"{where}.{key}")
        ev = sc.get("evidence", [])
        if isinstance(ev, str):
            ev = [ev]
        if not ev:
            add("evidence", "(missing)", False, where)
        for e in ev:
            add("evidence", e[:90], norm(e) in nsrc, where)
    for s in story.get("sources", []):
        add("url", s["url"], s["url"] in src, "end card")
    report["summary"] = {
        "numbers_checked": sum(1 for c in report["checks"] if c["kind"] == "number"),
        "evidence_checked": sum(1 for c in report["checks"] if c["kind"] == "evidence"),
        "urls_checked": sum(1 for c in report["checks"] if c["kind"] == "url"),
        "failures": [c for c in report["checks"] if not c["ok"]],
    }
    return report


# ====================================================================== auto builder
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BARE_URL_RE = re.compile(r"(?<!\()https?://[^\s)\]]+")


def parse_items(path):
    """Split a journal file into bullet items with headline, body, links, section."""
    items, section = [], ""
    txt = open(path).read()
    lines = txt.splitlines()
    cur = None

    def flush():
        if cur and cur["raw"].strip():
            items.append(cur)

    for ln in lines:
        if ln.startswith("#"):
            flush(); cur = None
            section = ln.lstrip("#").strip()
            continue
        if re.match(r"^\s*(-|\d+\.)\s+", ln) and not ln.startswith("  "):
            flush()
            cur = {"file": path, "section": section, "raw": re.sub(r"^\s*(-|\d+\.)\s+", "", ln)}
        elif ln.strip().startswith("**") and cur is None:
            cur = {"file": path, "section": section, "raw": ln.strip()}
        elif cur is not None and ln.strip():
            if re.match(r"^\s*-\s+https?://", ln):
                cur["raw"] += " " + ln.strip()[2:]
            elif ln.startswith("  "):
                cur["raw"] += " " + ln.strip().lstrip("- ")
            else:
                flush(); cur = None
    flush()
    for it in items:
        raw = it["raw"]
        it["links"] = [(l, u) for l, u in LINK_RE.findall(raw)]
        bare = [u.rstrip(".,;") for u in BARE_URL_RE.findall(LINK_RE.sub("", raw))]
        it["links"] += [(re.sub(r"^https?://(www\.)?", "", u).split("/")[0], u) for u in bare]
        m = re.match(r"\*\*(.+?)\*\*", raw)
        it["headline"] = m.group(1).strip().rstrip(".:") if m else ""
        body = LINK_RE.sub("", raw)
        body = BARE_URL_RE.sub("", body)
        body = body.replace("**", "").replace(" · ", " ").strip()
        body = re.sub(r"\s+\(\s*\)", "", body)
        body = re.sub(r"[\s·]+$", "", body)
        it["body"] = body
    return items


ABBR = r"(?<!\b[A-Z]\.)(?<!\ba\.m\.)(?<!\bp\.m\.)(?<!\bU\.S\.)(?<!\bvs\.)(?<!\bNo\.)(?<!\bSt\.)(?<!\bDr\.)(?<!\bMr\.)(?<!\bJr\.)"


def sentences(body):
    parts = re.split(ABBR + r"(?:(?<=[.!?])|(?<=[.!?][\"\u201d]))\s+(?=[A-Z\"'(@])", body)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def score_item(it, kws):
    h, b = it["headline"].lower(), it["body"].lower()
    s = 0
    for k in kws:
        s += 4 * h.count(k) + b.count(k)
    return s


def interest(it):
    b = it["body"]
    return len(NUM_RE.findall(b)) * 1.5 + len(b) / 200 + (3 if it["headline"] else 0) + \
        (2 if '"' in b else 0) - (8 if re.search(r"\b(quiet|not new|no follow-up)\b", b[:80], re.I) else 0)


def date_of(path):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path)
    return m.group(1) if m else ""


def nice_date(d):
    import datetime
    try:
        dt = datetime.date.fromisoformat(d)
        return dt.strftime("%b %-d, %Y").upper()
    except Exception:
        return d


def pick(arg, topic=None):
    """arg = journal path or topic words. Returns (items, label)."""
    if os.path.exists(arg) and arg.endswith(".md"):
        items = [i for i in parse_items(arg) if len(i["body"]) > 160]
        if topic:
            kws = topic.lower().split()
            items.sort(key=lambda i: -score_item(i, kws))
        else:
            items.sort(key=lambda i: -interest(i))
        return items, os.path.basename(arg)
    kws = [k for k in arg.lower().split() if len(k) > 1]
    pool = []
    for f in journal_files():
        pool += [i for i in parse_items(f) if len(i["body"]) > 160]
    pool = [i for i in pool if score_item(i, kws) > 0]
    pool.sort(key=lambda i: (-score_item(i, kws), -int(date_of(i["file"]).replace("-", "") or 0)))
    return pool, arg


def _kicker(it):
    sec = re.sub(r"^[A-Z]\.\s*", "", it["section"]).split("(")[0].strip() or "Interest Journal"
    sec = re.sub(r"^Interest Journal research:.*", "Interest Journal", sec)
    return f"{sec} · {nice_date(date_of(it['file']))}"


def _num_card(sent):
    """Pull 'number + context' pairs from a sentence for stat cards."""
    cards = []
    for m in re.finditer(r"([$~]?\d[\d,]*(?:\.\d+)?\s?(?:%|[kKMB]\b|million|billion|trillion|Tbps|kW|kg|mph)?)", sent):
        tok = m.group(1).strip()
        prev = sent[max(0, m.start() - 8):m.start()]
        if re.fullmatch(r"(19|20)\d\d", tok) or (m.start() > 0 and sent[m.start() - 1].isalnum()) or \
                re.search(r"(Flight|No\.|Group|v|V)\s?$", prev):
            continue
        if re.fullmatch(r"\d{1,2}", tok) and re.search(r"(Oct|Sept?|Nov|Dec|Jan|a\.m|p\.m|:)", sent[max(0, m.start() - 6):m.end() + 6]):
            continue
        tail = sent[m.end():].strip()
        tail = re.split(r"[,;.()]", tail)[0]
        words = re.findall(r"[A-Za-z][\w'\-]*", tail)[:5]
        while words and words[-1].lower() in ("and", "only", "the", "of", "to", "a", "in", "for", "with", "than"):
            words.pop()
        lead = re.findall(r"[A-Za-z][\w'\-]*", sent[:m.start()])[-3:]
        label = " ".join(words) if len(words) >= 2 else " ".join(lead + words)
        cards.append({"big": tok, "label": label})
    # dedupe
    seen, out = set(), []
    for c in cards:
        if c["big"] not in seen:
            out.append(c); seen.add(c["big"])
    return out


def _highlight(sent):
    """Mark numbers and capitalised phrases with *...* for kinetic emphasis (max 3)."""
    marks = 0
    def rep(m):
        nonlocal marks
        if marks >= 3:
            return m.group(0)
        marks += 1
        return "*" + m.group(0) + "*"
    return re.sub(r"(?<![A-Za-z\d])\$?\d[\d,.]*%?(?![A-Za-z\d])|\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+", rep, sent)


def _scene_for(sents, gi, label=None):
    cap = " ".join(sents)
    quote = re.search(r"\"([^\"]{18,160})\"", cap)
    cards = _num_card(cap)
    if quote and gi > 0:
        sc = {"type": "quote", "label": label or "In their words",
              "data": {"text": quote.group(1), "who": "as quoted in Jim's journal", "size": 64}}
    elif len(cards) >= 2:
        sc = {"type": "cards", "label": label or "By the numbers", "heading": _short(sents[0], 60),
              "data": {"cards": cards[:3]}}
    elif len(cards) == 1 and len(cap) < 170:
        sc = {"type": "cards", "label": label or "Key number", "heading": "",
              "data": {"cards": [cards[0] | {"label": _short(cap, 120)}]}}
    else:
        lines = [_highlight(x) for x in sents][:3]
        sc = {"type": "kinetic", "label": label or f"Part {gi + 1}",
              "data": {"lines": lines, "size": 48 if len(cap) > 200 else 54 if len(cap) > 120 else 62}}
    sc["caption"] = cap
    sc["evidence"] = list(sents)
    sc["min"] = 7.0
    return sc


def _drop_headline(sents, headline):
    """Remove the bold headline from the first sentence; keep any remainder that is a real sentence."""
    if not sents or not headline or not sents[0].startswith(headline[:20]):
        return sents
    rest = sents[0][len(headline):].lstrip(" .:")
    return ([rest] if len(rest) > 30 else []) + sents[1:]


def _short(s, n):
    s = s.strip().rstrip(".")
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut + "…"


def auto_storyboard(arg, topic=None, index=0, max_scenes=6):
    items, label = pick(arg, topic)
    if not items:
        raise SystemExit(f"No journal item matched {arg!r}")
    it = items[min(index, len(items) - 1)]
    sents = sentences(it["body"])
    headline = re.sub(r"^(New|Update|Follow-up)\s*[:\-]\s*", "", it["headline"], flags=re.I)
    if it["headline"]:
        sents = _drop_headline(sents, it["headline"])
    if not headline and sents:
        headline = _short(sents.pop(0), 80)
    # one sentence per scene when short, otherwise group to ~18-45 words
    groups = []
    if len(sents) <= max_scenes:
        groups = [[x] for x in sents]
    else:
        cur = []
        for x in sents:
            cur.append(x)
            if sum(len(y.split()) for y in cur) >= 22:
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        groups = groups[:max_scenes]
    scenes = [_scene_for(g, gi) for gi, g in enumerate(groups)]
    files, links = [it["file"]], list(it["links"])
    # top up with related journal items (other days / other bullets) if we have fewer than 4 scenes
    for rel in items[index + 1:]:
        if len(scenes) >= 4:
            break
        if rel["body"] == it["body"]:
            continue
        rs = sentences(rel["body"])
        if not rs:
            continue
        lead = rs[0] if not rel["headline"] or not rs[0].startswith(rel["headline"][:20]) or len(rs) == 1 else rs[1]
        sc = _scene_for([lead], len(scenes), label="Related · " + nice_date(date_of(rel["file"])))
        scenes.append(sc)
        if rel["file"] not in files:
            files.append(rel["file"])
        links += rel["links"][:2]
    title = headline if len(headline) <= 95 else _short(headline, 90)
    sid = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    seen, sources = set(), []
    for l, u in links:
        if u not in seen:
            sources.append({"label": l, "url": u}); seen.add(u)
    body_all = " ".join([it["body"]] + [s_["caption"] for s_ in scenes])
    return {
        "id": f"auto-{date_of(it['file'])}-{sid}",
        "title": title,
        "kicker": _kicker(it),
        "subtitle": f"An auto-generated explainer from Jim's Interest Journal ({os.path.basename(it['file'])}).",
        "title_narration": title,
        "theme": "agents" if re.search(r"agent|claude|openai|grok bot|cursor|anthropic", body_all, re.I) else
                 "ravens" if re.search(r"ravens|lamar|orioles|terps|chelsea", body_all, re.I) else
                 "markets" if re.search(r"stock|shares|price target", body_all, re.I) else "space",
        "length_scale": 0.95,
        "source_files": files,
        "as_of": "Auto storyboard: every caption is a verbatim sentence from " + ", ".join(os.path.basename(f) for f in files) + ".",
        "scenes": scenes,
        "sources": sources[:8],
        "music": "pad",
        "auto": True,
    }


def recap_storyboard(path, n=5):
    """A daily recap: the top headline from each section of one journal file, one scene each."""
    items = [i for i in parse_items(path) if i["headline"] and len(i["body"]) > 160
             and not re.match(r"(not new|quiet|smaller|other launches)", i["headline"], re.I)]
    by_sec = {}
    for i in items:
        by_sec.setdefault(i["section"], []).append(i)
    for v in by_sec.values():
        v.sort(key=lambda i: -interest(i))
    chosen, k = [], 0
    while len(chosen) < n and any(by_sec.values()):
        for sec in list(by_sec):
            if by_sec[sec] and len(chosen) < n:
                chosen.append(by_sec[sec].pop(0))
        k += 1
    scenes, links = [], []
    for gi, it in enumerate(chosen):
        sents = _drop_headline(sentences(it["body"]), it["headline"])
        lead = sents[0] if sents else it["headline"]
        if len(lead) > 150:
            # the sentence splitter keeps "...sessions. 2.1.292 adds..." together; split before a digit-led sentence
            parts = re.split(r"(?<!\bNo)(?<!\bvs)(?<!\bSt)(?<=[a-z)]\.)\s+(?=\d)", lead)
            if len(parts) > 1 and len(parts[0]) >= 40:
                lead = parts[0]
        sec = re.sub(r"^[A-Z]\.\s*", "", it["section"]).split("(")[0].strip()
        hl = it["headline"].rstrip(".")
        # keep each recap scene to ~8-10 s of narration so 5 stories land near one minute
        if len(hl) + len(lead) < 120:
            cap = hl + ". " + lead
        elif 40 <= len(hl) <= 110:
            cap = hl + "."
        else:
            cap = min([c for c in (hl + ".", lead) if len(c) >= 40] or [lead], key=len)
        sc = {"type": "kinetic", "label": f"{gi + 1} · {sec}", "heading": _short(it["headline"], 70),
              "data": {"lines": [_highlight(lead)], "size": 48 if len(lead) > 150 else 56},
              "caption": cap, "evidence": [lead, hl], "min": 7.0}
        scenes.append(sc)
        links += it["links"][:1]
    d = nice_date(date_of(path))
    return {
        "id": f"recap-{date_of(path)}",
        "title": f"Daily recap: {d.title()}",
        "kicker": f"Interest Journal recap · {d}",
        "subtitle": "The top story from each section of Jim's journal, in about a minute.",
        "title_narration": f"Your daily recap.",
        "theme": "space", "length_scale": 0.95,
        "source_files": [path],
        "as_of": f"Auto recap: each caption is a verbatim sentence from {os.path.basename(path)}.",
        "scenes": scenes,
        "sources": [{"label": l, "url": u} for l, u in links],
        "music": "pad", "auto": True,
    }
