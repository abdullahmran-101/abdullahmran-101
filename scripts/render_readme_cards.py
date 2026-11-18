#!/usr/bin/env python3
"""Renders every static SVG card in ../cards and the README that composes them.

Design system v2  ("technical, white-on-black")
  Colour   near-black canvas, white as the primary accent, purple as the data colour.
           No gradients, opacity, filters or animation, so GitHub renders it identically everywhere.
  Type     Inter Display for headings, Inter for body, DejaVu Sans Mono for labels and code.
           All text is converted to outlines (GitHub blocks web fonts inside SVG images).
  Grid     880-unit canvas, 40-unit page margin, 800-unit content width, 16-unit gutter.
  Motif    engineering-drawing corner brackets, dot grids, hairlines, terminal and YAML panels.

Run locally:   python scripts/render_readme_cards.py
Real contribution data: set GITHUB_TOKEN (the daily workflow does this).
Requires:      pip install fonttools
"""
import json, os, math, random, datetime as dt, urllib.request
from pathlib import Path
from xml.dom import minidom

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

USER = "abdullahmran-101"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cards"
FONT_DIR = ROOT / "fonts"

# ------------------------------------------------------------------ palette
BG = "#09090B"      # canvas
PANEL = "#101013"   # raised surface
LINE = "#23232A"    # hairlines, outlines
LINE2 = "#3A3A44"   # stronger outlines, chips
GRID = "#4A4A55"    # inactive marks, bars
DIM = "#6E6E7A"     # tertiary text
MUTED = "#9A9AA6"   # secondary text
TEXT = "#F4F4F6"    # primary text
WHITE = "#FFFFFF"   # primary accent
PURPLE = "#8B5CF6"  # data accent
DEEP = "#4C2BB8"    # solid purple fills
LILAC = "#C4B5FD"   # pale purple
PAGE, INK, GREY, CREAM, BLACK = BG, TEXT, MUTED, TEXT, BG

# ------------------------------------------------------------------ grid
W, M, CW, G = 880, 40, 800, 16
R_CARD, R_TAG = 2, 2


# ------------------------------------------------------------------ typography engine
class Face:
    """One font file: advances, outlines and GPOS pair kerning (pure fontTools)."""

    def __init__(self, path):
        self.font = TTFont(str(path))
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"]
        self.gs = self.font.getGlyphSet()
        self._paths, self._kern = {}, {}
        self._subs = self._load_kerning()

    def _load_kerning(self):
        subs = []
        if "GPOS" not in self.font:
            return subs
        gpos = self.font["GPOS"].table
        wanted = set()
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "kern":
                wanted.update(fr.Feature.LookupListIndex)
        for i in sorted(wanted):
            lk = gpos.LookupList.Lookup[i]
            for st in lk.SubTable:
                if lk.LookupType == 9:
                    st = st.ExtSubTable
                if st.__class__.__name__ != "PairPos":
                    continue
                cov = {g: n for n, g in enumerate(st.Coverage.glyphs)}
                subs.append((st, cov))
        return subs

    def glyph(self, ch):
        return self.cmap.get(ord(ch)) or self.cmap[ord("?")]

    def advance(self, g):
        return self.hmtx[g][0]

    def path(self, g):
        if g not in self._paths:
            pen = SVGPathPen(self.gs, ntos=lambda v: ("%g" % v))
            self.gs[g].draw(pen)
            self._paths[g] = pen.getCommands()
        return self._paths[g]

    def kern(self, a, b):
        key = (a, b)
        if key in self._kern:
            return self._kern[key]
        v = 0
        for st, cov in self._subs:
            if a not in cov:
                continue
            if st.Format == 1:
                found = False
                for rec in st.PairSet[cov[a]].PairValueRecord:
                    if rec.SecondGlyph == b:
                        v1 = rec.Value1
                        v = getattr(v1, "XAdvance", 0) if v1 else 0
                        found = True
                        break
                if found:
                    break
            else:
                c1 = st.ClassDef1.classDefs.get(a, 0)
                c2 = st.ClassDef2.classDefs.get(b, 0)
                v1 = st.Class1Record[c1].Class2Record[c2].Value1
                v = getattr(v1, "XAdvance", 0) if v1 else 0
                break
        self._kern[key] = v
        return v


FACES = {
    "r": Face(FONT_DIR / "Inter-Regular.otf"),
    "m": Face(FONT_DIR / "Inter-Medium.otf"),
    "s": Face(FONT_DIR / "Inter-SemiBold.otf"),
    "d": Face(FONT_DIR / "InterDisplay-SemiBold.otf"),
    "mono": Face(FONT_DIR / "DejaVuSansMono.ttf"),
    "monob": Face(FONT_DIR / "DejaVuSansMono-Bold.ttf"),
}


def layout(txt, size, wt, track):
    """Return ([(glyph, x_units)], total_units). Tracking is in em."""
    f = FACES[wt]
    tr = track * f.upm
    pos, x, prev = [], 0.0, None
    for ch in txt:
        g = f.glyph(ch)
        if prev is not None:
            x += f.kern(prev, g)
        pos.append((g, x))
        x += f.advance(g) + tr
        prev = g
    return pos, max(0.0, x - tr)


def measure(txt, size, wt="r", track=0.0):
    _, total = layout(txt, size, wt, track)
    return total * size / FACES[wt].upm


