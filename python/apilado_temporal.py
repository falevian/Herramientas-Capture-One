#!/usr/bin/env python3
"""
apilado_temporal.py: synthetic long exposure by temporal stacking.

Combines a sequence of photographs taken from a tripod (or hand-held, with
--align) by applying a temporal operator pixel by pixel:

  mean     a long exposure with a rectangular shutter
  hann     weighted mean with a Hann window, without the side lobes of the sinc
  median   robust estimator: removes transient things (people, cars, birds)
  sigma    mean with outlier rejection (median and MAD): robust and less noisy
  max      lighten mode: light trails and star trails
  min      darken mode

Everything is computed in linear light. The input images are linearised with
the given curve (--curve) and the result is encoded again with the same
curve, keeping the ICC profile of the first image.

With --align, each image is registered against the first one before stacking
(pyramidal ECC with an initial estimate by phase correlation) and the borders
that lack data in some image are cropped at the end. --align-model selects the
transformation: euclidean for a tripod that has moved, homography for
hand-held sequences. --align-region restricts the registration to a static
region.

Accepted inputs: 8 or 16 bit TIFF, JPEG and PNG. With rawpy installed, also
RAW files (developed linear, sRGB, camera white balance).

Typical use with Capture One:
  1. Equalise the adjustments of the whole sequence (copy and apply).
  2. Export with a 16 bit TIFF recipe, Adobe RGB (1998) profile.
  3. Run:
       python apilado_temporal.py exported_folder -o output_folder \\
              --ops mean,median,max,hann --curve 2.2 --comparison
  4. Import the resulting TIFF files in Capture One and develop from there.

Usual curves: Adobe RGB (1998) -> 2.2, ProPhoto RGB -> 1.8, sRGB -> srgb.

Messages and help are shown in English or Spanish (--lang, or the LANG
environment variable). Every option also has a Spanish spelling (--curva,
--alinear, --comparativa...) and the operators accept the Spanish names
(media, mediana, maximo, minimo). Output files are named stack_<op>_n<N>.tif
and comparison.jpg.

Dependencies: numpy, tifffile, Pillow. Optional: opencv-python (for --align)
and rawpy (for RAW).
"""

import argparse
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

EXT_IMAGEN = {".tif", ".tiff", ".jpg", ".jpeg", ".png"}
EXT_RAW = {".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2", ".dng", ".iiq", ".pef", ".srw"}
OPS_FLUJO = {"mean", "hann", "max", "min"}
OPS_PILA = {"median", "sigma"}
OPS_TODAS = OPS_FLUJO | OPS_PILA
OPS_ORDEN = ["mean", "hann", "median", "sigma", "max", "min"]
# nombres aceptados en la línea de órdenes -> nombre canónico
OPS_ALIAS = {"media": "mean", "mediana": "median", "maximo": "max", "máximo": "max",
             "minimo": "min", "mínimo": "min", "maximum": "max", "minimum": "min",
             "average": "mean"}
MODELOS_ALIAS = {"traslacion": "translation", "traslación": "translation", "euclideo": "euclidean",
                 "euclídeo": "euclidean", "afin": "affine", "afín": "affine", "homografia": "homography",
                 "homografía": "homography"}
ICC_TAG = 34675


# ---------------------------------------------------------------- idioma

def _idioma():
    """'en' o 'es': --lang/--idioma en la línea de órdenes; si no, LC_ALL, LC_MESSAGES o LANG."""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        for clave in ("--lang", "--idioma"):
            if a == clave and i + 1 < len(argv):
                return "es" if argv[i + 1].lower().startswith("es") else "en"
            if a.startswith(clave + "="):
                return "es" if a.split("=", 1)[1].lower().startswith("es") else "en"
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return "es" if v.lower().startswith("es") else "en"
    return "en"


IDIOMA = _idioma()

