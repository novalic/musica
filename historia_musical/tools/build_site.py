#!/usr/bin/env python3
"""Genera el sitio HTML del curso a partir de LESSON.md y ROADMAP.md.

Fuentes de verdad:
  README.md                 -> titulo y bajada del sitio (primer "# " y primer parrafo)
  ROADMAP.md                -> fases y lecciones (tablas "| N.M | Leccion | Que aprendes | Estado |")
  lessons/pP_lMM_*/LESSON.md -> contenido de cada leccion (fase P, leccion M; se cita como P.M)
                               (tambien acepta el formato viejo lNN_* con numeros "NN")

Genera:
  index.html, assets/js/lessons-data.js, lessons/*/index.html

Uso:  make site     (o: uv run --no-project --with markdown python tools/build_site.py)
Configuracion opcional: tools/site.json
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SITE_ID = ROOT.name
HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0"
SHELL_START = re.compile(
    r"^\s*(\$ )?(make|cp|cd|uv|git|pip|python|python3|docker|open|export|curl|kubectl|helm|kind|minikube|"
    r"terraform|ansible|ansible-playbook|ansible-galaxy|npm|npx|pnpm|node|go|protoc|grpcurl|mkdir|ls|cat|"
    r"echo|brew|apt|apt-get|sudo|pytest|vite)\b"
)


def load_config() -> dict:
    cfg = {
        "run_cmd": "make test L={num}",
        "work_hint": "Implementá los ejercicios hasta que <code>{run_cmd}</code> quede en verde "
                     "(si un test falla, el test dice exactamente qué se espera).",
        "extra_hljs_languages": [],
        "has_exercises": True,
    }
    f = ROOT / "tools" / "site.json"
    if f.exists():
        cfg.update(json.loads(f.read_text(encoding="utf-8")))
    return cfg


CFG = load_config()
NUM_RE = r"(\d+(?:\.\d+)?)"


def lesson_glob(num: str, what: str = "lessons/{}_*/LESSON.md") -> list[Path]:
    """Directorios de una leccion: 'P.M' -> pP_lMM_*, 'NN' -> lNN_*."""
    if "." in num:
        p, m = num.split(".")
        prefix = f"p{int(p)}_l{int(m):02d}"
    else:
        prefix = f"l{num}"
    return sorted(ROOT.glob(what.format(prefix)))


def inline_md(text: str) -> str:
    """Markdown en linea (backticks y negritas) -> HTML, sin <p>."""
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out


def plain(text: str) -> str:
    return re.sub(r"[`*]", "", text)


def read_site_meta() -> tuple[str, str]:
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    title = next(l[2:].strip() for l in lines if l.startswith("# "))
    paras, buf, started = [], [], False
    for l in lines:
        if l.startswith("# "):
            started = True
            continue
        if not started:
            continue
        if l.strip() == "" or l.startswith("#"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            if l.startswith("#") and paras:
                break
            continue
        buf.append(l.strip())
    lead = paras[0] if paras else ""
    return title, lead


def parse_roadmap() -> tuple[list[str], list[dict], str]:
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    phases: list[str] = []
    lessons: list[dict] = []
    phase = None
    final_lines: list[str] = []
    in_final = False
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            phase = m.group(1).strip()
            in_final = phase.lower().startswith("proyecto final")
            if in_final:
                final_lines.append(f"## {phase}")
            continue
        if in_final:
            final_lines.append(line)
            continue
        m = re.match(rf"^\|\s*{NUM_RE}\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if m and phase:
            num, title, summary, status = m.groups()
            if phase not in phases:
                phases.append(phase)
            matches = lesson_glob(num)
            lesson_dir = matches[0].parent.name if matches else None
            # "ready" = tiene carpeta Y el ROADMAP la marca done (evita contar
            # como listos los placeholders LESSON.md creados solo para que
            # los links del README no rompan).
            lessons.append({
                "num": num,
                "dir": lesson_dir,
                "title": plain(title),
                "summary": inline_md(summary),
                "summaryText": plain(summary),
                "phase": phase,
                "ready": lesson_dir is not None and "✅" in status,
            })
    final_html = ""
    if final_lines:
        final_html = markdown.markdown("\n".join(final_lines), extensions=["tables", "fenced_code"])
    return phases, lessons, final_html


def slugify(value: str, separator: str = "-") -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[\s_-]+", separator, value)


def tag_code_blocks(body: str) -> str:
    def repl(m: re.Match) -> str:
        code = m.group(1)
        raw = html.unescape(code)
        lines = [l for l in raw.splitlines() if l.strip()]
        lang = "bash" if lines and all(SHELL_START.match(l) for l in lines) else "plaintext"
        return f'<pre><code class="language-{lang}">{code}</code></pre>'
    return re.sub(r"<pre><code>(.*?)</code></pre>", repl, body, flags=re.S)


def callouts(body: str) -> str:
    body = body.replace("<blockquote>", '<div class="callout tip"><span class="callout-label">Clave</span>')
    return body.replace("</blockquote>", "</div>")


def render_lesson(lesson: dict, prev_l: dict | None, next_l: dict | None, site_title: str) -> str:
    ldir = ROOT / "lessons" / lesson["dir"]
    src = (ldir / "LESSON.md").read_text(encoding="utf-8")

    lines = src.splitlines()
    h1 = lesson["title"]
    if lines and lines[0].startswith("# "):
        h1 = lines[0][2:].strip()
        h1 = re.sub(r"^[\d.]+\s*[—-]\s*", "", h1)
        lines = lines[1:]
    rest = "\n".join(lines).strip()

    lead = ""
    m = re.match(r"^\*\*Objetivo:\*\*\s*(.+?)(?:\n\s*\n|$)", rest, flags=re.S)
    if m:
        lead_txt = " ".join(m.group(1).split())
        lead = inline_md(lead_txt[:1].upper() + lead_txt[1:])
        rest = rest[m.end():]

    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"],
                           extension_configs={"toc": {"slugify": slugify, "toc_depth": "2"}})
    body = md.convert(rest)
    body = callouts(tag_code_blocks(body))
    toc_items = "\n".join(
        f'        <li><a href="#{t["id"]}">{html.escape(t["name"])}</a></li>' for t in md.toc_tokens
    )

    num = lesson["num"]
    skip = {"LESSON.md", "index.html", "__init__.py", "__pycache__"}
    ex_files = sorted(p.name for p in ldir.iterdir() if p.is_file() and p.name not in skip)
    ex_dirs = sorted(p.name + "/" for p in ldir.iterdir() if p.is_dir() and p.name not in skip)
    files_html = ", ".join(f'<a href="{f}"><code>{f}</code></a>' for f in ex_files + ex_dirs)
    tests = sorted(ROOT.glob("tests/test_" + ldir.name.split("_", 2)[0] + "_" + ldir.name.split("_", 2)[1] + "_*"))
    if "." not in num:
        tests = sorted(ROOT.glob(f"tests/test_l{num}_*.py"))
    if tests:
        sep = ", " if files_html else ""
        files_html += f'{sep}<a href="../../tests/{tests[0].name}"><code>tests/{tests[0].name}</code></a>'
    run_cmd = CFG["run_cmd"].format(num=num)
    steps = ["Leé esta página entera."]
    if CFG["has_exercises"] and (ex_files or tests):
        steps.append(CFG["work_hint"].format(run_cmd=run_cmd, num=num))
    steps.append("Respondé en voz alta las preguntas del final y anotá lo que te costó en ✎ Mis notas.")
    steps_html = "\n".join(f"        <li>{s}</li>" for s in steps)
    files_line = (f'<p style="margin:8px 0 0">Archivos: {files_html}</p>' if files_html else "")

    def nav_link(l: dict | None, cls: str, label: str) -> str:
        if not l:
            return f'<span class="{cls}"></span>'
        return (f'<a href="../{l["dir"]}/index.html" class="{cls}"><small>{label}</small>'
                f'{l["num"]} — {html.escape(l["title"])}</a>')

    extra_langs = "".join(
        f'<script src="{HLJS}/languages/{lang}.min.js"></script>\n' for lang in CFG["extra_hljs_languages"]
    )
    return f"""<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{num} — {html.escape(h1)} · {html.escape(site_title)}</title>