def wrap(txt, size, wt, maxw, track=0.0):
    lines, cur = [], ""
    for word in txt.replace(" \u00b7 ", "\u00a0\u00b7 ").split(" "):
        t = (cur + " " + word).strip()
        if cur and measure(t, size, wt, track) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Canvas:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.defs, self._ids = [], [], {}

    # ---- primitives
    def rect(self, x, y, w, h, fill, r=0):
        rr = f' rx="{n(r)}"' if r else ""
        self.parts.append(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"{rr} fill="{fill}"/>')

    def _rpath(self, x, y, w, h, fill, r, tl, tr, br, bl):
        a, b, c, d = (r if tl else 0), (r if tr else 0), (r if br else 0), (r if bl else 0)
        p = (f"M{n(x+a)},{n(y)} H{n(x+w-b)} " + (f"A{n(b)},{n(b)} 0 0 1 {n(x+w)},{n(y+b)} " if b else "")
             + f"V{n(y+h-c)} " + (f"A{n(c)},{n(c)} 0 0 1 {n(x+w-c)},{n(y+h)} " if c else "")
             + f"H{n(x+d)} " + (f"A{n(d)},{n(d)} 0 0 1 {n(x)},{n(y+h-d)} " if d else "")
             + f"V{n(y+a)} " + (f"A{n(a)},{n(a)} 0 0 1 {n(x+a)},{n(y)} " if a else "") + "Z")
        self.parts.append(f'<path d="{p}" fill="{fill}"/>')

    def rrect(self, x, y, w, h, fill, r=R_CARD, tl=True, tr=True, br=True, bl=True):
        """Rectangle with per-corner rounding. Cards get a grey outline."""
        if fill == PANEL:
            self._rpath(x, y, w, h, LINE, r, tl, tr, br, bl)
            self._rpath(x + 1.5, y + 1.5, w - 3, h - 3, PANEL, max(r - 1, 0), tl, tr, br, bl)
        else:
            self._rpath(x, y, w, h, fill, r, tl, tr, br, bl)

    def line(self, x1, y1, x2, y2, stroke=GREY, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" stroke="{stroke}" stroke-width="{n(sw)}"{d}/>')

    def hair(self, x1, x2, y, stroke=LINE):
        self.line(x1, y + .5, x2, y + .5, stroke, 1)

    def vhair(self, x, y1, y2, stroke=LINE):
        self.line(x + .5, y1, x + .5, y2, stroke, 1)

    def poly(self, pts, fill="none", stroke=None, sw=1, close=True):
        d = "M" + " L".join(f"{n(x)},{n(y)}" for x, y in pts) + (" Z" if close else "")
        s = f' stroke="{stroke}" stroke-width="{n(sw)}" stroke-linejoin="round"' if stroke else ""
        self.parts.append(f'<path d="{d}" fill="{fill}"{s}/>')

    # ---- text
    def _gid(self, wt, g):
        key = (wt, g)
        if key not in self._ids:
            gid = f"{wt}{len(self._ids)}"
            self._ids[key] = gid
            d = FACES[wt].path(g)
            if d:
                self.defs.append(f'<path id="{gid}" d="{d}"/>')
            else:
                self._ids[key] = None
        return self._ids[key]

    def text(self, x, y, txt, size=14, wt="r", fill=INK, anchor="start", track=0.0):
        """Baseline-anchored text drawn as outlines. Returns rendered width."""
        face = FACES[wt]
        pos, total = layout(txt, size, wt, track)
        sc = size / face.upm
        width = total * sc
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses = []
        for g, ux in pos:
            gid = self._gid(wt, g)
            if gid:
                uses.append(f'<use xlink:href="#{gid}" x="{n(ux)}"/>')
        if uses:
            self.parts.append(f'<g transform="translate({n(x)} {n(y)}) scale({sc:.5f} {-sc:.5f})" fill="{fill}">{"".join(uses)}</g>')
        return width

    def label(self, x, y, txt, fill=PURPLE, anchor="start", size=11):
        return self.text(x, y, txt.upper(), size, "m", fill, anchor, 0.08)

    def para(self, x, y, txt, size, wt, maxw, lh, fill=INK, track=0.0, first_black=False):
        lines = wrap(txt, size, wt, maxw, track)
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, size, wt, fill, "start", track)
        return len(lines)

    def tag(self, x, y, txt, fill=LINE, ink=TEXT, size=12, h=26, px=11, wt="r"):
        w = measure(txt, size, wt) + 2 * px
        self.rect(x, y, w, h, fill, R_TAG)
        self.text(x + px, y + h / 2 + 0.3637 * size, txt, size, wt, ink)
        return w

    def render(self):
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{n(self.w)}" height="{n(self.h)}" viewBox="0 0 {n(self.w)} {n(self.h)}" role="img" aria-label="{esc(self.title)}">\n'
                f'<title>{esc(self.title)}</title>{defs}\n'
                f'<rect width="{n(self.w)}" height="{n(self.h)}" fill="{PAGE}"/>\n' + "\n".join(self.parts) + "\n</svg>\n")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CAP = 0.7275  # Inter cap-height / em


def cell_layout(count, gutter=G):
    """Slices for a row of separately linked images that still align to the 800-wide grid."""
    cw = (CW - (count - 1) * gutter) / count
    out = []
    for i in range(count):
        left = M if i == 0 else gutter / 2
        right = M if i == count - 1 else gutter / 2
        out.append(dict(w=left + cw + right, x=left, cw=cw))
    return out


def pct(w):
    return f"{math.floor(w / W * 100000) / 1000:g}%"

# ------------------------------------------------------------------ canvas extensions
def _outline(self, x, y, w, h, stroke=LINE, r=R_CARD, sw=1):
    self.parts.append(f'<rect x="{n(x + sw / 2)}" y="{n(y + sw / 2)}" width="{n(w - sw)}" height="{n(h - sw)}" rx="{n(r)}" fill="none" stroke="{stroke}" stroke-width="{n(sw)}"/>')


def _dots(self, x, y, w, h, pitch=16, fill="#1C1C22", size=1.6):
    pid = f"dg{len(self.defs)}"
    self.defs.append(f'<pattern id="{pid}" x="{n(x)}" y="{n(y)}" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse"><rect width="{size}" height="{size}" fill="{fill}"/></pattern>')
    self.parts.append(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" fill="url(#{pid})"/>')


def _brackets(self, x, y, w, h, l=14, stroke=WHITE, sw=1.5):
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x + w, y + h, -1, -1), (x, y + h, 1, -1)):
        self.parts.append(f'<path d="M{n(px + dx * l)},{n(py)} H{n(px)} V{n(py + dy * l)}" fill="none" stroke="{stroke}" stroke-width="{n(sw)}"/>')


def _mono(self, x, y, txt, size=12, fill=MUTED, anchor="start", bold=False, track=0.0):
    return self.text(x, y, txt, size, "monob" if bold else "mono", fill, anchor, track)


def _mlabel(self, x, y, txt, fill=MUTED, anchor="start", size=10.5, bold=False):
    return self.text(x, y, txt.upper(), size, "monob" if bold else "mono", fill, anchor, 0.06)


def _chip(self, x, y, txt, size=12, h=26, px=11, wt="r", ink=TEXT, stroke=LINE2, fill=None, solid=None):
    w = measure(txt, size, wt) + 2 * px
    if solid:
        self.rect(x, y, w, h, solid, R_TAG)
    else:
        if fill:
            self.rect(x, y, w, h, fill, R_TAG)
        self.outline(x, y, w, h, stroke, R_TAG)
    self.text(x + px, y + h / 2 + 0.3637 * size, txt, size, wt, ink)
    return w


for _f in (_outline, _dots, _brackets, _mono, _mlabel, _chip):
    setattr(Canvas, _f.__name__.lstrip("_"), _f)
Canvas.label = lambda self, x, y, txt, fill=PURPLE, anchor="start", size=10.5: self.mlabel(x, y, txt, fill, anchor, size)


# ------------------------------------------------------------------ shared pieces
def section_header(idx, name, caption):
    c = Canvas(W, 124, f"{idx} {name}")
    c.rect(M, 24, CW, 1, LINE)
    c.rect(M, 23, 40, 3, WHITE)
    c.rect(M + CW - 6, 22, 6, 6, PURPLE)
    c.mono(M, 60, idx, 12, PURPLE, bold=True)
    c.mono(M + 26, 60, "/ 06", 12, DIM)
    c.mono(M + CW, 60, caption.lower(), 11.5, DIM, "end")
    c.text(M, 106, name, 38, "d", WHITE, track=-0.03)
    return c.render()


def card_columns(count):
    cw = (CW - (count - 1) * G) / count
    return [(M + i * (cw + G), cw) for i in range(count)]