TEXTOS = {
    "en": {
        "etiquetas": {"mean": "Mean", "hann": "Hann", "median": "Median", "sigma": "Sigma",
                      "max": "Maximum", "min": "Minimum"},
        "rawpy": "Reading {name} needs rawpy (pip install rawpy).",
        "opencv": "Alignment needs OpenCV (pip install opencv-python).",
        "no_alinea": "    warning: this image could not be aligned, used as it is",
        "no_encuentro": "Cannot find {e}",
        "dos": "At least two images are needed.",
        "ops_desconocidas": "Unknown operators: {malas}. Available: {buenas} "
                            "(the Spanish names media, mediana, maximo, minimo are also accepted).",
        "modelo_desconocido": "Unknown alignment model: {m}. Available: translation, euclidean, affine, homography.",
        "inicio": "{n} images, operators: {ops}",
        "zona_mal": "--align-region must be x0,y0,x1,y1 as fractions between 0 and 1, for example 0,0,1,0.5",
        "pila": "Median and sigma need the whole stack on disk: {gb:.1f} GB in {d}",
        "tamano": "{name} has a different size ({a} versus {b}).",
        "recorte": "Cropping the borders without data: {w}x{h} -> {w2}x{h2} pixels",
        "guardado": "Saved {p}",
        "curva_mal": "--curve must be a number, srgb or linear",
        "descripcion": "Synthetic long exposure: combines a sequence with temporal operators in linear light.",
        "h_entradas": "folder with the sequence, or list of files, in temporal order",
        "h_salida": "output folder (default: stack)",
        "h_ops": "comma-separated operators: mean, hann, median, sigma, max, min",
        "h_curva": "encoding curve of the inputs: an exponent (2.2 Adobe RGB, 1.8 ProPhoto), srgb or linear. Default 2.2",
        "h_alinear": "align every image with the first one (needs OpenCV)",
        "h_zona": "static region used for the alignment, as x0,y0,x1,y1 in fractions of the image "
                  "(for example 0,0,1,0.5 for the upper half). Leave out water and clouds",
        "h_modelo": "translation, euclidean (shift and rotation, default), affine, or homography "
                    "(full perspective, for hand-held sequences)",
        "h_sin_recorte": "with --align, keep the borders that are left without data when the images move",
        "h_kappa": "rejection threshold for the sigma operator, in MAD units",
        "h_comparativa": "write comparison.jpg with all the results",
        "h_temporal": "folder for the temporary stack on disk (median and sigma)",
        "h_lang": "language of messages and help: en or es (default: from LANG)",
        "m_entradas": "INPUT", "m_salida": "FOLDER", "m_curva": "CURVE", "m_zona": "X0,Y0,X1,Y1",
        "m_modelo": "MODEL", "m_temporal": "FOLDER",
    },
    "es": {
        "etiquetas": {"mean": "Media", "hann": "Hann", "median": "Mediana", "sigma": "Sigma",
                      "max": "Máximo", "min": "Mínimo"},
        "rawpy": "Para leer {name} hace falta rawpy (pip install rawpy).",
        "opencv": "El alineado necesita OpenCV (pip install opencv-python).",
        "no_alinea": "    aviso: no se pudo alinear esta imagen, se usa sin mover",
        "no_encuentro": "No encuentro {e}",
        "dos": "Hacen falta al menos dos imágenes.",
        "ops_desconocidas": "Operadores desconocidos: {malas}. Disponibles: {buenas} "
                            "(también valen media, mediana, maximo, minimo).",
        "modelo_desconocido": "Modelo de alineado desconocido: {m}. Disponibles: traslacion, euclideo, afin, homografia.",
        "inicio": "{n} imágenes, operadores: {ops}",
        "zona_mal": "--zona-alineado debe ser x0,y0,x1,y1 en fracciones entre 0 y 1, por ejemplo 0,0,1,0.5",
        "pila": "Mediana o sigma necesitan la pila completa en disco: {gb:.1f} GB en {d}",
        "tamano": "{name} tiene un tamaño distinto ({a} frente a {b}).",
        "recorte": "Recorte de los bordes sin datos: {w}x{h} -> {w2}x{h2} píxeles",
        "guardado": "Guardado {p}",
        "curva_mal": "--curva debe ser un número, srgb o lineal",
        "descripcion": "Exposición larga sintética: combina una secuencia con operadores temporales en luz lineal.",
        "h_entradas": "carpeta con la secuencia o lista de ficheros, en orden temporal",
        "h_salida": "carpeta de salida (por defecto: stack)",
        "h_ops": "operadores separados por comas: mean, hann, median, sigma, max, min "
                 "(o media, mediana, maximo, minimo)",
        "h_curva": "curva de codificación de las entradas: un exponente (2.2 Adobe RGB, 1.8 ProPhoto), "
                   "srgb o lineal. Por defecto 2.2",
        "h_alinear": "alinea cada imagen con la primera (requiere OpenCV)",
        "h_zona": "región estática usada para alinear, como x0,y0,x1,y1 en fracciones de la imagen "
                  "(por ejemplo 0,0,1,0.5 para la mitad superior). Deja fuera el agua y el cielo con nubes",
        "h_modelo": "traslacion, euclideo (giro y desplazamiento, por defecto), afin, u homografia "
                    "(perspectiva completa, para secuencias a pulso)",
        "h_sin_recorte": "con --alinear, no recorta los bordes que quedan sin datos al mover las imágenes",
        "h_kappa": "umbral de rechazo para el operador sigma, en MAD",
        "h_comparativa": "genera comparison.jpg con todos los resultados",
        "h_temporal": "carpeta para la pila temporal en disco (mediana y sigma)",
        "h_lang": "idioma de los mensajes y de la ayuda: en o es (por defecto, según LANG)",
        "m_entradas": "ENTRADA", "m_salida": "CARPETA", "m_curva": "CURVA", "m_zona": "X0,Y0,X1,Y1",
        "m_modelo": "MODELO", "m_temporal": "CARPETA",
    },
}
_T = TEXTOS[IDIOMA]
ETIQUETAS = _T["etiquetas"]


