#!/usr/bin/env python3
"""
apilado_temporal.py

Combina una secuencia de fotografías tomadas desde trípode aplicando distintos
operadores temporales píxel a píxel:

  media    equivale a una exposición larga con obturador rectangular
  hann     media ponderada con ventana de Hann, sin los lóbulos laterales del sinc
  mediana  estimador robusto: elimina lo transitorio (personas, coches, pájaros)
  sigma    media con rechazo de valores atípicos (mediana y MAD), robusta y con menos ruido
  maximo   modo aclarar: estelas de luces y estrellas
  minimo   modo oscurecer

Todo el cálculo se hace en luz lineal. Las imágenes de entrada se linealizan
según la curva indicada (--curva) y el resultado se vuelve a codificar con la
misma curva, conservando el perfil ICC de la primera imagen.

Con --alinear, cada imagen se registra contra la primera antes de combinarla (ECC en
pirámide con estimación inicial por correlación de fase) y al final se recortan los
bordes que no tienen datos en todas las imágenes. --modelo-alineado elige la
transformación: euclideo para un trípode que se ha movido, homografia para
secuencias a pulso. --zona-alineado limita el registro a una región estática.

Entradas admitidas: TIFF de 8 o 16 bits, JPEG y PNG. Si está instalado rawpy,
también RAW (se revelan en lineal, espacio sRGB, con el balance de la cámara).

Uso típico con Capture One:
  1. Iguala los ajustes de toda la secuencia (copiar y aplicar ajustes).
  2. Exporta con una receta TIFF de 16 bits, perfil Adobe RGB (1998).
  3. Ejecuta:
       python apilado_temporal.py carpeta_exportada -o carpeta_salida \\
              --ops media,mediana,maximo,hann --curva 2.2 --comparativa
  4. Importa los TIFF resultantes en Capture One y revela desde ahí.

Curvas habituales: Adobe RGB (1998) -> 2.2, ProPhoto RGB -> 1.8, sRGB -> srgb.

Dependencias: numpy, tifffile, Pillow. Opcionales: opencv-python (para --alinear)
y rawpy (para RAW).
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
OPS_FLUJO = {"media", "hann", "maximo", "minimo"}
OPS_PILA = {"mediana", "sigma"}
OPS_TODAS = OPS_FLUJO | OPS_PILA
ETIQUETAS = {
    "media": "Media",
    "hann": "Hann",
    "mediana": "Mediana",
    "sigma": "Sigma",
    "maximo": "Máximo",
    "minimo": "Mínimo",
}
ICC_TAG = 34675


# ---------------------------------------------------------------- lectura

def leer_imagen(ruta):
    """Devuelve (array float32 en [0,1] con forma H x W x C, perfil ICC o None, es_lineal)."""
    ext = ruta.suffix.lower()
    icc = None

    if ext in EXT_RAW:
        try:
            import rawpy
        except ImportError:
            sys.exit(f"Para leer {ruta.name} hace falta rawpy (pip install rawpy).")
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
    if curva == "lineal":
        return x
    if curva == "srgb":
        return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return np.power(x, float(curva), dtype=np.float32)


def desde_lineal(y, curva):
    y = np.clip(y, 0.0, 1.0)
    if curva == "lineal":
        return y
    if curva == "srgb":
        return np.where(y <= 0.0031308, y * 12.92, 1.055 * y ** (1 / 2.4) - 0.055).astype(np.float32)
    return np.power(y, 1.0 / float(curva), dtype=np.float32)


# ---------------------------------------------------------------- alineado

MODELOS_ALINEADO = {
    "traslacion": "MOTION_TRANSLATION",   # solo desplazamiento
    "euclideo": "MOTION_EUCLIDEAN",       # desplazamiento y giro: trípode que se ha movido
    "afin": "MOTION_AFFINE",              # añade escala y cizalla
    "homografia": "MOTION_HOMOGRAPHY",    # perspectiva completa: secuencias a pulso
}


class Alineador:
    """Registro de cada imagen contra la primera con ECC de OpenCV, en pirámide de tres
    escalas y con una estimación inicial del desplazamiento por correlación de fase,
    para que converja aunque las fotos se hayan movido bastante (secuencias a pulso)."""

    def __init__(self, referencia_lineal, zona=None, modelo="euclideo", lado_max=1600):
        """zona: (x0, y0, x1, y1) en fracciones de la imagen; solo esa región se usa para alinear.
        Conviene elegir algo estático y con detalle (árboles, rocas, edificios) y dejar fuera
        el agua y las nubes, porque si no el alineado intenta seguir las olas."""
        try:
            import cv2
        except ImportError:
            sys.exit("El alineado necesita OpenCV (pip install opencv-python).")
        self.cv2 = cv2
        self.modo = getattr(cv2, MODELOS_ALINEADO[modelo])
        self.homografia = modelo == "homografia"
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
            print("    aviso: no se pudo alinear esta imagen, se usa sin mover", file=sys.stderr)
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
            sys.exit(f"No encuentro {e}")
    if len(rutas) < 2:
        sys.exit("Hacen falta al menos dos imágenes.")
    return rutas


def procesar(args):
    rutas = recoger_ficheros(args.entradas)
    ops = [o.strip() for o in args.ops.split(",") if o.strip()]
    desconocidas = set(ops) - OPS_TODAS
    if desconocidas:
        sys.exit(f"Operadores desconocidos: {', '.join(sorted(desconocidas))}. "
                 f"Disponibles: {', '.join(sorted(OPS_TODAS))}")

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    n = len(rutas)
    print(f"{n} imágenes, operadores: {', '.join(ops)}")

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
            sys.exit("--zona-alineado debe ser x0,y0,x1,y1 en fracciones entre 0 y 1, por ejemplo 0,0,1,0.5")
    alineador = Alineador(ref_lineal, zona, args.modelo_alineado) if args.alinear else None
    validez = np.ones(forma[:2], bool) if alineador else None

    pesos = ventana_hann(n)
    acumulados = {}
    if "media" in ops:
        acumulados["media"] = np.zeros(forma, np.float64)
    if "hann" in ops:
        acumulados["hann"] = np.zeros(forma, np.float64)
    if "maximo" in ops:
        acumulados["maximo"] = np.full(forma, -np.inf, np.float32)
    if "minimo" in ops:
        acumulados["minimo"] = np.full(forma, np.inf, np.float32)

    necesita_pila = any(o in OPS_PILA for o in ops)
    pila = None
    if necesita_pila:
        dir_tmp = Path(args.temporal) if args.temporal else Path(tempfile.gettempdir())
        fichero_pila = dir_tmp / f"pila_{os.getpid()}.u16"
        gigas = n * np.prod(forma) * 2 / 1e9
        print(f"Mediana o sigma necesitan la pila completa en disco: {gigas:.1f} GB en {dir_tmp}")
        pila = np.memmap(fichero_pila, dtype=np.uint16, mode="w+", shape=(n,) + forma)

    for k, ruta in enumerate(rutas):
        print(f"  [{k + 1}/{n}] {ruta.name}")
        if k == 0:
            lin = ref_lineal
        else:
            img, _, _ = leer_imagen(ruta)
            if img.shape != forma:
                sys.exit(f"{ruta.name} tiene un tamaño distinto ({img.shape} frente a {forma}).")
            lin = a_lineal(img, curva_entrada)
            if alineador:
                lin, valido = alineador.alinear(lin)
                validez &= valido
        if "media" in acumulados:
            acumulados["media"] += lin
        if "hann" in acumulados:
            acumulados["hann"] += pesos[k] * lin
        if "maximo" in acumulados:
            np.maximum(acumulados["maximo"], lin, out=acumulados["maximo"])
        if "minimo" in acumulados:
            np.minimum(acumulados["minimo"], lin, out=acumulados["minimo"])
        if pila is not None:
            pila[k] = np.round(np.clip(lin, 0, 1) * 65535).astype(np.uint16)

    resultados = {}
    if "media" in acumulados:
        resultados["media"] = (acumulados["media"] / n).astype(np.float32)
    for op in ("hann", "maximo", "minimo"):
        if op in acumulados:
            resultados[op] = acumulados[op].astype(np.float32)

    if pila is not None:
        pila.flush()
        h, w, c = forma
        filas_bloque = max(1, int(256e6 / (n * w * c * 4)))
        if "mediana" in ops:
            resultados["mediana"] = np.empty(forma, np.float32)
        if "sigma" in ops:
            resultados["sigma"] = np.empty(forma, np.float32)
        for y0 in range(0, h, filas_bloque):
            y1 = min(h, y0 + filas_bloque)
            bloque = pila[:, y0:y1].astype(np.float32) / 65535.0
            med = np.median(bloque, axis=0)
            if "mediana" in ops:
                resultados["mediana"][y0:y1] = med
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
            print(f"Recorte de los bordes sin datos: {w}x{h} -> {x1 - x0}x{y1 - y0} píxeles")
            for op in resultados:
                resultados[op] = resultados[op][y0:y1, x0:x1]

    codificados = []
    for op in ops:
        datos = desde_lineal(resultados[op], curva_salida)
        destino = salida / f"apilado_{op}_n{n}.tif"
        guardar_tiff(destino, datos, icc)
        codificados.append((ETIQUETAS[op], datos))
        print(f"Guardado {destino}")

    if args.comparativa:
        destino = salida / "comparativa.jpg"
        hoja_comparativa(destino, codificados)
        print(f"Guardado {destino}")


def main():
    p = argparse.ArgumentParser(
        description="Exposición larga sintética: combina una secuencia con operadores temporales en luz lineal.")
    p.add_argument("entradas", nargs="+", help="Carpeta con la secuencia o lista de ficheros, en orden temporal")
    p.add_argument("-o", "--salida", default="apilado", help="Carpeta de salida (por defecto: apilado)")
    p.add_argument("--ops", default="media,mediana,maximo,hann",
                   help="Operadores separados por comas: media, hann, mediana, sigma, maximo, minimo")
    p.add_argument("--curva", default="2.2",
                   help="Curva de codificación de las entradas: un exponente (2.2 Adobe RGB, 1.8 ProPhoto), "
                        "srgb o lineal. Por defecto 2.2")
    p.add_argument("--alinear", action="store_true", help="Alinea cada imagen con la primera (requiere OpenCV)")
    p.add_argument("--zona-alineado",
                   help="Región estática usada para alinear, como x0,y0,x1,y1 en fracciones de la imagen "
                        "(por ejemplo 0,0,1,0.5 para la mitad superior). Deja fuera el agua y el cielo con nubes")
    p.add_argument("--modelo-alineado", choices=list(MODELOS_ALINEADO), default="euclideo",
                   help="traslacion, euclideo (giro y desplazamiento, por defecto), afin, "
                        "u homografia (perspectiva completa, para secuencias a pulso)")
    p.add_argument("--sin-recorte", action="store_true",
                   help="Con --alinear, no recorta los bordes que quedan sin datos al mover las imágenes")
    p.add_argument("--kappa", type=float, default=2.5, help="Umbral de rechazo para el operador sigma, en MAD")
    p.add_argument("--comparativa", action="store_true", help="Genera comparativa.jpg con todos los resultados")
    p.add_argument("--temporal", help="Carpeta para la pila temporal en disco (mediana y sigma)")
    args = p.parse_args()
    if args.curva not in ("srgb", "lineal"):
        try:
            float(args.curva)
        except ValueError:
            sys.exit("--curva debe ser un número, srgb o lineal")
    procesar(args)


if __name__ == "__main__":
    main()
