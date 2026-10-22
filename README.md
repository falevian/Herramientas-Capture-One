# Herramientas para Capture One

Dos herramientas para el menú Scripts de Capture One Pro en macOS:

- **Apilado temporal.** Combina una secuencia de fotos, hecha con trípode o a pulso, mediante operadores temporales píxel a píxel calculados en luz lineal: media, media con ventana de Hann, mediana, media con rechazo sigma, máximo y mínimo. Sirve para conseguir una exposición larga sintética sin filtro de densidad neutra, para borrar lo transitorio (personas, coches, pájaros) o para acumular estelas. Si el trípode se ha movido o la secuencia es a pulso, alinea antes las fotos (registro ECC en pirámide, euclídeo o por homografía) y recorta los bordes que quedan sin datos.
- **Grano de película.** Añade a cada imagen seleccionada un grano físicamente escalado según la película elegida (Tri-X, Kodachrome 64 y 25, Velvia 50, Pro 400H) y según el recorte de la foto: una imagen recortada a la mitad se trata como medio fotograma ampliado y el grano se ve proporcionalmente mayor.

Las dos funcionan igual: exportan las variantes seleccionadas con todos sus ajustes como TIFF de 16 bits en Adobe RGB (1998), las procesan con un programa en Python y vuelven a importar el resultado en el documento abierto.

## Requisitos

- macOS con Capture One Pro: la orden de procesado por script solo existe en la versión Pro.
- Python 3 con numpy, tifffile, pillow y opencv-python. Los scripts buscan primero el Python de miniforge en `~/miniforge3/bin/python3` y, si no está, usan el del sistema; el instalador se encarga de las librerías.

## Instalación

```
git clone https://github.com/falevian/Herramientas-Capture-One.git
cd Herramientas-Capture-One
bash instalar.sh
```

El instalador copia los programas en Python a `~/Pictures/Apilado temporal` y `~/Pictures/Grano`, instala las librerías, compila los dos AppleScript en `~/Library/Scripts/Capture One Scripts` y comprueba que todo responde. Después, en Capture One, actualiza el menú Scripts: deben aparecer “Apilado temporal” y “Grano de película”.

La guía completa está en [INSTALACION.md](INSTALACION.md) (y en texto plano en [INSTALACION.txt](INSTALACION.txt)): instalación paso a paso, uso de cada herramienta, dónde quedan los archivos, problemas conocidos y desinstalación.

## Contenido

```
instalar.sh                        instalador automático
python/
  apilado_temporal.py              combina la secuencia en luz lineal, con alineado opcional
  grano.py                         modelo de grano calibrado con las hojas técnicas
applescript/
  apilado_capture_one.applescript  “Apilado temporal” en el menú Scripts
  grano_capture_one.applescript    “Grano de película” en el menú Scripts
INSTALACION.md, INSTALACION.txt    guía completa
```

## Uso desde Terminal

Los dos programas funcionan por sí solos, sin Capture One, con cualquier carpeta de TIFF, JPEG o PNG:

```
python3 apilado_temporal.py secuencia -o resultado --ops media,mediana,maximo,hann --curva 2.2 --comparativa
python3 apilado_temporal.py secuencia -o resultado --ops mediana --alinear --modelo-alineado homografia --zona-alineado 0,0,1,0.5
python3 grano.py entrada.tif salida.tif --pelicula trix --espacio adobergb
python3 grano.py entrada.jpg web.jpg --pelicula k64 --ancho-salida 2000
```

Con `-h` cualquiera de los dos muestra todas sus opciones.

## Relación con Fotografía para científicos

Estas herramientas acompañan al sitio [Fotografía para científicos](https://falevian.github.io/Photographers/), cuyo código está en [falevian/Photographers](https://github.com/falevian/Photographers):

- El modelo de grano se describe en [Películas clásicas en perfiles ICC](https://falevian.github.io/Photographers/peliculas-icc.html). La versión de este repositorio añade la lectura y escritura de TIFF de 16 bits, la conservación del perfil ICC y la opción `--espacio` para trabajar en Adobe RGB.
- La teoría del apilado temporal está en la [herramienta de exposición larga](https://falevian.github.io/Photographers/exposicion-larga.html), en su [manual](https://falevian.github.io/Photographers/manual-exposicion-larga.html) y en la ficha [Exposición larga](https://falevian.github.io/Photographers/paseos/exposicion-larga.html) del paseo fotográfico.

## Licencia

MIT. Véase [LICENSE](LICENSE).

---

**English summary.** Two tools for the Scripts menu of Capture One Pro on macOS: temporal stacking of a sequence (mean, Hann-weighted mean, median, sigma-clipped mean, maximum and minimum, computed in linear light, with optional ECC alignment and cropping) and physically scaled film grain (Tri-X, Kodachrome 64 and 25, Velvia 50, Pro 400H). Both export the selected variants as 16-bit Adobe RGB TIFF, process them in Python and re-import the result. The documentation is in Spanish.
