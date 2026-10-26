#!/usr/bin/env python3
"""Genera index.html (el catalogo de cursos) desde COURSES.md.

Fuente de verdad: COURSES.md en la raiz del repo.
  - "# Titulo" y el primer parrafo -> hero del index.
  - Cada "## Categoria" + la tabla "| Curso | Descripcion | Progreso |" que
    le sigue -> una seccion con una grilla de cards.
  - La celda "Curso" es un link markdown "[nombre](ruta/index.html)".

Uso:  make site   (o: python3 tools/build_index.py)
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ROW_RE = re.compile(r"^\|(.+)\|\s*$")

# Filas de leccion en un ROADMAP.md con numeracion "fase.leccion" (ej "1.1"),
# que es el formato que usan los cursos de este repo.
ROADMAP_ROW_RE = re.compile(r"^\| *\d+\.\d+ *\|")
ROADMAP_DONE_RE = re.compile(r"^\| *\d+\.\d+ *\|.*✅ *\|$")


def inline(text: str) -> str:
    """Minimal inline markdown -> html: just escape (descriptions are plain text)."""
    return html.escape(text.strip())


def parse_courses_md() -> tuple[str, str, list[tuple[str, list[dict]]]]:
    text = (ROOT / "COURSES.md").read_text(encoding="utf-8")
    lines = text.splitlines()

    title = next(l[2:].strip() for l in lines if l.startswith("# "))

    # Hero paragraph: first non-empty, non-heading block after the title.
    lead_lines: list[str] = []
    i = 0
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    while i < len(lines) and lines[i].strip() != "" and not lines[i].startswith("#"):
        lead_lines.append(lines[i].strip())
        i += 1
    lead = " ".join(lead_lines)

    categories: list[tuple[str, list[dict]]] = []
    current_cat = None
    current_courses: list[dict] = []
    j = 0
    while j < len(lines):
        line = lines[j]
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_cat is not None:
                categories.append((current_cat, current_courses))
            current_cat = m.group(1).strip()
            current_courses = []
            j += 1
            continue
        row_m = ROW_RE.match(line)
        if row_m and current_cat is not None:
            cells = [c.strip() for c in row_m.group(1).split("|")]
            if len(cells) == 3 and not re.match(r"^-{2,}$", cells[0]) and cells[0] != "Curso":
                link_m = LINK_RE.match(cells[0])
                if link_m:
                    current_courses.append(
                        {
                            "name": link_m.group(1),
                            "href": link_m.group(2),
                            "desc": cells[1],
                            "progress": cells[2],
                        }
                    )
        j += 1
    if current_cat is not None:
        categories.append((current_cat, current_courses))

    return title, lead, categories


def roadmap_counts(slug: str) -> tuple[int, int] | None:
    """Lee el ROADMAP.md real del proyecto `slug` y devuelve (listas, total):
    listas = filas "P.M" marcadas con check (contenido generado), total =
    todas las filas "P.M" del roadmap (lo que en definitiva se va a dictar
    del curso). Esa es la fuente de verdad real; la celda "Progreso" de
    COURSES.md queda solo como texto descriptivo legado para quien lee el
    markdown a mano, facil de desincronizar porque nadie la actualiza cuando
    se generan lecciones nuevas.

    Devuelve None (el caller debe usar el fallback de la celda "Progreso" de
    COURSES.md) cuando el curso no tiene ROADMAP.md, o lo tiene pero con otra
    numeracion de capitulo que no matchea "P.M".
    """
    roadmap = ROOT / slug / "ROADMAP.md"
    if not roadmap.is_file():
        return None
    lines = roadmap.read_text(encoding="utf-8").splitlines()
    total = sum(1 for l in lines if ROADMAP_ROW_RE.match(l))
    if total == 0:
        return None
    ready = sum(1 for l in lines if ROADMAP_DONE_RE.match(l))
    return ready, total


def render_card(course: dict) -> str:
    slug = course["href"].split("/")[0]
    counts = roadmap_counts(slug)
    if counts is not None:
        ready, total = counts
    else:
        # Fallback: parsear "X/Y" de la celda "Progreso" de COURSES.md. Si no
        # tiene ese formato, el unico numero que aparece vale como total Y
        # tambien como "ready" (se asume que ese curso ya tiene todo su
        # contenido armado).
        m = re.match(r"\s*(\d+)\s*/\s*(\d+)", course["progress"])
        if m:
            ready, total = int(m.group(1)), int(m.group(2))
        else:
            m2 = re.search(r"(\d+)", course["progress"])
            n = int(m2.group(1)) if m2 else 0
            ready, total = n, n
    return f"""        <a class="card" href="{html.escape(course['href'])}" data-course="{html.escape(slug)}" data-ready="{ready}" data-total="{total}">
          <div class="card-top">
            <h3>{html.escape(course['name'])}</h3>
            <span class="badge">{html.escape(course['progress'])}</span>
          </div>
          <p>{inline(course['desc'])}</p>
        </a>"""


def render_section(category: str, courses: list[dict]) -> str:
    cards = "\n".join(render_card(c) for c in courses)
    return f"""    <section class="category">
      <h2>{html.escape(category)}</h2>
      <div class="card-grid">
{cards}
      </div>
    </section>"""


def render_index(title: str, lead: str, categories: list[tuple[str, list[dict]]]) -> str:
    total_courses = sum(len(cs) for _, cs in categories)
    sections = "\n\n".join(render_section(cat, cs) for cat, cs in categories)
    return f"""<!DOCTYPE html>