# ------------------------------------------------------------------ hero
def hero():
    H = 480
    c = Canvas(W, H, "Abdullah Imran. ML Engineer and Data Scientist. Lahore, Pakistan.")
    c.dots(M, 72, CW, 260)
    c.rect(M, 24, CW, 1, LINE)
    c.rect(M, 23, 40, 3, WHITE)
    c.mono(M, 54, "~/abdullah-imran/profile", 11.5, DIM)
    sw = c.mlabel(M + CW, 54, "Available · roles & contracts", WHITE, "end", 11, True)
    c.rect(M + CW - sw - 16, 46, 7, 7, WHITE)

    c.text(M, 182, "Abdullah Imran", 64, "d", WHITE, track=-0.035)
    w1 = c.text(M, 228, "ML Engineer", 22, "m", WHITE, track=-0.01)
    c.text(M + w1 + 12, 228, "/", 22, "r", PURPLE)
    c.text(M + w1 + 34, 228, "Data Scientist", 22, "m", MUTED, track=-0.01)
    c.para(M, 266, "I build intelligent systems, machine learning solutions, AI-powered applications and data-driven products.", 15, "r", 450, 23, MUTED)
    tx = M
    for t_ in ["python", "pytorch", "fastapi", "rag", "langgraph", "docker", "pgvector"]:
        tx += c.chip(tx, 314, t_, 11, 24, 10, "mono", TEXT, LINE2, fill=BG) + 6

    px, py, pw = 560, 88, 280
    rows = 9
    ph = 40 + rows * 21 + 18
    c.rect(px, py, pw, ph, PANEL)
    c.outline(px, py, pw, ph, LINE)
    c.hair(px, px + pw, py + 32)
    c.mono(px + 16, py + 21, "whoami.sh", 11, MUTED)
    c.mono(px + pw - 16, py + 21, "zsh", 11, DIM, "end")
    y = py + 58
    def line(parts):
        nonlocal y
        x = px + 16
        for t_, col in parts:
            x += c.mono(x, y, t_, 12, col)
        y += 21
    line([("$ ", PURPLE), ("whoami", WHITE)])
    line([("abdullah-imran", MUTED)])
    y += 21
    line([("$ ", PURPLE), ("cat status.txt", WHITE)])
    for k, v in (("role", "ml_engineer"), ("base", "lahore_pk · remote"), ("focus", "ml · genai · vision"), ("status", "open_to_work")):
        line([(f"{k:<8}", DIM), (v, WHITE if k == "status" else TEXT)])
    c.mono(px + 16, y, "$ ", 12, PURPLE)
    c.rect(px + 16 + 14.4, y - 11, 8, 14, WHITE)
    c.brackets(px - 7, py - 7, pw + 14, ph + 14, 12, WHITE, 1.5)

    sy = 362
    c.rect(M, sy, CW, 96, WHITE)
    stats = [("13", "Systems shipped"), ("6", "Certifications"), ("5", "Roles & communities"), ("90%", "Model accuracy")]
    for i, (big, lab) in enumerate(stats):
        x = M + i * 200
        c.text(x + 28, sy + 56, big, 40, "d", BG, track=-0.035)
        c.mlabel(x + 28, sy + 78, lab, "#3A3A44", size=10, bold=True)
        if i:
            c.rect(x, sy + 18, 1, 60, "#D4D4DA")
    return c.render()


# ------------------------------------------------------------------ nav
NAV = [("about", "About"), ("journey", "Journey"), ("systems", "Systems"), ("stack", "Stack"), ("activity", "Activity"), ("contact", "Contact")]


def nav_cell(i):
    L = cell_layout(len(NAV), 0)[i]
    c = Canvas(L["w"], 56, f"{NAV[i][1]}")
    x0 = M if i == 0 else 0
    x1 = L["w"] - (M if i == len(NAV) - 1 else 0)
    c.rect(x0, 0, x1 - x0, 1, LINE)
    c.hair(x0, x1, 55)
    pad = 14
    c.mono(x0 + pad, 33, f"{i+1:02d}", 11, PURPLE, bold=True)
    c.mono(x0 + pad + 26, 33, NAV[i][1].lower(), 11.5, WHITE)
    if i < len(NAV) - 1:
        c.vhair(x1 - 1, 1, 55)
    return c.render()


# ------------------------------------------------------------------ about
def yaml_tokens(s):
    toks = []
    ind = len(s) - len(s.lstrip())
    toks.append((s[:ind], TEXT))
    s = s.lstrip()
    com, trail = "", ""
    if "#" in s:
        s, com = s.split("#", 1)
        com = "#" + com
        trail = s[len(s.rstrip()):]
        s = s.rstrip()
    if s.startswith("- "):
        toks += [("- ", DIM), (s[2:], LILAC)]
    elif ":" in s:
        k, v = s.split(":", 1)
        toks += [(k, TEXT), (":", DIM)]
        lead = v[:len(v) - len(v.lstrip())]
        v = v.strip()
        toks.append((lead, TEXT))
        if v == "true":
            toks.append((v, WHITE))
        elif v.isdigit():
            toks.append((v, PURPLE))
        elif v.startswith("["):
            items = v[1:-1].split(", ")
            toks.append(("[", DIM))
            for j, it in enumerate(items):
                toks.append((it, LILAC))
                if j < len(items) - 1:
                    toks.append((", ", DIM))
            toks.append(("]", DIM))
        elif v:
            toks.append((v, LILAC))
    else:
        toks.append((s, LILAC))
    if com:
        toks.append((trail, TEXT))
        toks.append((com, DIM))
    return toks


YAML = ["name: abdullah_imran", "role: [ml_engineer, data_scientist]", "location: lahore_pk  # remote", "focus:", "  - machine_learning", "  - generative_ai",
        "  - computer_vision", "stack: [python, sql, fastapi]", "shipped:", "  systems: 13", "  certifications: 6", "principles:", "  - grounding_over_fluency",
        "  - safety_gates_first", "  - observable_agents", "open_to_work: true"]


def about():
    H = 470
    c = Canvas(W, H + 16, "About Abdullah Imran. ML Engineer and Data Scientist, shown as a profile.yaml file.")
    pw = 368
    c.rect(M, 0, pw, H, PANEL)
    c.outline(M, 0, pw, H, LINE)
    c.hair(M, M + pw, 36)
    c.rect(M + 16, 15, 7, 7, WHITE)
    c.mono(M + 32, 23, "profile.yaml", 11, WHITE)
    c.mono(M + pw - 16, 23, "main", 11, DIM, "end")
    for i, ln in enumerate(YAML):
        y = 70 + i * 21.5
        c.mono(M + 36, y, f"{i+1:>2}", 11, GRID, "end")
        x = M + 54
        for t_, col in yaml_tokens(ln):
            x += c.mono(x, y, t_, 12, col, bold=(col == WHITE and t_ == "true"))
    c.hair(M, M + pw, H - 34)
    c.mono(M + 16, H - 13, "yaml  ·  utf-8", 10.5, DIM)
    c.mono(M + pw - 16, H - 13, f"{len(YAML)} lines", 10.5, DIM, "end")

    x = M + pw + 16
    w = W - M - x
    c.mono(x, 14, "// about", 11.5, PURPLE, bold=True)
    k = c.para(x, 62, "ML Engineer and Data Scientist. I turn messy data and ambiguous problems into measurable, deployable intelligence.", 22, "m", w, 31, WHITE, track=-0.015)
    y = 62 + (k - 1) * 31 + 38
    c.para(x, y, "My work spans classical machine learning and statistical modeling through to LLM applications, retrieval pipelines and computer vision. I write the Python and SQL, build the FastAPI services around the models, and integrate them into the systems that use them.", 14, "r", w, 22, MUTED)
    ny, nh = H - 132, 132
    c.rect(x, ny, w, nh, WHITE)
    c.rect(x + 24, ny + 26, 7, 7, BG)
    c.mlabel(x + 40, ny + 34, "Now", BG, size=10.5, bold=True)
    c.text(x + 24, ny + 66, "Freelance ML Engineer & Data Scientist", 16, "s", BG, track=-0.01)
    c.para(x + 24, ny + 92, "Independent and remote since October 2026. Open to roles and client contracts.", 13, "r", w - 48, 20, "#3A3A44")
    c.brackets(x - 5, ny - 5, w + 10, nh + 10, 10, PURPLE, 1.5)
    return c.render()


