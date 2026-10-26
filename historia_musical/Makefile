.DEFAULT_GOAL := help

.PHONY: help site open images

help:
	@echo "Targets disponibles:"
	@echo "  make site     regenera el sitio HTML desde LESSON.md y ROADMAP.md"
	@echo "  make open     abre el sitio en el navegador"
	@echo "  make images   procesa tools/images_incoming/ (webp, resize, limpia metadata)"

site:
	uv run --no-project --with markdown python tools/build_site.py

open:
	open index.html

images:
	uv run --no-project --with pillow python3 tools/optimize_images.py