<html lang="es" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{inline(lead)}">
<link rel="stylesheet" href="assets/css/style.css">
<script>
  /* Aplica el tema guardado antes de pintar (misma clave que usa el sitio
     cursos: musica-theme), para evitar flash del tema por defecto. */
  (function () {{
    try {{
      var t = localStorage.getItem("musica-theme");
      if (t) document.documentElement.setAttribute("data-theme", t);
    }} catch (e) {{}}
  }})();
</script>
</head>
<body>
<!-- GENERADO por tools/build_index.py desde COURSES.md: no editar a mano. -->
<main class="page">
  <div class="hero">
    <div class="hero-top">
      <h1>{html.escape(title)}</h1>
      <div class="theme-select-wrap">
        <select class="theme-select" id="theme-select" title="Cambiar tema">
          <option value="dark">Oscuro (Dracula)</option>
          <option value="light">Claro</option>
          <option value="dracula">Dracula</option>
          <option value="synthwave">Synthwave</option>
          <option value="vaporwave">Vaporwave</option>
          <option value="nineties">90s</option>
          <option value="nightcity">Night City</option>
          <option value="acid">Acid</option>
        </select>
      </div>
    </div>
    <p class="lead">{inline(lead)}</p>
    <p class="count">{total_courses} cursos</p>
  </div>

{sections}
</main>

<script>
  /* Selector de tema: misma clave musica-theme que usan los cursos,
     para que la eleccion se mantenga al navegar entre el catalogo y
     cualquier curso. */
  (function () {{
    var THEME_KEY = "musica-theme";
    var select = document.getElementById("theme-select");
    if (!select) return;
    var stored = null;
    try {{ stored = localStorage.getItem(THEME_KEY); }} catch (e) {{}}
    select.value = stored || document.documentElement.getAttribute("data-theme") || "dark";
    select.addEventListener("change", function () {{
      document.documentElement.setAttribute("data-theme", select.value);
      try {{ localStorage.setItem(THEME_KEY, select.value); }} catch (e) {{}}
    }});
  }})();

  /* Reemplaza el badge "listas/total" de cada card por "finalizadas/total",
     leyendo los flags de "leccion finalizada" que cada curso guarda en
     localStorage (ver assets/js/site.js de cada curso). El denominador es
     SIEMPRE el total de lecciones planificadas del curso (data-total), no
     cuantas tienen contenido generado (data-ready): lo que importa aca es
     cuanto le falta al usuario para terminar el curso completo. En file://
     todas las paginas del repo comparten el mismo localStorage, namespaced
     por curso ("<carpeta>-done-"). */
  (function () {{
    function donePrefixFor(slug) {{
      return slug + "-done-";
    }}
    document.querySelectorAll(".card[data-course]").forEach(function (card) {{
      const slug = card.dataset.course;
      const total = parseInt(card.dataset.total, 10);
      if (isNaN(total)) return;
      const prefix = donePrefixFor(slug);
      let done = 0;
      try {{
        for (let i = 0; i < localStorage.length; i++) {{
          const k = localStorage.key(i);
          if (k && k.indexOf(prefix) === 0 && localStorage.getItem(k) === "1") done++;
        }}
      }} catch (e) {{}}
      const badge = card.querySelector(".badge");
      if (badge) {{
        badge.textContent = done + "/" + total;
        badge.classList.toggle("badge--done", done > 0);
      }}
    }});
  }})();
</script>
</body>
</html>
"""


def main() -> None:
    title, lead, categories = parse_courses_md()
    out = ROOT / "index.html"
    out.write_text(render_index(title, lead, categories), encoding="utf-8")
    total = sum(len(cs) for _, cs in categories)
    print(f"OK: index.html generado con {total} cursos en {len(categories)} categorias.")


if __name__ == "__main__":
    main()
