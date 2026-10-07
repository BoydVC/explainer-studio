"""Scene renderers. Each takes (ctx, scene, t, d, th, story) in 1920x1080 design units."""
import math, random
from .gfx import *

CX0, CX1 = 120, 1800          # content x-range
TOP = 170                     # content top
BOT = 860                     # content bottom (caption band below)


def heading(ctx, sc, t, th, y=TOP + 50):
    lab = sc.get("label")
    if lab:
        p = ease_out(prog(t, 0.1, 0.5))
        font(ctx, MONO, 26, True)
        rgba(ctx, th["accent"], p)
        ctx.rectangle(CX0, y - 22, 34 * p, 4)
        ctx.fill()
        text(ctx, lab.upper(), CX0 + 48, y - 10)
        y += 56
    h = sc.get("heading")
    if h:
        hh = kinetic(ctx, h, CX0, y + 30, 1640, 62, t, 0.2, th, fam=HEAD, bold=True, stagger=0.035)
        y += hh + 20
    return y


# ------------------------------------------------------------------ title
def draw_title(ctx, sc, t, d, th, story):
    # big ring motif on the right
    cx, cy, R = 1500, 520, 330
    p = ease_out(prog(t, 0.0, 1.4))
    ctx.set_line_width(2)
    for i, rr in enumerate([R, R * 0.74, R * 0.48]):
        rgba(ctx, th["accent"], 0.22 + 0.1 * i)
        ctx.arc(cx, cy, rr, -math.pi / 2, -math.pi / 2 + 2 * math.pi * p)
        ctx.stroke()
        ang = t * (0.5 + 0.3 * i) + i * 2
        rgba(ctx, th["accent2"] if i == 1 else th["accent"], p)
        circle(ctx, cx + rr * math.cos(ang), cy + rr * math.sin(ang), 9 - 2 * i)
        ctx.fill()
    g_a = 0.9 * p
    rgba(ctx, th["accent"], 0.12 * g_a)
    circle(ctx, cx, cy, R * 0.3)
    ctx.fill()

    # kicker (typewriter)
    kick = story.get("kicker", "")
    n = int(len(kick) * clamp((t - 0.2) / 0.9))
    font(ctx, MONO, 30, True)
    rgba(ctx, th["accent"])
    text(ctx, kick[:n] + ("▍" if n < len(kick) and int(t * 6) % 2 == 0 else ""), CX0, 330)
    # accent bar
    bp = ease_out(prog(t, 0.3, 0.8))
    rgba(ctx, th["accent2"])
    rrect(ctx, CX0, 360, 140 * bp, 8, 4)
    ctx.fill()
    # title
    title = story["title"]
    size = 96
    font(ctx, DISPLAY, size, True)
    while size > 54:
        font(ctx, DISPLAY, size, True)
        placed, nl = layout_words(ctx, tokens(title), 1180, size * 1.12)
        if nl <= 3:
            break
        size -= 6
    hh = kinetic(ctx, title, CX0, 470, 1180, size, t, 0.55, th, fam=DISPLAY, bold=True, stagger=0.09, rise=50,
                 line_gap=1.12)
    sub = story.get("subtitle")
    if sub:
        sp = ease_out(prog(t, 1.4, 0.8))
        font(ctx, BODY, 40, False)
        rgba(ctx, th["muted"], sp)
        for i, line in enumerate(wrap(ctx, sub, 1150)[:3]):
            text(ctx, line, CX0, 470 + hh + 30 + i * 54 + (1 - sp) * 20)


