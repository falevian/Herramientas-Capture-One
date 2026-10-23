#!/bin/bash
# Installer for the Capture One tools: temporal stack, film grain, film development
# and zone map.
# Instalador de las herramientas para Capture One: apilado temporal, grano de
# película, revelado de película y mapa de zonas.
#
# Usage / Uso:
#   bash instalar.sh
#   LANGUAGE=es bash instalar.sh            dialogs in Spanish / diálogos en español
#   LANGUAGE=en bash instalar.sh            dialogs in English / diálogos en inglés
#   PYTHON=/path/to/python3 bash instalar.sh
# Without LANGUAGE the dialogs follow the macOS language.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$HOME/miniforge3/bin/python3}"
IDIOMA="${LANGUAGE:-}"
case "$IDIOMA" in
    es*|ES*) IDIOMA=es ;;
    en*|EN*) IDIOMA=en ;;
    *) IDIOMA="" ;;
esac
# Language of the installer messages and of the script names in the menu
if [ -n "$IDIOMA" ]; then
    L="$IDIOMA"
elif osascript -e 'user locale of (system info)' 2>/dev/null | grep -q '^es'; then
    L=es
else
    L=en
fi
msg() { if [ "$L" = es ]; then echo "$2"; else echo "$1"; fi; }

if [ ! -x "$PY" ]; then
    msg "Cannot find $PY, using /usr/bin/python3" "No encuentro $PY, uso /usr/bin/python3"
    PY=/usr/bin/python3
fi

APILADO="$HOME/Pictures/Apilado temporal"
GRANO="$HOME/Pictures/Grano"
REVELADO="$HOME/Pictures/Revelado"
SCRIPTS="$HOME/Library/Scripts/Capture One Scripts"

# AppleScript file, menu name in English, menu name in Spanish
HERRAMIENTAS=(
    "apilado|Temporal stack|Apilado temporal"
    "grano|Film grain|Grano de película"
    "revelado|Film development|Revelado de película"
    "zonas|Zone map|Mapa de zonas"
)

conservar () {
    # copies $1 into folder $2; if a different file was there, keeps it as *_anterior.py
    local destino="$2/$(basename "$1")"
    if [ -f "$destino" ] && ! cmp -s "$1" "$destino"; then
        cp "$destino" "${destino%.py}_anterior.py"
        msg "   There was a different $(basename "$1"); saved as $(basename "${destino%.py}")_anterior.py" \
            "   Había un $(basename "$1") distinto; guardado como $(basename "${destino%.py}")_anterior.py"
    fi
    cp "$1" "$2/"
}

msg "1. Creating folders" "1. Creando carpetas"
mkdir -p "$APILADO" "$GRANO" "$REVELADO" "$SCRIPTS"

msg "2. Copying the Python programs" "2. Copiando los programas en Python"
cp "$DIR/python/apilado_temporal.py" "$APILADO/"
conservar "$DIR/python/grano.py" "$GRANO"
for f in revelado.py zonas.py espacio_color.py peliculas.py; do
    conservar "$DIR/python/revelado/$f" "$REVELADO"
done

msg "3. Installing libraries in $PY" "3. Instalando librerías en $PY"
"$PY" -m pip install --quiet numpy tifffile pillow opencv-python

msg "4. Compiling the Capture One scripts" "4. Compilando los scripts de Capture One"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for h in "${HERRAMIENTAS[@]}"; do
    IFS='|' read -r f nombre_en nombre_es <<< "$h"
    if [ "$L" = es ]; then nombre="$nombre_es"; otro="$nombre_en"; else nombre="$nombre_en"; otro="$nombre_es"; fi
    sed -e "s|^property idiomaFijo : \"\"|property idiomaFijo : \"$IDIOMA\"|" \
        -e "s|^property pythonFijo : \"\"|property pythonFijo : \"$PY\"|" \
        "$DIR/applescript/${f}_capture_one.applescript" > "$TMP/$f.applescript"
    osacompile -o "$SCRIPTS/$nombre.scpt" "$TMP/$f.applescript"
    # the same tool under its name in the other language would appear twice in the menu
    if [ -f "$SCRIPTS/$otro.scpt" ]; then
        rm "$SCRIPTS/$otro.scpt"
        msg "   Removed the copy in the other language: $otro.scpt" \
            "   Eliminada la copia en el otro idioma: $otro.scpt"
    fi
done

msg "5. Check" "5. Comprobación"
"$PY" -c "import numpy, tifffile, PIL, cv2; print('   OK: numpy, tifffile, pillow, opencv')"
"$PY" "$REVELADO/revelado.py" --check --film k64 --lang "$L" | sed 's/^/   /'
ls -1 "$SCRIPTS"

echo
msg "Done. In Capture One, refresh the Scripts menu." "Listo. En Capture One, actualiza el menú Scripts."