def grid_panel(c, y, items, cols, cell_h, draw, line=LINE):
    cw = CW / cols
    rows = math.ceil(len(items) / cols)
    c.rrect(M, y, CW, rows * cell_h, PANEL)
    for r in range(1, rows):
        c.rect(M + 1, y + r * cell_h - 1, CW - 2, 1, line)
    for k in range(1, cols):
        c.rect(M + k * cw - 1, y + 1, 1, rows * cell_h - 2, line)
    for i, it in enumerate(items):
        draw(c, M + (i % cols) * cw, y + (i // cols) * cell_h, cw, it, i)
    return y + rows * cell_h


def practice():
    items = [("ML/DL", "Machine Learning & Deep Learning", "Model design, training, evaluation and tuning."),
             ("STATS", "Statistical Analysis & Predictive Modeling", "Turning data into forecasts and decisions."),
             ("GENAI", "Generative AI, LLMs & RAG", "Grounded, retrieval-backed language applications."),
             ("CV/NLP", "Computer Vision & NLP", "Perception and language models in real products."),
             ("API", "Python, SQL & FastAPI", "Backend engineering around the model."),
             ("AUTO", "AI Integration & Automation", "Intelligent workflows wired into existing systems.")]
    ch = 152
    c = Canvas(W, 2 * ch + 16, "Capabilities: machine learning, statistics, generative AI, computer vision and NLP, backend, automation")

    def draw(cv, x, y, w, it, i):
        tag, t, b = it
        cv.mono(x + 22, y + 34, f"[{tag}]", 11, PURPLE, bold=True)
        cv.mono(x + w - 22, y + 34, f"{i+1:02d}", 11, GRID, "end")
        yy = y + 70
        for ln in wrap(t, 15, "s", w - 44, -0.01):
            cv.text(x + 22, yy, ln, 15, "s", WHITE, track=-0.01)
            yy += 20
        yy += 4
        for ln in wrap(b, 12.5, "r", w - 44):
            cv.text(x + 22, yy, ln, 12.5, "r", MUTED)
            yy += 18
    grid_panel(c, 0, items, 3, ch, draw)
    return c.render()


# ------------------------------------------------------------------ journey (gantt timeline)
EVENTS = [("UMT Google Developers Club", "Leadership & community \u00b7 Lahore", (2024, 8), (2025, 9)),
          ("Cosmi Code", "Machine Learning Intern \u00b7 Remote", (2024, 9), (2024, 12)),
          ("UET \u00d7 Devsinc", "AI/ML Fellow \u00b7 Lahore", (2025, 1), (2025, 3)),
          ("Sunsprinkle", "Junior Machine Learning Engineer \u00b7 Lahore", (2025, 11), (2026, 10)),
          ("Freelance", "ML Engineer & Data Scientist \u00b7 Remote", (2026, 10), None)]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def timeline():
    base = (2024, 8)
    mi = lambda ym: (ym[0] - base[0]) * 12 + (ym[1] - base[1])
    today = dt.date.today()
    tnow = mi((today.year, today.month)) + (today.day - 1) / 30
    span = max(29, math.ceil(tnow) + 2)
    x0, x1 = M + 262, M + CW
    pm = (x1 - x0) / span
    lane, top = 66, 96
    H = top + len(EVENTS) * lane + 44
    c = Canvas(W, H, "Career timeline: UMT Google Developers Club, Cosmi Code, UET x Devsinc, Sunsprinkle, Freelance")
    c.mono(M, 26, "// timeline", 11.5, PURPLE, bold=True)
    c.mono(M + CW, 26, "aug 2024 \u2192 present", 11.5, DIM, "end")
    c.rect(M, 44, CW, 1, LINE)
    for m in range(span):
        y_, mo = base[0] + (base[1] - 1 + m) // 12, (base[1] - 1 + m) % 12
        if mo % 3 == 0:
            x = x0 + m * pm
            c.rect(x, 84, 1, len(EVENTS) * lane + 8, LINE)
            c.mono(x + 5, 76, f"{MONTHS[mo]} {str(y_)[2:]}".upper(), 9.5, WHITE if mo == 0 else DIM, bold=(mo == 0))
    for i, (org, role, s, e) in enumerate(EVENTS):
        y = top + i * lane
        c.hair(M, M + CW, y - 6, LINE)
        c.text(M, y + 22, org, 15, "s", WHITE, track=-0.01)
        yy = y + 40
        for ln in wrap(role, 12, "r", 240):
            c.text(M, yy, ln, 12, "r", MUTED)
            yy += 16
        a = x0 + mi(s) * pm
        cur = e is None
        b = x0 + (tnow if cur else mi(e) + 1) * pm
        c.rect(a, y + 18, max(b - a, 4), 16, WHITE if cur else PURPLE, 2)
        lab = f"{MONTHS[s[1]-1]} {str(s[0])[2:]} \u2013 " + ("now" if cur else f"{MONTHS[e[1]-1]} {str(e[0])[2:]}")
        tw = measure(lab, 10, "mono")
        if b + 10 + tw <= x1:
            c.mono(b + 10, y + 30, lab, 10, DIM)
        else:
            c.mono(a - 10, y + 30, lab, 10, WHITE if cur else DIM, "end")
    yb = top + len(EVENTS) * lane
    tx = x0 + tnow * pm
    c.line(tx, 84, tx, yb + 2, WHITE, 1, "3 3")
    c.rect(tx - 3, yb + 2, 7, 7, WHITE)
    c.mlabel(tx, yb + 26, "today", WHITE, "middle", 9.5, True)
    return c.render()


def now():
    H = 264
    c = Canvas(W, H + 16, "Active development: SupplyChainIQ. Also currently exploring.")
    lw = 488
    rx, rw = M + lw + G, CW - lw - G
    c.rrect(M, 0, lw, H, PANEL)
    c.rrect(rx, 0, rw, H, PANEL)
    c.mono(M + 24, 38, "// active development", 11, PURPLE, bold=True)
    c.hair(M + 24, M + lw - 24, 58)
    c.text(M + 24, 100, "SupplyChainIQ", 26, "d", WHITE, track=-0.025)
    k = c.para(M + 24, 128, "Agentic GraphRAG platform for supply chain risk and dependency intelligence.", 13.5, "r", lw - 48, 21, MUTED)
    tx = M + 24
    for t_ in ["Neo4j", "LangGraph", "FastAPI", "pgvector"]:
        tx += c.chip(tx, 128 + (k - 1) * 21 + 20, t_, 11, 24, 10, "mono", TEXT, LINE2) + 6
    c.hair(M + 24, M + lw - 24, H - 56)
    c.rect(M + 24, H - 33, 7, 7, WHITE)
    c.mlabel(M + 40, H - 26, "In development", WHITE, size=10, bold=True)
    c.mlabel(M + lw - 24, H - 26, "Started Nov 2026", PURPLE, "end", 10, True)
    c.mono(rx + 24, 38, "// exploring", 11, PURPLE, bold=True)
    c.hair(rx + 24, rx + rw - 24, 58)
    x, y = rx + 24, 80
    for s_ in ["Agentic AI", "Multimodal fusion", "pgvector", "RBAC & multi-tenancy", "Next.js dashboards", "Production MLOps"]:
        w = measure(s_, 12, "r") + 22
        if x + w > rx + rw - 24:
            x, y = rx + 24, y + 34
        c.chip(x, y, s_, 12, 26, 11)
        x += w + 6
    return c.render()


# ------------------------------------------------------------------ systems
REPOS = [
    ("CareerOS AI", "Career intelligence \u00b7 RAG", "Evidence-driven readiness: every CV skill claim is checked against GitHub, certificates and docs before it counts.", ["Django", "pgvector", "LangGraph", "Celery"],
     "https://github.com/abdullahmran-101/CareerOS-AI"),
    ("HealMatrix AI", "Healthcare \u00b7 Multimodal", "Crisis-gated multimodal assistant fusing text, voice, face and posture.", ["RAG", "RoBERTa", "FastAPI", "Docker"],
     "https://github.com/abdullahmran-101/Heal-Matrix-AI"),
    ("Cheatify", "Computer vision", "Real-time exam proctoring with object detection, pose and gaze risk scoring.", ["YOLOv12", "MediaPipe", "OpenCV"],
     "https://github.com/abdullahmran-101/Cheatify-AI-Proctoring-System"),
    ("AgentFlow AI", "Agents", "Multi-provider ReAct platform with live tool traces, memory and failover.", ["LangGraph", "SSE", "FastAPI"],
     "https://github.com/abdullahmran-101/Agentflow-AI"),
    ("Research Forge AI", "RAG \u00b7 Research", "Self-hosted research-to-report pipeline with citation enforcement.", ["SearXNG", "ChromaDB", "Celery"],
     "https://github.com/abdullahmran-101/Research-Forge-AI"),
]


def repo_height(single=False):
    cw = cell_layout(1 if single else 2)[0]["cw"]
    hs = []
    for name, dom, desc, tags, _ in (REPOS[-1:] if single else REPOS[:-1] if len(REPOS) % 2 else REPOS):
        k = len(wrap(desc, 14, "r", cw - 56))
        hs.append(128 + k * 22 + 20 + 26 + 28 + 56 - 20)
    return max(hs)


def repo(i):
    L = cell_layout(1)[0] if (i == len(REPOS) - 1 and len(REPOS) % 2) else cell_layout(2)[i % 2]
    name, dom, desc, tags, url = REPOS[i]
    H = repo_height(i == len(REPOS) - 1 and len(REPOS) % 2 == 1)
    c = Canvas(L["w"], H + 16, f"{name}. {desc}")
    x, cw = L["x"], L["cw"]
    c.rrect(x, 0, cw, H, PANEL)
    c.parts.append(f'<path d="M{n(x)},{n(22)} V{n(0)} H{n(x + 22)}" fill="none" stroke="{WHITE}" stroke-width="2"/>')
    c.mlabel(x + 28, 40, dom, PURPLE, size=10.5, bold=True)
    c.mono(x + cw - 28, 40, f"{i+1:02d}", 11, DIM, "end")
    c.text(x + 28, 92, name, 28, "d", WHITE, track=-0.025)
    k = c.para(x + 28, 126, desc, 14, "r", cw - 56, 22, MUTED)
    ty = 126 + (k - 1) * 22 + 24
    tx = x + 28
    for t in tags:
        tx += c.chip(tx, ty, t, 11, 24, 10, "mono", TEXT, LINE2) + 6
    c.hair(x + 28, x + cw - 28, H - 56, LINE)
    c.text(x + 28, H - 24, "View repository", 13, "s", WHITE)
    c.text(x + cw - 28, H - 24, "\u2197", 15, "r", WHITE, "end")
    return c.render()


CATALOGUE = [("CareerOS AI", "Career intelligence \u00b7 RAG", "Django \u00b7 pgvector \u00b7 LangGraph"), ("HealMatrix AI", "Healthcare \u00b7 Multimodal", "LLaMA 3.3 \u00b7 FAISS \u00b7 RoBERTa"), ("VITA", "Healthcare \u00b7 Multimodal", "Transformer fusion \u00b7 ElevenLabs"),
             ("Cheatify", "Computer vision", "YOLOv12 \u00b7 MediaPipe"), ("IntelliFall AI", "CV \u00b7 IoT", "Fall detection system"),
             ("MalVision AI", "Security \u00b7 XAI", "Streamlit \u00b7 explainability"), ("Research Forge AI", "RAG \u00b7 Research", "SearXNG \u00b7 ChromaDB \u00b7 Celery"),
             ("AgentFlow AI", "Agents", "LangGraph \u00b7 SSE \u00b7 SQLite"), ("Pocho AI", "RAG", "Django \u00b7 TF-IDF \u00b7 Grok"),
             ("QuickByte AI", "LLM application", "Nutrition-focused LLM platform"), ("WhatsAgent AI", "Automation", "n8n \u00b7 Twilio \u00b7 Airtable"),
             ("Quantifier AI", "Automation", "Lead scoring: HOT \u00b7 WARM \u00b7 COLD"), ("FraudShield AI", "Predictive ML", "scikit-learn")]


def catalogue():
    ch = 116
    H = 48 + 4 * ch + 16
    c = Canvas(W, H, "All 13 shipped systems by domain")
    c.mono(M, 26, "// all shipped systems", 11.5, PURPLE, bold=True)
    c.mono(M + CW, 26, "13 total", 11.5, WHITE, "end", bold=True)

    def draw(cv, x, y, w, it, i):
        nm, dom, tech = it
        cv.text(x + 20, y + 36, nm, 15, "s", WHITE, track=-0.01)
        yy = y + 58
        for ln in wrap(dom.upper(), 9.5, "mono", w - 40, 0.06):
            cv.text(x + 20, yy, ln, 9.5, "mono", DIM, track=0.06)
            yy += 14
        yy += 6
        for ln in wrap(tech, 12, "r", w - 40):
            cv.text(x + 20, yy, ln, 12, "r", MUTED)
            yy += 17
    grid_panel(c, 48, CATALOGUE, 4, ch, draw)
    bx = M + CW / 4
    by = 48 + 3 * ch
    c.rect(bx + 1, by + 1, 3 * CW / 4 - 2, ch - 2, WHITE)
    c.rect(bx + 24, by + 28, 7, 7, BG)
    c.mlabel(bx + 40, by + 36, "In development", BG, size=10.5, bold=True)
    c.text(bx + 24, by + 72, "SupplyChainIQ \u00b7 Agentic GraphRAG for supply chain risk", 15, "s", BG, track=-0.01)
    return c.render()


# ------------------------------------------------------------------ stack
SKILLS = [
    ("Full-Stack Web Development & APIs",
     ["Python", "Next.js", "HTML5 / CSS3", "FastAPI", "Django", "Flask", "Django REST Framework", "REST APIs", "Pydantic", "WebSockets", "Celery"]),
    ("Databases", ["PostgreSQL", "SQL", "MongoDB", "Airtable", "Redis", "Vector DBs: FAISS, ChromaDB, Weaviate, Pinecone"]),
    ("Generative AI, LLMs & RAG",
     ["Large Language Models", "LLM Fine-Tuning", "OpenAI API", "Google Gemini API", "Grok API", "Groq API", "Ollama Models", "Hugging Face",
      "AI Agents & Automation", "n8n \u00b7 Zapier", "Function Calling & Tool Use", "Embeddings & Semantic Search", "RAG", "Agentic RAG", "Graph RAG",
      "Chunking & Re-ranking", "LangChain", "LangGraph", "LangSmith", "Ragas / DeepEval", "Model Context Protocol (MCP)", "Prompt Engineering"]),
    ("Machine Learning & Computer Vision",
     ["PyTorch", "TensorFlow", "Keras", "Scikit-learn", "XGBoost / LightGBM", "CNN", "Hugging Face Transformers", "Model Fine-Tuning", "LoRA / PEFT",
      "Computer Vision", "OpenCV", "YOLO", "MediaPipe", "Multimodal AI", "Faster R-CNN", "Object Tracking (DeepSORT)", "Image Segmentation"]),
    ("Cloud & Deployment", ["AWS SageMaker", "Docker", "CI/CD", "MLflow", "Streamlit", "Hugging Face Spaces", "Modal", "Vercel", "Netlify"]),
    ("AI-Assisted Development", ["Claude Code", "Cursor", "GitHub Copilot", "AI-Assisted Debugging", "AI Code Review & Validation"]),
]
CORE = {"Python", "PyTorch", "FastAPI", "RAG", "LangGraph", "Docker"}


def skills():
    x0, xmax, th, gap = 280, M + CW, 26, 6
    groups, H = [], 44
    for name, items in SKILLS:
        placed, x, row = [], x0, 0
        for it in items:
            w = measure(it, 12, "r") + 22
            if x + w > xmax:
                x, row = x0, row + 1
            placed.append((it, x, row, w))
            x += w + gap
        left = wrap(name, 16, "s", 200, -0.01)
        h = max((row + 1) * (th + gap) - gap, len(left) * 22 + 22) + 48
        groups.append((name, left, placed, row, H, h, len(items)))
        H += h
    H += 16
    c = Canvas(W, H, "Skills: " + "; ".join(s[0] for s in SKILLS))
    c.mono(M, 26, "// full skill matrix", 11.5, PURPLE, bold=True)
    lw = c.mono(M + CW, 26, "core stack", 11, DIM, "end")
    c.rect(M + CW - lw - 22, 17, 12, 12, WHITE, 2)
    c.rect(M, 44, CW, 1, LINE)
    for name, left, placed, rows, y, h, cnt in groups:
        top = y + 24
        for i, ln in enumerate(left):
            c.text(M, top + 16 + i * 22, ln, 16, "s", WHITE, track=-0.01)
        c.mono(M, top + 16 + len(left) * 22 + 4, f"{cnt:02d} skills", 10.5, PURPLE, bold=True)
        for it, x, row, w in placed:
            if it in CORE:
                c.chip(x, top + row * (th + gap), it, 12, th, 11, "m", BG, solid=WHITE)
            else:
                c.chip(x, top + row * (th + gap), it, 12, th, 11, "r", TEXT, LINE2)
        if y + h < H - 16:
            c.hair(M, M + CW, y + h - 1)
    return c.render()


def pipeline():
    steps = [("Perceive", ["Computer vision", "Whisper speech", "Text & documents"]), ("Retrieve", ["FAISS \u00b7 ChromaDB", "BGE embeddings", "Cross-encoder rerank"]),
             ("Reason", ["LLMs & ReAct agents", "Provider routing", "Policy & safety gates"]), ("Serve", ["FastAPI \u00b7 Django", "Celery \u00b7 Redis", "SSE live traces"]),
             ("Ship", ["Docker \u00b7 Compose", "VPS deployment", "n8n automation"])]
    top, nh, nw = 56, 176, 148
    pitch = (CW - nw) / 4
    c = Canvas(W, top + nh + 16, "How I build: perceive, retrieve, reason, serve, ship")
    c.mono(M, 26, "// how i build", 11.5, PURPLE, bold=True)
    c.mono(M + CW, 26, "grounded outputs \u00b7 observable agents \u00b7 deployable by default", 10.5, DIM, "end")
    for i, (nm, items) in enumerate(steps):
        x = M + i * pitch
        last = i == len(steps) - 1
        if last:
            c.rect(x, top, nw, nh, WHITE)
        else:
            c.rrect(x, top, nw, nh, PANEL)
        c.mono(x + 18, top + 32, f"{i+1:02d}", 11, BG if last else PURPLE, bold=True)
        c.text(x + 18, top + 70, nm, 20, "d", BG if last else WHITE, track=-0.02)
        c.rect(x + 18, top + 88, 24, 1, "#3A3A44" if last else LINE2)
        for k, s in enumerate(items):
            col = BG if last else (WHITE if k == 0 else MUTED)
            c.text(x + 16, top + 114 + k * 21, s, 11.5, "m" if k == 0 else "r", col if k == 0 else ("#3A3A44" if last else MUTED))
        if not last:
            xe, ym = x + nw, top + 28
            c.line(xe, ym, x + pitch, ym, WHITE, 1)
            c.poly([(x + pitch - 6, ym - 4), (x + pitch, ym), (x + pitch - 6, ym + 4)], WHITE)
    return c.render()


# ------------------------------------------------------------------ activity data
def fetch_days():
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        q = "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"
        req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": q, "variables": {"u": USER}}).encode(),
                                     headers={"Authorization": f"bearer {tok}", "Content-Type": "application/json", "User-Agent": "readme-cards"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                weeks = json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            return [(d["date"], d["contributionCount"]) for wk in weeks for d in wk["contributionDays"]], True
        except Exception as e:  # noqa
            print("GitHub fetch failed, using sample data:", e)
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    days, d = [], start
    while d <= today:
        v = 0 if rnd.random() < .38 else rnd.randint(1, 14) + (4 if d.weekday() < 5 and rnd.random() < .3 else 0)
        days.append((d.isoformat(), v))
        d += dt.timedelta(days=1)
    print("NOTE: sample contribution data in use. Set GITHUB_TOKEN for real data.")
    return days, False


def weekly(days):
    return [sum(v for _, v in days[i:i + 7]) for i in range(0, len(days), 7)]


def kpi_values(days):
    wk = weekly(days)
    counts = [v for _, v in days]
    act = [v for v in counts if v]
    cur, k = 0, len(days) - 1
    if k >= 0 and days[k][1] == 0:
        k -= 1
    while k >= 0 and days[k][1] > 0:
        cur, k = cur + 1, k - 1
    return round(100 * len(act) / max(1, len(counts))), sum(act) / max(1, len(act)), max(wk), cur


LIVE = True
SAMPLE_NOTE = "Sample data \u00b7 replaced by live GitHub data on the first workflow run"


def kpis(days):
    pc, avg, best, cur = kpi_values(days)
    items = [(f"{pc}%", "Active days", "of the last 12 months"), (f"{avg:.1f}", "Avg per active day", "contributions"),
             (str(best), "Best week", "contributions in 7 days"), (str(cur), "Current streak", "days in a row")]
    H = 128
    c = Canvas(W, H + 16, "Activity summary: " + "; ".join(f"{b} {l}" for b, l, _ in items))
    for (x, cw), (big, lab, sub) in zip(card_columns(4), items):
        c.rrect(x, 0, cw, H, PANEL)
        c.parts.append(f'<path d="M{n(x)},18 V0 H{n(x + 18)}" fill="none" stroke="{WHITE}" stroke-width="2"/>')
        c.mlabel(x + 22, 36, lab, DIM, size=10, bold=True)
        c.text(x + 22, 84, big, 42, "d", WHITE, track=-0.035)
        c.text(x + 22, 108, sub, 12, "r", MUTED)
    return c.render()


HEAT = (0, GRID, DEEP, PURPLE, WHITE)


def heatmap(days):
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    cols = len(weeks)
    x0, x1 = M + 36, M + CW
    pitch = (x1 - x0) / cols
    cell = pitch - 3
    mx = max((v for _, v in days), default=1) or 1
    total = sum(v for _, v in days)
    top = 92
    H = top + 7 * pitch + 78
    c = Canvas(W, int(H), f"Contribution heatmap: {total:,} contributions in the last 12 months")
    c.mono(M, 26, "// contributions", 11.5, PURPLE, bold=True)
    c.mono(M + CW, 26, f"{total:,} in the last 12 months", 11.5, WHITE, "end", bold=True)
    c.rect(M, 44, CW, 1, LINE)
    last_m, last_c = None, -9
    for ci, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0][0]).strftime("%b")
        if m != last_m and ci - last_c >= 3:
            c.mono(x0 + ci * pitch, 78, m.lower(), 10.5, DIM)
            last_m, last_c = m, ci
        for ri, (_, v) in enumerate(wk):
            lvl = 0 if v == 0 else 1 + min(3, int(v * 4 / (mx + 1)))
            x, y = x0 + ci * pitch, top + ri * pitch
            if lvl:
                s = cell * (0, .55, .7, .85, 1)[lvl]
                c.rect(x + (cell - s) / 2, y + (cell - s) / 2, s, s, HEAT[lvl])
            else:
                c.rect(x + cell / 2 - 1, y + cell / 2 - 1, 2, 2, LINE2)
    for ri, nm in ((0, "mon"), (2, "wed"), (4, "fri")):
        c.mono(M, top + ri * pitch + cell / 2 + 4, nm, 10.5, DIM)
    ly = top + 7 * pitch + 28
    lx = M + CW - 5 * (cell + 5) - 70
    c.mono(M, ly + cell / 2 + 4, "each mark is a day" if LIVE else SAMPLE_NOTE.lower(), 10.5, DIM if LIVE else WHITE)
    c.mono(lx - 8, ly + cell / 2 + 4, "less", 10.5, DIM, "end")
    for k in range(5):
        x = lx + k * (cell + 5)
        if k:
            s = cell * (0, .55, .7, .85, 1)[k]
            c.rect(x + (cell - s) / 2, ly + (cell - s) / 2, s, s, HEAT[k])
        else:
            c.rect(x + cell / 2 - 1, ly + cell / 2 - 1, 2, 2, LINE2)
    c.mono(lx + 5 * (cell + 5) + 3, ly + cell / 2 + 4, "more", 10.5, DIM)
    return c.render()


def weekday_trend(days):
    H = 308
    c = Canvas(W, H + 16, "Most active weekday and weekly contribution trend")
    (xa, cwa), (xb, cwb) = card_columns(2)
    c.rrect(xa, 0, cwa, H, PANEL)
    c.rrect(xb, 0, cwb, H, PANEL)
    tot = [0] * 7
    for ds, v in days:
        tot[dt.date.fromisoformat(ds).weekday()] += v
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    mx = max(tot) or 1
    bi = tot.index(mx)
    c.mono(xa + 24, 38, "// weekday", 11, PURPLE, bold=True)
    c.mono(xa + cwa - 24, 38, f"{names[bi]} leads", 11, WHITE, "end", bold=True)
    base = 256
    c.hair(xa + 24, xa + cwa - 24, base)
    pitch = (cwa - 48) / 7
    bw = 22
    for i, v in enumerate(tot):
        bh = max(3, v / mx * 150)
        x = xa + 24 + i * pitch + (pitch - bw) / 2
        c.rect(x, base - bh, bw, bh, WHITE if i == bi else GRID)
        c.mono(x + bw / 2, base - bh - 9, str(v), 10.5, WHITE if i == bi else MUTED, "middle")
        c.mono(x + bw / 2, base + 22, names[i], 10.5, WHITE if i == bi else DIM, "middle")

    wk = weekly(days)
    c.mono(xb + 24, 38, "// weekly trend", 11, PURPLE, bold=True)
    x0, x1, y0, y1 = xb + 24, xb + cwb - 24, 100, 256
    wm = max(wk) or 1
    pts = [(x0 + i * (x1 - x0) / (len(wk) - 1), y1 - v / wm * (y1 - y0)) for i, v in enumerate(wk)]
    c.poly(pts + [(x1, y1), (x0, y1)], DEEP)
    c.poly(pts, "none", LILAC, 2, close=False)
    avg = sum(wk) / len(wk)
    ay = y1 - avg / wm * (y1 - y0)
    c.line(x0, ay, x1, ay, MUTED, 1, "3 4")
    c.hair(x0, x1, y1)
    c.mono(xb + cwb - 24, 38, f"avg {avg:.0f} / week", 11, WHITE, "end", bold=True)
    c.rect(pts[-1][0] - 5, pts[-1][1] - 5, 10, 10, WHITE)
    c.mono(x0, y1 + 22, "52 weeks ago", 10.5, DIM)
    c.mono(x1, y1 + 22, "this week", 10.5, DIM, "end")
    return c.render()


def monthly(days):
    months = {}
    for ds, v in days:
        d = dt.date.fromisoformat(ds)
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + v
    keys = sorted(months)[-12:]
    vals = [months[k] for k in keys]
    top = max(vals) or 1
    best = max(days, key=lambda t: t[1])
    streak = run = 0
    for _, v in days:
        run = run + 1 if v else 0
        streak = max(streak, run)
    total = sum(v for _, v in days)
    H = 296
    c = Canvas(W, H + 16, f"Contributions by month. Total {total:,}, longest streak {streak} days, busiest day {best[0]} with {best[1]}")
    c.rrect(M, 0, CW, H, PANEL)
    c.mono(M + 24, 38, "// contributions by month", 11, PURPLE, bold=True)
    base, pitch, bw = 244, 40.5, 24
    c.hair(M + 24, M + 24 + 12 * pitch, base)
    for i, (k, v) in enumerate(zip(keys, vals)):
        bh = max(3, v / top * 140)
        x = M + 24 + i * pitch + (pitch - bw) / 2
        c.rect(x, base - bh, bw, bh, WHITE if v == top else GRID)
        c.mono(x + bw / 2, base - bh - 9, str(v), 10.5, WHITE if v == top else MUTED, "middle")
        c.mono(x + bw / 2, base + 22, dt.date(k[0], k[1], 1).strftime("%b").lower(), 10.5, DIM, "middle")
    sx = M + 24 + 12 * pitch + 24
    c.vhair(sx - 12, 24, H - 24)
    stats = [("Total", f"{total:,}"), ("Longest streak", f"{streak} days"), (f"Busiest day \u00b7 {best[0]}", str(best[1]))]
    for i, (lab, val) in enumerate(stats):
        y = 38 + i * 84
        c.mlabel(sx + 12, y, lab, DIM, size=9.5, bold=True)
        c.text(sx + 12, y + 40, val, 30, "d", WHITE, track=-0.03)
        if i < 2:
            c.hair(sx + 12, M + CW - 24, y + 62)
    return c.render()


# ------------------------------------------------------------------ contact + footer
def engage():
    E = [("Full-time role", "AI/ML engineering, applied GenAI, backend intelligence."), ("Contract build", "RAG systems, agents, LLM apps, computer vision pipelines."),
         ("Automation", "n8n and Zapier workflows with LLM decision steps."), ("Prototype to production", "Notebook or demo to a FastAPI service with Docker deploy.")]
    cols = card_columns(4)
    k = max(len(wrap(b, 13, "r", cols[0][1] - 2)) for _, b in E)
    H = 52 + 54 + k * 20 + 16 + 16
    c = Canvas(W, H, "Work with me: full-time, contract builds, automation, prototype to production")
    c.mono(M, 26, "// work with me", 11.5, PURPLE, bold=True)
    for (x, cw), (t, b), i in zip(cols, E, range(4)):
        c.rect(x, 44, cw, 1, LINE2)
        c.rect(x, 43, 24, 3, WHITE)
        c.mono(x, 78, f"{i+1:02d}", 10.5, PURPLE, bold=True)
        c.text(x, 106, t, 16, "s", WHITE, track=-0.01)
        c.para(x, 132, b, 13, "r", cw - 2, 20, MUTED)
    return c.render()


CONTACTS = [("Primary email", "abdullahmran96@gmail.com", "mailto:abdullahmran96@gmail.com"),
            ("Alternative email", "abdullahmran.001@gmail.com", "mailto:abdullahmran.001@gmail.com"),
            ("Phone", "+92 3164009363", "tel:+923164009363")]
LINKS = [("GitHub", "abdullahmran-101", "https://github.com/abdullahmran-101"),
         ("LinkedIn", "abdullah-imran", "https://www.linkedin.com/in/abdullah-imran-211658230")]


def contact(i):
    L = cell_layout(3)[i]
    lab, val, _ = CONTACTS[i]
    H = 112
    c = Canvas(L["w"], H + 16, f"{lab}: {val}")
    x, cw = L["x"], L["cw"]
    if i == 0:
        c.rect(x, 0, cw, H, WHITE)
        c.mlabel(x + 24, 40, lab, BG, size=10.5, bold=True)
        c.text(x + 24, 84, val, 14, "s", BG, track=-0.01)
        c.text(x + cw - 24, 40, "\u2197", 15, "r", BG, "end")
    else:
        c.rrect(x, 0, cw, H, PANEL)
        c.mlabel(x + 24, 40, lab, PURPLE, size=10.5, bold=True)
        c.text(x + 24, 84, val, 14, "s", WHITE, track=-0.01)
        c.text(x + cw - 24, 40, "\u2197", 15, "r", WHITE, "end")
    return c.render()


def link(i):
    L = cell_layout(2)[i]
    lab, val, _ = LINKS[i]
    H = 96
    c = Canvas(L["w"], H + 16, f"{lab}: {val}")
    x, cw = L["x"], L["cw"]
    c.rrect(x, 0, cw, H, PANEL)
    c.mlabel(x + 24, 36, lab, PURPLE, size=10.5, bold=True)
    c.text(x + 24, 70, val, 14, "s", WHITE, track=-0.01)
    c.text(x + cw - 24, 36, "\u2197", 15, "r", WHITE, "end")
    return c.render()


def footer():
    H = 200
    c = Canvas(W, H + 40, "The model is the easy part. The system around it is the product.")
    c.dots(M, 0, CW, H)
    c.rect(M + 1, 1, CW - 2, H - 2, "#0C0C0F")
    c.dots(M + 1, 1, CW - 2, H - 2, 16, "#17171C")
    c.outline(M, 0, CW, H, LINE)
    c.text(M + 40, 84, "The model is the easy part.", 30, "d", WHITE, track=-0.025)
    c.text(M + 40, 124, "The system around it is the product.", 30, "d", PURPLE, track=-0.025)
    c.hair(M + 40, M + CW - 40, H - 62, LINE)
    c.mono(M + 40, H - 34, "abdullahmran96@gmail.com", 10.5, MUTED)
    c.mono(M + 40, H - 16, "+92 3164009363", 10.5, MUTED)
    c.mono(M + CW - 40, H - 34, "abdullah imran \u00b7 lahore", 10.5, WHITE, "end")
    c.mono(M + CW - 40, H - 16, "ml engineer | data scientist", 10.5, MUTED, "end")
    return c.render()


# ------------------------------------------------------------------ README
def readme():
    def img(name, alt, width="100%"):
        return f'<img src="./cards/{name}.svg" width="{width}" alt="{esc(alt)}" />'

    nav = "".join(f'<a href="#{a}">{img(f"nav-{i+1}", lab, pct(L["w"]))}</a>'
                  for i, ((a, lab), L) in enumerate(zip(NAV, cell_layout(len(NAV), 0))))
    repos = []
    for r in range(math.ceil(len(REPOS) / 2)):
        ids = [k for k in (r * 2, r * 2 + 1) if k < len(REPOS)]
        L = cell_layout(len(ids))
        repos.append("".join(f'<a href="{REPOS[k][4]}">{img(f"repo-{k+1}", REPOS[k][0], pct(L[j]["w"]))}</a>' for j, k in enumerate(ids)))
    L3 = cell_layout(3)
    contacts = "".join(f'<a href="{CONTACTS[i][2]}">{img(f"contact-{i+1}", CONTACTS[i][0] + " " + CONTACTS[i][1], pct(L3[i]["w"]))}</a>' for i in range(3))
    L2 = cell_layout(2)
    links = "".join(f'<a href="{LINKS[i][2]}">{img(f"link-{i+1}", LINKS[i][0] + " " + LINKS[i][1], pct(L2[i]["w"]))}</a>' for i in range(2))
    rows = [
        f'<a href="https://github.com/{USER}">{img("hero", "Abdullah Imran. ML Engineer and Data Scientist. Lahore, Pakistan.")}</a>',
        nav,
        '<a name="about"></a>' + img("head-about", "01 About"),
        img("about", "About Abdullah Imran"),
        img("practice", "Capabilities"),
        '<a name="journey"></a>' + img("head-journey", "02 Journey"),
        img("timeline", "Career timeline"),
        img("now", "Active development and currently exploring"),
        '<a name="systems"></a>' + img("head-systems", "03 Systems"),
        *repos,
        img("catalogue", "All shipped systems"),
        '<a name="stack"></a>' + img("head-stack", "04 Stack"),
        img("skills", "Full skill matrix"),
        img("pipeline", "How I build: perceive, retrieve, reason, serve, ship"),
        '<a name="activity"></a>' + img("head-activity", "05 Activity"),
        img("kpis", "Activity summary"),
        img("heatmap", "Contribution heatmap, refreshed daily"),
        img("weekday-trend", "Most active weekday and weekly trend"),
        img("monthly", "Contributions by month"),
        '<a name="contact"></a>' + img("head-contact", "06 Contact"),
        img("engage", "Work with me"),
        contacts, links,
        img("footer", "The model is the easy part. The system around it is the product."),
    ]
    return ("<!-- Generated by scripts/render_readme_cards.py. Edit the script, not this file.\n"
            "     Keep images in a row on one line with no spaces between them. -->\n"
            '<div align="center">\n' + "<br>\n".join(rows) + "\n</div>\n")


def main():
    global LIVE
    OUT.mkdir(parents=True, exist_ok=True)
    days, LIVE = fetch_days()
    F = {
        "hero": hero(), "about": about(), "practice": practice(), "skills": skills(), "pipeline": pipeline(),
        "catalogue": catalogue(), "timeline": timeline(), "now": now(), "engage": engage(), "footer": footer(),
        "head-about": section_header("01", "About", "Profile and capabilities"),
        "head-journey": section_header("02", "Journey", "Career timeline and current work"),
        "head-systems": section_header("03", "Systems", "Selected repositories"),
        "head-stack": section_header("04", "Stack", "Skills and method"),
        "head-activity": section_header("05", "Activity", "Pulse and patterns"),
        "head-contact": section_header("06", "Contact", "Open to remote"),
    }
    if LIVE or not os.environ.get("GITHUB_ACTIONS"):
        F.update({"kpis": kpis(days), "heatmap": heatmap(days), "weekday-trend": weekday_trend(days), "monthly": monthly(days)})
    else:
        print("GitHub data unavailable in CI: keeping the previously committed activity cards.")
    for i in range(len(NAV)):
        F[f"nav-{i+1}"] = nav_cell(i)
    for i in range(len(REPOS)):
        F[f"repo-{i+1}"] = repo(i)
    for i in range(len(CONTACTS)):
        F[f"contact-{i+1}"] = contact(i)
    for i in range(len(LINKS)):
        F[f"link-{i+1}"] = link(i)
    for name, content in F.items():
        minidom.parseString(content.encode("utf-8"))
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    keep = {f"{k}.svg" for k in F} | {"kpis.svg", "heatmap.svg", "weekday-trend.svg", "monthly.svg"}
    for old in OUT.glob("*.svg"):
        if old.name not in keep:
            old.unlink()
    (ROOT / "README.md").write_text(readme(), encoding="utf-8")
    print(f"wrote {len(F)} cards + README.md")


if __name__ == "__main__":
    main()