# ------------------------------------------------------------------ kinetic statement
def draw_kinetic(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    lines = sc["data"].get("lines", [])
    size = sc["data"].get("size", 58)
    y += 40
    start = 0.6
    for ln in lines:
        h = kinetic(ctx, ln, CX0, y + size, 1640, size, t, start, th, fam=BODY, bold=False if size < 50 else True,
                    stagger=0.05)
        y += h + 26
        start += 0.05 * len(ln.split()) + 0.35


# ------------------------------------------------------------------ big number
def draw_bignumber(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    D = sc["data"]
    v = float(D["value"])
    p = ease_out(prog(t, 0.5, 1.8))
    cur = v * p
    s = fmt_num(cur, D.get("decimals", 0), D.get("prefix", ""), D.get("suffix", ""))
    if p >= 1 and D.get("display"):
        s = D["display"]
    size = D.get("size", 210)
    font(ctx, DISPLAY, size, True)
    while tw(ctx, s) > 1640 and size > 90:
        size -= 10
        font(ctx, DISPLAY, size, True)
    pre = D.get("pre")
    by = max(y + (70 if pre else 30) + size * 0.75, 600)
    if pre:
        font(ctx, MONO, 34, True)
        rgba(ctx, th["muted"], ease_out(prog(t, 0.4, 0.5)))
        text(ctx, pre.upper(), CX0, by - size * 0.75 - 30)
    font(ctx, DISPLAY, size, True)
    # glow
    rgba(ctx, th["accent"], 0.25 * p)
    for dx, dy in ((3, 3), (-3, -3)):
        ctx.move_to(CX0 + dx, by + dy)
        ctx.show_text(s)
    rgba(ctx, th["accent"])
    ctx.move_to(CX0, by)
    ctx.show_text(s)
    lab = D.get("label")
    if lab:
        kinetic(ctx, lab, CX0, by + 90, 980 if D.get("compare") else 1640, 50, t, 1.3, th, fam=BODY, bold=True,
                stagger=0.04)
    comps = D.get("compare", [])
    if comps:
        x = 1180
        for i, c in enumerate(comps):
            cp = ease_back(prog(t, 1.8 + i * 0.35, 0.6))
            if cp <= 0:
                continue
            yy = by - size * 0.75 + i * 165
            rgba(ctx, th["text"], 0.06 * cp)
            rrect(ctx, x, yy, 600, 140, 22)
            ctx.fill()
            rgba(ctx, th["accent2"], cp)
            font(ctx, HEAD, 64, True)
            text(ctx, c["big"], x + 34, yy + 78)
            font(ctx, BODY, 28)
            rgba(ctx, th["muted"], cp)
            text(ctx, c["label"], x + 36, yy + 118)


# ------------------------------------------------------------------ stat cards
def draw_cards(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    cards = sc["data"]["cards"]
    n = len(cards)
    gap = 36
    cw = (1680 - gap * (n - 1)) / n
    ch = min(340, BOT - y - 60)
    cy = max(y + 40, 420)
    for i, c in enumerate(cards):
        p = ease_back(prog(t, 0.6 + i * 0.4, 0.7))
        if p <= 0:
            continue
        x = CX0 + i * (cw + gap)
        yy = cy + (1 - p) * 60
        a = clamp(p)
        rgba(ctx, th["text"], 0.07 * a)
        rrect(ctx, x, yy, cw, ch, 28)
        ctx.fill()
        rgba(ctx, th["accent2"] if c.get("alt") else th["accent"], a)
        rrect(ctx, x, yy, cw, 8, 4)
        ctx.fill()
        size = 96 if n <= 3 else 76
        font(ctx, HEAD, size, True)
        while tw(ctx, c["big"]) > cw - 60 and size > 40:
            size -= 6
            font(ctx, HEAD, size, True)
        rgba(ctx, th["accent2"] if c.get("alt") else th["accent"], a)
        text(ctx, c["big"], x + 34, yy + 40 + size)
        font(ctx, BODY, 38 if n <= 3 else 32, False)
        rgba(ctx, th["text"], a)
        for j, ln in enumerate(wrap(ctx, c["label"], cw - 68)[:4]):
            text(ctx, ln, x + 34, yy + 70 + size + 30 + j * 48)


# ------------------------------------------------------------------ bars
def draw_bars(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    D = sc["data"]
    items = D["items"]
    mx = D.get("max") or max(abs(float(i["value"])) for i in items)
    n = len(items)
    bh = 92 if n <= 2 else 78 if n <= 3 else 60
    gap = 56 if n <= 3 else 30
    y0 = max(y + 50, 400)
    lx, bx, bw = CX0, 720, 960
    for i, it in enumerate(items):
        p = ease_out(prog(t, 0.7 + i * 0.35, 1.2))
        yy = y0 + i * (bh + gap)
        a = clamp(prog(t, 0.5 + i * 0.35, 0.4))
        font(ctx, BODY, 38, True)
        rgba(ctx, th["text"], a)
        text(ctx, it["label"], lx, yy + bh * 0.66)
        rgba(ctx, th["text"], 0.07 * a)
        rrect(ctx, bx, yy, bw, bh, bh / 2)
        ctx.fill()
        frac = float(it["value"]) / mx
        col = th["accent2"] if it.get("highlight") else th["accent"]
        if p > 0:
            g = cairo.LinearGradient(bx, 0, bx + bw * frac, 0)
            g.add_color_stop_rgba(0, *col[:3], 0.55)
            g.add_color_stop_rgba(1, *col[:3], 1)
            ctx.set_source(g)
            rrect(ctx, bx, yy, max(bh, bw * frac * p), bh, bh / 2)
            ctx.fill()
        val = float(it["value"]) * p
        s = fmt_num(val, D.get("decimals", 0), D.get("prefix", ""), D.get("suffix", ""))
        if p >= 1 and it.get("display"):
            s = it["display"]
        font(ctx, MONO, 36, True)
        endx = bx + max(bh, bw * frac * p)
        if endx + 22 + tw(ctx, s) > 1800:
            rgba(ctx, th["bg0"], a)
            text(ctx, s, endx - 30, yy + bh * 0.66, "right")
        else:
            rgba(ctx, th["text"], a)
            text(ctx, s, endx + 22, yy + bh * 0.66)
    note = D.get("note")
    if note:
        na = ease_out(prog(t, 0.9 + n * 0.35 + 0.6, 0.6))
        font(ctx, BODY, 32)
        rgba(ctx, th["muted"], na)
        text(ctx, note, CX0, min(BOT - 10, y0 + n * (bh + gap) + 50))


# ------------------------------------------------------------------ line / steps chart
def draw_line(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    D = sc["data"]
    pts = D["points"]
    vals = [float(p["value"]) for p in pts]
    lo, hi = min(vals + [D.get("min", min(vals))]), max(vals + [D.get("max", max(vals))])
    pad = (hi - lo) * 0.25 or 1
    lo -= pad
    hi += pad
    x0, x1 = 260, 1660
    y0, y1 = max(y + 120, 440), BOT - 90
    inv = D.get("invert", False)

    def py(v):
        f = (v - lo) / (hi - lo)
        if inv:
            f = 1 - f
        return y1 - f * (y1 - y0)

    xs = [x0 + i * (x1 - x0) / max(1, len(pts) - 1) for i in range(len(pts))]
    ap = ease_out(prog(t, 0.4, 0.6))
    # axis / zero line
    if lo < 0 < hi and D.get("zero_label"):
        rgba(ctx, th["muted"], 0.6 * ap)
        ctx.set_line_width(2)
        ctx.set_dash([10, 10])
        ctx.move_to(x0 - 80, py(0)); ctx.line_to(x1 + 80, py(0)); ctx.stroke()
        ctx.set_dash([])
        font(ctx, MONO, 24, True)
        text(ctx, D["zero_label"], x0 - 80, py(0) - 14)
    for lbl, yv in D.get("bands", []):
        pass
    # line draw progress
    lp = prog(t, 0.8, 0.9 * len(pts))
    segs = len(pts) - 1
    ctx.set_line_width(7)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    rgba(ctx, th["accent"])
    if segs > 0 and lp > 0:
        total = lp * segs
        ctx.move_to(xs[0], py(vals[0]))
        for i in range(segs):
            f = clamp(total - i)
            if f <= 0:
                break
            ctx.line_to(xs[i] + (xs[i + 1] - xs[i]) * f, py(vals[i]) + (py(vals[i + 1]) - py(vals[i])) * f)
        ctx.stroke()
    for i, p_ in enumerate(pts):
        appear = 0.8 + 0.9 * i
        pp = ease_back(prog(t, appear, 0.5))
        if pp <= 0:
            continue
        X, Y = xs[i], py(vals[i])
        col = th["accent2"] if p_.get("highlight") else th["accent"]
        rgba(ctx, col, 0.25 * clamp(pp))
        circle(ctx, X, Y, 30 * pp); ctx.fill()
        rgba(ctx, col)
        circle(ctx, X, Y, 14 * pp); ctx.fill()
        a = clamp(pp)
        font(ctx, HEAD, 54, True)
        rgba(ctx, col, a)
        text(ctx, p_.get("display", str(p_["value"])), X, Y - 46, "center")
        font(ctx, BODY, 30, False)
        rgba(ctx, th["muted"], a)
        for j, ln in enumerate(wrap(ctx, p_.get("label", ""), 360)[:2]):
            lw_ = tw(ctx, ln)
            rgba(ctx, th["bg0"], 0.75 * a)
            rrect(ctx, X - lw_ / 2 - 10, Y + 66 + j * 38 - 28, lw_ + 20, 38, 8); ctx.fill()
            rgba(ctx, th["muted"], a)
            text(ctx, ln, X, Y + 66 + j * 38, "center")
    note = D.get("note")
    if note:
        na = ease_out(prog(t, 0.9 * len(pts) + 1.2, 0.6))
        font(ctx, BODY, 32, True)
        rgba(ctx, th["accent2"], na)
        text(ctx, note, CX1, y0 - 90, "right")


# ------------------------------------------------------------------ timeline
def draw_timeline(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    ev = sc["data"]["events"]
    n = len(ev)
    x0, x1 = 200, 1720
    ly = max(y + 210, 600)
    lp = ease_in_out(prog(t, 0.4, 1.2))
    ctx.set_line_width(6)
    rgba(ctx, th["muted"], 0.35)
    ctx.move_to(x0, ly); ctx.line_to(x0 + (x1 - x0) * lp, ly); ctx.stroke()
    for i, e in enumerate(ev):
        X = x0 + i * (x1 - x0) / max(1, n - 1)
        st = 0.8 + i * (max(0.6, (d - 3.0) / max(1, n)) * 0.75)
        pp = ease_back(prog(t, st, 0.55))
        if pp <= 0:
            continue
        status = e.get("status", "done")
        col = th["accent"] if status == "done" else th["accent2"] if status == "next" else th["muted"]
        # filled progress segment
        if i > 0 and status == "done":
            Xp = x0 + (i - 1) * (x1 - x0) / max(1, n - 1)
            rgba(ctx, th["accent"], 0.9)
            ctx.set_line_width(6)
            ctx.move_to(Xp, ly); ctx.line_to(Xp + (X - Xp) * clamp(pp), ly); ctx.stroke()
        rgba(ctx, col, 0.25 * clamp(pp))
        circle(ctx, X, ly, 34 * pp); ctx.fill()
        rgba(ctx, col)
        if status == "tbd":
            ctx.set_line_width(4)
            circle(ctx, X, ly, 16 * pp); ctx.stroke()
        else:
            circle(ctx, X, ly, 16 * pp); ctx.fill()
        a = clamp(pp)
        up = i % 2 == 0
        font(ctx, MONO, 30, True)
        rgba(ctx, col, a)
        text(ctx, e["date"], X, ly - 66 if up else ly + 92, "center")
        font(ctx, BODY, 31, False)
        rgba(ctx, th["text"], a)
        lines = wrap(ctx, e["label"], 330)[:3]
        for j, ln in enumerate(lines):
            if up:
                yy = ly - 112 - (len(lines) - 1 - j) * 40
            else:
                yy = ly + 140 + j * 40
            text(ctx, ln, X, yy, "center")


# ------------------------------------------------------------------ quote
def draw_quote(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th) if sc.get("heading") or sc.get("label") else TOP + 60
    D = sc["data"]
    qa = ease_out(prog(t, 0.2, 0.6))
    font(ctx, DISPLAY, 260, True)
    rgba(ctx, th["accent"], 0.35 * qa)
    text(ctx, "\u201C", CX0 - 10, y + 230)
    size = D.get("size", 70)
    h = kinetic(ctx, D["text"], CX0 + 140, y + 170, 1500, size, t, 0.5, th, fam=HEAD, bold=True, stagger=0.07,
                line_gap=1.2)
    who = D.get("who")
    if who:
        wa = ease_out(prog(t, 0.5 + 0.07 * len(D["text"].split()) + 0.4, 0.6))
        font(ctx, MONO, 32, True)
        rgba(ctx, th["accent2"], wa)
        text(ctx, "— " + who, CX0 + 140, y + 170 + h + 40)


# ------------------------------------------------------------------ dot grid comparison
def draw_dots(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    D = sc["data"]
    groups = D["groups"]
    per = float(D["per_dot"])
    step = D.get("step", 50)
    r = step * 0.4
    y0 = max(y + 60, 420)
    x = CX0
    for gi, g in enumerate(groups):
        ndots = int(round(float(g["value"]) / per))
        cols = g.get("cols", D.get("cols", 20))
        st = 0.6 + gi * 1.6
        col = th["accent2"] if g.get("alt") else th["accent"]
        la = ease_out(prog(t, st, 0.5))
        font(ctx, HEAD, 64, True)
        rgba(ctx, col, la)
        text(ctx, g["big"], x, y0 + 10)
        font(ctx, BODY, 32)
        rgba(ctx, th["muted"], la)
        text(ctx, g["label"], x, y0 + 56)
        for k in range(ndots):
            cx = x + (k % cols) * step + r
            cy = y0 + 110 + (k // cols) * step
            pp = ease_back(prog(t, st + 0.25 + k * (1.1 / max(ndots, 1)), 0.35))
            if pp <= 0:
                continue
            rgba(ctx, col, 0.18)
            circle(ctx, cx, cy, r * pp * 1.25)
            ctx.fill()
            rgba(ctx, col, 0.95)
            circle(ctx, cx, cy, r * pp * 0.8)
            ctx.fill()
        x += cols * step + 110
    legend = D.get("legend")
    if legend:
        la = ease_out(prog(t, 0.6 + len(groups) * 1.6 + 0.3, 0.6))
        font(ctx, MONO, 26, True)
        rgba(ctx, th["muted"], la)
        text(ctx, legend, CX0, BOT - 10)


# ------------------------------------------------------------------ satellite cluster
def draw_cluster(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    D = sc["data"]
    n = int(D.get("n", 10))
    cx, cy, R = 560, max(y + 270, 600), 210
    ring = ease_out(prog(t, 0.4, 1.0))
    pos = []
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n + t * 0.12
        pos.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    # links
    lp = prog(t, 1.2, 1.4)
    ctx.set_line_width(3)
    for i in range(n):
        for j in range(i + 1, n):
            if (j - i) in (1, n - 1) or (j - i) == n // 2:
                f = clamp(lp * 1.4 - ((i + j) % n) / (n * 2.5))
                if f <= 0:
                    continue
                (ax, ay), (bx, by) = pos[i], pos[j]
                rgba(ctx, th["accent"], 0.45 * f)
                ctx.move_to(ax, ay); ctx.line_to(ax + (bx - ax) * f, ay + (by - ay) * f); ctx.stroke()
                if f >= 1:
                    ph = (t * 0.9 + (i * 0.37)) % 1
                    rgba(ctx, th["accent2"], 0.95)
                    circle(ctx, ax + (bx - ax) * ph, ay + (by - ay) * ph, 5); ctx.fill()
    for i, (px, py_) in enumerate(pos):
        pp = ease_back(prog(t, 0.4 + i * 0.08, 0.5))
        if pp <= 0:
            continue
        ctx.save()
        ctx.translate(px, py_)
        ctx.scale(pp, pp)
        rgba(ctx, th["accent"], 0.2)
        circle(ctx, 0, 0, 30); ctx.fill()
        rgba(ctx, th["text"])
        ctx.rectangle(-11, -11, 22, 22); ctx.fill()
        rgba(ctx, th["accent"])
        ctx.rectangle(-38, -6, 22, 12); ctx.fill()
        ctx.rectangle(16, -6, 22, 12); ctx.fill()
        ctx.restore()
    ca = ease_out(prog(t, 0.6, 0.6))
    rgba(ctx, th["bg0"], 0.85 * ca)
    circle(ctx, cx, cy, 92); ctx.fill()
    rgba(ctx, th["accent"], 0.5 * ca)
    ctx.set_line_width(2)
    circle(ctx, cx, cy, 92); ctx.stroke()
    font(ctx, MONO, 30, True)
    rgba(ctx, th["accent2"], ca)
    text(ctx, D.get("center", ""), cx, cy + 10, "center")
    # side facts
    facts = D.get("facts", [])
    for i, f in enumerate(facts):
        fa = ease_out(prog(t, 1.6 + i * 0.6, 0.6))
        if fa <= 0:
            continue
        fy = max(y + 80, 400) + i * 135
        rgba(ctx, th["text"], 0.07 * fa)
        rrect(ctx, 960, fy, 840, 112, 20); ctx.fill()
        font(ctx, HEAD, 52, True)
        rgba(ctx, th["accent"], fa)
        text(ctx, f["big"], 992, fy + 70)
        bw_ = tw(ctx, f["big"])
        font(ctx, BODY, 32)
        rgba(ctx, th["text"], fa)
        lines = wrap(ctx, f["label"], 840 - bw_ - 90)
        for j, ln in enumerate(lines[:2]):
            text(ctx, ln, 992 + bw_ + 30, fy + (70 if len(lines) == 1 else 50 + j * 40))


# ------------------------------------------------------------------ flow diagram
def draw_flow(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    steps = sc["data"]["steps"]
    n = len(steps)
    gap = 90
    bw = (1680 - gap * (n - 1)) / n
    bh = 300
    by = max(y + 60, 420)
    for i, s in enumerate(steps):
        st = 0.6 + i * 0.7
        p = ease_back(prog(t, st, 0.6))
        x = CX0 + i * (bw + gap)
        if i > 0:
            ap = ease_out(prog(t, st - 0.35, 0.4))
            ax0 = x - gap + 12
            ax1 = ax0 + (gap - 24) * ap
            rgba(ctx, th["accent2"])
            ctx.set_line_width(5)
            ctx.move_to(ax0, by + bh / 2); ctx.line_to(ax1, by + bh / 2); ctx.stroke()
            if ap > 0.9:
                ctx.move_to(ax1 + 6, by + bh / 2); ctx.line_to(ax1 - 14, by + bh / 2 - 14)
                ctx.line_to(ax1 - 14, by + bh / 2 + 14); ctx.close_path(); ctx.fill()
        if p <= 0:
            continue
        a = clamp(p)
        ctx.save()
        ctx.translate(x + bw / 2, by + bh / 2)
        ctx.scale(0.8 + 0.2 * p, 0.8 + 0.2 * p)
        ctx.translate(-(x + bw / 2), -(by + bh / 2))
        rgba(ctx, th["text"], 0.08 * a)
        rrect(ctx, x, by, bw, bh, 26); ctx.fill()
        rgba(ctx, th["accent"], a)
        ctx.set_line_width(3)
        rrect(ctx, x, by, bw, bh, 26); ctx.stroke()
        font(ctx, HEAD, 40, True)
        rgba(ctx, th["accent"], a)
        tls = wrap(ctx, s["title"], bw - 44)[:3]
        for j, ln in enumerate(tls):
            text(ctx, ln, x + bw / 2, by + 70 + j * 46, "center")
        font(ctx, BODY, 29)
        rgba(ctx, th["text"], a)
        for j, ln in enumerate(wrap(ctx, s.get("sub", ""), bw - 44)[:4]):
            text(ctx, ln, x + bw / 2, by + 70 + len(tls) * 46 + 30 + j * 37, "center")
        ctx.restore()
    note = sc["data"].get("note")
    if note:
        na = ease_out(prog(t, 0.6 + n * 0.7 + 0.3, 0.6))
        font(ctx, BODY, 32)
        rgba(ctx, th["muted"], na)
        text(ctx, note, CX0, by + bh + 80)


# ------------------------------------------------------------------ trajectory (launch arc)
def draw_trajectory(ctx, sc, t, d, th, story):
    y = heading(ctx, sc, t, th)
    ev = sc["data"]["events"]
    n = len(ev)
    # planet limb along the bottom
    ecx, ecy, ER = 960, 3110, 2400
    g = cairo.RadialGradient(ecx, ecy, ER - 60, ecx, ecy, ER + 40)
    g.add_color_stop_rgba(0, *th["accent"][:3], 0.16)
    g.add_color_stop_rgba(1, *th["accent"][:3], 0.0)
    ctx.set_source(g)
    circle(ctx, ecx, ecy, ER + 40); ctx.fill()
    rgba(ctx, th["accent"], 0.55)
    ctx.set_line_width(3)
    circle(ctx, ecx, ecy, ER); ctx.stroke()
    top = max(y + 150, 450)
    def arcpt(f):
        x = 250 + 1420 * f
        base = ecy - math.sqrt(max(0.0, ER ** 2 - (x - ecx) ** 2))
        lift = (base - 20 - top) * math.sin(math.pi * min(1.0, f * 1.0)) ** 0.75
        return x, base - 14 - lift
    total = prog(t, 0.6, max(2.0, d * 0.62))
    ctx.set_line_width(6)
    ctx.set_dash([2, 16])
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    rgba(ctx, th["muted"], 0.6)
    steps = 140
    ctx.move_to(*arcpt(0))
    for k in range(1, steps + 1):
        ctx.line_to(*arcpt(k / steps))
    ctx.stroke()
    ctx.set_dash([])
    rgba(ctx, th["accent2"])
    ctx.move_to(*arcpt(0))
    kk = int(steps * total)
    for k in range(1, kk + 1):
        ctx.line_to(*arcpt(k / steps))
    ctx.stroke()
    if 0 < total < 1:
        hx, hy = arcpt(total)
        rgba(ctx, th["accent2"], 0.3); circle(ctx, hx, hy, 22); ctx.fill()
        rgba(ctx, th["text"]); circle(ctx, hx, hy, 9); ctx.fill()
    for i, e in enumerate(ev):
        f = e.get("at", i / max(1, n - 1))
        if total < f - 0.001:
            continue
        pp = ease_back(clamp((total - f) * 8 + 0.01))
        X, Y = arcpt(f)
        col = th["accent2"] if e.get("alt") else th["accent"]
        rgba(ctx, col, 0.25 * clamp(pp)); circle(ctx, X, Y, 26 * pp); ctx.fill()
        rgba(ctx, col)
        circle(ctx, X, Y, 12 * pp); ctx.fill()
        a = clamp(pp)
        font(ctx, BODY, 30, True)
        lines = wrap(ctx, e["label"], 290)[:2]
        lx = min(max(X, 190), 1730)
        ytxt = Y - 44 - (len(lines) - 1) * 36
        if e.get("time"):
            font(ctx, MONO, 26, True)
            rgba(ctx, col, a)
            text(ctx, e["time"], lx, ytxt - 40, "center")
        font(ctx, BODY, 30, True)
        rgba(ctx, th["text"], a)
        for j, ln in enumerate(lines):
            text(ctx, ln, lx, ytxt + j * 36, "center")


# ------------------------------------------------------------------ end card
def draw_end(ctx, sc, t, d, th, story):
    a = ease_out(prog(t, 0.1, 0.6))
    font(ctx, MONO, 28, True)
    rgba(ctx, th["accent"], a)
    text(ctx, "SOURCES CITED IN JIM'S INTEREST JOURNAL", CX0, 230)
    rgba(ctx, th["accent2"], a)
    rrect(ctx, CX0, 252, 120 * a, 6, 3); ctx.fill()
    srcs = story.get("sources", [])
    y = 330
    size = 32 if len(srcs) <= 6 else 27
    for i, s in enumerate(srcs[:9]):
        sa = ease_out(prog(t, 0.4 + i * 0.18, 0.5))
        font(ctx, BODY, size + 2, True)
        rgba(ctx, th["text"], sa)
        text(ctx, s["label"], CX0 + (1 - sa) * 30, y)
        font(ctx, MONO, size - 8, False)
        rgba(ctx, th["muted"], sa)
        url = s["url"]
        if len(url) > 118:
            url = url[:115] + "..."
        text(ctx, url, CX0 + (1 - sa) * 30, y + size + 6)
        y += size * 2 + 26
    fa = ease_out(prog(t, 1.2, 0.8))
    font(ctx, BODY, 28)
    rgba(ctx, th["muted"], fa)
    note = story.get("as_of", "")
    for j, ln in enumerate(wrap(ctx, note, 1500)[:2]):
        text(ctx, ln, CX0, 960 + j * 38)
    font(ctx, MONO, 24, True)
    rgba(ctx, th["accent"], fa)
    text(ctx, "EXPLAINER STUDIO  ·  BUILT FROM JIM'S INTEREST JOURNAL", CX0, 1045)


DRAW = {
    "title": draw_title, "kinetic": draw_kinetic, "bignumber": draw_bignumber, "cards": draw_cards,
    "bars": draw_bars, "line": draw_line, "timeline": draw_timeline, "quote": draw_quote, "dots": draw_dots,
    "cluster": draw_cluster, "flow": draw_flow, "trajectory": draw_trajectory, "end": draw_end,
}
