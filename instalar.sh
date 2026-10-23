#!/bin/bash
# Installer for the temporal stacking and film grain tools for Capture One.
# Instalador de las herramientas de apilado temporal y grano para Capture One.
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
SCRIPTS="$HOME/Library/Scripts/Capture One Scripts"
if [ "$L" = es ]; then
    NOMBRE_APILADO="Apilado temporal"; NOMBRE_GRANO="Grano de película"
    OTRO_APILADO="Temporal stack"; OTRO_GRANO="Film grain"
else
    NOMBRE_APILADO="Temporal stack"; NOMBRE_GRANO="Film grain"
    OTRO_APILADO="Apilado temporal"; OTRO_GRANO="Grano de película"
fi

msg "1. Creating folders" "1. Creando carpetas"
mkdir -p "$APILADO" "$GRANO" "$SCRIPTS"

msg "2. Copying the Python programs" "2. Copiando los programas en Python"
cp "$DIR/python/apilado_temporal.py" "$APILADO/"
if [ -f "$GRANO/grano.py" ] && ! cmp -s "$DIR/python/grano.py" "$GRANO/grano.py"; then
    cp "$GRANO/grano.py" "$GRANO/grano_anterior.py"
    msg "   There was a different grano.py; saved as grano_anterior.py" \
        "   Había un grano.py distinto; guardado como grano_anterior.py"
fi
cp "$DIR/python/grano.py" "$GRANO/"

msg "3. Installing libraries in $PY" "3. Instalando librerías en $PY"
"$PY" -m pip install --quiet numpy tifffile pillow opencv-python

msg "4. Compiling the Capture One scripts" "4. Compilando los scripts de Capture One"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for f in apilado grano; do
    sed -e "s|^property idiomaFijo : \"\"|property idiomaFijo : \"$IDIOMA\"|" \
        -e "s|^property pythonFijo : \"\"|property pythonFijo : \"$PY\"|" \
        "$DIR/applescript/${f}_capture_one.applescript" > "$TMP/$f.applescript"
done
osacompile -o "$SCRIPTS/$NOMBRE_APILADO.scpt" "$TMP/apilado.applescript"
osacompile -o "$SCRIPTS/$NOMBRE_GRANO.scpt" "$TMP/grano.applescript"
# The same tools under the names of the other language would appear twice in the menu
for viejo in "$OTRO_APILADO" "$OTRO_GRANO"; do
    if [ -f "$SCRIPTS/$viejo.scpt" ]; then
        rm "$SCRIPTS/$viejo.scpt"
        msg "   Removed the copy in the other language: $viejo.scpt" \
            "   Eliminada la copia en el otro idioma: $viejo.scpt"
    fi
done

msg "5. Check" "5. Comprobación"
"$PY" -c "import numpy, tifffile, PIL, cv2; print('   OK: numpy, tifffile, pillow, opencv')"
ls -1 "$SCRIPTS"

echo
msg "Done. In Capture One, refresh the Scripts menu." "Listo. En Capture One, actualiza el menú Scripts."