<meta name="description" content="{html.escape(lesson['summaryText'])}">
<link rel="stylesheet" href="../../assets/css/style.css">
<link rel="stylesheet" href="{HLJS}/styles/dracula.min.css">
</head>
<body>
<!-- GENERADO por tools/build_site.py desde LESSON.md: no editar a mano. -->
<script>const BASE_PREFIX = "../../";</script>
<div class="layout">
  <nav id="sidebar" class="sidebar"></nav>
  <button id="sidebar-toggle" class="sidebar-toggle" aria-label="Abrir menu">&#9776;</button>

  <main class="content">
    <div class="chapter-meta">
      <a href="../../index.html" class="back-index">&larr; Indice</a>
      <span class="chapter-num">Lección {num}</span>
      <span class="chapter-category">{html.escape(lesson['phase'])}</span>
    </div>
    <h1>{html.escape(h1)}</h1>
    <p class="lead">{lead}</p>

    <div class="task-box">
      <strong class="task-title">Cómo trabajar esta lección</strong>
      <ol>
{steps_html}
      </ol>
      {files_line}
    </div>

    <nav class="toc" aria-label="Tabla de contenidos">
      <strong>En esta lección</strong>
      <ul>
{toc_items}
      </ul>
    </nav>

{body}

    <nav class="chapter-nav">
      {nav_link(prev_l, "prev", "Anterior")}
      {nav_link(next_l, "next", "Siguiente")}
    </nav>

    <div class="lesson-done"></div>
  </main>
</div>

