.DEFAULT_GOAL := help

.PHONY: help site open

help:
	@echo "Targets disponibles:"
	@echo "  make site   regenera index.html (catalogo de cursos) desde COURSES.md"
	@echo "  make open   abre el catalogo en el navegador"

site:
	python3 tools/build_index.py

open:
	open index.html
