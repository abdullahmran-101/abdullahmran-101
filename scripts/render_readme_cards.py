#!/usr/bin/env python3
"""Renders every animated SVG card in ../cards  (aurora palette on a deep navy base).

Run locally:   python scripts/render_readme_cards.py
Real contribution data: set GITHUB_TOKEN (the daily workflow does this).
"""
import json, os, math, random, datetime as dt, urllib.request
from pathlib import Path
from xml.dom import minidom

USER = "abdullahmran-101"
OUT = Path(__file__).resolve().parent.parent / "cards"

CY, VI, PK, AM, GR = "#22D3EE", "#8B5CF6", "#F472B6", "#FBBF24", "#34D399"
BG0, BG2, LN = "#070A14", "#151C36", "#2A3558"
TX, MU, DM = "#F1F5F9", "#94A3B8", "#64748B"
ACC = [CY, VI, PK, AM, GR]
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
NB = "\u00a0"

BASE_CSS = """
.pulse{animation:pulse 2.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.rise{opacity:0;animation:rise .9s cubic-bezier(.2,.8,.2,1) forwards}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.fade{opacity:0;animation:fade .8s ease forwards}
@keyframes fade{to{opacity:1}}
.tw{animation:tw 3s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.12}50%{opacity:.9}}
.float{animation:float 5s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01s!important;animation-iteration-count:1!important}}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def T(x, y, s, size=14, fill=TX, mono=False, weight=400, anchor="start", ls=0, cls="", delay=None, extra=""):
    c = f' class="{cls}"' if cls else ""
    d = f' style="animation-delay:{delay}s"' if delay is not None else ""
    fam = MONO if mono else SANS
    return (f'<text{c}{d} x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" font-family="{fam}" {extra}>{esc(s)}</text>')


def chip(x, y, s, col, fs=12, h=28):
    cw = int(len(s) * fs * 0.61 + 24)
    g = (f'<rect x="{x}" y="{y}" width="{cw}" height="{h}" rx="{h/2}" fill="{col}" fill-opacity=".10" '
         f'stroke="{col}" stroke-opacity=".75"/>' + T(x + cw / 2, y + h / 2 + fs * .35, s, fs, TX, mono=True, anchor="middle"))
    return g, cw


def svg(w, h, body, css="", defs=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img">
<defs>
<linearGradient id="aur" x1="0" y1="0" x2="1" y2="0" spreadMethod="reflect"><stop offset="0" stop-color="{CY}"/><stop offset=".5" stop-color="{VI}"/><stop offset="1" stop-color="{PK}"/><animate attributeName="x1" values="0;.7;0" dur="9s" repeatCount="indefinite"/><animate attributeName="x2" values="1;1.7;1" dur="9s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="aurv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PK}"/><stop offset=".5" stop-color="{VI}"/><stop offset="1" stop-color="{CY}"/></linearGradient>
<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CY}" stop-opacity="0"/><stop offset=".5" stop-color="{CY}"/><stop offset="1" stop-color="{CY}" stop-opacity="0"/></linearGradient>
<filter id="glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="45"/></filter>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#1B2442"/></pattern>
{defs}
</defs>
<style>{BASE_CSS}{css}</style>
{body}
</svg>'''


def frame(w, h, r=16):
    return (f'<clipPath id="cl"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>'
            f'<rect width="{w}" height="{h}" rx="{r}" fill="{BG0}"/>'
            f'<g clip-path="url(#cl)">'
            f'<circle cx="{w*.08:.0f}" cy="{h*.1:.0f}" r="{h*.75:.0f}" fill="{CY}" opacity=".13" filter="url(#blur)"/>'
            f'<circle cx="{w*.92:.0f}" cy="{h*.95:.0f}" r="{h*.75:.0f}" fill="{VI}" opacity=".20" filter="url(#blur)"/>'
            f'<circle cx="{w*.55:.0f}" cy="{h*1.1:.0f}" r="{h*.4:.0f}" fill="{PK}" opacity=".10" filter="url(#blur)"/>'
            f'<rect width="{w}" height="{h}" fill="url(#dots)"/></g>'
            f'<rect x=".6" y=".6" width="{w-1.2}" height="{h-1.2}" rx="{r}" stroke="url(#aur)" stroke-opacity=".6" stroke-width="1.2"/>')


def card(w, h, inner, css=""):
    return svg(w, h, f'<g transform="translate(6,6)">{frame(w-12, h-12)}{inner}</g>', css)


def waves(w, base, color_a, color_b):
    def path(amp, ph, wl, y):
        pts = " ".join(f"L{x},{y + amp*math.sin(2*math.pi*x/wl + ph):.1f}" for x in range(0, w + 601, 20))
        return f"M0,{y + amp*math.sin(ph):.1f} {pts} L{w+600},{base+200} L0,{base+200} Z"
    return (f'<g clip-path="url(#cl)"><path class="wv1" d="{path(14,0,600,base)}" fill="{color_a}" fill-opacity=".16"/>'
            f'<path class="wv2" d="{path(10,1.6,600,base+14)}" fill="{color_b}" fill-opacity=".14"/></g>')


WAVE_CSS = ".wv1{animation:wv 14s linear infinite}.wv2{animation:wv 22s linear infinite reverse}@keyframes wv{to{transform:translateX(-600px)}}"


# ------------------------------------------------------------------ hero
def hero():
    w, h = 1200, 500
    css = WAVE_CSS + """
