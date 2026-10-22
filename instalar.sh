#!/bin/bash
# Instalador de las herramientas de apilado temporal y grano para Capture One.
# Uso: bash instalar.sh
# Para usar otro Python: PYTHON=/ruta/a/python3 bash instalar.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$HOME/miniforge3/bin/python3}"
if [ ! -x "$PY" ]; then
    echo "No encuentro $PY, uso /usr/bin/python3"
    PY=/usr/bin/python3
fi

APILADO="$HOME/Pictures/Apilado temporal"
GRANO="$HOME/Pictures/Grano"
SCRIPTS="$HOME/Library/Scripts/Capture One Scripts"

echo "1. Creando carpetas"
mkdir -p "$APILADO" "$GRANO" "$SCRIPTS"

echo "2. Copiando los programas en Python"
cp "$DIR/python/apilado_temporal.py" "$APILADO/"
if [ -f "$GRANO/grano.py" ] && ! cmp -s "$DIR/python/grano.py" "$GRANO/grano.py"; then
    cp "$GRANO/grano.py" "$GRANO/grano_anterior.py"
    echo "   Había un grano.py distinto; guardado como grano_anterior.py"
fi
cp "$DIR/python/grano.py" "$GRANO/"

echo "3. Instalando librerías en $PY"
"$PY" -m pip install --quiet numpy tifffile pillow opencv-python

echo "4. Compilando los scripts de Capture One"
osacompile -o "$SCRIPTS/Apilado temporal.scpt" "$DIR/applescript/apilado_capture_one.applescript"
osacompile -o "$SCRIPTS/Grano de película.scpt" "$DIR/applescript/grano_capture_one.applescript"

echo "5. Comprobación"
"$PY" -c "import numpy, tifffile, PIL, cv2; print('   Librerías correctas')"
ls -1 "$SCRIPTS"

echo
echo "Listo. En Capture One, actualiza el menú Scripts."