# ---------------------------------------------------------------- lectura

def leer_imagen(ruta):
    """Devuelve (array float32 en [0,1] con forma H x W x C, perfil ICC o None, es_lineal)."""
    ext = ruta.suffix.lower()
    icc = None

    if ext in EXT_RAW:
        try:
            import rawpy
        except ImportError:
            sys.exit(_T["rawpy"].format(name=ruta.name))
        with rawpy.imread(str(ruta)) as r:
            arr = r.postprocess(gamma=(1, 1), no_auto_bright=True, output_bps=16,
                                use_camera_wb=True)
        return arr.astype(np.float32) / 65535.0, None, True

    if ext in (".tif", ".tiff"):
        import tifffile
        with tifffile.TiffFile(ruta) as t:
            pagina = t.pages[0]
            arr = pagina.asarray()
            etiqueta = pagina.tags.get(ICC_TAG)
            if etiqueta is not None:
                icc = bytes(etiqueta.value)
        # TIFF planar: canales primero
        if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[-1] not in (3, 4):
            arr = np.moveaxis(arr, 0, -1)
    else:
        from PIL import Image
        with Image.open(ruta) as im:
            icc = im.info.get("icc_profile")
            arr = np.asarray(im.convert("RGB"))

    if arr.ndim == 2:
        arr = arr[..., None]
    if arr.shape[-1] == 4:
        arr = arr[..., :3]

    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float32) / np.iinfo(arr.dtype).max
    else:
        arr = np.clip(arr.astype(np.float32), 0.0, 1.0)
    return arr, icc, False


# ---------------------------------------------------------------- curvas

