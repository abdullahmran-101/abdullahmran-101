#!/usr/bin/env python3
"""Renders every animated SVG card in ../cards. Strictly black / white / grey.

Run locally:   python scripts/render_readme_cards.py
With real contribution data: set GITHUB_TOKEN (the daily workflow does this).
"""
import json, os, random, datetime as dt, urllib.request
from pathlib import Path
from xml.dom import minidom

USER = "abdullahmran-101"
OUT = Path(__file__).resolve().parent.parent / "cards"

K0, K1, K2 = "#0A0A0A", "#111111", "#1C1C1C"
G1, G2, W1, W2 = "#777777", "#B3B3B3", "#E5E5E5", "#FFFFFF"
MID = "#444444"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

BASE_CSS = """
.pulse{animation:pulse 2.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
.rise{opacity:0;animation:rise .9s cubic-bezier(.2,.8,.2,1) forwards}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.fade{opacity:0;animation:fade .8s ease forwards}
@keyframes fade{to{opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01s!important;animation-iteration-count:1!important}}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def T(x, y, s, size=14, fill=W1, mono=False, weight=400, anchor="start", ls=0, cls="", delay=None, extra=""):
    c = f' class="{cls}"' if cls else ""
    d = f' style="animation-delay:{delay}s"' if delay is not None else ""
    fam = MONO if mono else SANS
    return (f'<text{c}{d} x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" font-family="{fam}" {extra}>{esc(s)}</text>')


def svg(w, h, body, css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{K2}"/><stop offset="1" stop-color="{K0}"/></linearGradient>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{K2}"/></pattern>
<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{W2}" stop-opacity="0"/><stop offset=".5" stop-color="{W2}" stop-opacity=".9"/><stop offset="1" stop-color="{W2}" stop-opacity="0"/></linearGradient>
</defs>
<style>{BASE_CSS}{css}</style>
{body}
</svg>'''


def frame(w, h, r=14):
    return (f'<rect width="{w}" height="{h}" rx="{r}" fill="{K0}"/>'
            f'<rect width="{w}" height="{h}" rx="{r}" fill="url(#bg)" opacity=".7"/>'
            f'<rect width="{w}" height="{h}" rx="{r}" fill="url(#dots)"/>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{r}" stroke="{G1}" stroke-opacity=".35"/>')


def card(w, h, inner, css=""):
    return svg(w, h, f'<g transform="translate(6,6)">{frame(w-12, h-12)}{inner}</g>', css)


# ------------------------------------------------------------------ hero
def hero():
    w, h = 1200, 440
    css = """
