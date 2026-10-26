#!/bin/bash
# uso: _dev/mkproject.sh <nombre> "<titulo del curso>" "<bajada>"
# Crea <raiz>/<nombre> con el generador de sitio y los assets de historia_musical.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
NAME=$1; TITLE=$2; LEAD=$3
D=$ROOT/$NAME
mkdir -p "$D/tools" "$D/assets" "$D/lessons"
cp "$ROOT/historia_musical/tools/build_site.py" "$D/tools/"
cp -r "$ROOT/historia_musical/assets/css" "$ROOT/historia_musical/assets/js" "$D/assets/"
cp "$ROOT/historia_musical/Makefile" "$D/Makefile"
echo '{}' > "$D/tools/site.json"
printf '# %s\n\n%s\n' "$TITLE" "$LEAD" > "$D/README.md"
: > "$D/ROADMAP.md"
echo "creado $D"