def a_lineal(x, curva):
    if curva in ("lineal", "linear"):
        return x
    if curva == "srgb":
        return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return np.power(x, float(curva), dtype=np.float32)


def desde_lineal(y, curva):
    y = np.clip(y, 0.0, 1.0)
    if curva in ("lineal", "linear"):
        return y
    if curva == "srgb":
        return np.where(y <= 0.0031308, y * 12.92, 1.055 * y ** (1 / 2.4) - 0.055).astype(np.float32)
    return np.power(y, 1.0 / float(curva), dtype=np.float32)


# ---------------------------------------------------------------- alineado

MODELOS_ALINEADO = {
    "translation": "MOTION_TRANSLATION",  # solo desplazamiento
    "euclidean": "MOTION_EUCLIDEAN",      # desplazamiento y giro: trípode que se ha movido
    "affine": "MOTION_AFFINE",            # añade escala y cizalla
    "homography": "MOTION_HOMOGRAPHY",    # perspectiva completa: secuencias a pulso
}


class Alineador:
    """Registro de cada imagen contra la primera con ECC de OpenCV, en pirámide de tres
    escalas y con una estimación inicial del desplazamiento por correlación de fase,
    para que converja aunque las fotos se hayan movido bastante (secuencias a pulso)."""

    def __init__(self, referencia_lineal, zona=None, modelo="euclidean", lado_max=1600):
        """zona: (x0, y0, x1, y1) en fracciones de la imagen; solo esa región se usa para alinear.
        Conviene elegir algo estático y con detalle (árboles, rocas, edificios) y dejar fuera
        el agua y las nubes, porque si no el alineado intenta seguir las olas."""
        try:
            import cv2
        except ImportError:
            sys.exit(_T["opencv"])
        self.cv2 = cv2
        self.modo = getattr(cv2, MODELOS_ALINEADO[modelo])
        self.homografia = modelo == "homography"
        h, w = referencia_lineal.shape[:2]
        fino = min(1.0, lado_max / max(h, w))
        self.escalas = [e for e in (fino / 4, fino / 2, fino) if max(h, w) * e >= 64] or [fino]
        gris = self._gris(referencia_lineal)
        self.refs = [self._reducir(gris, e) for e in self.escalas]
        self.mascaras = [self._mascara(r.shape, zona) for r in self.refs]

    def _gris(self, img):
        gris = img.mean(axis=2) if img.shape[2] > 1 else img[..., 0]
        return np.power(np.clip(gris, 0, 1), 1 / 2.2).astype(np.float32)

    def _reducir(self, gris, e):
        cv2 = self.cv2
        if e < 1.0:
            gris = cv2.resize(gris, None, fx=e, fy=e, interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(gris, (0, 0), 1.0)

    @staticmethod
    def _mascara(forma, zona):
        if not zona:
            return None
        hh, ww = forma
        x0, y0, x1, y1 = zona
        m = np.zeros((hh, ww), np.uint8)
        m[int(y0 * hh):int(y1 * hh), int(x0 * ww):int(x1 * ww)] = 255
        return m

    def _cambiar_escala(self, matriz, f):
        """Pasa la transformación de una escala a otra f veces mayor."""
        m = matriz.copy()
        if self.homografia:
            m[0:2, 2] *= f
            m[2, 0:2] /= f
        else:
            m[:, 2] *= f
        return m

    def alinear(self, img):
        """Devuelve (imagen alineada, máscara de píxeles válidos)."""
        cv2 = self.cv2
        gris = self._gris(img)
        matriz = np.eye(3, 3, dtype=np.float32) if self.homografia else np.eye(2, 3, dtype=np.float32)

        # Estimación inicial del desplazamiento en la escala más gruesa
        mov0 = self._reducir(gris, self.escalas[0])
        ventana = cv2.createHanningWindow((mov0.shape[1], mov0.shape[0]), cv2.CV_32F)
        (dx, dy), _ = cv2.phaseCorrelate(self.refs[0], mov0, ventana)
        matriz[0, 2], matriz[1, 2] = dx, dy

        # Los modelos con más parámetros (afín, homografía) divergen en las escalas gruesas.
        # La pirámide se resuelve con el modelo euclídeo, que es robusto, y en la escala
        # fina se sube por la escalera afín y homografía, aceptando cada peldaño solo si
        # mejora la correlación y no deforma la imagen de forma absurda.
        matriz = matriz[:2].copy()
        if self.modo == cv2.MOTION_TRANSLATION:
            modo_piramide, escalera = cv2.MOTION_TRANSLATION, []
        else:
            modo_piramide = cv2.MOTION_EUCLIDEAN
            escalera = {cv2.MOTION_EUCLIDEAN: [],
                        cv2.MOTION_AFFINE: [cv2.MOTION_AFFINE],
                        cv2.MOTION_HOMOGRAPHY: [cv2.MOTION_AFFINE, cv2.MOTION_HOMOGRAPHY]}[self.modo]
        criterio = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
        anterior = self.escalas[0]
        convergio = False
        cc = -1.0
        mov = mov0
        for e, ref, masc in zip(self.escalas, self.refs, self.mascaras):
            matriz[:, 2] *= e / anterior
            anterior = e
            mov = mov0 if e == self.escalas[0] else self._reducir(gris, e)
            try:
                cc, matriz = cv2.findTransformECC(ref, mov, matriz, modo_piramide, criterio, masc, 5)
                convergio = True
            except cv2.error:
                pass
        h, w = img.shape[:2]
        if not convergio:
            print(_T["no_alinea"], file=sys.stderr)
            return img, np.ones((h, w), bool)
        for modo in escalera:
            inicial = matriz.copy()
            if modo == cv2.MOTION_HOMOGRAPHY and inicial.shape[0] == 2:
                inicial = np.vstack([inicial, np.array([0, 0, 1], np.float32)])
            try:
                cc_n, candidata = cv2.findTransformECC(self.refs[-1], mov, inicial, modo, criterio,
                                                       self.mascaras[-1], 5)
            except cv2.error:
                break
            lineal = candidata[:2, :2]
            razonable = abs(np.linalg.det(lineal) - 1.0) < 0.1
            if candidata.shape[0] == 3:
                hh, ww = mov.shape
                razonable &= abs(candidata[2, 0]) * ww < 0.1 and abs(candidata[2, 1]) * hh < 0.1
            if cc_n >= cc and razonable:
                cc, matriz = cc_n, candidata
            else:
                break
        if self.homografia and matriz.shape[0] == 2:
            matriz = np.vstack([matriz, np.array([0, 0, 1], np.float32)])
        matriz = self._cambiar_escala(matriz, 1.0 / anterior)

        banderas = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
        unos = np.ones((h, w), np.float32)
        if self.homografia:
            salida = cv2.warpPerspective(img, matriz, (w, h), flags=banderas, borderMode=cv2.BORDER_REPLICATE)
            valido = cv2.warpPerspective(unos, matriz, (w, h), flags=banderas,
                                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        else:
            salida = cv2.warpAffine(img, matriz, (w, h), flags=banderas, borderMode=cv2.BORDER_REPLICATE)
            valido = cv2.warpAffine(unos, matriz, (w, h), flags=banderas,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        if salida.ndim == 2:
            salida = salida[..., None]
        return salida, valido > 0.999


def rectangulo_valido(valido):
    """Rectángulo más grande, alineado con los ejes, en el que todas las imágenes tienen
    datos. Se obtiene pelando bordes: en cada paso se quita la fila o columna exterior
    con mayor fracción de píxeles inválidos."""
    h, w = valido.shape
    y0, y1, x0, x1 = 0, h, 0, w
    while y1 - y0 > 2 and x1 - x0 > 2:
        sub = valido[y0:y1, x0:x1]
        ancho, alto = x1 - x0, y1 - y0
        malos = [(~sub[0]).sum() / ancho, (~sub[-1]).sum() / ancho,
                 (~sub[:, 0]).sum() / alto, (~sub[:, -1]).sum() / alto]
        peor = int(np.argmax(malos))
        if malos[peor] == 0:
            break
        if peor == 0:
            y0 += 1
        elif peor == 1:
            y1 -= 1
        elif peor == 2:
            x0 += 1
        else:
            x1 -= 1
    return y0, y1, x0, x1


# ---------------------------------------------------------------- escritura

def guardar_tiff(ruta, datos01, icc):
    import tifffile
    datos = np.round(np.clip(datos01, 0, 1) * 65535).astype(np.uint16)
    if datos.shape[-1] == 1:
        datos = datos[..., 0]
        fotometria = "minisblack"
    else:
        fotometria = "rgb"
    extra = [(ICC_TAG, 7, len(icc), icc, True)] if icc else []
    tifffile.imwrite(ruta, datos, photometric=fotometria, compression="zlib", extratags=extra)


def miniatura(datos01, lado=900):
    from PIL import Image
    arr = np.round(np.clip(datos01, 0, 1) * 255).astype(np.uint8)
    if arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=2)
    im = Image.fromarray(arr, "RGB")
    im.thumbnail((lado, lado), Image.LANCZOS)
    return im


def hoja_comparativa(ruta, imagenes):
    """imagenes: lista de (etiqueta, datos codificados en [0,1])."""
    from PIL import Image, ImageDraw, ImageFont
    minis = [(et, miniatura(d)) for et, d in imagenes]
    w = max(m.width for _, m in minis)
    h = max(m.height for _, m in minis)
    columnas = 2 if len(minis) > 1 else 1
    filas = math.ceil(len(minis) / columnas)
    margen, alto_texto = 24, 44
    hoja = Image.new("RGB", (columnas * w + (columnas + 1) * margen,
                             filas * (h + alto_texto) + (filas + 1) * margen), (24, 24, 24))
    dibujo = ImageDraw.Draw(hoja)
    fuente = None
    for candidata in ("/System/Library/Fonts/Helvetica.ttc",
                      "/System/Library/Fonts/Supplemental/Arial.ttf",
                      "/Library/Fonts/Arial.ttf",
                      "C:/Windows/Fonts/arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "DejaVuSans.ttf"):
        try:
            fuente = ImageFont.truetype(candidata, 26)
            break
        except OSError:
            continue
    if fuente is None:
        try:
            fuente = ImageFont.load_default(size=26)
        except TypeError:
            fuente = ImageFont.load_default()
    for i, (et, m) in enumerate(minis):
        c, f = i % columnas, i // columnas
        x = margen + c * (w + margen)
        y = margen + f * (h + alto_texto + margen)
        hoja.paste(m, (x + (w - m.width) // 2, y + alto_texto))
        dibujo.text((x, y + 6), et, fill=(235, 235, 235), font=fuente)
    hoja.save(ruta, quality=92)


# ---------------------------------------------------------------- núcleo

def ventana_hann(n):
    # Hann sin ceros en los extremos, para no desperdiciar el primer y el último fotograma
    w = np.hanning(n + 2)[1:-1]
    return (w / w.sum()).astype(np.float64)


def recoger_ficheros(entradas):
    rutas = []
    for e in entradas:
        p = Path(e)
        if p.is_dir():
            rutas += sorted(q for q in p.iterdir()
                            if q.suffix.lower() in EXT_IMAGEN | EXT_RAW and not q.name.startswith("."))
        elif p.is_file():
            rutas.append(p)
        else:
            sys.exit(_T["no_encuentro"].format(e=e))
    if len(rutas) < 2:
        sys.exit(_T["dos"])
    return rutas


def procesar(args):
    rutas = recoger_ficheros(args.entradas)
    ops = [o.strip().lower() for o in args.ops.split(",") if o.strip()]
    ops = list(dict.fromkeys(OPS_ALIAS.get(o, o) for o in ops))
    desconocidas = [o for o in ops if o not in OPS_TODAS]
    if desconocidas:
        sys.exit(_T["ops_desconocidas"].format(malas=", ".join(desconocidas), buenas=", ".join(OPS_ORDEN)))

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    n = len(rutas)
    print(_T["inicio"].format(n=n, ops=", ".join(ops)))

    primera, icc, es_lineal = leer_imagen(rutas[0])
    curva_entrada = "lineal" if es_lineal else args.curva
    curva_salida = "srgb" if es_lineal else args.curva
    if es_lineal:
        icc = None
    forma = primera.shape
    ref_lineal = a_lineal(primera, curva_entrada)
    zona = None
    if args.zona_alineado:
        try:
            zona = tuple(float(v) for v in args.zona_alineado.split(","))
            assert len(zona) == 4 and 0 <= zona[0] < zona[2] <= 1 and 0 <= zona[1] < zona[3] <= 1
        except (ValueError, AssertionError):
            sys.exit(_T["zona_mal"])
    alineador = Alineador(ref_lineal, zona, args.modelo_alineado) if args.alinear else None
    validez = np.ones(forma[:2], bool) if alineador else None

    pesos = ventana_hann(n)
    acumulados = {}
    if "mean" in ops:
        acumulados["mean"] = np.zeros(forma, np.float64)
    if "hann" in ops:
        acumulados["hann"] = np.zeros(forma, np.float64)
    if "max" in ops:
        acumulados["max"] = np.full(forma, -np.inf, np.float32)
    if "min" in ops:
        acumulados["min"] = np.full(forma, np.inf, np.float32)

    necesita_pila = any(o in OPS_PILA for o in ops)
    pila = None
    if necesita_pila:
        dir_tmp = Path(args.temporal) if args.temporal else Path(tempfile.gettempdir())
        fichero_pila = dir_tmp / f"pila_{os.getpid()}.u16"
        gigas = n * np.prod(forma) * 2 / 1e9
        print(_T["pila"].format(gb=gigas, d=dir_tmp))
        pila = np.memmap(fichero_pila, dtype=np.uint16, mode="w+", shape=(n,) + forma)

    for k, ruta in enumerate(rutas):
        print(f"  [{k + 1}/{n}] {ruta.name}")
        if k == 0:
            lin = ref_lineal
        else:
            img, _, _ = leer_imagen(ruta)
            if img.shape != forma:
                sys.exit(_T["tamano"].format(name=ruta.name, a=img.shape, b=forma))
            lin = a_lineal(img, curva_entrada)
            if alineador:
                lin, valido = alineador.alinear(lin)
                validez &= valido
        if "mean" in acumulados:
            acumulados["mean"] += lin
        if "hann" in acumulados:
            acumulados["hann"] += pesos[k] * lin
        if "max" in acumulados:
            np.maximum(acumulados["max"], lin, out=acumulados["max"])
        if "min" in acumulados:
            np.minimum(acumulados["min"], lin, out=acumulados["min"])
        if pila is not None:
            pila[k] = np.round(np.clip(lin, 0, 1) * 65535).astype(np.uint16)

    resultados = {}
    if "mean" in acumulados:
        resultados["mean"] = (acumulados["mean"] / n).astype(np.float32)
    for op in ("hann", "max", "min"):
        if op in acumulados:
            resultados[op] = acumulados[op].astype(np.float32)

    if pila is not None:
        pila.flush()
        h, w, c = forma
        filas_bloque = max(1, int(256e6 / (n * w * c * 4)))
        if "median" in ops:
            resultados["median"] = np.empty(forma, np.float32)
        if "sigma" in ops:
            resultados["sigma"] = np.empty(forma, np.float32)
        for y0 in range(0, h, filas_bloque):
            y1 = min(h, y0 + filas_bloque)
            bloque = pila[:, y0:y1].astype(np.float32) / 65535.0
            med = np.median(bloque, axis=0)
            if "median" in ops:
                resultados["median"][y0:y1] = med
            if "sigma" in ops:
                mad = np.median(np.abs(bloque - med), axis=0) * 1.4826
                umbral = args.kappa * np.maximum(mad, 1e-5)
                validos = np.abs(bloque - med) <= umbral
                cuenta = validos.sum(axis=0)
                suma = np.where(validos, bloque, 0).sum(axis=0)
                resultados["sigma"][y0:y1] = np.where(cuenta > 0, suma / np.maximum(cuenta, 1), med)
        del pila
        try:
            os.remove(fichero_pila)
        except OSError:
            pass

    if validez is not None and not args.sin_recorte:
        y0, y1, x0, x1 = rectangulo_valido(validez)
        h, w = validez.shape
        if (y0, y1, x0, x1) != (0, h, 0, w):
            print(_T["recorte"].format(w=w, h=h, w2=x1 - x0, h2=y1 - y0))
            for op in resultados:
                resultados[op] = resultados[op][y0:y1, x0:x1]

    codificados = []
    for op in ops:
        datos = desde_lineal(resultados[op], curva_salida)
        destino = salida / f"stack_{op}_n{n}.tif"
        guardar_tiff(destino, datos, icc)
        codificados.append((ETIQUETAS[op], datos))
        print(_T["guardado"].format(p=destino))

    if args.comparativa:
        destino = salida / "comparison.jpg"
        hoja_comparativa(destino, codificados)
        print(_T["guardado"].format(p=destino))


def main():
    p = argparse.ArgumentParser(description=_T["descripcion"])
    p.add_argument("entradas", nargs="+", metavar=_T["m_entradas"], help=_T["h_entradas"])
    p.add_argument("-o", "--output", "--salida", dest="salida", default="stack",
                   metavar=_T["m_salida"], help=_T["h_salida"])
    p.add_argument("--ops", default="mean,median,max,hann", help=_T["h_ops"])
    p.add_argument("--curve", "--curva", dest="curva", default="2.2", metavar=_T["m_curva"], help=_T["h_curva"])
    p.add_argument("--align", "--alinear", dest="alinear", action="store_true", help=_T["h_alinear"])
    p.add_argument("--align-region", "--zona-alineado", dest="zona_alineado", metavar=_T["m_zona"], help=_T["h_zona"])
    p.add_argument("--align-model", "--modelo-alineado", dest="modelo_alineado", default="euclidean",
                   metavar=_T["m_modelo"], help=_T["h_modelo"])
    p.add_argument("--no-crop", "--sin-recorte", dest="sin_recorte", action="store_true", help=_T["h_sin_recorte"])
    p.add_argument("--kappa", type=float, default=2.5, help=_T["h_kappa"])
    p.add_argument("--comparison", "--comparativa", dest="comparativa", action="store_true", help=_T["h_comparativa"])
    p.add_argument("--temp", "--temporal", dest="temporal", metavar=_T["m_temporal"], help=_T["h_temporal"])
    p.add_argument("--lang", "--idioma", dest="lang", choices=["en", "es"], default=IDIOMA, help=_T["h_lang"])
    args = p.parse_args()
    args.curva = args.curva.strip().lower()
    if args.curva not in ("srgb", "lineal", "linear"):
        try:
            float(args.curva)
        except ValueError:
            sys.exit(_T["curva_mal"])
    m = args.modelo_alineado.strip().lower()
    args.modelo_alineado = MODELOS_ALIAS.get(m, m)
    if args.modelo_alineado not in MODELOS_ALINEADO:
        sys.exit(_T["modelo_desconocido"].format(m=m))
    procesar(args)


if __name__ == "__main__":
    main()
