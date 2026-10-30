# Herramientas de fotografía para Capture One

*[Read in English](README.md)*

Cinco herramientas para el menú Scripts de Capture One Pro en macOS:

- **Apilado temporal.** Combina una secuencia de fotos, hecha con trípode o a pulso, mediante operadores temporales píxel a píxel calculados en luz lineal: media, media con ventana de Hann, mediana, media con rechazo sigma, máximo y mínimo. Sirve para conseguir una exposición larga sintética sin filtro de densidad neutra, para borrar lo transitorio (personas, coches, pájaros) o para acumular estelas. Si el trípode se ha movido o la secuencia es a pulso, alinea antes las fotos (registro ECC en pirámide, euclídeo o por homografía) y recorta los bordes que quedan sin datos.
- **Grano de película.** Añade a cada imagen seleccionada un grano físicamente escalado según la película elegida (Tri-X, Kodachrome 64 y 25, Velvia 50, Pro 400H) y según el recorte de la foto: una imagen recortada a la mitad se trata como medio fotograma ampliado y el grano se ve proporcionalmente mayor. La amplitud está calibrada con la granularidad rms de la hoja técnica, y el grano depende del tono como en una diapositiva o en una copia de un negativo.
- **Revelado de película.** Revela la imagen con los modelos espectrales de [peliculas.py](https://github.com/falevian/Photographers/tree/main/scripts/peliculas), evaluados píxel a píxel en lugar de pasar por la tabla 3D de un perfil ICC. La exportación deja dos pasos de margen por encima del blanco difuso, de modo que el hombro de la película comprime las luces en lugar de recortarlas. Con Tri-X añade virados y filtros de color delante del objetivo simulados sobre la sensibilidad espectral, y puede terminar con el grano de la misma película.
- **Mapa de zonas.** Dibuja el sistema de zonas de una imagen en falso color, con la superficie de cada zona, y como curvas de nivel sobre la imagen en gris, para decidir reservados y quemados. Lee la copia tal como está revelada, la escena como un fotómetro, o los tonos que daría una copia modelada de Tri-X a grado 2.
- **Contraste en la mediana.** Sube o baja el contraste con una curva logística con el pivote en la mediana de la luminosidad. Como la mediana conmuta con cualquier curva creciente, la mediana de la imagen se queda exactamente donde estaba. La curva puede escribirse en la curva Luma de Capture One, donde queda editable (el script mide y ajusta el pivote a la escala propia de Capture One), o aplicarse en Python sobre L* conservando la cromaticidad. Con una capa de ajustes seleccionada, deduce la máscara de la capa y fija la mediana solo dentro de ella.

Todas exportan las variantes seleccionadas como TIFF de 16 bits, las procesan con un programa en Python y vuelven a importar el resultado en el documento abierto (el mapa de zonas se abre en Vista Previa, y el contraste en la mediana puede quedarse como curva dentro de Capture One). Los diálogos siguen el idioma de macOS, español o inglés.

## Requisitos

- macOS con Capture One Pro: la orden de procesado por script solo existe en la versión Pro.
- Python 3 con numpy, tifffile, pillow y opencv-python. Por defecto las herramientas usan el Python de miniforge en `~/miniforge3/bin/python3` o, si no está, el del sistema; el instalador se encarga de las librerías y admite cualquier otro Python.

## Instalación

```
git clone https://github.com/falevian/Herramientas-Capture-One.git
cd Herramientas-Capture-One
LANGUAGE=es bash instalar.sh
```

El instalador copia los programas en Python a `~/Pictures/Apilado temporal`, `~/Pictures/Grano` y `~/Pictures/Revelado`, instala las librerías, compila los cinco AppleScript en `~/Library/Scripts/Capture One Scripts` y comprueba que todo responde. Después, en Capture One, actualiza el menú Scripts: deben aparecer “Apilado temporal”, “Grano de película”, “Revelado de película”, “Mapa de zonas” y “Contraste en la mediana”. `LANGUAGE=es` fija los diálogos en español aunque macOS esté en inglés; sin esa variable siguen el idioma del sistema. `PYTHON=/ruta/a/python3` elige otro Python.

La guía completa está en [INSTALACION.md](INSTALACION.md) (y en texto plano en [INSTALACION.txt](INSTALACION.txt)): instalación paso a paso, uso de cada herramienta, dónde quedan los archivos, problemas conocidos y desinstalación.

## Contenido

```
instalar.sh                          instalador automático
python/
  apilado_temporal.py                combina la secuencia en luz lineal, con alineado opcional
  grano.py                           modelo de grano calibrado con las hojas técnicas
  revelado/
    revelado.py                      revelado de película píxel a píxel
    zonas.py                         mapa del sistema de zonas
    contraste_mediana.py             contraste con la mediana fija
    espacio_color.py                 lectura de imágenes y perfiles ICC
    peliculas.py                     modelos espectrales de las películas
applescript/
  apilado_capture_one.applescript    “Apilado temporal” en el menú Scripts
  grano_capture_one.applescript      “Grano de película”
  revelado_capture_one.applescript   “Revelado de película”
  zonas_capture_one.applescript      “Mapa de zonas”
  mediana_capture_one.applescript    “Contraste en la mediana”
INSTALACION.md, INSTALACION.txt      guía completa
INSTALL.md, INSTALL.txt              guía completa en inglés
```

## Uso desde Terminal

Los programas funcionan por sí solos, sin Capture One, con cualquier TIFF, JPEG o PNG:

```
python3 apilado_temporal.py secuencia -o resultado --ops media,mediana,maximo,hann --curva 2.2 --comparativa
python3 apilado_temporal.py secuencia -o resultado --ops mediana --alinear --modelo-alineado homografia --zona-alineado 0,0,1,0.5
python3 grano.py entrada.tif salida.tif --pelicula trix --espacio auto
python3 revelado.py lineal.tif salida.tif --pelicula trix --virado selenio --filtro rojo --margen 2
python3 zonas.py foto.tif --modo escena --margen 3
python3 contraste_mediana.py aplicar foto.tif salida.tif --contraste 1.3
```

Con `-h` cualquiera de ellos muestra todas sus opciones. Los mensajes siguen la variable `LANG` o `--lang es|en`, y todas las opciones tienen también su nombre en inglés.

## Relación con Fotografía para científicos

Estas herramientas acompañan al sitio [Fotografía para científicos](https://falevian.github.io/Photographers/), cuyo código está en [falevian/Photographers](https://github.com/falevian/Photographers):

- Los modelos de película y el grano se describen en [Películas clásicas en perfiles ICC](https://falevian.github.io/Photographers/peliculas-icc.html). peliculas.py es el mismo archivo que en ese repositorio; el grano.py de aquí añade la lectura y escritura de TIFF de 16 bits, la conservación del perfil ICC y la opción `--espacio` (sRGB, Adobe RGB, ProPhoto o auto).
- La teoría del apilado temporal está en la [herramienta de exposición larga](https://falevian.github.io/Photographers/exposicion-larga.html), en su [manual](https://falevian.github.io/Photographers/manual-exposicion-larga.html) y en la ficha [Exposición larga](https://falevian.github.io/Photographers/paseos/exposicion-larga.html) del paseo fotográfico.

## Licencia

MIT. Véase [LICENSE](LICENSE).