.draw{stroke-dashoffset:100;animation:draw 1.8s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.scan{animation:scan 3.8s ease-in-out infinite}
@keyframes scan{0%{transform:translateY(0);opacity:0}12%{opacity:1}88%{opacity:1}100%{transform:translateY(116px);opacity:0}}
.node{fill:@K2;animation:node 3.2s ease-in-out infinite}
@keyframes node{0%,100%{fill:@K2}50%{fill:@W2}}
""".replace("@K2", K2).replace("@W2", W2)
    b = [frame(w, h, 18)]
    b.append(T(48, 56, "ABDULLAH-IMRAN / PROFILE.SYS", 13, G1, mono=True, ls=3))
    b.append(f'<circle class="pulse" cx="856" cy="52" r="4" fill="{W2}"/>')
    b.append(T(872, 56, "OPEN TO ROLES & CONTRACTS", 13, G2, mono=True, extra='textLength="280"'))
    b.append(f'<line x1="48" y1="80" x2="1152" y2="80" stroke="{G1}" stroke-opacity=".3"/>')

    x, y, bw, bh, L = 70, 150, 740, 120, 26
    b.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" stroke="{G1}" stroke-opacity=".6" '
             f'pathLength="100" stroke-dasharray="100" class="draw"/>')
    for cx, cy, dx, dy in [(x, y, 1, 1), (x + bw, y, -1, 1), (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1)]:
        b.append(f'<path class="fade" style="animation-delay:1.2s" d="M{cx},{cy+dy*L} V{cy} H{cx+dx*L}" '
                 f'stroke="{W2}" stroke-width="3"/>')
    b.append(f'<g class="fade" style="animation-delay:1.6s"><rect x="{x}" y="{y-26}" width="150" height="26" fill="{W2}"/>'
             + T(x + 12, y - 8, "engineer 0.98", 13, K0, mono=True, weight=700) + '</g>')
    b.append(T(96, 240, "ABDULLAH IMRAN", 80, W2, weight=800, cls="rise", delay=0.3,
               extra='textLength="690" lengthAdjust="spacingAndGlyphs"'))
    b.append(f'<rect class="scan" x="{x}" y="{y}" width="{bw}" height="2" fill="url(#beam)"/>')
    b.append(T(70, 330, "AI/ML ENGINEER  ×  COMPUTER VISION  ×  INTELLIGENT PRODUCT DEVELOPMENT", 17, W1,
               mono=True, cls="fade", delay=0.9, extra='textLength="740"'))
    b.append(T(70, 374, "Build systems that survive contact with reality.", 22, G2, cls="fade", delay=1.2))
    b.append(T(70, 418, "LAHORE, PK  ·  REMOTE", 12, G1, mono=True, ls=2))
    b.append(T(1152, 418, "12 SHIPPED SYSTEMS", 12, G1, mono=True, ls=2, anchor="end"))

    b.append(T(900, 128, "PERCEPTION  →  REASONING  →  ACTION", 11, G1, mono=True, extra='textLength="252"'))
    layers = [(900, 4), (1010, 5), (1120, 3)]
    pts = [[(lx, 150 + i * (170 / (n - 1))) for i in range(n)] for lx, n in layers]
    for a, c in zip(pts, pts[1:]):
        for (x1, y1) in a:
            for (x2, y2) in c:
                b.append(f'<line x1="{x1}" y1="{y1:.1f}" x2="{x2}" y2="{y2:.1f}" stroke="{G1}" stroke-opacity=".28"/>')
    for li, layer in enumerate(pts):
        for i, (nx, ny) in enumerate(layer):
            b.append(f'<circle class="node" style="animation-delay:{li*.7+i*.25:.2f}s" cx="{nx}" cy="{ny:.1f}" r="6" stroke="{W1}"/>')
    return svg(w, h, "".join(b), css)


# ------------------------------------------------------------------ intro
def intro():
    w, h = 1200, 190
    b = [frame(w, h)]
    b.append(T(40, 46, "// INTRODUCTION", 13, G1, mono=True, ls=3))
    b.append(T(40, 96, "I design, build and deploy end-to-end intelligent systems: the model, the retrieval layer,", 22, W1, cls="rise", delay=.1))
    b.append(T(40, 130, "the agent logic, the backend API and the container it ships in.", 22, G2, cls="rise", delay=.3))
    b.append(f'<line x1="40" y1="148" x2="1160" y2="148" stroke="{G1}" stroke-opacity=".25"/>')
    b.append(T(40, 172, "PERCEPTION  →  KNOWLEDGE  →  REASONING  →  SERVICE  →  DELIVERY", 12, G1, mono=True, extra='textLength="720"'))
    return svg(w, h, "".join(b))


# ------------------------------------------------------------------ worlds
def world(i, title, stat, label, lines, motif, left, right):
    inner = [T(28, 42, f"0{i} / {title}", 13, G2, mono=True, ls=3),
             f'<line x1="28" y1="58" x2="360" y2="58" stroke="{G1}" stroke-opacity=".3"/>',
             T(28, 150, stat, 76, W2, weight=800, cls="rise", delay=.2 * i),
             T(28, 176, label, 11, G1, mono=True, ls=2)]
    for k, s in enumerate(lines):
        inner.append(T(28, 214 + k * 22, s, 14, W1 if k == 0 else G2, cls="fade", delay=.6 + k * .2 + i * .2))
    inner.append(motif)
    outer = ""
    for flag, ex in ((left, 6), (right, 394)):
        if flag:
            x2 = ex - 6 if ex == 6 else ex + 6
            outer += (f'<line x1="{ex}" y1="156" x2="{x2}" y2="156" stroke="{W2}" stroke-opacity=".6" stroke-width="1.5"/>'
                      f'<circle class="pulse" cx="{ex}" cy="156" r="3" fill="{W2}"/>')
    css = """
.sq{animation:sq 2.8s ease-in-out infinite}
@keyframes sq{0%,100%{opacity:.15}50%{opacity:1}}
.sl{animation:sl 3s ease-in-out infinite}
@keyframes sl{0%,100%{transform:translateX(0)}50%{transform:translateX(-14px)}}
"""
    body = f'<g transform="translate(6,6)">{frame(388, 288)}{"".join(inner)}</g>{outer}'
    return svg(400, 300, body, css)


def motif_engineer():
    g = ""
    for k, s in enumerate((72, 48, 24)):
        g += (f'<rect class="sq" style="animation-delay:{k*.4}s" x="{320-s/2}" y="{110-s/2}" width="{s}" height="{s}" '
              f'stroke="{W1}" stroke-width="1.5"/>')
    return g + f'<circle cx="320" cy="110" r="2.5" fill="{W2}"/>'


def motif_builder():
    g = ""
    for k in range(4):
        fill = W2 if k == 3 else "none"
        g += (f'<rect class="sl" style="animation-delay:{k*.35}s" x="{282+(k%2)*10}" y="{84+k*18}" width="64" height="12" rx="3" '
              f'fill="{fill}" stroke="{W1}" stroke-width="1.5"/>')
    return g


def motif_explorer():
    g = "".join(f'<circle cx="320" cy="110" r="{r}" stroke="{G1}" stroke-opacity=".7"/>' for r in (14, 28, 42))
    g += (f'<g><circle cx="362" cy="110" r="4" fill="{W2}"/>'
          f'<animateTransform attributeName="transform" type="rotate" from="0 320 110" to="360 320 110" dur="9s" repeatCount="indefinite"/></g>'
          f'<circle cx="320" cy="110" r="2.5" fill="{W2}"/>')
    return g


# ------------------------------------------------------------------ section titles
def title(idx, name, sub):
    w, h = 1200, 84
    b = [frame(w, h, 12),
         T(32, 50, f"[ {idx} ]", 14, G1, mono=True),
         T(110, 53, name, 26, W2, weight=700, ls=6),
         T(1168, 50, sub, 12, G1, mono=True, anchor="end", ls=2),
         f'<line x1="32" y1="70" x2="1168" y2="70" stroke="{G1}" stroke-opacity=".25"/>',
         f'<rect x="32" y="69" width="90" height="2" fill="url(#beam)">'
         f'<animateTransform attributeName="transform" type="translate" from="0 0" to="1046 0" dur="4.5s" repeatCount="indefinite"/></rect>']
    return svg(w, h, "".join(b))


# ------------------------------------------------------------------ skills
SKILLS = [
    (["Full-Stack Web", "Development & APIs"],
     ["Python", "Next.js", "HTML5 / CSS3", "FastAPI", "Django", "Flask", "Django REST Framework",
      "REST APIs", "Pydantic", "WebSockets", "Celery"]),
    (["Databases"],
     ["PostgreSQL", "SQL", "MongoDB", "Airtable", "Redis",
      "Vector DBs: FAISS, ChromaDB, Weaviate, Pinecone"]),
    (["Generative AI,", "LLMs & RAG"],
     ["Large Language Models", "LLM Fine-Tuning", "OpenAI API", "Google Gemini API", "Grok API", "Groq API",
      "Ollama Models", "Hugging Face", "AI Agents & Automation", "n8n · Zapier", "Function Calling & Tool Use",
      "Embeddings & Semantic Search", "RAG", "Agentic RAG", "Graph RAG", "Chunking & Re-ranking",
      "LangChain", "LangGraph", "LangSmith", "Ragas / DeepEval", "Model Context Protocol (MCP)",
      "Prompt Engineering"]),
    (["Machine Learning", "& Computer Vision"],
     ["PyTorch", "TensorFlow", "Keras", "Scikit-learn", "XGBoost / LightGBM", "CNN",
      "Hugging Face Transformers", "Model Fine-Tuning", "LoRA / PEFT", "Computer Vision", "OpenCV", "YOLO",
      "MediaPipe", "Multimodal AI", "Faster R-CNN", "Object Tracking (DeepSORT)", "Image Segmentation"]),
    (["Cloud &", "Deployment"],
     ["AWS SageMaker", "Docker", "CI/CD", "MLflow", "Streamlit", "Hugging Face Spaces", "Modal",
      "Vercel", "Netlify"]),
    (["AI-Assisted", "Development"],
     ["Claude Code", "Cursor", "GitHub Copilot", "AI-Assisted Debugging", "AI Code Review & Validation"]),
]


def skills():
    w, x0, xmax = 1200, 310, 1160
    css = ".chip{opacity:0;animation:fade .6s ease forwards}"
    b, y, n = [], 30, 0
    for names, items in SKILLS:
        # lay out chips first to know the row count
        x, row, placed = x0, 0, []
        for it in items:
            cw = int(len(it) * 7.3 + 24)
            if x + cw > xmax:
                x, row = x0, row + 1
            placed.append((it, x, row, cw))
            x += cw + 8
        block = max((row + 1) * 38, 52)
        b.append(T(40, y + 22, names[0], 17, W2, weight=600))
        if len(names) > 1:
            b.append(T(40, y + 44, names[1], 17, W2, weight=600))
        b.append(T(40, y + (66 if len(names) > 1 else 44), f"{len(items)} SKILLS", 11, G1, mono=True, ls=2))
        for it, cx, r, cw in placed:
            cy = y + r * 38
            b.append(f'<g class="chip" style="animation-delay:{n*.04:.2f}s"><rect x="{cx}" y="{cy}" width="{cw}" height="30" rx="15" '
                     f'stroke="{G1}" stroke-opacity=".8"/>' + T(cx + cw / 2, cy + 20, it, 12, W1, mono=True, anchor="middle") + '</g>')
            n += 1
        y += max(block, 80) + 18
        b.append(f'<line x1="40" y1="{y-9}" x2="1160" y2="{y-9}" stroke="{G1}" stroke-opacity=".25"/>')
    b.pop()  # no divider after the last block
    h = y + 12
    return svg(w, h, frame(w, h) + "".join(b), css)


# ------------------------------------------------------------------ contributions
def fetch_days():
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        q = ("query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{weeks{"
             "contributionDays{date contributionCount}}}}}}")
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": q, "variables": {"u": USER}}).encode(),
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
        c = 0 if rnd.random() < .38 else rnd.randint(1, 14) + (4 if d.weekday() < 5 and rnd.random() < .3 else 0)
        days.append((d.isoformat(), c))
        d += dt.timedelta(days=1)
    print("NOTE: sample contribution data in use. Set GITHUB_TOKEN for real data.")
    return days, False


def heatmap(days):
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    cols = len(weeks)
    pitch, size = 20, 16
    x0 = (1200 - (cols * pitch - 4)) // 2
    mx = max((c for _, c in days), default=1) or 1
    total = sum(c for _, c in days)
    lv = [K2, MID, G1, G2, W2]
    w, h = 1200, 270
    css = ".c{opacity:0;animation:fade .5s ease forwards}"
    b = [frame(w, h), T(40, 44, "CONTRIBUTIONS", 13, G2, mono=True, ls=3),
         T(1160, 44, f"{total:,} IN THE LAST 12 MONTHS", 13, G1, mono=True, ls=2, anchor="end")]
    last_m, last_c = None, -9
    for ci, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0][0]).strftime("%b").upper()
        if m != last_m and ci - last_c >= 3:
            b.append(T(x0 + ci * pitch, 72, m, 11, G1, mono=True))
            last_m, last_c = m, ci
        for ri, (_, c) in enumerate(wk):
            level = 0 if c == 0 else 1 + min(3, int(c * 4 / (mx + 1)))
            b.append(f'<rect class="c" style="animation-delay:{ci*.018:.3f}s" x="{x0+ci*pitch}" y="{84+ri*pitch}" '
                     f'width="{size}" height="{size}" rx="3" fill="{lv[level]}"/>')
    lx = 1160 - 5 * 20 - 90
    b.append(T(lx, 252, "LESS", 11, G1, mono=True))
    for k in range(5):
        b.append(f'<rect x="{lx+44+k*20}" y="242" width="14" height="14" rx="3" fill="{lv[k]}"/>')
    b.append(T(1160, 252, "MORE", 11, G1, mono=True, anchor="end"))
    return svg(w, h, "".join(b), css)


def activity(days):
    months = {}
    for ds, c in days:
        d = dt.date.fromisoformat(ds)
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    keys = sorted(months)[-12:]
    vals = [months[k] for k in keys]
    top = max(vals) or 1
    best = max(days, key=lambda t: t[1])
    streak = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        streak = max(streak, run)
    total = sum(c for _, c in days)
    w, h = 1200, 270
    css = ".bar{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .9s cubic-bezier(.2,.8,.2,1) forwards}@keyframes grow{to{transform:scaleY(1)}}"
    b = [frame(w, h), T(40, 46, "ACTIVITY / BY MONTH", 13, G2, mono=True, ls=3),
         f'<line x1="40" y1="212" x2="800" y2="212" stroke="{G1}" stroke-opacity=".4"/>',
         f'<line x1="840" y1="40" x2="840" y2="240" stroke="{G1}" stroke-opacity=".3"/>']
    for i, (k, v) in enumerate(zip(keys, vals)):
        bh = max(3, int(v / top * 120))
        x = 52 + i * 62
        last = i == len(keys) - 1
        b.append(f'<rect class="bar" style="animation-delay:{i*.07:.2f}s" x="{x}" y="{212-bh}" width="38" height="{bh}" rx="3" fill="{W2 if last else G1}"/>')
        b.append(T(x + 19, 212 - bh - 8, str(v), 11, G2, mono=True, anchor="middle", cls="fade", delay=.9))
        b.append(T(x + 19, 232, dt.date(k[0], k[1], 1).strftime("%b").upper(), 11, G1, mono=True, anchor="middle"))
    for n, (lab, val) in enumerate([("TOTAL", f"{total:,}"), ("LONGEST STREAK", f"{streak} DAYS"),
                                    (f"BUSIEST DAY · {best[0]}", str(best[1]))]):
        y = 84 + n * 62
        b.append(T(880, y, lab, 11, G1, mono=True, ls=2))
        b.append(T(880, y + 34, val, 34, W2, weight=700))
    return svg(w, h, "".join(b), css)


# ------------------------------------------------------------------ repos
def repo(i, name, d1, d2, chips, kind):
    inner = [T(28, 40, f"FEATURED / 0{i}", 12, G1, mono=True, ls=3),
             f'<line x1="28" y1="54" x2="360" y2="54" stroke="{G1}" stroke-opacity=".3"/>',
             T(28, 94, name, 28, W2, weight=700, cls="rise", delay=.1 * i),
             T(28, 124, d1, 14, G2), T(28, 144, d2, 14, G2)]
    x = 28
    for c in chips:
        cw = int(len(c) * 7.4 + 24)
        inner.append(f'<rect x="{x}" y="164" width="{cw}" height="26" rx="13" stroke="{G1}" stroke-opacity=".7"/>')
        inner.append(T(x + cw / 2, 181, c, 12, W1, mono=True, anchor="middle"))
        x += cw + 8
    inner.append(T(28, 214, "VIEW REPOSITORY  →", 12, W2, mono=True, ls=2))
    if kind == "fusion":
        for k, yy in enumerate((44, 62, 80, 98)):
            inner.append(f'<circle class="sq" style="animation-delay:{k*.3}s" cx="300" cy="{yy}" r="3" fill="{W2}"/>')
            inner.append(f'<line x1="300" y1="{yy}" x2="338" y2="71" stroke="{G1}" stroke-opacity=".6"/>')
        inner.append(f'<circle cx="338" cy="71" r="6" fill="{W2}"/><line x1="338" y1="71" x2="366" y2="71" stroke="{W1}"/>')
    elif kind == "detect":
        inner.append(f'<rect x="312" y="48" width="52" height="46" stroke="{W1}" stroke-width="1.5" class="sq"/>')
        inner.append(f'<path d="M338 42V100M306 71H370" stroke="{G1}" stroke-opacity=".6"/><circle cx="338" cy="71" r="3" fill="{W2}"/>')
    else:
        inner.append(f'<circle cx="338" cy="71" r="22" stroke="{G1}" stroke-dasharray="4 5"/>'
                     f'<g><circle cx="338" cy="49" r="4" fill="{W2}"/>'
                     f'<animateTransform attributeName="transform" type="rotate" from="0 338 71" to="360 338 71" dur="6s" repeatCount="indefinite"/></g>'
                     f'<circle cx="338" cy="71" r="3" fill="{W2}"/>')
    return card(400, 240, "".join(inner), ".sq{animation:sq 2.4s ease-in-out infinite}@keyframes sq{0%,100%{opacity:.25}50%{opacity:1}}")


# ------------------------------------------------------------------ now
def now():
    w, h = 1200, 300
    b = [frame(w, h), T(40, 46, "ACTIVE DEVELOPMENT", 13, G2, mono=True, ls=3),
         f'<line x1="780" y1="30" x2="780" y2="270" stroke="{G1}" stroke-opacity=".3"/>',
         T(820, 46, "CURRENTLY EXPLORING", 13, G2, mono=True, ls=3)]
    rows = [("Hospital Procurement Platform", "Forecasting and supplier scoring shipped", 5, 2, "V2 / V5"),
            ("AI Coding Assistant", "VS Code extension, FastAPI multi-LLM router", 10, 2, "PHASE 2 / 10"),
            ("Lahori", "Lahore food discovery platform", 0, 0, "IN DEVELOPMENT")]
    for r, (name, sub, n, done, lab) in enumerate(rows):
        y = 100 + r * 62
        b.append(T(40, y, name, 19, W2, weight=600))
        b.append(T(40, y + 22, sub, 12, G1, mono=True))
        if n:
            sw = 210 // n - 6
            for k in range(n):
                fill = W2 if k < done else K2
                b.append(f'<rect x="{410+k*(sw+6)}" y="{y-12}" width="{sw}" height="10" rx="2" fill="{fill}" stroke="{G1}" stroke-opacity="{0 if k < done else .5}"/>')
            b.append(T(410, y + 22, lab, 11, G2, mono=True, ls=2))
        else:
            b.append(f'<circle class="pulse" cx="414" cy="{y-7}" r="4" fill="{W2}"/>')
            b.append(T(428, y-3, lab, 11, G2, mono=True, ls=2))
    x, y, i = 820, 76, 0
    for c in ["Agentic AI", "Multimodal fusion", "pgvector", "RBAC & multi-tenancy", "Next.js dashboards", "Production MLOps"]:
        cw = int(len(c) * 7.8 + 28)
        if x + cw > 1160:
            x, y = 820, y + 44
        b.append(f'<g class="fade" style="animation-delay:{.3+i*.15:.2f}s"><rect x="{x}" y="{y}" width="{cw}" height="30" rx="15" stroke="{G1}" stroke-opacity=".8"/>'
                 + T(x + cw / 2, y + 20, c, 13, W1, mono=True, anchor="middle") + '</g>')
        x += cw + 10
        i += 1
    return svg(w, h, "".join(b))


def footer():
    w, h = 1200, 110
    b = [frame(w, h),
         T(600, 52, "THE MODEL IS THE EASY PART. THE SYSTEM AROUND IT IS THE PRODUCT.", 14, G2, mono=True, anchor="middle", extra='textLength="900"'),
         f'<line x1="40" y1="76" x2="1160" y2="76" stroke="{G1}" stroke-opacity=".25"/>',
         f'<rect x="40" y="75" width="90" height="2" fill="url(#beam)"><animateTransform attributeName="transform" type="translate" from="0 0" to="1030 0" dur="5s" repeatCount="indefinite"/></rect>',
         T(600, 98, "ABDULLAH IMRAN  ·  LAHORE", 11, G1, mono=True, anchor="middle", ls=3)]
    return svg(w, h, "".join(b))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    days, _ = fetch_days()
    files = {
        "hero": hero(), "intro": intro(),
        "world-engineer": world(1, "ENGINEER", "90%", "BODY-FAT MODEL ACCURACY",
                                ["Computer vision · Deep learning", "YOLOv12 · MediaPipe · KeypointRCNN", "Production-ready intelligent systems"],
                                motif_engineer(), False, True),
        "world-builder": world(2, "BUILDER", "12", "SHIPPED SYSTEMS",
                               ["FastAPI · Django · Celery · Docker", "RAG apps, agents, automation APIs", "From prototype to deployed product"],
                               motif_builder(), True, True),
        "world-explorer": world(3, "EXPLORER", "3", "ACTIVE BUILDS",
                                ["Agentic AI · multimodal fusion", "LLMs, retrieval, new tooling", "Experiments and open source"],
                                motif_explorer(), True, False),
        "title-stack": title("01", "TECH STACK", "LAYERS OF THE SYSTEM"),
        "title-contrib": title("02", "CONTRIBUTIONS", "COMMITS, DAILY"),
        "title-systems": title("03", "FEATURED SYSTEMS", "SELECTED REPOSITORIES"),
        "title-now": title("04", "NOW", "BUILDING AND EXPLORING"),
        "title-contact": title("05", "CONTACT", "OPEN TO REMOTE"),
        "skills": skills(), "heatmap": heatmap(days), "activity": activity(days),
        "repo-healmatrix": repo(1, "HealMatrix AI", "Crisis-gated multimodal assistant fusing", "text, voice, face and posture.",
                                ["RAG", "RoBERTa", "FastAPI", "Docker"], "fusion"),
        "repo-cheatify": repo(2, "Cheatify", "Real-time exam proctoring with object", "detection, pose and gaze risk scoring.",
                              ["YOLOv12", "MediaPipe", "OpenCV"], "detect"),
        "repo-agentflow": repo(3, "AgentFlow AI", "Multi-provider ReAct platform with live", "tool traces, memory and failover.",
                               ["LangGraph", "SSE", "FastAPI"], "loop"),
        "now": now(), "footer": footer(),
    }
    for name, content in files.items():
        minidom.parseString(content.encode("utf-8"))  # fails loudly on invalid XML
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} cards to {OUT}")


if __name__ == "__main__":
    main()