.draw{stroke-dashoffset:100;animation:draw 1.8s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.scan{animation:scan 3.8s ease-in-out infinite}
@keyframes scan{0%{transform:translateY(0);opacity:0}12%{opacity:1}88%{opacity:1}100%{transform:translateY(116px);opacity:0}}
.cyc{opacity:0;animation:cyc 15s infinite both}
@keyframes cyc{0%{opacity:0;transform:translateY(8px)}3%{opacity:1;transform:none}17%{opacity:1;transform:none}20%{opacity:0;transform:translateY(-8px)}100%{opacity:0}}
"""
    rnd = random.Random(3)
    b = [frame(w, h, 20)]
    for _ in range(46):
        b.append(f'<circle class="tw" style="animation-delay:{rnd.random()*3:.2f}s" cx="{rnd.randint(20,1180)}" cy="{rnd.randint(96,430)}" r="{rnd.choice([.8,1,1.3,1.7])}" fill="{TX}"/>')
    b.append(waves(w, 440, CY, PK))
    b.append(f'<circle class="pulse" cx="52" cy="52" r="4" fill="{CY}" filter="url(#glow)"/>')
    b.append(T(66, 57, "ABDULLAH-IMRAN / PROFILE.SYS", 13, MU, mono=True, ls=3))
    b.append(f'<circle class="pulse" cx="856" cy="52" r="4" fill="{GR}" filter="url(#glow)"/>')
    b.append(T(872, 57, "OPEN TO ROLES & CONTRACTS", 13, GR, mono=True, extra='textLength="280"'))
    b.append(f'<line x1="48" y1="80" x2="1152" y2="80" stroke="url(#aur)" stroke-opacity=".5"/>')

    x, y, bw, bh, L = 70, 150, 740, 120, 26
    b.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" stroke="{CY}" stroke-opacity=".45" pathLength="100" stroke-dasharray="100" class="draw"/>')
    for cx, cy, dx, dy in [(x, y, 1, 1), (x + bw, y, -1, 1), (x, y + bh, 1, -1), (x + bw, y + bh, -1, -1)]:
        b.append(f'<path class="fade" style="animation-delay:1.2s" d="M{cx},{cy+dy*L} V{cy} H{cx+dx*L}" stroke="{CY}" stroke-width="3" filter="url(#glow)"/>')
    b.append(f'<g class="fade" style="animation-delay:1.6s"><rect x="{x}" y="{y-26}" width="150" height="26" fill="{CY}"/>'
             + T(x + 12, y - 8, "engineer 0.98", 13, BG0, mono=True, weight=700)
             + f'<rect x="{x+bw-210}" y="{y+bh}" width="210" height="26" fill="{PK}"/>'
             + T(x + bw - 198, y + bh + 18, "computer vision 0.97", 13, BG0, mono=True, weight=700) + '</g>')
    b.append(T(96, 240, "ABDULLAH IMRAN", 80, "url(#aur)", weight=800, cls="rise", delay=.3,
               extra='textLength="690" lengthAdjust="spacingAndGlyphs" filter="url(#glow)"'))
    b.append(f'<rect class="scan" x="{x}" y="{y}" width="{bw}" height="2" fill="url(#beam)"/>')
    roles = [("AI / ML ENGINEER", CY), ("COMPUTER VISION", PK), ("LLMs · RAG · AGENTS", VI),
             ("INTELLIGENT PRODUCT DEVELOPMENT", AM), ("FASTAPI · DOCKER · MLOPS", GR)]
    for k, (r, c) in enumerate(roles):
        b.append(T(70, 328, "▸ " + r, 22, c, mono=True, weight=700, cls="cyc", delay=k * 3))
    b.append(T(70, 368, "AI/ML ENGINEER  ×  COMPUTER VISION  ×  INTELLIGENT PRODUCT DEVELOPMENT", 15, MU, mono=True, cls="fade", delay=.9, extra='textLength="740"'))
    b.append(T(70, 412, "Build systems that survive contact with reality.", 22, TX, cls="fade", delay=1.2))
    b.append(T(70, 474, "LAHORE, PK  ·  REMOTE", 12, MU, mono=True, ls=2))
    b.append(T(1152, 474, "12 SHIPPED SYSTEMS  ·  6 CERTIFICATIONS", 12, MU, mono=True, ls=2, anchor="end"))

    b.append(T(900, 140, "PERCEPTION → REASONING → ACTION", 11, DM, mono=True, extra='textLength="252"'))
    layers, cols = [(900, 4), (1010, 5), (1120, 3)], [CY, VI, PK]
    pts = [[(lx, 170 + i * (190 / (n - 1))) for i in range(n)] for lx, n in layers]
    k = 0
    for li, (a, c) in enumerate(zip(pts, pts[1:])):
        for ai, (x1, y1) in enumerate(a):
            for ci, (x2, y2) in enumerate(c):
                b.append(f'<line x1="{x1}" y1="{y1:.1f}" x2="{x2}" y2="{y2:.1f}" stroke="{LN}"/>')
                if (li * 7 + ai * 3 + ci) % 3 == 0:
                    col = ACC[k % 5]
                    b.append(f'<circle r="2.6" fill="{col}" filter="url(#glow)"><animateMotion path="M{x1},{y1:.1f} L{x2},{y2:.1f}" dur="2.2s" begin="{k*.37:.2f}s" repeatCount="indefinite"/></circle>')
                    k += 1
    for li, layer in enumerate(pts):
        for i, (nx, ny) in enumerate(layer):
            b.append(f'<circle class="pulse" style="animation-delay:{li*.6+i*.3:.1f}s" cx="{nx}" cy="{ny:.1f}" r="7" fill="{BG0}" stroke="{cols[li]}" stroke-width="2" filter="url(#glow)"/>')
    return svg(w, h, "".join(b), css)


# ------------------------------------------------------------------ marquee
def marquee(items, rev=False):
    w, h = 1200, 64
    sep = " ✦ "
    L = len("".join(i + sep for i in items)) * 12
    tsp = "".join(f'<tspan fill="{ACC[i % 5]}">{esc(it)}</tspan><tspan fill="{DM}">{sep}</tspan>' for i, it in enumerate(items))
    frm, to = ((-L, 0) if rev else (0, -L))
    t = lambda x: (f'<text x="{x}" y="39" font-size="18" font-weight="700" font-family="{MONO}" textLength="{L}">{tsp}</text>')
    defs = (f'<linearGradient id="fl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="fr" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG0}" stop-opacity="0"/></linearGradient>')
    body = (frame(w, h, 14) + '<g clip-path="url(#cl)">'
            f'<g><animateTransform attributeName="transform" type="translate" from="{frm} 0" to="{to} 0" dur="{L/55:.0f}s" repeatCount="indefinite"/>{t(0)}{t(L)}</g>'
            f'<rect width="140" height="{h}" fill="url(#fl)"/><rect x="{w-140}" width="140" height="{h}" fill="url(#fr)"/></g>')
    return svg(w, h, body, "", defs)


# ------------------------------------------------------------------ intro / terminal
def intro():
    w, h = 1200, 210
    b = [frame(w, h), T(40, 46, "// INTRODUCTION", 13, CY, mono=True, ls=3),
         T(40, 96, "I design, build and deploy end-to-end intelligent systems: the model, the retrieval layer,", 22, TX, cls="rise", delay=.1),
         T(40, 130, "the agent logic, the backend API and the container it ships in.", 22, MU, cls="rise", delay=.3)]
    x = 40
    for i, s in enumerate(["PERCEPTION", "KNOWLEDGE", "REASONING", "SERVICE", "DELIVERY"]):
        g, cw = chip(x, 160, s, ACC[i], 12, 30)
        b.append(f'<g class="fade" style="animation-delay:{.5+i*.15:.2f}s">{g}</g>')
        x += cw
        if i < 4:
            b.append(T(x + 14, 180, "→", 14, DM, mono=True, anchor="middle"))
            x += 28
    return svg(w, h, "".join(b))


def terminal():
    w, h = 1200, 400
    lines = [("OK", "Loading identity", "Abdullah Imran, AI/ML Engineer"), ("OK", "Starting perception", "vision | speech | text"),
             ("OK", "Linking knowledge", "FAISS | ChromaDB | SQLite | Postgres"), ("OK", "Attaching reasoning", "LLaMA 3.3 70B | Gemini | GPT | Grok"),
             ("OK", "Spawning agents", "ReAct loops | multi-provider routing"), ("OK", "Exposing services", "FastAPI | Django | Celery | n8n"),
             ("OK", "Containerising", "Docker"), ("WARN", "Notebook-only demos", "disabled by policy"),
             ("OK", "Profile ready", "type a command below")]
    b = [frame(w, h, 16), f'<rect x="0" y="0" width="{w}" height="44" rx="16" fill="{BG2}" fill-opacity=".7"/>',
         f'<circle cx="28" cy="22" r="6" fill="{PK}"/><circle cx="50" cy="22" r="6" fill="{AM}"/><circle cx="72" cy="22" r="6" fill="{GR}"/>',
         T(600, 27, "abdullah@lahore: ~", 13, MU, mono=True, anchor="middle")]
    clips, t = [], .4

    def line(n, y, parts):
        nonlocal t
        clips.append(f'<clipPath id="t{n}"><rect x="30" y="{y-18}" width="0" height="26"><animate attributeName="width" from="0" to="1130" begin="{t:.1f}s" dur=".7s" fill="freeze"/></rect></clipPath>')
        tsp = "".join(f'<tspan fill="{c}">{esc(s).replace(" ", NB)}</tspan>' for s, c in parts)
        b.append(f'<g clip-path="url(#t{n})">' + f'<text x="40" y="{y}" font-size="15" font-family="{MONO}">{tsp}</text></g>')
        t += .55

    line(0, 84, [("abdullah@lahore", GR), (":", TX), ("~", VI), ("$ ", TX), ("./boot_profile.sh", CY)])
    for i, (tag, lab, val) in enumerate(lines):
        dots = "." * max(3, 26 - len(lab))
        line(i + 1, 122 + i * 26, [("[ OK ]" if tag == "OK" else "[WARN]", GR if tag == "OK" else AM), (f"  {lab} {dots} ", MU), (val, TX)])
    y_last = 122 + len(lines) * 26 + 12
    line(99, y_last, [("abdullah@lahore", GR), (":", TX), ("~", VI), ("$ ", TX)])
    b.append(f'<rect x="{40+19*9.0:.0f}" y="{y_last-14}" width="9" height="18" fill="{CY}"><animate attributeName="opacity" values="1;0;1" dur="1s" begin="{t:.1f}s" repeatCount="indefinite"/></rect>')
    return svg(w, h, "".join(clips) + "".join(b))


# ------------------------------------------------------------------ worlds + stat tiles
def world(i, title, acc, stat, label, lines, motif, left, right):
    inner = [T(28, 42, f"0{i} / {title}", 13, acc, mono=True, ls=3),
             f'<line x1="28" y1="58" x2="360" y2="58" stroke="{acc}" stroke-opacity=".35"/>',
             T(28, 150, stat, 76, acc, weight=800, cls="rise", delay=.2 * i, extra='filter="url(#glow)"'),
             T(28, 176, label, 11, MU, mono=True, ls=2)]
    for k, s in enumerate(lines):
        inner.append(T(28, 214 + k * 22, s, 14, TX if k == 0 else MU, cls="fade", delay=.6 + k * .2 + i * .2))
    inner.append(motif)
    outer = ""
    for flag, ex in ((left, 6), (right, 394)):
        if flag:
            x2 = ex - 6 if ex == 6 else ex + 6
            outer += (f'<line x1="{ex}" y1="156" x2="{x2}" y2="156" stroke="{acc}" stroke-width="2"/>'
                      f'<circle class="pulse" cx="{ex}" cy="156" r="3.5" fill="{acc}" filter="url(#glow)"/>')
    css = """
.sq{animation:sq 2.8s ease-in-out infinite}
@keyframes sq{0%,100%{opacity:.2}50%{opacity:1}}
.sl{animation:sl 3s ease-in-out infinite}
@keyframes sl{0%,100%{transform:translateX(0)}50%{transform:translateX(-14px)}}
"""
    return svg(400, 300, f'<g transform="translate(6,6)">{frame(388, 288)}{"".join(inner)}</g>{outer}', css)


def motif_engineer(c):
    g = "".join(f'<rect class="sq" style="animation-delay:{k*.4}s" x="{320-s/2}" y="{110-s/2}" width="{s}" height="{s}" stroke="{c}" stroke-width="2" filter="url(#glow)"/>' for k, s in enumerate((72, 48, 24)))
    return g + f'<circle cx="320" cy="110" r="2.5" fill="{c}"/>'


def motif_builder(c):
    return "".join(f'<rect class="sl" style="animation-delay:{k*.35}s" x="{282+(k%2)*10}" y="{84+k*18}" width="64" height="12" rx="3" '
                   f'fill="{c if k == 3 else "none"}" stroke="{c}" stroke-width="1.5" filter="url(#glow)"/>' for k in range(4))


def motif_explorer(c):
    g = "".join(f'<circle cx="320" cy="110" r="{r}" stroke="{c}" stroke-opacity=".5"/>' for r in (14, 28, 42))
    return g + (f'<g><circle cx="362" cy="110" r="4" fill="{AM}" filter="url(#glow)"/><animateTransform attributeName="transform" type="rotate" from="0 320 110" to="360 320 110" dur="9s" repeatCount="indefinite"/></g>'
                f'<g><circle cx="306" cy="110" r="3" fill="{CY}"/><animateTransform attributeName="transform" type="rotate" from="360 320 110" to="0 320 110" dur="5s" repeatCount="indefinite"/></g>'
                f'<circle cx="320" cy="110" r="3" fill="{c}"/>')


def tile(i, big, label, acc, kind, val):
    inner = [T(24, 84, big, 54, acc, weight=800, cls="rise", delay=.15 * i, extra='filter="url(#glow)"'), T(24, 114, label, 11, MU, mono=True, ls=2)]
    if kind == "ring":
        C = 2 * math.pi * 30
        inner.append(f'<circle cx="228" cy="68" r="30" stroke="{LN}" stroke-width="7"/>'
                     f'<circle cx="228" cy="68" r="30" stroke="{acc}" stroke-width="7" stroke-linecap="round" transform="rotate(-90 228 68)" filter="url(#glow)" stroke-dasharray="0 {C:.1f}">'
                     f'<animate attributeName="stroke-dasharray" from="0 {C:.1f}" to="{C*val/100:.1f} {C:.1f}" dur="1.6s" begin="{.2*i}s" fill="freeze"/></circle>')
    else:
        for k in range(val):
            cx, cy = 190 + (k % 4) * 20, 40 + (k // 4) * 20
            inner.append(f'<circle class="tw" style="animation-delay:{k*.25:.2f}s" cx="{cx}" cy="{cy}" r="5" fill="{acc}" filter="url(#glow)"/>')
    return card(300, 150, "".join(inner))


# ------------------------------------------------------------------ section titles
def title(idx, name, sub, acc):
    w, h = 1200, 84
    b = [frame(w, h, 14), f'<rect x="32" y="27" width="58" height="28" rx="14" fill="{acc}" fill-opacity=".14" stroke="{acc}"/>',
         T(61, 46, idx, 13, acc, mono=True, anchor="middle", weight=700), T(110, 52, name, 26, "url(#aur)", weight=800, ls=6),
         T(1168, 50, sub, 12, MU, mono=True, anchor="end", ls=2),
         f'<line x1="32" y1="70" x2="1168" y2="70" stroke="{LN}"/>',
         f'<rect x="32" y="69" width="110" height="2.5" fill="url(#beam)"><animateTransform attributeName="transform" type="translate" from="0 0" to="1026 0" dur="4.5s" repeatCount="indefinite"/></rect>']
    return svg(w, h, "".join(b))


# ------------------------------------------------------------------ skills
SKILLS = [
    (["Full-Stack Web", "Development & APIs"], CY,
     ["Python", "Next.js", "HTML5 / CSS3", "FastAPI", "Django", "Flask", "Django REST Framework", "REST APIs", "Pydantic", "WebSockets", "Celery"]),
    (["Databases"], GR, ["PostgreSQL", "SQL", "MongoDB", "Airtable", "Redis", "Vector DBs: FAISS, ChromaDB, Weaviate, Pinecone"]),
    (["Generative AI,", "LLMs & RAG"], VI,
     ["Large Language Models", "LLM Fine-Tuning", "OpenAI API", "Google Gemini API", "Grok API", "Groq API", "Ollama Models", "Hugging Face",
      "AI Agents & Automation", "n8n · Zapier", "Function Calling & Tool Use", "Embeddings & Semantic Search", "RAG", "Agentic RAG", "Graph RAG",
      "Chunking & Re-ranking", "LangChain", "LangGraph", "LangSmith", "Ragas / DeepEval", "Model Context Protocol (MCP)", "Prompt Engineering"]),
    (["Machine Learning", "& Computer Vision"], PK,
     ["PyTorch", "TensorFlow", "Keras", "Scikit-learn", "XGBoost / LightGBM", "CNN", "Hugging Face Transformers", "Model Fine-Tuning", "LoRA / PEFT",
      "Computer Vision", "OpenCV", "YOLO", "MediaPipe", "Multimodal AI", "Faster R-CNN", "Object Tracking (DeepSORT)", "Image Segmentation"]),
    (["Cloud &", "Deployment"], AM, ["AWS SageMaker", "Docker", "CI/CD", "MLflow", "Streamlit", "Hugging Face Spaces", "Modal", "Vercel", "Netlify"]),
    (["AI-Assisted", "Development"], CY, ["Claude Code", "Cursor", "GitHub Copilot", "AI-Assisted Debugging", "AI Code Review & Validation"]),
]


def skills():
    w, x0, xmax = 1200, 310, 1160
    css = ".chip{opacity:0;animation:fade .6s ease forwards}"
    b, y, n = [], 30, 0
    for names, acc, items in SKILLS:
        x, row, placed = x0, 0, []
        for it in items:
            cw = int(len(it) * 7.3 + 24)
            if x + cw > xmax:
                x, row = x0, row + 1
            placed.append((it, x, row, cw))
            x += cw + 8
        block = max((row + 1) * 38, 52)
        b.append(f'<rect x="40" y="{y+4}" width="4" height="{40 if len(names)>1 else 22}" rx="2" fill="{acc}" filter="url(#glow)"/>')
        b.append(T(56, y + 22, names[0], 17, TX, weight=700))
        if len(names) > 1:
            b.append(T(56, y + 44, names[1], 17, TX, weight=700))
        b.append(T(56, y + (66 if len(names) > 1 else 44), f"{len(items)} SKILLS", 11, acc, mono=True, ls=2))
        for it, cx, r, cw in placed:
            cy = y + r * 38
            b.append(f'<g class="chip" style="animation-delay:{n*.04:.2f}s"><rect x="{cx}" y="{cy}" width="{cw}" height="30" rx="15" fill="{acc}" fill-opacity=".09" stroke="{acc}" stroke-opacity=".7"/>'
                     + T(cx + cw / 2, cy + 20, it, 12, TX, mono=True, anchor="middle") + '</g>')
            n += 1
        y += max(block, 80) + 18
        b.append(f'<line x1="40" y1="{y-9}" x2="1160" y2="{y-9}" stroke="{LN}"/>')
    b.pop()
    h = y + 12
    return svg(w, h, frame(w, h) + "".join(b), css)


# ------------------------------------------------------------------ insights
def radar():
    data = [("Python", 92), ("LLM Apps", 90), ("RAG", 88), ("FastAPI", 86), ("Agents", 85), ("Vision", 82), ("Docker", 78), ("MLOps", 72)]
    R, n = 112, len(data)
    ang = lambda i: -math.pi / 2 + i * 2 * math.pi / n
    g = []
    for f in (.25, .5, .75, 1):
        g.append(f'<polygon points="{" ".join(f"{R*f*math.cos(ang(i)):.1f},{R*f*math.sin(ang(i)):.1f}" for i in range(n))}" stroke="{LN}"/>')
    for i in range(n):
        g.append(f'<line x1="0" y1="0" x2="{R*math.cos(ang(i)):.1f}" y2="{R*math.sin(ang(i)):.1f}" stroke="{LN}"/>')
    pts = [(R * v / 100 * math.cos(ang(i)), R * v / 100 * math.sin(ang(i))) for i, (_, v) in enumerate(data)]
    g.append(f'<polygon class="rad" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="url(#aur)" fill-opacity=".28" stroke="{CY}" stroke-width="2" filter="url(#glow)"/>')
    for i, ((x, y), (nm, v)) in enumerate(zip(pts, data)):
        g.append(f'<circle class="pulse" style="animation-delay:{i*.25:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{ACC[i%5]}" filter="url(#glow)"/>')
        lx, ly = (R + 30) * math.cos(ang(i)), (R + 30) * math.sin(ang(i))
        an = "middle" if abs(lx) < 8 else ("start" if lx > 0 else "end")
        g.append(T(f"{lx:.1f}", f"{ly-2:.1f}", nm, 13, TX, anchor=an, weight=600) + T(f"{lx:.1f}", f"{ly+14:.1f}", str(v), 12, ACC[i % 5], mono=True, anchor=an))
    inner = (T(28, 40, "SELF-ASSESSED PROFICIENCY", 13, CY, mono=True, ls=3) + T(28, 60, "radar, out of 100", 11, DM, mono=True)
             + f'<g transform="translate(294 208)">{"".join(g)}</g>')
    return card(600, 380, inner, ".rad{animation:radin 1.6s cubic-bezier(.2,.8,.2,1) both}@keyframes radin{from{transform:scale(0)}to{transform:scale(1)}}")


def donut():
    segs = [("Agents & Automation", 3, AM), ("RAG & LLM Apps", 3, VI), ("Computer Vision & Security", 3, CY),
            ("Healthcare Multimodal AI", 2, PK), ("Predictive ML & Fraud", 1, GR)]
    cx, cy, r = 170, 208, 90
    C, tot, start, g = 2 * math.pi * r, 12, 0, []
    for i, (nm, v, c) in enumerate(segs):
        ln = C * v / tot - 4
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{c}" stroke-width="30" stroke-dasharray="0 {C:.1f}" stroke-dashoffset="{-start:.1f}" transform="rotate(-90 {cx} {cy})" filter="url(#glow)">'
                 f'<animate attributeName="stroke-dasharray" from="0 {C:.1f}" to="{ln:.1f} {C-ln:.1f}" dur="1.2s" begin="{i*.25:.2f}s" fill="freeze"/></circle>')
        start += C * v / tot
        ly = 110 + i * 46
        g.append(f'<rect x="330" y="{ly-12}" width="14" height="14" rx="4" fill="{c}"/>' + T(354, ly, nm, 15, TX, weight=600) + T(560, ly, str(v), 15, c, mono=True, anchor="end", weight=700)
                 + f'<rect x="354" y="{ly+8}" width="206" height="4" rx="2" fill="{LN}"/><rect x="354" y="{ly+8}" width="{206*v/3:.0f}" height="4" rx="2" fill="{c}" opacity=".9"/>')
    inner = (T(28, 40, "PROJECT PORTFOLIO BY DOMAIN", 13, PK, mono=True, ls=3) + "".join(g)
             + T(cx, cy + 8, "12", 44, TX, weight=800, anchor="middle") + T(cx, cy + 30, "SHIPPED", 11, MU, mono=True, anchor="middle", ls=2))
    return card(600, 380, inner)


def pipeline():
    w, h = 1200, 290
    steps = [("01 PERCEIVE", CY, ["Computer vision", "Whisper speech", "Text & documents"]), ("02 RETRIEVE", VI, ["FAISS · ChromaDB", "BGE embeddings", "Cross-encoder rerank"]),
             ("03 REASON", PK, ["LLMs & ReAct agents", "Provider routing", "Policy & safety gates"]), ("04 SERVE", AM, ["FastAPI · Django", "Celery · Redis", "SSE live traces"]),
             ("05 SHIP", GR, ["Docker · Compose", "VPS deployment", "n8n automation"])]
    b = [frame(w, h), T(40, 44, "HOW I BUILD", 13, CY, mono=True, ls=3)]
    b.append(f'<line x1="50" y1="150" x2="1144" y2="150" stroke="{LN}" stroke-width="2" stroke-dasharray="4 6"/>')
    for i, (nm, c, items) in enumerate(steps):
        x = 50 + i * 226
        b.append(f'<g class="fade" style="animation-delay:{i*.2:.1f}s"><rect x="{x}" y="86" width="190" height="130" rx="14" fill="{BG2}" fill-opacity=".85" stroke="{c}" stroke-opacity=".6"/>'
                 f'<rect x="{x}" y="86" width="190" height="5" rx="2" fill="{c}" filter="url(#glow)"/>' + T(x + 18, 120, nm, 14, c, mono=True, weight=700, ls=1))
        for k, s in enumerate(items):
            b.append(T(x + 18, 150 + k * 22, s, 13, TX if k == 0 else MU))
        b.append('</g>')
        if i < 4:
            b.append(T(x + 208, 155, "›", 26, c, mono=True, anchor="middle"))
    for k in range(3):
        b.append(f'<circle r="5" fill="{ACC[k]}" filter="url(#glow)"><animateMotion path="M50,150 L1144,150" dur="6s" begin="{k*2}s" repeatCount="indefinite"/></circle>')
    b.append(T(600, 262, "Grounded outputs. Observable agents. Deployable by default.", 14, MU, mono=True, anchor="middle"))
    return svg(w, h, "".join(b))


# ------------------------------------------------------------------ contributions
def fetch_days():
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        q = ("query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}")
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
        c = 0 if rnd.random() < .38 else rnd.randint(1, 14) + (4 if d.weekday() < 5 and rnd.random() < .3 else 0)
        days.append((d.isoformat(), c))
        d += dt.timedelta(days=1)
    print("NOTE: sample contribution data in use. Set GITHUB_TOKEN for real data.")
    return days, False


def heatmap(days):
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)]
    cols, pitch, size = len(weeks), 20, 16
    x0 = (1200 - (cols * pitch - 4)) // 2
    mx = max((c for _, c in days), default=1) or 1
    total = sum(c for _, c in days)
    lv = ["#141A30", "#0E4F6B", "#0EA5C6", "#7C5CFF", PK]
    w, h = 1200, 270
    b = [frame(w, h), T(40, 44, "CONTRIBUTIONS", 13, CY, mono=True, ls=3),
         T(1160, 44, f"{total:,} IN THE LAST 12 MONTHS", 13, MU, mono=True, ls=2, anchor="end")]
    last_m, last_c = None, -9
    for ci, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0][0]).strftime("%b").upper()
        if m != last_m and ci - last_c >= 3:
            b.append(T(x0 + ci * pitch, 72, m, 11, DM, mono=True))
            last_m, last_c = m, ci
        for ri, (_, c) in enumerate(wk):
            level = 0 if c == 0 else 1 + min(3, int(c * 4 / (mx + 1)))
            b.append(f'<rect class="c" style="animation-delay:{ci*.018:.3f}s" x="{x0+ci*pitch}" y="{84+ri*pitch}" width="{size}" height="{size}" rx="3" fill="{lv[level]}"/>')
    lx = 1160 - 5 * 20 - 90
    b.append(T(lx, 252, "LESS", 11, DM, mono=True))
    for k in range(5):
        b.append(f'<rect x="{lx+44+k*20}" y="242" width="14" height="14" rx="3" fill="{lv[k]}"/>')
    b.append(T(1160, 252, "MORE", 11, DM, mono=True, anchor="end"))
    return svg(w, h, "".join(b), ".c{opacity:0;animation:fade .5s ease forwards}")


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
    b = [frame(w, h), T(40, 46, "ACTIVITY / BY MONTH", 13, VI, mono=True, ls=3),
         f'<line x1="40" y1="212" x2="800" y2="212" stroke="{LN}"/>', f'<line x1="840" y1="40" x2="840" y2="240" stroke="{LN}"/>']
    for i, (k, v) in enumerate(zip(keys, vals)):
        bh = max(3, int(v / top * 120))
        x = 52 + i * 62
        b.append(f'<rect class="bar" style="animation-delay:{i*.07:.2f}s" x="{x}" y="{212-bh}" width="38" height="{bh}" rx="4" fill="url(#aurv)" filter="url(#glow)"/>')
        b.append(T(x + 19, 212 - bh - 8, str(v), 11, MU, mono=True, anchor="middle", cls="fade", delay=.9))
        b.append(T(x + 19, 232, dt.date(k[0], k[1], 1).strftime("%b").upper(), 11, DM, mono=True, anchor="middle"))
    for n, (lab, val, c) in enumerate([("TOTAL", f"{total:,}", CY), ("LONGEST STREAK", f"{streak} DAYS", PK), (f"BUSIEST DAY · {best[0]}", str(best[1]), AM)]):
        y = 84 + n * 62
        b.append(T(880, y, lab, 11, MU, mono=True, ls=2) + T(880, y + 34, val, 34, c, weight=800, extra='filter="url(#glow)"'))
    return svg(w, h, "".join(b), css)


# ------------------------------------------------------------------ repos / catalogue
def repo(i, name, d1, d2, chips, kind, acc):
    inner = [T(28, 42, f"FEATURED / 0{i}", 12, acc, mono=True, ls=3), f'<line x1="28" y1="58" x2="560" y2="58" stroke="{LN}"/>',
             T(28, 104, name, 32, "url(#aur)", weight=800, cls="rise", delay=.1 * i), T(28, 140, d1, 15, TX), T(28, 162, d2, 15, MU)]
    x = 28
    for c in chips:
        g, cw = chip(x, 184, c, acc, 12, 28)
        inner.append(g)
        x += cw + 8
    inner.append(T(28, 238, "VIEW REPOSITORY  →", 12, acc, mono=True, ls=2, weight=700))
    if kind == "fusion":
        for k, (yy, c) in enumerate(zip((84, 108, 132, 156), (CY, VI, PK, AM))):
            inner.append(f'<circle class="sq" style="animation-delay:{k*.3}s" cx="360" cy="{yy}" r="4" fill="{c}" filter="url(#glow)"/><line x1="360" y1="{yy}" x2="430" y2="120" stroke="{LN}"/>')
            inner.append(f'<circle r="2.5" fill="{c}"><animateMotion path="M360,{yy} L430,120" dur="2s" begin="{k*.5}s" repeatCount="indefinite"/></circle>')
        inner.append(f'<polygon points="430,100 450,120 430,140 410,120" fill="{BG2}" stroke="{PK}" stroke-width="2" filter="url(#glow)"/>'
                     f'<line x1="450" y1="120" x2="520" y2="90" stroke="{PK}"/><line x1="450" y1="120" x2="520" y2="150" stroke="{CY}"/>'
                     f'<circle cx="520" cy="90" r="6" fill="{PK}" filter="url(#glow)"/><circle cx="520" cy="150" r="6" fill="{CY}" filter="url(#glow)"/>'
                     + T(534, 94, "ESCALATE", 10, PK, mono=True) + T(534, 154, "RAG+LLM", 10, CY, mono=True))
    elif kind == "gauge":
        inner.append(f'<path d="M370,170 A80,80 0 0 1 530,170" stroke="{LN}" stroke-width="12" stroke-linecap="round"/>'
                     f'<path d="M370,170 A80,80 0 0 1 530,170" stroke="url(#aur)" stroke-width="12" stroke-linecap="round" pathLength="100" stroke-dasharray="0 100" filter="url(#glow)">'
                     f'<animate attributeName="stroke-dasharray" values="0 100;72 100;38 100;85 100;0 100" dur="7s" repeatCount="indefinite"/></path>'
                     + T(450, 160, "RISK", 12, MU, mono=True, anchor="middle", ls=3) + f'<rect class="sq" x="410" y="86" width="80" height="44" stroke="{CY}" stroke-width="2" fill="none" filter="url(#glow)"/>')
    elif kind == "loop":
        inner.append(f'<circle cx="450" cy="120" r="52" stroke="{LN}" stroke-width="2" stroke-dasharray="5 6"/>'
                     + T(450, 124, "ReAct", 14, TX, mono=True, anchor="middle", weight=700) + T(450, 64, "THOUGHT", 10, CY, mono=True, anchor="middle")
                     + T(520, 168, "ACTION", 10, VI, mono=True) + T(380, 168, "OBSERVE", 10, PK, mono=True, anchor="end")
                     + f'<g><circle cx="450" cy="68" r="5" fill="{CY}" filter="url(#glow)"/><animateTransform attributeName="transform" type="rotate" from="0 450 120" to="360 450 120" dur="5s" repeatCount="indefinite"/></g>')
    else:
        for k in range(5):
            cx = 360 + k * 45
            inner.append(f'<circle class="sq" style="animation-delay:{k*.4}s" cx="{cx}" cy="120" r="9" fill="{BG2}" stroke="{ACC[k]}" stroke-width="2" filter="url(#glow)"/>')
            if k < 4:
                inner.append(f'<line x1="{cx+9}" y1="120" x2="{cx+36}" y2="120" stroke="{LN}" stroke-width="2"/>')
        inner.append(f'<circle r="4" fill="{TX}" filter="url(#glow)"><animateMotion path="M360,120 L540,120" dur="3s" repeatCount="indefinite"/></circle>'
                     + T(450, 160, "PLAN → SEARCH → CHUNK → RETRIEVE → CITE", 9, MU, mono=True, anchor="middle"))
    return card(600, 270, "".join(inner), ".sq{animation:sq 2.4s ease-in-out infinite}@keyframes sq{0%,100%{opacity:.3}50%{opacity:1}}")


CATALOGUE = [("HealMatrix AI", "HEALTHCARE · MULTIMODAL", PK, "LLaMA 3.3 · FAISS · RoBERTa"), ("VITA", "HEALTHCARE · MULTIMODAL", PK, "Transformer fusion · ElevenLabs"),
             ("Cheatify", "COMPUTER VISION", CY, "YOLOv12 · MediaPipe"), ("IntelliFall AI", "CV · IoT", CY, "Fall detection system"),
             ("MalVision AI", "SECURITY · XAI", CY, "Streamlit · explainability"), ("Research Forge AI", "RAG · RESEARCH", VI, "SearXNG · ChromaDB · Celery"),
             ("AgentFlow AI", "AGENTS", AM, "LangGraph · SSE · SQLite"), ("Pocho AI", "RAG", VI, "Django · TF-IDF · Grok"),
             ("QuickByte AI", "LLM APPLICATION", VI, "Nutrition-focused LLM platform"), ("WhatsAgent AI", "AUTOMATION", AM, "n8n · Twilio · Airtable"),
             ("Quantifier AI", "AUTOMATION", AM, "Lead scoring: HOT · WARM · COLD"), ("FraudShield AI", "PREDICTIVE ML", GR, "scikit-learn")]


def catalogue():
    w, h = 1200, 440
    b = [frame(w, h), T(40, 44, "12 SHIPPED SYSTEMS", 13, CY, mono=True, ls=3)]
    for i, (c, lab) in enumerate([(PK, "Healthcare"), (CY, "Vision"), (VI, "RAG / LLM"), (AM, "Agents"), (GR, "Predictive")]):
        b.append(f'<circle cx="{700+i*98}" cy="40" r="4" fill="{c}"/>' + T(710 + i * 98, 44, lab, 11, MU, mono=True))
    for i, (nm, dom, c, tech) in enumerate(CATALOGUE):
        x, y = 40 + (i % 4) * 282, 70 + (i // 4) * 120
        b.append(f'<g class="fade" style="animation-delay:{i*.1:.1f}s"><rect x="{x}" y="{y}" width="270" height="108" rx="12" fill="{BG2}" fill-opacity=".8" stroke="{c}" stroke-opacity=".5"/>'
                 f'<rect x="{x}" y="{y+14}" width="4" height="80" rx="2" fill="{c}" filter="url(#glow)"/>'
                 + T(x + 22, y + 38, nm, 18, TX, weight=700) + T(x + 22, y + 62, dom, 11, c, mono=True, ls=1) + T(x + 22, y + 86, tech, 12, MU) + '</g>')
    return svg(w, h, "".join(b))


def principles():
    w, h = 1200, 330
    P = [("Grounding over fluency", "Retrieval + reranking; every claim", "traces back to a source.", CY), ("Safety gates first", "Crisis detection runs ahead of", "the LLM, never improvised on.", PK),
         ("Observable agents", "Live tool-call traces over SSE,", "so reasoning is inspectable.", VI), ("Provider independence", "Routing across Groq, Gemini and", "OpenRouter beats vendor lock-in.", AM),
         ("Multimodal by default", "Face, posture, voice and text are", "fused signals, not separate demos.", GR), ("Resilient automation", "n8n flows ship with retries and", "an error-notifier workflow.", CY),
         ("Incremental delivery", "Progressively harder versions,", "each one working end to end.", PK), ("Ship. Measure. Improve.", "Build. Evaluate. Optimize.", "Deploy. Repeat.", VI)]
    b = [frame(w, h), T(40, 44, "ENGINEERING PRINCIPLES", 13, AM, mono=True, ls=3)]
    for i, (t1, l1, l2, c) in enumerate(P):
        x, y = 40 + (i % 4) * 282, 68 + (i // 4) * 126
        b.append(f'<g class="fade" style="animation-delay:{i*.12:.2f}s"><rect x="{x}" y="{y}" width="270" height="114" rx="12" fill="{c}" fill-opacity=".07" stroke="{c}" stroke-opacity=".45"/>'
                 f'<circle class="pulse" style="animation-delay:{i*.3:.1f}s" cx="{x+24}" cy="{y+28}" r="5" fill="{c}" filter="url(#glow)"/>'
                 + T(x + 40, y + 33, t1, 16, TX, weight=700) + T(x + 22, y + 66, l1, 13, MU) + T(x + 22, y + 86, l2, 13, MU) + '</g>')
    return svg(w, h, "".join(b))


def timeline():
    w, h = 1200, 330
    ev = [("OCT 2022", "B.S. Data Science", "begins", CY), ("JUL 2024", "AI/ML Fellow", "ACM UET x DevSinc", VI), ("OCT 2024", "ML Core Team", "UMT GoDoc", PK),
          ("DEC 2024", "Junior ML Engineer", "Sunsprinkle · remote", AM), ("JUN 2026", "B.S. completed", "Data Science", GR), ("OCT 2026", "Freelance AI/ML", "Engineer · remote · now", CY)]
    b = [frame(w, h), T(40, 44, "JOURNEY", 13, GR, mono=True, ls=3), f'<line x1="100" y1="165" x2="1100" y2="165" stroke="{LN}" stroke-width="3"/>',
         f'<path d="M100,165 H1100" stroke="url(#aur)" stroke-width="3" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100" filter="url(#glow)"><animate attributeName="stroke-dashoffset" from="100" to="0" dur="3s" fill="freeze"/></path>']
    for i, (d, t1, t2, c) in enumerate(ev):
        x = 100 + i * 200
        up = i % 2 == 0
        y0, y1 = (156, 138) if up else (174, 192)
        ty = 90 if up else 214
        b.append(f'<g class="fade" style="animation-delay:{.5+i*.4:.1f}s"><line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{c}" stroke-opacity=".6"/>'
                 + T(x, ty, d, 12, c, mono=True, anchor="middle", ls=2, weight=700) + T(x, ty + 22, t1, 16, TX, anchor="middle", weight=700) + T(x, ty + 42, t2, 12, MU, mono=True, anchor="middle") + '</g>')
        b.append(f'<circle cx="{x}" cy="165" r="9" fill="{BG0}" stroke="{c}" stroke-width="3" filter="url(#glow)"/>'
                 f'<circle cx="{x}" cy="165" r="9" stroke="{c}" fill="none"><animate attributeName="r" values="9;24" dur="2.4s" begin="{i*.4:.1f}s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0" dur="2.4s" begin="{i*.4:.1f}s" repeatCount="indefinite"/></circle>')
    return svg(w, h, "".join(b))


def now():
    w, h = 1200, 300
    b = [frame(w, h), T(40, 46, "ACTIVE DEVELOPMENT", 13, CY, mono=True, ls=3), f'<line x1="780" y1="30" x2="780" y2="270" stroke="{LN}"/>',
         T(820, 46, "CURRENTLY EXPLORING", 13, PK, mono=True, ls=3)]
    rows = [("Hospital Procurement Platform", "Forecasting and supplier scoring shipped", 5, 2, "V2 / V5", CY),
            ("AI Coding Assistant", "VS Code extension, FastAPI multi-LLM router", 10, 2, "PHASE 2 / 10", VI), ("Lahori", "Lahore food discovery platform", 0, 0, "IN DEVELOPMENT", AM)]
    for r, (name, sub, n, done, lab, c) in enumerate(rows):
        y = 100 + r * 62
        b.append(T(40, y, name, 19, TX, weight=700) + T(40, y + 22, sub, 12, MU, mono=True))
        if n:
            sw = 210 // n - 6
            for k in range(n):
                on = k < done
                b.append(f'<rect x="{410+k*(sw+6)}" y="{y-12}" width="{sw}" height="10" rx="3" fill="{c if on else BG2}" stroke="{c}" stroke-opacity="{0 if on else .45}"' + (' filter="url(#glow)"' if on else '') + '/>')
            b.append(T(410, y + 22, lab, 11, c, mono=True, ls=2))
        else:
            b.append(f'<circle class="pulse" cx="414" cy="{y-7}" r="4" fill="{c}" filter="url(#glow)"/>' + T(428, y - 3, lab, 11, c, mono=True, ls=2))
    x, y = 820, 76
    for i, s in enumerate(["Agentic AI", "Multimodal fusion", "pgvector", "RBAC & multi-tenancy", "Next.js dashboards", "Production MLOps"]):
        g, cw = chip(x, y, s, ACC[i % 5], 13, 32)
        if x + cw > 1160:
            x, y = 820, y + 46
            g, cw = chip(x, y, s, ACC[i % 5], 13, 32)
        b.append(f'<g class="fade" style="animation-delay:{.3+i*.15:.2f}s">{g}</g>')
        x += cw + 10
    return svg(w, h, "".join(b))


def engage():
    w, h = 1200, 200
    E = [("Full-time role", "AI/ML engineering, applied GenAI,", "backend intelligence.", CY), ("Contract build", "RAG systems, agents, LLM apps,", "computer vision pipelines.", VI),
         ("Automation", "n8n and Zapier workflows with", "LLM decision steps.", PK), ("Prototype to production", "Notebook or demo to a FastAPI", "service with Docker deploy.", GR)]
    b = [frame(w, h), T(40, 44, "WORK WITH ME", 13, PK, mono=True, ls=3)]
    for i, (t1, l1, l2, c) in enumerate(E):
        x = 40 + i * 282
        b.append(f'<g class="fade" style="animation-delay:{i*.15:.2f}s"><rect x="{x}" y="66" width="270" height="108" rx="12" fill="{c}" fill-opacity=".07" stroke="{c}" stroke-opacity=".5"/>'
                 f'<rect x="{x}" y="66" width="270" height="4" rx="2" fill="{c}" filter="url(#glow)"/>'
                 + T(x + 22, 104, t1, 18, TX, weight=700) + T(x + 22, 130, l1, 13, MU) + T(x + 22, 150, l2, 13, MU) + '</g>')
    return svg(w, h, "".join(b))


def footer():
    w, h = 1200, 200
    b = [frame(w, h, 18), waves(w, 120, CY, PK),
         T(600, 70, "THE MODEL IS THE EASY PART. THE SYSTEM AROUND IT IS THE PRODUCT.", 15, "url(#aur)", mono=True, weight=700, anchor="middle", extra='textLength="900"'),
         f'<rect x="40" y="94" width="1120" height="1.5" fill="{LN}"/><rect x="40" y="93" width="110" height="3" fill="url(#beam)"><animateTransform attributeName="transform" type="translate" from="0 0" to="1010 0" dur="5s" repeatCount="indefinite"/></rect>',
         T(600, 160, "ABDULLAH IMRAN  ·  LAHORE  ·  BUILD. EVALUATE. OPTIMIZE. DEPLOY.", 11, MU, mono=True, anchor="middle", ls=3)]
    return svg(w, h, "".join(b), WAVE_CSS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    days, _ = fetch_days()
    F = {
        "hero": hero(),
        "marquee-tech": marquee(["PYTHON", "PYTORCH", "TENSORFLOW", "OPENCV", "YOLO", "FASTAPI", "DJANGO", "LANGGRAPH", "LANGCHAIN", "RAG", "MCP", "DOCKER", "POSTGRESQL", "REDIS", "MLFLOW", "SAGEMAKER", "HUGGING FACE", "N8N"]),
        "intro": intro(), "terminal": terminal(),
        "world-engineer": world(1, "ENGINEER", CY, "90%", "BODY-FAT MODEL ACCURACY", ["Computer vision · Deep learning", "YOLOv12 · MediaPipe · KeypointRCNN", "Production-ready intelligent systems"], motif_engineer(CY), False, True),
        "world-builder": world(2, "BUILDER", VI, "12", "SHIPPED SYSTEMS", ["FastAPI · Django · Celery · Docker", "RAG apps, agents, automation APIs", "From prototype to deployed product"], motif_builder(VI), True, True),
        "world-explorer": world(3, "EXPLORER", PK, "3", "ACTIVE BUILDS", ["Agentic AI · multimodal fusion", "LLMs, retrieval, new tooling", "Experiments and open source"], motif_explorer(PK), True, False),
        "tile-1": tile(1, "12", "SYSTEMS SHIPPED", CY, "dots", 12), "tile-2": tile(2, "6", "CERTIFICATIONS", VI, "dots", 6),
        "tile-3": tile(3, "90%", "MODEL ACCURACY", PK, "ring", 90), "tile-4": tile(4, "30%", "FASTER ML PIPELINE", AM, "ring", 30),
        "title-stack": title("01", "TECH STACK", "LAYERS OF THE SYSTEM", CY), "skills": skills(),
        "title-insights": title("02", "INSIGHTS", "PROFICIENCY AND PORTFOLIO", VI), "radar": radar(), "donut": donut(), "pipeline": pipeline(),
        "title-contrib": title("03", "CONTRIBUTIONS", "COMMITS, DAILY", PK), "heatmap": heatmap(days), "activity": activity(days),
        "title-systems": title("04", "FEATURED SYSTEMS", "SELECTED REPOSITORIES", AM),
        "repo-healmatrix": repo(1, "HealMatrix AI", "Crisis-gated multimodal assistant fusing", "text, voice, face and posture.", ["RAG", "RoBERTa", "FastAPI", "Docker"], "fusion", PK),
        "repo-cheatify": repo(2, "Cheatify", "Real-time exam proctoring with object", "detection, pose and gaze risk scoring.", ["YOLOv12", "MediaPipe", "OpenCV"], "gauge", CY),
        "repo-agentflow": repo(3, "AgentFlow AI", "Multi-provider ReAct platform with live", "tool traces, memory and failover.", ["LangGraph", "SSE", "FastAPI"], "loop", AM),
        "repo-researchforge": repo(4, "Research Forge AI", "Self-hosted research-to-report pipeline", "with citation enforcement.", ["SearXNG", "ChromaDB", "Celery"], "stages", VI),
        "catalogue": catalogue(),
        "title-journey": title("05", "JOURNEY & CRAFT", "TIMELINE AND PRINCIPLES", GR), "timeline": timeline(), "principles": principles(),
        "title-now": title("06", "NOW", "BUILDING AND EXPLORING", CY), "now": now(), "engage": engage(),
        "marquee-principles": marquee(["GROUNDED OUTPUTS", "OBSERVABLE AGENTS", "DEPLOYABLE BY DEFAULT", "BUILD. EVALUATE. OPTIMIZE. DEPLOY.", "FROM RAW DATA TO DEPLOYABLE INTELLIGENCE"], rev=True),
        "title-contact": title("07", "CONTACT", "OPEN TO REMOTE", PK), "footer": footer(),
    }
    for name, content in F.items():
        minidom.parseString(content.encode("utf-8"))
        (OUT / f"{name}.svg").write_text(content, encoding="utf-8")
    print(f"wrote {len(F)} cards to {OUT}")


if __name__ == "__main__":
    main()
