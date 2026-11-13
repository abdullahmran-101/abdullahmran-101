#!/usr/bin/env python3
"""Renders every static SVG card in ../cards and the README that composes them.

Design system
  Colour   four values only: WHITE, BLACK, BEIGE, GREY. No gradients, opacity, filters or animation.
  Type     Inter (Display cut for headings), converted to outlines so it renders identically
           everywhere (GitHub blocks web fonts inside SVG images). Fonts live in ../fonts.
  Grid     880-unit canvas, 40-unit page margin, 800-unit content width, 16-unit gutter.
  Shape    4-unit radius on containers, 3 on tags, hairlines at 1 unit, no shadows.

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
WHITE = "#FFFFFF"
BLACK = "#111111"
BEIGE = "#F0EBE1"
GREY = "#6B665E"
PALETTE = {WHITE, BLACK, BEIGE, GREY}

# ------------------------------------------------------------------ grid
W, M, CW, G = 880, 40, 800, 16
R_CARD, R_TAG = 4, 3


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

    def rrect(self, x, y, w, h, fill, r=R_CARD, tl=True, tr=True, br=True, bl=True):
        """Rectangle with per-corner rounding."""
        a, b, c, d = (r if tl else 0), (r if tr else 0), (r if br else 0), (r if bl else 0)
        p = (f"M{n(x+a)},{n(y)} H{n(x+w-b)} " + (f"A{n(b)},{n(b)} 0 0 1 {n(x+w)},{n(y+b)} " if b else "")
             + f"V{n(y+h-c)} " + (f"A{n(c)},{n(c)} 0 0 1 {n(x+w-c)},{n(y+h)} " if c else "")
             + f"H{n(x+d)} " + (f"A{n(d)},{n(d)} 0 0 1 {n(x)},{n(y+h-d)} " if d else "")
             + f"V{n(y+a)} " + (f"A{n(a)},{n(a)} 0 0 1 {n(x+a)},{n(y)} " if a else "") + "Z")
        self.parts.append(f'<path d="{p}" fill="{fill}"/>')

    def line(self, x1, y1, x2, y2, stroke=GREY, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" stroke="{stroke}" stroke-width="{n(sw)}"{d}/>')

    def hair(self, x1, x2, y, stroke=GREY):
        self.line(x1, y + .5, x2, y + .5, stroke, 1)

    def vhair(self, x, y1, y2, stroke=GREY):
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

    def text(self, x, y, txt, size=14, wt="r", fill=BLACK, anchor="start", track=0.0):
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

    def label(self, x, y, txt, fill=GREY, anchor="start", size=11):
        return self.text(x, y, txt.upper(), size, "m", fill, anchor, 0.08)

    def para(self, x, y, txt, size, wt, maxw, lh, fill=BLACK, track=0.0, first_black=False):
        lines = wrap(txt, size, wt, maxw, track)
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, size, wt, fill, "start", track)
        return len(lines)

    def tag(self, x, y, txt, fill=BEIGE, ink=BLACK, size=12, h=26, px=11, wt="r"):
        w = measure(txt, size, wt) + 2 * px
        self.rect(x, y, w, h, fill, R_TAG)
        self.text(x + px, y + h / 2 + 0.3637 * size, txt, size, wt, ink)
        return w

    def render(self):
        defs = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{n(self.w)}" height="{n(self.h)}" viewBox="0 0 {n(self.w)} {n(self.h)}" role="img" aria-label="{esc(self.title)}">\n'
                f'<title>{esc(self.title)}</title>{defs}\n'
                f'<rect width="{n(self.w)}" height="{n(self.h)}" fill="{WHITE}"/>\n' + "\n".join(self.parts) + "\n</svg>\n")


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


# ------------------------------------------------------------------ shared pieces
def section_header(idx, name, caption):
    c = Canvas(W, 132, f"{idx} {name}")
    c.rect(M, 24, CW, 2, BLACK)
    c.label(M, 56, idx)
    c.label(W - M, 56, caption, anchor="end")
    c.text(M, 106, name, 34, "d", BLACK, track=-0.025)
    return c.render()


def card_columns(count):
    cw = (CW - (count - 1) * G) / count
    return [(M + i * (cw + G), cw) for i in range(count)]


# ------------------------------------------------------------------ hero
def hero():
    c = Canvas(W, 456, "Abdullah Imran. AI/ML engineer. Computer vision and intelligent product development. Lahore, Pakistan.")
    c.rect(M, 24, CW, 2, BLACK)
    c.label(M, 56, "Profile")
    sw = c.label(W - M, 56, "Open to roles and contracts", fill=BLACK, anchor="end")
    c.rect(W - M - sw - 18, 49, 8, 8, BLACK)

    c.text(M, 170, "Abdullah Imran", 60, "d", BLACK, track=-0.035)
    c.text(M, 220, "AI/ML Engineer", 22, "m", BLACK, track=-0.01)
    c.para(M, 252, "Computer vision and intelligent product development.", 16, "r", 440, 24, GREY)
    c.label(M, 296, "Lahore, Pakistan  ·  Remote")

    px, py, pw, rows = 568, 88, 272, 3
    c.rrect(px, py, pw, rows * 64, BEIGE)
    facts = [("Location", "Lahore, Pakistan · Remote"), ("Focus", "Computer vision · LLMs · Agents"), ("Status", "Open to roles and contracts")]
    for i, (k, v) in enumerate(facts):
        y = py + i * 64
        c.label(px + 20, y + 28, k, size=10.5)
        c.text(px + 20, y + 49, v, 14, "m", BLACK)
        if i < rows - 1:
            c.hair(px + 20, px + pw - 20, y + 64 - 1)

    sy = 328
    c.rrect(M, sy, CW, 96, BLACK)
    stats = [("12", "Systems shipped"), ("6", "Certifications"), ("90%", "Model accuracy"), ("30%", "Faster ML pipeline")]
    for i, (big, lab) in enumerate(stats):
        x = M + i * 200
        c.text(x + 24, sy + 50, big, 36, "d", WHITE, track=-0.03)
        c.label(x + 24, sy + 74, lab, fill=BEIGE, size=10.5)
        if i:
            c.vhair(x, sy + 20, sy + 76, GREY)
    return c.render()


# ------------------------------------------------------------------ nav
NAV = [("overview", "Overview"), ("stack", "Stack"), ("insights", "Insights"), ("activity", "Activity"),
       ("systems", "Systems"), ("journey", "Journey"), ("contact", "Contact")]


def nav_cell(i):
    L = cell_layout(len(NAV), 0)[i]
    c = Canvas(L["w"], 56, f"{NAV[i][1]}")
    x0, x1 = L["x"] - (M if i == 0 else 0), L["x"] + L["cw"]
    x0 = M if i == 0 else 0
    x1 = L["w"] - (M if i == len(NAV) - 1 else 0)
    c.rect(x0, 0, x1 - x0, 1, BLACK)
    c.hair(x0, x1, 55)
    pad = 14
    c.text(x0 + pad, 33, f"{i+1:02d}", 11, "m", GREY, track=0.04)
    c.text(x0 + pad + 24, 33, NAV[i][1].upper(), 11, "m", BLACK, track=0.08)
    if i < len(NAV) - 1:
        c.vhair(x1 - 1, 1, 55)
    return c.render()


# ------------------------------------------------------------------ overview
def intro():
    c = Canvas(W, 10, "I design, build and deploy end-to-end intelligent systems: the model, the retrieval layer, the agent logic, the backend API and the container it ships in.")
    c.label(M, 52, "About")
    txt = ("I design, build and deploy end-to-end intelligent systems: the model, the retrieval layer, "
           "the agent logic, the backend API and the container it ships in.")
    k = c.para(240, 58, txt, 22, "m", 600, 34, BLACK, track=-0.012)
    y = 58 + (k - 1) * 34 + 40
    x = 240
    stages = ["Perception", "Knowledge", "Reasoning", "Service", "Delivery"]
    for i, s in enumerate(stages):
        x += c.tag(x, y, s.upper(), BEIGE, BLACK, 10.5, 28, 12, "m") + 0
        if i < len(stages) - 1:
            c.text(x + 9, y + 19, "→", 12, "r", GREY, "middle")
            x += 18
    c.h = int(y + 28 + 40)
    return c.render()


def practice():
    items = [("Engineer", "Computer vision · Deep learning", "YOLOv12 · MediaPipe · KeypointRCNN", "Production-ready intelligent systems"),
             ("Builder", "FastAPI · Django · Celery · Docker", "RAG apps, agents, automation APIs", "From prototype to deployed product"),
             ("Explorer", "Agentic AI · Multimodal fusion", "LLMs, retrieval, new tooling", "Experiments and open source")]
    cols = card_columns(3)
    inner = cols[0][1] - 44
    blocks = []
    for it in items:
        blocks.append([wrap(s, 13, "m" if k == 0 else "r", inner) for k, s in enumerate(it[1:])])
    nlines = max(sum(len(b) for b in bl) for bl in blocks)
    H = 124 + nlines * 20 + 2 * 14 + 28
    c = Canvas(W, H + 16, "Practice areas: engineer, builder, explorer")
    for (x, cw), it, bl in zip(cols, items, blocks):
        c.rrect(x, 0, cw, H, BEIGE)
        c.label(x + 22, 40, f"{items.index(it)+1:02d}", size=10.5)
        c.text(x + 22, 84, it[0], 26, "d", BLACK, track=-0.02)
        c.hair(x + 22, x + cw - 22, 106)
        y = 138
        for k, lines in enumerate(bl):
            for ln in lines:
                c.text(x + 22, y, ln, 13, "m" if k == 0 else "r", BLACK if k == 0 else GREY)
                y += 20
            y += 14
    return c.render()


def architecture():
    rows = [("Identity", "Abdullah Imran · AI/ML Engineer", "Active"), ("Perception", "Vision · Speech · Text", "Active"),
            ("Knowledge", "FAISS · ChromaDB · SQLite · PostgreSQL", "Active"), ("Reasoning", "LLaMA 3.3 70B · Gemini · GPT · Grok", "Active"),
            ("Agents", "ReAct loops · Multi-provider routing", "Active"), ("Services", "FastAPI · Django · Celery · n8n", "Active"),
            ("Containers", "Docker", "Active"), ("Delivery policy", "Notebook-only demos disabled by policy", "Enforced")]
    top, rh = 44, 44
    H = top + 36 + len(rows) * rh + 16
    c = Canvas(W, H, "System architecture: identity, perception, knowledge, reasoning, agents, services, containers and delivery policy")
    c.label(M, 26, "System architecture")
    c.rect(M, top, CW, 1, BLACK)
    c.label(M + 48, top + 24, "Layer", size=10.5)
    c.label(M + 260, top + 24, "Components", size=10.5)
    c.label(M + CW, top + 24, "Status", size=10.5, anchor="end")
    c.hair(M, M + CW, top + 36)
    for i, (lay, comp, st) in enumerate(rows):
        y = top + 36 + 1 + i * rh
        base = y + rh / 2 + CAP * 14 / 2
        c.text(M, base, f"{i+1:02d}", 11, "m", GREY, track=0.04)
        c.text(M + 48, base, lay, 14, "s", BLACK)
        c.text(M + 260, base, comp, 14, "r", BLACK)
        tw = measure(st, 12, "m")
        c.text(M + CW, base, st, 12, "m", BLACK, "end")
        c.rect(M + CW - tw - 16, y + rh / 2 - 3.5, 7, 7, BLACK)
        c.hair(M, M + CW, y + rh - 1)
    return c.render()


# ------------------------------------------------------------------ stack
SKILLS = [
    ("Full-Stack Web Development & APIs",
     ["Python", "Next.js", "HTML5 / CSS3", "FastAPI", "Django", "Flask", "Django REST Framework", "REST APIs", "Pydantic", "WebSockets", "Celery"]),
    ("Databases", ["PostgreSQL", "SQL", "MongoDB", "Airtable", "Redis", "Vector DBs: FAISS, ChromaDB, Weaviate, Pinecone"]),
    ("Generative AI, LLMs & RAG",
     ["Large Language Models", "LLM Fine-Tuning", "OpenAI API", "Google Gemini API", "Grok API", "Groq API", "Ollama Models", "Hugging Face",
      "AI Agents & Automation", "n8n · Zapier", "Function Calling & Tool Use", "Embeddings & Semantic Search", "RAG", "Agentic RAG", "Graph RAG",
      "Chunking & Re-ranking", "LangChain", "LangGraph", "LangSmith", "Ragas / DeepEval", "Model Context Protocol (MCP)", "Prompt Engineering"]),
    ("Machine Learning & Computer Vision",
     ["PyTorch", "TensorFlow", "Keras", "Scikit-learn", "XGBoost / LightGBM", "CNN", "Hugging Face Transformers", "Model Fine-Tuning", "LoRA / PEFT",
      "Computer Vision", "OpenCV", "YOLO", "MediaPipe", "Multimodal AI", "Faster R-CNN", "Object Tracking (DeepSORT)", "Image Segmentation"]),
    ("Cloud & Deployment", ["AWS SageMaker", "Docker", "CI/CD", "MLflow", "Streamlit", "Hugging Face Spaces", "Modal", "Vercel", "Netlify"]),
    ("AI-Assisted Development", ["Claude Code", "Cursor", "GitHub Copilot", "AI-Assisted Debugging", "AI Code Review & Validation"]),
]


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
    c.label(M, 26, "Full skill matrix")
    c.rect(M, 44, CW, 1, BLACK)
    for name, left, placed, rows, y, h, cnt in groups:
        top = y + 24
        for i, ln in enumerate(left):
            c.text(M, top + 16 + i * 22, ln, 16, "s", BLACK, track=-0.01)
        c.label(M, top + 16 + len(left) * 22 + 2, f"{cnt} skills", size=10.5)
        for it, x, row, w in placed:
            c.tag(x, top + row * (th + gap), it, BEIGE, BLACK, 12, th, 11)
        if y + h < H - 16:
            c.hair(M, M + CW, y + h - 1)
    return c.render()


# ------------------------------------------------------------------ insights
def radar_domain():
    H = 380
    c = Canvas(W, H + 16, "Self-assessed proficiency radar and project portfolio by domain")
    (xa, cwa), (xb, cwb) = card_columns(2)
    c.rrect(xa, 0, cwa, H, BEIGE)
    c.rrect(xb, 0, cwb, H, BEIGE)

    # radar
    data = [("Python", 92), ("LLM Apps", 90), ("RAG", 88), ("FastAPI", 86), ("Agents", 85), ("Vision", 82), ("Docker", 78), ("MLOps", 72)]
    c.label(xa + 24, 38, "Self-assessed proficiency")
    c.text(xa + 24, 60, "Out of 100", 12, "r", GREY)
    cx, cy, R, k = xa + cwa / 2, 218, 98, len(data)
    ang = lambda i: -math.pi / 2 + i * 2 * math.pi / k
    pts = [(cx + R * v / 100 * math.cos(ang(i)), cy + R * v / 100 * math.sin(ang(i))) for i, (_, v) in enumerate(data)]
    c.poly(pts, WHITE)  # solid fill first, grid is drawn over it so it stays readable
    for f in (.25, .5, .75, 1):
        c.poly([(cx + R * f * math.cos(ang(i)), cy + R * f * math.sin(ang(i))) for i in range(k)], "none", GREY, 1)
    for i in range(k):
        c.line(cx, cy, cx + R * math.cos(ang(i)), cy + R * math.sin(ang(i)), GREY, 1)
    c.poly(pts, "none", BLACK, 1.75)
    for x, y in pts:
        c.rect(x - 3, y - 3, 6, 6, BLACK)
    for i, (nm, v) in enumerate(data):
        a = ang(i)
        lx, ly = cx + (R + 22) * math.cos(a), cy + (R + 22) * math.sin(a)
        an = "middle" if abs(math.cos(a)) < .2 else ("start" if math.cos(a) > 0 else "end")
        dy = -16 if math.sin(a) < -.9 else (10 if math.sin(a) > .9 else -2)
        c.text(lx, ly + dy, nm, 12, "m", BLACK, an)
        c.text(lx, ly + dy + 14, str(v), 11, "r", GREY, an)

    # domains
    segs = [("Agents & Automation", 3), ("RAG & LLM Apps", 3), ("Computer Vision & Security", 3), ("Healthcare Multimodal AI", 2), ("Predictive ML & Fraud", 1)]
    c.label(xb + 24, 38, "Portfolio by domain")
    c.text(xb + 24, 60, "Systems shipped by area", 12, "r", GREY)
    c.text(xb + cwb - 24, 62, "12", 44, "d", BLACK, "end", -0.03)
    for i, (nm, v) in enumerate(segs):
        y = 118 + i * 50
        c.text(xb + 24, y, nm, 13, "m", BLACK)
        c.text(xb + cwb - 24, y, str(v), 13, "s", BLACK, "end")
        c.rect(xb + 24, y + 13, cwb - 48, 4, WHITE)
        c.rect(xb + 24, y + 13, (cwb - 48) * v / 3, 4, BLACK)
    return c.render()


def stackmix():
    segs = [("Python & ML", 35), ("LLMs & agents", 25), ("Backend & APIs", 20), ("Retrieval", 12), ("DevOps", 8)]
    c = Canvas(W, 190, "Toolchain emphasis: Python and ML 35%, LLMs and agents 25%, backend 20%, retrieval 12%, DevOps 8%")
    c.label(M, 26, "Toolchain emphasis")
    c.label(M + CW, 26, "Self-estimated share of stack", anchor="end")
    x = M
    for i, (nm, v) in enumerate(segs):
        w = CW * v / 100
        c.rect(x, 48, w - (3 if i < len(segs) - 1 else 0), 28, BLACK if i % 2 == 0 else GREY)
        c.text(x, 128, f"{v}%", 28, "d", BLACK, track=-0.03)
        c.label(x, 152, nm, size=10)
        x += w
    return c.render()


def pipeline():
    steps = [("Perceive", ["Computer vision", "Whisper speech", "Text & documents"]), ("Retrieve", ["FAISS \u00b7 ChromaDB", "BGE embeddings", "Cross-encoder rerank"]),
             ("Reason", ["LLMs & ReAct agents", "Provider routing", "Policy & safety gates"]), ("Serve", ["FastAPI \u00b7 Django", "Celery \u00b7 Redis", "SSE live traces"]),
             ("Ship", ["Docker \u00b7 Compose", "VPS deployment", "n8n automation"])]
    H = 232
    c = Canvas(W, H + 16, "How I build: perceive, retrieve, reason, serve, ship")
    c.rrect(M, 0, CW, H, BEIGE)
    c.label(M + 24, 38, "How I build")
    c.label(M + CW - 24, 38, "Grounded outputs. Observable agents. Deployable by default.", anchor="end", size=10.5)
    c.hair(M + 24, M + CW - 24, 58)
    colw = (CW - 48) / 5
    for i, (nm, items) in enumerate(steps):
        x = M + 24 + i * colw
        px = x if i == 0 else x + 16
        if i:
            c.vhair(x, 84, H - 32)
        c.text(px, 100, f"{i+1:02d}", 11, "m", GREY, track=0.04)
        c.text(px, 134, nm, 19, "d", BLACK, track=-0.02)
        for k, s in enumerate(items):
            c.text(px, 166 + k * 21, s, 12, "m" if k == 0 else "r", BLACK if k == 0 else GREY)
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


def kpis(days):
    pc, avg, best, cur = kpi_values(days)
    items = [(f"{pc}%", "Active days", "of the last 12 months"), (f"{avg:.1f}", "Average per active day", "contributions"),
             (str(best), "Best week", "contributions in 7 days"), (str(cur), "Current streak", "days in a row")]
    H = 128
    c = Canvas(W, H + 16, "Activity summary: " + "; ".join(f"{b} {l}" for b, l, _ in items))
    for (x, cw), (big, lab, sub) in zip(card_columns(4), items):
        c.rrect(x, 0, cw, H, BEIGE)
        c.label(x + 22, 36, lab, size=10)
        c.text(x + 22, 82, big, 40, "d", BLACK, track=-0.035)
        c.text(x + 22, 106, sub, 12, "r", GREY)
    return c.render()


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
    c.label(M, 26, "Contributions")
    c.label(M + CW, 26, f"{total:,} in the last 12 months", fill=BLACK, anchor="end")
    c.rect(M, 44, CW, 1, BLACK)
    last_m, last_c = None, -9
    for ci, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0][0]).strftime("%b")
        if m != last_m and ci - last_c >= 3:
            c.text(x0 + ci * pitch, 78, m, 11, "r", GREY)
            last_m, last_c = m, ci
        for ri, (_, v) in enumerate(wk):
            lvl = 0 if v == 0 else 1 + min(3, int(v * 4 / (mx + 1)))
            x, y = x0 + ci * pitch, top + ri * pitch
            c.rect(x, y, cell, cell, BEIGE)
            if lvl:
                s = cell * (0, .3, .5, .72, 1)[lvl]
                c.rect(x + (cell - s) / 2, y + (cell - s) / 2, s, s, BLACK)
    for ri, nm in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
        c.text(M, top + ri * pitch + cell / 2 + 4, nm, 11, "r", GREY)
    ly = top + 7 * pitch + 28
    lx = M + CW - 5 * (cell + 5) - 70
    c.text(M, ly + cell / 2 + 4, "Each square is a day; the inner mark scales with contributions.", 11, "r", GREY)
    c.text(lx - 8, ly + cell / 2 + 4, "Less", 11, "r", GREY, "end")
    for k in range(5):
        x = lx + k * (cell + 5)
        c.rect(x, ly, cell, cell, BEIGE)
        if k:
            s = cell * (0, .3, .5, .72, 1)[k]
            c.rect(x + (cell - s) / 2, ly + (cell - s) / 2, s, s, BLACK)
    c.text(lx + 5 * (cell + 5) + 3, ly + cell / 2 + 4, "More", 11, "r", GREY)
    return c.render()


def weekday_trend(days):
    H = 308
    c = Canvas(W, H + 16, "Most active weekday and weekly contribution trend")
    (xa, cwa), (xb, cwb) = card_columns(2)
    c.rrect(xa, 0, cwa, H, BEIGE)
    c.rrect(xb, 0, cwb, H, BEIGE)
    tot = [0] * 7
    for ds, v in days:
        tot[dt.date.fromisoformat(ds).weekday()] += v
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    mx = max(tot) or 1
    bi = tot.index(mx)
    c.label(xa + 24, 38, "Most active weekday")
    c.label(xa + cwa - 24, 38, f"{names[bi]} leads", fill=BLACK, anchor="end")
    base = 256
    c.hair(xa + 24, xa + cwa - 24, base)
    pitch = (cwa - 48) / 7
    bw = 22
    for i, v in enumerate(tot):
        bh = max(3, v / mx * 150)
        x = xa + 24 + i * pitch + (pitch - bw) / 2
        c.rect(x, base - bh, bw, bh, BLACK if i == bi else GREY)
        c.text(x + bw / 2, base - bh - 9, str(v), 11, "m", BLACK if i == bi else GREY, "middle")
        c.text(x + bw / 2, base + 22, names[i], 11, "m" if i == bi else "r", BLACK if i == bi else GREY, "middle")

    wk = weekly(days)
    c.label(xb + 24, 38, "Weekly trend")
    x0, x1, y0, y1 = xb + 24, xb + cwb - 24, 100, 256
    wm = max(wk) or 1
    pts = [(x0 + i * (x1 - x0) / (len(wk) - 1), y1 - v / wm * (y1 - y0)) for i, v in enumerate(wk)]
    c.poly(pts + [(x1, y1), (x0, y1)], WHITE)
    c.poly(pts, "none", BLACK, 1.75, close=False)
    avg = sum(wk) / len(wk)
    ay = y1 - avg / wm * (y1 - y0)
    c.line(x0, ay, x1, ay, GREY, 1, "3 4")
    c.hair(x0, x1, y1)
    c.label(xb + cwb - 24, 38, f"Average {avg:.0f} / week", fill=BLACK, anchor="end")
    c.rect(pts[-1][0] - 4, pts[-1][1] - 4, 8, 8, BLACK)
    c.text(x0, y1 + 22, "52 weeks ago", 11, "r", GREY)
    c.text(x1, y1 + 22, "This week", 11, "r", GREY, "end")
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
    c.rrect(M, 0, CW, H, BEIGE)
    c.label(M + 24, 38, "Contributions by month")
    base, pitch, bw = 244, 40.5, 24
    c.hair(M + 24, M + 24 + 12 * pitch, base)
    for i, (k, v) in enumerate(zip(keys, vals)):
        bh = max(3, v / top * 140)
        x = M + 24 + i * pitch + (pitch - bw) / 2
        c.rect(x, base - bh, bw, bh, BLACK if v == top else GREY)
        c.text(x + bw / 2, base - bh - 9, str(v), 11, "m", BLACK if v == top else GREY, "middle")
        c.text(x + bw / 2, base + 22, dt.date(k[0], k[1], 1).strftime("%b"), 11, "r", GREY, "middle")
    sx = M + 24 + 12 * pitch + 24
    c.vhair(sx - 12, 24, H - 24)
    stats = [("Total", f"{total:,}"), ("Longest streak", f"{streak} days"), (f"Busiest day · {best[0]}", str(best[1]))]
    for i, (lab, val) in enumerate(stats):
        y = 38 + i * 84
        c.label(sx + 12, y, lab, size=10)
        c.text(sx + 12, y + 40, val, 30, "d", BLACK, track=-0.03)
        if i < 2:
            c.hair(sx + 12, M + CW - 24, y + 62)
    return c.render()


# ------------------------------------------------------------------ systems
REPOS = [
    ("HealMatrix AI", "Healthcare · Multimodal", "Crisis-gated multimodal assistant fusing text, voice, face and posture.", ["RAG", "RoBERTa", "FastAPI", "Docker"],
     "https://github.com/abdullahmran-101/Heal-Matrix-AI"),
    ("Cheatify", "Computer vision", "Real-time exam proctoring with object detection, pose and gaze risk scoring.", ["YOLOv12", "MediaPipe", "OpenCV"],
     "https://github.com/abdullahmran-101/Cheatify-AI-Proctoring-System"),
    ("AgentFlow AI", "Agents", "Multi-provider ReAct platform with live tool traces, memory and failover.", ["LangGraph", "SSE", "FastAPI"],
     "https://github.com/abdullahmran-101/Agentflow-AI"),
    ("Research Forge AI", "RAG · Research", "Self-hosted research-to-report pipeline with citation enforcement.", ["SearXNG", "ChromaDB", "Celery"],
     "https://github.com/abdullahmran-101/Research-Forge-AI"),
]


def repo_height():
    cw = cell_layout(2)[0]["cw"]
    hs = []
    for name, dom, desc, tags, _ in REPOS:
        k = len(wrap(desc, 14, "r", cw - 56))
        hs.append(128 + k * 22 + 20 + 26 + 28 + 56 - 20)
    return max(hs)


def repo(i):
    L = cell_layout(2)[i % 2]
    name, dom, desc, tags, url = REPOS[i]
    H = repo_height()
    c = Canvas(L["w"], H + 16, f"{name}. {desc}")
    x, cw = L["x"], L["cw"]
    c.rrect(x, 0, cw, H, BEIGE)
    c.label(x + 28, 40, dom, size=10.5)
    c.label(x + cw - 28, 40, f"{i+1:02d}", anchor="end", size=10.5)
    c.text(x + 28, 92, name, 28, "d", BLACK, track=-0.025)
    k = c.para(x + 28, 126, desc, 14, "r", cw - 56, 22, GREY)
    ty = 126 + (k - 1) * 22 + 24
    tx = x + 28
    for t in tags:
        tx += c.tag(tx, ty, t, WHITE, BLACK, 12, 26, 11) + 6
    c.hair(x + 28, x + cw - 28, H - 56)
    c.text(x + 28, H - 24, "View repository", 13, "s", BLACK)
    c.text(x + cw - 28, H - 24, "↗", 15, "r", BLACK, "end")
    return c.render()


CATALOGUE = [("HealMatrix AI", "Healthcare · Multimodal", "LLaMA 3.3 · FAISS · RoBERTa"), ("VITA", "Healthcare · Multimodal", "Transformer fusion · ElevenLabs"),
             ("Cheatify", "Computer vision", "YOLOv12 · MediaPipe"), ("IntelliFall AI", "CV · IoT", "Fall detection system"),
             ("MalVision AI", "Security · XAI", "Streamlit · explainability"), ("Research Forge AI", "RAG · Research", "SearXNG · ChromaDB · Celery"),
             ("AgentFlow AI", "Agents", "LangGraph · SSE · SQLite"), ("Pocho AI", "RAG", "Django · TF-IDF · Grok"),
             ("QuickByte AI", "LLM application", "Nutrition-focused LLM platform"), ("WhatsAgent AI", "Automation", "n8n · Twilio · Airtable"),
             ("Quantifier AI", "Automation", "Lead scoring: HOT · WARM · COLD"), ("FraudShield AI", "Predictive ML", "scikit-learn")]


def grid_panel(c, y, items, cols, cell_h, draw):
    cw = CW / cols
    rows = math.ceil(len(items) / cols)
    c.rrect(M, y, CW, rows * cell_h, BEIGE)
    for r in range(1, rows):
        c.rect(M, y + r * cell_h - 1, CW, 2, WHITE)
    for k in range(1, cols):
        c.rect(M + k * cw - 1, y, 2, rows * cell_h, WHITE)
    for i, it in enumerate(items):
        draw(c, M + (i % cols) * cw, y + (i // cols) * cell_h, cw, it, i)
    return y + rows * cell_h


def catalogue():
    ch = 116
    H = 48 + 3 * ch + 16
    c = Canvas(W, H, "All 12 shipped systems by domain")
    c.label(M, 26, "All shipped systems")
    c.label(M + CW, 26, "12 total", fill=BLACK, anchor="end")

    def draw(cv, x, y, w, it, i):
        nm, dom, tech = it
        cv.text(x + 20, y + 36, nm, 15, "s", BLACK, track=-0.01)
        yy = y + 58
        for ln in wrap(dom.upper(), 10, "m", w - 40, 0.06):
            cv.text(x + 20, yy, ln, 10, "m", GREY, track=0.06)
            yy += 14
        yy += 6
        for ln in wrap(tech, 12, "r", w - 40):
            cv.text(x + 20, yy, ln, 12, "r", BLACK)
            yy += 17
    grid_panel(c, 48, CATALOGUE, 4, ch, draw)
    return c.render()


# ------------------------------------------------------------------ journey
def timeline():
    ev = [("Oct 2022", "B.S. Data Science", "Begins"), ("Jul 2024", "AI/ML Fellow", "ACM UET × DevSinc"), ("Oct 2024", "ML Core Team", "UMT GoDoc"),
          ("Dec 2024", "Junior ML Engineer", "Sunsprinkle · Remote"), ("Jun 2026", "B.S. completed", "Data Science"), ("Oct 2026", "Freelance AI/ML Engineer", "Remote · Present")]
    colw = CW / len(ev)
    tl = max(len(wrap(t, 15, "s", colw - 18, -0.01)) for _, t, _ in ev)
    H = 118 + tl * 20 + 44
    c = Canvas(W, H, "Timeline from 2022 to freelance AI/ML engineer in 2026")
    c.label(M, 26, "Timeline")
    c.label(M + CW, 26, "2022 – 2026", anchor="end")
    c.rect(M, 44, CW, 1, BLACK)
    ly = 92
    c.hair(M, M + CW, ly)
    for i, (d, t, s) in enumerate(ev):
        x = M + i * colw
        last = i == len(ev) - 1
        c.label(x, 76, d, fill=BLACK, size=10.5)
        c.rect(x, ly - 4, 10, 10, BLACK)
        if last:
            c.rect(x + 2.5, ly - 1.5, 5, 5, WHITE)
        y = 128
        for ln in wrap(t, 15, "s", colw - 18, -0.01):
            c.text(x, y, ln, 15, "s", BLACK, track=-0.01)
            y += 20
        c.text(x, y + 4, s, 12, "r", GREY)
    return c.render()


PRINCIPLES = [("Grounding over fluency", "Retrieval and reranking; every claim traces back to a source."),
              ("Safety gates first", "Crisis detection runs ahead of the LLM, never improvised on."),
              ("Observable agents", "Live tool-call traces over SSE, so reasoning is inspectable."),
              ("Provider independence", "Routing across Groq, Gemini and OpenRouter beats vendor lock-in."),
              ("Multimodal by default", "Face, posture, voice and text are fused signals, not separate demos."),
              ("Resilient automation", "n8n flows ship with retries and an error-notifier workflow."),
              ("Incremental delivery", "Progressively harder versions, each one working end to end."),
              ("Ship. Measure. Improve.", "Build. Evaluate. Optimize. Deploy. Repeat.")]


def principles():
    inner = CW / 4 - 40
    ch = 62 + max(len(wrap(t, 15, "s", inner, -0.01)) * 20 + 6 + len(wrap(b, 12.5, "r", inner)) * 18 for t, b in PRINCIPLES) + 22
    H = 48 + 2 * ch + 16
    c = Canvas(W, H, "Engineering principles")
    c.label(M, 26, "Engineering principles")

    def draw(cv, x, y, w, it, i):
        t, body = it
        cv.text(x + 20, y + 34, f"{i+1:02d}", 10.5, "m", GREY, track=0.04)
        yy = y + 62
        for ln in wrap(t, 15, "s", w - 40, -0.01):
            cv.text(x + 20, yy, ln, 15, "s", BLACK, track=-0.01)
            yy += 20
        yy += 6
        for ln in wrap(body, 12.5, "r", w - 40):
            cv.text(x + 20, yy, ln, 12.5, "r", GREY)
            yy += 18
    grid_panel(c, 48, PRINCIPLES, 4, ch, draw)
    return c.render()


def now():
    H = 300
    c = Canvas(W, H + 16, "Active development and currently exploring")
    lw = 488
    rx, rw = M + lw + G, CW - lw - G
    c.rrect(M, 0, lw, H, BEIGE)
    c.rrect(rx, 0, rw, H, BEIGE)
    c.label(M + 24, 38, "Active development")
    c.hair(M + 24, M + lw - 24, 58)
    rows = [("Hospital Procurement Platform", "Forecasting and supplier scoring shipped", 5, 2, "V2 / V5"),
            ("AI Coding Assistant", "VS Code extension, FastAPI multi-LLM router", 10, 2, "Phase 2 / 10"), ("Lahori", "Lahore food discovery platform", 0, 0, "In development")]
    for r, (name, sub, cnt, done, lab) in enumerate(rows):
        y = 94 + r * 74
        c.text(M + 24, y, name, 15, "s", BLACK, track=-0.01)
        c.text(M + 24, y + 22, sub, 12, "r", GREY)
        px, pw = M + lw - 24 - 140, 140
        if cnt:
            sg = (pw - (cnt - 1) * 3) / cnt
            for k in range(cnt):
                c.rect(px + k * (sg + 3), y - 12, sg, 8, BLACK if k < done else WHITE)
            c.label(px + pw, y + 22, lab, anchor="end", size=10)
        else:
            c.label(px + pw, y + 22, lab, anchor="end", size=10)
        if r < 2:
            c.hair(M + 24, M + lw - 24, y + 40)
    c.label(rx + 24, 38, "Currently exploring")
    c.hair(rx + 24, rx + rw - 24, 58)
    x, y = rx + 24, 80
    for s in ["Agentic AI", "Multimodal fusion", "pgvector", "RBAC & multi-tenancy", "Next.js dashboards", "Production MLOps"]:
        w = measure(s, 12, "r") + 22
        if x + w > rx + rw - 24:
            x, y = rx + 24, y + 34
        c.tag(x, y, s, WHITE, BLACK, 12, 26, 11)
        x += w + 6
    return c.render()


def engage():
    E = [("Full-time role", "AI/ML engineering, applied GenAI, backend intelligence."), ("Contract build", "RAG systems, agents, LLM apps, computer vision pipelines."),
         ("Automation", "n8n and Zapier workflows with LLM decision steps."), ("Prototype to production", "Notebook or demo to a FastAPI service with Docker deploy.")]
    cols = card_columns(4)
    k = max(len(wrap(b, 13, "r", cols[0][1] - 2)) for _, b in E)
    H = 52 + 54 + k * 20 + 16 + 16
    c = Canvas(W, H, "Work with me: full-time, contract builds, automation, prototype to production")
    c.label(M, 26, "Work with me")
    for (x, cw), (t, b), i in zip(cols, E, range(4)):
        c.rect(x, 44, cw, 2, BLACK)
        c.label(x, 78, f"{i+1:02d}", size=10.5)
        c.text(x, 106, t, 16, "s", BLACK, track=-0.01)
        c.para(x, 132, b, 13, "r", cw - 2, 20, GREY)
    return c.render()


# ------------------------------------------------------------------ contact + footer
CONTACTS = [("LinkedIn", "abdullah-imran", "https://www.linkedin.com/in/abdullah-imran-211658230"),
            ("Email", "abdullahmran.001@gmail.com", "mailto:abdullahmran.001@gmail.com"),
            ("GitHub", "abdullahmran-101", "https://github.com/abdullahmran-101")]


def contact(i):
    L = cell_layout(3)[i]
    lab, val, _ = CONTACTS[i]
    H = 112
    c = Canvas(L["w"], H + 16, f"{lab}: {val}")
    x, cw = L["x"], L["cw"]
    c.rrect(x, 0, cw, H, BEIGE)
    c.label(x + 24, 40, lab, size=10.5)
    c.text(x + 24, 84, val, 14, "s", BLACK, track=-0.01)
    c.text(x + cw - 24, 40, "↗", 15, "r", BLACK, "end")
    return c.render()


def footer():
    H = 192
    c = Canvas(W, H + 40, "The model is the easy part. The system around it is the product.")
    c.rrect(M, 0, CW, H, BLACK)
    c.text(M + 40, 78, "The model is the easy part.", 28, "d", WHITE, track=-0.025)
    c.text(M + 40, 116, "The system around it is the product.", 28, "d", BEIGE, track=-0.025)
    c.hair(M + 40, M + CW - 40, H - 56, GREY)
    c.label(M + 40, H - 26, "Abdullah Imran  \u00b7  Lahore", fill=BEIGE, size=10.5)
    c.label(M + CW - 40, H - 26, "Build. Evaluate. Optimize. Deploy.", fill=BEIGE, anchor="end", size=10.5)
    return c.render()


# ------------------------------------------------------------------ README
def readme():
    def img(name, alt, width="100%"):
        return f'<img src="./cards/{name}.svg" width="{width}" alt="{esc(alt)}" />'

    nav = "".join(f'<a href="#{a}">{img(f"nav-{i+1}", lab, pct(L["w"]))}</a>'
                  for i, ((a, lab), L) in enumerate(zip(NAV, cell_layout(len(NAV), 0))))
    repos = []
    for r in range(2):
        L = cell_layout(2)
        repos.append("".join(f'<a href="{REPOS[r*2+k][4]}">{img(f"repo-{r*2+k+1}", REPOS[r*2+k][0], pct(L[k]["w"]))}</a>' for k in range(2)))
    L3 = cell_layout(3)
    contacts = "".join(f'<a href="{CONTACTS[i][2]}">{img(f"contact-{i+1}", CONTACTS[i][0] + " " + CONTACTS[i][1], pct(L3[i]["w"]))}</a>' for i in range(3))
    rows = [
        f'<a href="https://github.com/{USER}">{img("hero", "Abdullah Imran. AI/ML engineer. Computer vision and intelligent product development. Lahore, Pakistan.")}</a>',
        nav,
        img("intro", "I design, build and deploy end-to-end intelligent systems."),
        '<a name="overview"></a>' + img("head-overview", "01 Overview"),
        img("practice", "Practice areas: engineer, builder, explorer"),
        img("architecture", "System architecture"),
        '<a name="stack"></a>' + img("head-stack", "02 Stack"),
        img("skills", "Full skill matrix"),
        '<a name="insights"></a>' + img("head-insights", "03 Insights"),
        img("radar-domain", "Self-assessed proficiency radar and project portfolio by domain"),
        img("stackmix", "Toolchain emphasis"),
        img("pipeline", "How I build: perceive, retrieve, reason, serve, ship"),
        '<a name="activity"></a>' + img("head-activity", "04 Activity"),
        img("kpis", "Activity summary"),
        img("heatmap", "Contribution heatmap, refreshed daily"),
        img("weekday-trend", "Most active weekday and weekly trend"),
        img("monthly", "Contributions by month"),
        '<a name="systems"></a>' + img("head-systems", "05 Systems"),
        repos[0], repos[1],
        img("catalogue", "All shipped systems"),
        '<a name="journey"></a>' + img("head-journey", "06 Journey"),
        img("timeline", "Timeline from 2022 to 2026"),
        img("principles", "Engineering principles"),
        img("now", "Active development and currently exploring"),
        img("engage", "Work with me"),
        '<a name="contact"></a>' + img("head-contact", "07 Contact"),
        contacts,
        img("footer", "The model is the easy part. The system around it is the product."),
    ]
    return ("<!-- Generated by scripts/render_readme_cards.py. Edit the script, not this file.\n"
            "     Keep images in a row on one line with no spaces between them. -->\n"
            '<div align="center">\n' + "<br>\n".join(rows) + "\n</div>\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    days, _ = fetch_days()
    F = {
        "hero": hero(), "intro": intro(), "practice": practice(), "architecture": architecture(), "skills": skills(),
        "radar-domain": radar_domain(), "stackmix": stackmix(), "pipeline": pipeline(),
        "kpis": kpis(days), "heatmap": heatmap(days), "weekday-trend": weekday_trend(days), "monthly": monthly(days),
        "catalogue": catalogue(), "timeline": timeline(), "principles": principles(), "now": now(), "engage": engage(), "footer": footer(),
        "head-overview": section_header("01", "Overview", "Practice and architecture"),
        "head-stack": section_header("02", "Stack", "Layers of the system"),
        "head-insights": section_header("03", "Insights", "Proficiency and portfolio"),
        "head-activity": section_header("04", "Activity", "Pulse and patterns"),
        "head-systems": section_header("05", "Systems", "Selected repositories"),
        "head-journey": section_header("06", "Journey", "Timeline, craft and current work"),
        "head-contact": section_header("07", "Contact", "Open to remote"),
    }
    for i in range(len(NAV)):
        F[f"nav-{i+1}"] = nav_cell(i)
    for i in range(len(REPOS)):
        F[f"repo-{i+1}"] = repo(i)
    for i in range(len(CONTACTS)):
        F[f"contact-{i+1}"] = contact(i)
    for name, content in F.items():
        minidom.parseString(content.encode("utf-8"))
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    (ROOT / "README.md").write_text(readme(), encoding="utf-8")
    print(f"wrote {len(F)} cards + README.md")


if __name__ == "__main__":
    main()