<script src="{HLJS}/highlight.min.js"></script>
{extra_langs}<script src="../../assets/js/lessons-data.js"></script>
<script src="../../assets/js/site.js"></script>
<script>hljs.highlightAll();</script>
</body>
</html>
"""


INDEX_JS = r"""
  (function () {
    const groups = document.getElementById("groups");
    function render(filterText) {
      groups.innerHTML = "";
      const q = (filterText || "").trim().toLowerCase();
      let any = false;
      PHASE_ORDER.forEach(function (phase) {
        let inPhase = LESSONS.filter(function (l) { return l.phase === phase; });
        if (q) inPhase = inPhase.filter(function (l) {
          return (l.num + " " + l.title + " " + l.summaryText).toLowerCase().indexOf(q) !== -1;
        });
        if (!inPhase.length) return;
        any = true;
        const title = document.createElement("div");
        title.className = "group-title";
        title.textContent = phase;
        groups.appendChild(title);
        const grid = document.createElement("div");
        grid.className = "card-grid";
        inPhase.forEach(function (l) {
          const el = document.createElement(l.ready ? "a" : "div");
          el.className = "card" + (l.ready ? "" : " pending");
          if (l.ready) el.href = "lessons/" + l.dir + "/index.html";
          const t = document.createElement("h3"); t.textContent = l.title;
          el.innerHTML = '<span class="card-num">Lección ' + l.num + '</span>' +
            (l.ready
              ? (window.sdIsDone && window.sdIsDone(l.dir) ? '<span class="tag-done">&check; finalizada</span>' : "")
              : '<span class="tag-pending">pendiente</span>');
          el.appendChild(t);
          const p = document.createElement("p"); p.innerHTML = l.summary; el.appendChild(p);
          grid.appendChild(el);
        });
        groups.appendChild(grid);
      });
      if (!any) {
        const empty = document.createElement("p");
        empty.style.color = "var(--text-faint)";
        empty.textContent = "Sin resultados para \"" + filterText + "\".";
        groups.appendChild(empty);
      }
    }
    render("");
    document.getElementById("hero-search").addEventListener("input", function (e) { render(e.target.value); });
  })();
"""


def render_index(title: str, lead: str, lessons: list[dict], final_html: str) -> str:
    ready = [l for l in lessons if l["ready"]]
    start = (f'<a href="lessons/{ready[0]["dir"]}/index.html">Empezar por la lección {ready[0]["num"]} &rarr;</a>'
             if ready else "")
    final_block = (f'<div class="callout final-project">{final_html}</div>' if final_html else "")
    return f"""<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(plain(lead))}">
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
<!-- GENERADO por tools/build_site.py desde README.md y ROADMAP.md: no editar a mano. -->
<script>const BASE_PREFIX = "";</script>
<div class="layout">
  <nav id="sidebar" class="sidebar"></nav>
  <button id="sidebar-toggle" class="sidebar-toggle" aria-label="Abrir menu">&#9776;</button>

  <main class="content" style="max-width: 1100px; padding: 0;">
    <div class="hero">
      <a href="../index.html" class="back-index">&larr; Todos los cursos</a>
      <h1>{html.escape(title)}</h1>
      <p class="lead">{inline_md(lead)}</p>
      <input type="search" class="hero-search" id="hero-search" placeholder="Buscar un tema...">
      <div class="hero-links">
        {start}
        <span style="color:var(--text-faint)">{len(ready)} de {len(lessons)} lecciones listas</span>
        <span id="done-count" style="color:var(--good)"></span>
      </div>
    </div>

    <div class="groups" id="groups"></div>
    <div class="groups">{final_block}</div>
  </main>
</div>

<script src="assets/js/lessons-data.js"></script>
<script src="assets/js/site.js"></script>
<script>{INDEX_JS}</script>
</body>
</html>
"""


def main() -> None:
    title, lead = read_site_meta()
    phases, lessons, final_html = parse_roadmap()

    data = (
        "/* GENERADO por tools/build_site.py desde ROADMAP.md: no editar a mano. */\n"
        f"const SITE = {json.dumps({'id': SITE_ID, 'title': title}, ensure_ascii=False)};\n"
        f"const PHASE_ORDER = {json.dumps(phases, ensure_ascii=False)};\n"
        f"const LESSONS = {json.dumps(lessons, ensure_ascii=False, indent=2)};\n"
    )
    (ROOT / "assets/js/lessons-data.js").write_text(data, encoding="utf-8")
    (ROOT / "index.html").write_text(render_index(title, lead, lessons, final_html), encoding="utf-8")

    ready = [l for l in lessons if l["ready"]]
    for i, l in enumerate(ready):
        prev_l = ready[i - 1] if i > 0 else None
        next_l = ready[i + 1] if i + 1 < len(ready) else None
        out = ROOT / "lessons" / l["dir"] / "index.html"
        out.write_text(render_lesson(l, prev_l, next_l, title), encoding="utf-8")
        print(f"  {out.relative_to(ROOT)}")
    print(f"OK: {len(ready)} lecciones generadas, {len(lessons) - len(ready)} pendientes.")


if __name__ == "__main__":
    main()
