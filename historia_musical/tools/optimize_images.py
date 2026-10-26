#!/usr/bin/env python3
"""Procesa las imagenes nuevas en tools/images_incoming/: las convierte a webp,
detecta su orientacion (horizontal/vertical/cuadrada), les cambia el tamano a
algo optimo para web, borra toda la metadata (EXIF/IPTC/XMP) y las mueve a la
carpeta de la leccion que les corresponde, segun tools/images_manifest.json.

Cada archivo en images_incoming/ se identifica por su nombre de archivo SIN
extension (el "id" del manifest), sin importar que extension tenga
(.jpg, .png, .heic convertido a jpg/png, etc. - cualquier formato que lea
Pillow). Al procesarlo con exito, se marca el id como "done" en el manifest y el
archivo original se BORRA (no se guarda ningun respaldo: los originales,
con su metadata, nunca deben quedar en el repo ni en ningun lado).

Uso:  make images
      (o: uv run --no-project --with pillow python3 tools/optimize_images.py)
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools" / "images_manifest.json"
INCOMING = ROOT / "tools" / "images_incoming"

MAX_LADO_LARGO = 1600  # px: lado mas largo de una imagen horizontal/vertical
MAX_LADO_CUADRADA = 1400  # px: lado de una imagen cuadrada
QUALITY = 85


def orientacion(width: int, height: int) -> str:
    if abs(width - height) <= max(width, height) * 0.03:
        return "cuadrada"
    return "horizontal" if width > height else "vertical"


def redimensionar(img: Image.Image, orient: str) -> Image.Image:
    w, h = img.size
    if orient == "cuadrada":
        target = min(max(w, h), MAX_LADO_CUADRADA)
        if target >= max(w, h):
            return img
        return img.resize((target, target), Image.Resampling.LANCZOS)
    largo = max(w, h)
    if largo <= MAX_LADO_LARGO:
        return img
    escala = MAX_LADO_LARGO / largo
    nuevo = (max(1, round(w * escala)), max(1, round(h * escala)))
    return img.resize(nuevo, Image.Resampling.LANCZOS)


def limpiar_y_convertir(path_origen: Path) -> tuple[bytes, str]:
    """Abre la imagen, descarta toda su metadata, la redimensiona segun su
    orientacion y la devuelve como bytes webp, junto con la orientacion
    detectada."""
    with Image.open(path_origen) as img:
        img.load()
        if img.mode == "P":
            img = img.convert("RGBA")
        elif img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        # Recrear la imagen desde los bytes de pixeles puros: esto descarta
        # EXIF, IPTC, XMP, perfiles de color y cualquier otro metadato del
        # archivo original (ubicacion, camara, fecha, autor, etc.).
        limpia = Image.frombytes(img.mode, img.size, img.tobytes())
    orient = orientacion(*limpia.size)
    limpia = redimensionar(limpia, orient)
    if limpia.mode == "RGBA":
        fondo = Image.new("RGB", limpia.size, (255, 255, 255))
        fondo.paste(limpia, mask=limpia.split()[3])
        limpia = fondo
    elif limpia.mode != "RGB":
        limpia = limpia.convert("RGB")
    buf = io.BytesIO()
    limpia.save(buf, format="WEBP", quality=QUALITY, method=6)
    return buf.getvalue(), orient


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: no existe {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pendientes = {e["id"]: e for e in manifest if e["status"] == "pending"}

    INCOMING.mkdir(parents=True, exist_ok=True)

    if not pendientes:
        print("No hay imagenes pendientes en el manifest.")
        return 0

    procesadas: list[str] = []
    sin_match: list[str] = []
    for archivo in sorted(INCOMING.iterdir()):
        if not archivo.is_file():
            continue
        stem = archivo.stem
        entry = pendientes.get(stem)
        if entry is None:
            sin_match.append(archivo.name)
            continue
        dest = ROOT / entry["dest"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            data, orient = limpiar_y_convertir(archivo)
        except (UnidentifiedImageError, OSError) as exc:
            print(f"ERROR procesando {archivo.name}: {exc}", file=sys.stderr)
            continue
        dest.write_bytes(data)
        entry["status"] = "done"
        entry["orientacion"] = orient
        archivo.unlink()
        procesadas.append(stem)

    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    restantes = sum(1 for e in manifest if e["status"] == "pending")
    print(f"OK: {len(procesadas)} imagenes procesadas, {restantes} pendientes.")
    if procesadas:
        print("Procesadas: " + ", ".join(procesadas))
    if sin_match:
        print(
            f"AVISO: {len(sin_match)} archivo(s) en images_incoming/ sin match "
            f"en el manifest (revisa el nombre): " + ", ".join(sin_match)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
