"""Low-level drawing helpers (cairo), easing, themes, text layout."""
import math, random, re
import cairocffi as cairo

W, H = 1920, 1080

DISPLAY = "Unbounded"      # title-card display face
HEAD = "Inter Tight"       # headings
BODY = "Inter"             # body / captions
MONO = "JetBrains Mono"    # labels, data


def hexc(h, a=1.0):
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


THEMES = {
    "space": dict(bg0="#05070F", bg1="#0B1430", glow="#1B3A7A", accent="#4CC9F0", accent2="#FF8A3D",
                  text="#F3F6FF", muted="#93A0BF", grid="#1A2747"),
    "agents": dict(bg0="#07060F", bg1="#17112E", glow="#3B2A7A", accent="#A78BFA", accent2="#34D399",
                   text="#F5F3FF", muted="#A39DBF", grid="#251E45"),
    "ravens": dict(bg0="#07050D", bg1="#1A0F33", glow="#3D1F7A", accent="#B794F4", accent2="#F2C14E",
                   text="#FAF7FF", muted="#A99FC2", grid="#28194A"),
    "markets": dict(bg0="#04090A", bg1="#0C2226", glow="#11515A", accent="#2DD4BF", accent2="#FBBF24",
                    text="#F0FDFA", muted="#8FB3B0", grid="#16363A"),
}


def theme(name):
    t = THEMES.get(name, THEMES["space"])
    return {k: hexc(v) for k, v in t.items()}


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, start, dur):
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, s=1.70158):
    x = clamp(x)
    c3 = s + 1
    return 1 + c3 * (x - 1) ** 3 + s * (x - 1) ** 2


# ---------------------------------------------------------------- primitives
def rgba(ctx, c, a=1.0):
    ctx.set_source_rgba(c[0], c[1], c[2], (c[3] if len(c) > 3 else 1.0) * a)


def font(ctx, fam=BODY, size=40, bold=False):
    ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def tw(ctx, s):
    return ctx.text_extents(s)[4]


def text(ctx, s, x, y, align="left"):
    w = tw(ctx, s)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    ctx.move_to(x, y)
    ctx.show_text(s)
    return w


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def circle(ctx, x, y, r):
    ctx.new_sub_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)


def wrap(ctx, s, maxw):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tw(ctx, t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def tokens(markup):
    """'plain *highlighted words* plain' -> [(word, highlighted)]"""
    out, hl = [], False
    for raw in markup.split():
        w = raw
        m = re.match(r"^([(\"'“‘\[]*)\*", w)          # "*word", "(*word", "\"*word"
        if m:
            hl = True
            w = m.group(1) + w[m.end():]
        end = bool(re.search(r"\*(?:[^\w\s]*|['’]s[^\w\s]*)$", w))   # "word*", "word*).", "word*'s"
        if end:
            w = w.replace("*", "")
        out.append((w, hl))
        if end:
            hl = False
    return out


def strip_markup(s):
    return s.replace("*", "")


def layout_words(ctx, toks, maxw, line_h, align="left"):
    """returns list of (word, hl, x, y_line_index) with x relative to 0 and total lines"""
    space = tw(ctx, " ")
    lines, cur, curw = [], [], 0.0
    for w, hl in toks:
        ww = tw(ctx, w)
        add = ww if not cur else space + ww
        if cur and curw + add > maxw:
            lines.append((cur, curw))
            cur, curw = [], 0.0
            add = ww
        cur.append((w, hl, ww))
        curw += add
    if cur:
        lines.append((cur, curw))
    placed = []
    for li, (items, lw) in enumerate(lines):
        x = 0.0 if align == "left" else (maxw - lw) / 2 if align == "center" else maxw - lw
        for w, hl, ww in items:
            placed.append((w, hl, x, li, ww))
            x += ww + space
    return placed, len(lines)


def kinetic(ctx, markup, x, y, maxw, size, t, start, th, fam=BODY, bold=True, stagger=0.045, rise=34,
            line_gap=1.22, align="left", color=None, hl_color=None, fade=0.38):
    """Word-by-word reveal. Returns total height."""
    font(ctx, fam, size, bold)
    toks = tokens(markup)
    placed, nl = layout_words(ctx, toks, maxw, size * line_gap, align)
    color = color or th["text"]
    hl_color = hl_color or th["accent"]
    for i, (w, hl, wx, li, ww) in enumerate(placed):
        p = prog(t, start + i * stagger, fade)
        if p <= 0:
            continue
        e = ease_out(p)
        yy = y + li * size * line_gap + (1 - e) * rise
        if hl:
            # soft underline glow for highlighted words
            rgba(ctx, hl_color, 0.18 * e)
            rrect(ctx, x + wx - 6, yy - size * 0.78, ww + 12, size * 1.02, 10)
            ctx.fill()
        rgba(ctx, hl_color if hl else color, e)
        ctx.move_to(x + wx, yy)
        ctx.show_text(w)
    return nl * size * line_gap


def fmt_num(v, decimals=0, prefix="", suffix=""):
    s = f"{v:,.{decimals}f}"
    return f"{prefix}{s}{suffix}"


# ---------------------------------------------------------------- background
class Background:
    def __init__(self, th, seed=7):
        self.th = th
        rnd = random.Random(seed)
        self.stars = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 2.2), rnd.uniform(0, 6.28),
                       rnd.uniform(0.4, 1.4)) for _ in range(170)]
        # static layer
        self.static = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c = cairo.Context(self.static)
        g = cairo.LinearGradient(0, 0, W * 0.4, H)
        g.add_color_stop_rgba(0, *th["bg1"][:3], 1)
        g.add_color_stop_rgba(1, *th["bg0"][:3], 1)
        c.set_source(g)
        c.paint()
        # faint grid
        rgba(c, th["grid"], 0.35)
        c.set_line_width(1)
        for x in range(0, W + 1, 96):
            c.move_to(x + 0.5, 0); c.line_to(x + 0.5, H)
        for y in range(0, H + 1, 96):
            c.move_to(0, y + 0.5); c.line_to(W, y + 0.5)
        c.stroke()
        # vignette
        v = cairo.RadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.75)
        v.add_color_stop_rgba(0, 0, 0, 0, 0)
        v.add_color_stop_rgba(1, 0, 0, 0, 0.55)
        c.set_source(v)
        c.paint()

    def draw(self, ctx, gt):
        ctx.set_source_surface(self.static, 0, 0)
        ctx.paint()
        # drifting glow
        gx = W * (0.72 + 0.12 * math.sin(gt * 0.11))
        gy = H * (0.30 + 0.10 * math.cos(gt * 0.08))
        g = cairo.RadialGradient(gx, gy, 0, gx, gy, 760)
        g.add_color_stop_rgba(0, *self.th["glow"][:3], 0.55)
        g.add_color_stop_rgba(1, *self.th["glow"][:3], 0)
        ctx.set_source(g)
        ctx.paint()
        g2x = W * (0.18 + 0.06 * math.cos(gt * 0.07))
        g2 = cairo.RadialGradient(g2x, H * 0.95, 0, g2x, H * 0.95, 620)
        g2.add_color_stop_rgba(0, *self.th["accent"][:3], 0.10)
        g2.add_color_stop_rgba(1, *self.th["accent"][:3], 0)
        ctx.set_source(g2)
        ctx.paint()
        for (x, y, r, ph, sp) in self.stars:
            a = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(gt * sp + ph))
            xx = (x - gt * 6 * sp) % W
            ctx.set_source_rgba(1, 1, 1, a)
            circle(ctx, xx, y, r)
            ctx.fill()
