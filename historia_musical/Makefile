.DEFAULT_GOAL := help

.PHONY: help site open

help:
	@echo "Targets disponibles:"
	@echo "  make site   regenera el sitio HTML desde LESSON.md y ROADMAP.md"
	@echo "  make open   abre el sitio en el navegador"

site:
	uv run --no-project --with markdown python tools/build_site.py

open:
	open index.html
