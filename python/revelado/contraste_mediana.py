#!/usr/bin/env python3
"""contraste_mediana.py: contrast with the median point fixed.

The median commutes with monotonic functions: if an increasing curve leaves the
value at the median fixed, the median of the resulting image is exactly the
same. Contrast goes up without the image getting lighter or darker in that
sense; the mean, instead, does move, and the script reports it.

The curve. In normalised lightness x = L*/100, with the median at m:

    logit(y) = logit(m) + c (logit(x) - logit(m)),   logit(t) = ln(t / (1 - t))

It leaves black, white and the median fixed, it is increasing for any c > 0,
and its slope at the median is exactly c: with c > 1 contrast rises in an S
shape and with c < 1 it falls. Near the ends it behaves like x^c, so with c > 1
it gently tightens the deepest shadows and the brightest highlights.

Four uses:

    measure     prints the median of an image (L*, zone and reflectance) and the mean;
                with --mask, the weighted median inside a mask
    points      prints the points of the curve, from 0 to 100, for the Luma curve of
                Capture One, with the pivot at the given value
    apply       applies the curve to an image and saves the result. The curve acts
                on luminance and keeps chromaticity (luminance method, the
                default) or on each channel (rgb method, which saturates like a
                film). Colours pushed out of gamut are moved towards the grey of
                the same luminance, so the median is kept exactly.
    mask        works out the mask of a Capture One layer from two exports with the
                curve of the layer flattened, one to black and one to white: the
                difference of L* between them, divided by 100, is the weight of the
                mask at each pixel (0 outside, 1 inside, in between in the
                feathering). It is saved as a 16 bit grey TIFF.

Usage:
    python3 contraste_mediana.py measure photo.tif
    python3 contraste_mediana.py points --pivot 46.5 --contrast 1.3
    python3 contraste_mediana.py apply photo.tif output.tif --contrast 1.3
    python3 contraste_mediana.py apply photo.tif output.tif --contrast 1.3 --region 0,0.4,1,1
    python3 contraste_mediana.py mask black.tif white.tif mask.tif
    python3 contraste_mediana.py measure photo.tif --mask mask.tif

--region restricts the computation of the median to a rectangle (fractions
x0,y0,x1,y1), for example to leave out a white sky or a black frame; the curve
is applied to the whole image.

Messages and help are shown in English or Spanish (--lang, or the LANG
environment variable). The commands and options also have their Spanish names
(medir, puntos, aplicar, mascara; --contraste, --pivote, --metodo luminancia,
--zona, --mascara, --espacio). The lines MEDIANA_LSTAR=... and
MASCARA_SUPERFICIE=... are the same in both languages, for scripts.

Needs numpy, Pillow and tifffile, and espacio_color.py in the same folder.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import espacio_color as ec  # noqa: E402

IDIOMA = ec.IDIOMA
_T = {
    'en': {
        'describir': 'L* %.2f (zone %s, %.2f), reflectance %.1f %%',
        'zona_mal': '--region must be x0,y0,x1,y1 as fractions between 0 and 1',
        'contraste_mal': '--contrast must be greater than 0',
        'descripcion': 'Contrast with the median point fixed.',
        'h_medir': 'median and mean of the lightness',
        'h_puntos': 'points of the curve for Capture One',
        'h_aplicar': 'apply the curve to an image',
        'h_entrada': 'image (TIFF, JPEG or PNG)',
        'h_salida': 'output image; same colour space and profile as the input',
        'h_zona': 'rectangle used for the median, as x0,y0,x1,y1 in fractions of the image',
        'h_espacio': 'input space if it has no profile (auto = that of the embedded profile)',
        'h_pivote': 'position of the pivot, from 0 to 100',
        'h_contraste': 'slope of the curve at the median: 1 changes nothing, 1.3 is a medium contrast',
        'h_metodo': 'luminance: on luminance, keeping chromaticity (default); rgb: on each channel, '
                    'saturating like a film',
        'h_lang': 'language of messages and help: en or es (default: from LANG)',
        'mediana': 'median %s',
        'media': 'mean   L* %.2f',
        'cabecera': 'contrast %g at the median, %s method',
        'antes': 'median before  %s',
        'despues': 'median after   %s',
        'media2': 'mean of L*: %.2f before, %.2f after',
        'std': 'standard deviation of L*: %.2f before, %.2f after',
        'metodos': {'luminancia': 'luminance', 'rgb': 'rgb'},
        'mascara_vacia': 'The mask is empty: no pixel has any weight.',
        'mascara_tamano': 'The mask (%dx%d) does not have the size of the image (%dx%d).',
        'distinto_tamano': 'The two exports do not have the same size.',
        'mascara_info': 'mask: %.1f %% of the image with weight above 0.5, total weight equivalent to %.1f %%',
        'mediana_mascara': 'median inside the mask %s',
        'media_mascara': 'mean inside the mask   L* %.2f',
        'h_mascara': 'work out the mask of a layer',
        'h_mascara_opt': 'grey TIFF with the weight of each pixel',
        'h_negra': 'export with the Luma curve of the layer flattened at 0',
        'h_blanca': 'export with the Luma curve of the layer flattened at 100',
        'h_salida_mascara': 'output mask, 16 bit grey TIFF',
    },
    'es': {
        'describir': 'L* %.2f (zona %s, %.2f), reflectancia %.1f %%',
        'zona_mal': '--zona debe ser x0,y0,x1,y1 en fracciones entre 0 y 1',
        'contraste_mal': '--contraste debe ser mayor que 0',
        'descripcion': 'Contraste con el punto de la mediana fijo.',
        'h_medir': 'mediana y media de la luminosidad',
        'h_puntos': 'puntos de la curva para Capture One',
        'h_aplicar': 'aplica la curva a una imagen',
        'h_entrada': 'imagen (TIFF, JPEG o PNG)',
        'h_salida': 'imagen de salida; mismo espacio de color y perfil que la entrada',
        'h_zona': 'rectángulo con el que se calcula la mediana, como x0,y0,x1,y1 en fracciones de la imagen',
        'h_espacio': 'espacio de la entrada si no trae perfil (auto = el del perfil incrustado)',
        'h_pivote': 'posición del pivote, de 0 a 100',
        'h_contraste': 'pendiente de la curva en la mediana: 1 no cambia nada, 1.3 es un contraste medio',
        'h_metodo': 'luminancia: sobre la luminancia, conservando la cromaticidad (por defecto); rgb: '
                    'sobre cada canal, satura como una película',
        'h_lang': 'idioma de los mensajes y de la ayuda: en o es (por defecto, según LANG)',
        'mediana': 'mediana %s',
        'media': 'media   L* %.2f',
        'cabecera': 'contraste %g en la mediana, método %s',
        'antes': 'mediana antes   %s',
        'despues': 'mediana después %s',
        'media2': 'media de L*: %.2f antes, %.2f después',
        'std': 'desviación típica de L*: %.2f antes, %.2f después',
        'metodos': {},
        'mascara_vacia': 'La máscara está vacía: no hay ningún píxel con peso.',
        'mascara_tamano': 'La máscara (%dx%d) no tiene el tamaño de la imagen (%dx%d).',
        'distinto_tamano': 'Las dos exportaciones no tienen el mismo tamaño.',
        'mascara_info': 'máscara: %.1f %% de la imagen con peso mayor que 0,5, peso total equivalente al %.1f %%',
        'mediana_mascara': 'mediana dentro de la máscara %s',
        'media_mascara': 'media dentro de la máscara   L* %.2f',
        'h_mascara': 'deduce la máscara de una capa',
        'h_mascara_opt': 'TIFF en gris con el peso de cada píxel',
        'h_negra': 'exportación con la curva Luma de la capa aplanada en 0',
        'h_blanca': 'exportación con la curva Luma de la capa aplanada en 100',
        'h_salida_mascara': 'máscara de salida, TIFF en gris de 16 bits',
    },
}[IDIOMA]
ORDENES = {'measure': 'medir', 'points': 'puntos', 'apply': 'aplicar', 'mask': 'mascara'}

ROMANOS = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
EPS = 1e-6


def lstar(Y):
    Y = np.asarray(Y, float)
    return np.where(Y > (6 / 29) ** 3, 116 * np.cbrt(np.clip(Y, 0, None)) - 16, Y * (29 / 3) ** 3)


def lum_desde_lstar(L):
    L = np.asarray(L, float)
    f = (L + 16) / 116
    return np.where(f > 6 / 29, f ** 3, L / (29 / 3) ** 3)


def curva(x, m, c):
    """Curva logística con pivote en m y pendiente c en el pivote; x, m en (0, 1)."""
    x = np.clip(np.asarray(x, float), 0.0, 1.0)
    m = float(np.clip(m, 0.01, 0.99))
    xi = np.clip(x, EPS, 1 - EPS)
    u = np.log(m / (1 - m)) + c * (np.log(xi / (1 - xi)) - np.log(m / (1 - m)))
    y = 1.0 / (1.0 + np.exp(-u))
    return np.where(x <= 0, 0.0, np.where(x >= 1, 1.0, y))


def recortar(arr, zona):
    if not zona:
        return arr
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = zona
    return arr[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h)), int(x0 * w):max(int(x0 * w) + 1, int(x1 * w))]


def luminancia(enc, esp):
    lin = esp.a_lineal(enc)
    Y = np.clip(lin @ esp.M[1], 0, None) / esp.M[1].sum()
    return lin, np.clip(Y, 0, 1)


def describir(L):
    Y = float(lum_desde_lstar(L))
    z = L / 10.0
    zi = int(np.clip(np.floor(z + 0.5), 0, 10))
    return _T['describir'] % (L, ROMANOS[zi], z, 100 * Y)


def puntos_capture_one(pivote, contraste):
    """Puntos (brillo, cantidad) de 0 a 100 para la curva Luma: los extremos, el pivote
    y dos puntos a cada lado, a un tercio y dos tercios de cada tramo."""
    p = float(np.clip(pivote, 2.0, 98.0)) / 100.0
    xs = [0.0, p / 3, 2 * p / 3, p, p + (1 - p) / 3, p + 2 * (1 - p) / 3, 1.0]
    ys = curva(np.array(xs), p, contraste)
    return [(100 * x, 100 * float(y)) for x, y in zip(xs, ys)]


def aplicar(enc, esp, contraste, m, metodo):
    h, w, _ = enc.shape
    out = np.empty_like(enc)
    filas = max(1, 2000000 // w)
    for y0 in range(0, h, filas):
        y1 = min(h, y0 + filas)
        bloque = enc[y0:y1].reshape(-1, 3)
        lin, Y = luminancia(bloque, esp)
        if metodo == 'rgb':
            # la curva sobre la luminosidad de cada canal por separado
            Lc = lstar(np.clip(lin, 0, 1)) / 100.0
            nuevo = lum_desde_lstar(100.0 * curva(Lc, m, contraste))
        else:
            L2 = 100.0 * curva(lstar(Y) / 100.0, m, contraste)
            Y2 = lum_desde_lstar(L2)
            with np.errstate(divide='ignore', invalid='ignore'):
                k = np.where(Y > 1e-9, Y2 / Y, 0.0)
            nuevo = lin * k[:, None]
            nuevo[Y <= 1e-9] = Y2[Y <= 1e-9, None]
        # fuera de gama: hacia el gris de la misma luminancia, que así no cambia
        Yn = np.clip(nuevo @ esp.M[1] / esp.M[1].sum(), 0, 1)[:, None]
        mx = nuevo.max(1, keepdims=True)
        mn = nuevo.min(1, keepdims=True)
        with np.errstate(divide='ignore', invalid='ignore'):
            t_alto = np.where(mx > 1, (1 - Yn) / np.maximum(mx - Yn, 1e-12), 1.0)
            t_bajo = np.where(mn < 0, Yn / np.maximum(Yn - mn, 1e-12), 1.0)
        t = np.clip(np.minimum(t_alto, t_bajo), 0, 1)
        nuevo = np.clip(Yn + (nuevo - Yn) * t, 0, 1)
        out[y0:y1] = esp.desde_lineal(nuevo).reshape(y1 - y0, w, 3)
    return out


def leer_zona(texto):
    if not texto:
        return None
    try:
        z = tuple(float(v) for v in texto.split(','))
        assert len(z) == 4 and 0 <= z[0] < z[2] <= 1 and 0 <= z[1] < z[3] <= 1
        return z
    except (ValueError, AssertionError):
        sys.exit(_T['zona_mal'])


def mediana_ponderada(v, w):
    v = np.asarray(v, float).ravel()
    w = np.asarray(w, float).ravel()
    ok = w > 0
    v, w = v[ok], w[ok]
    if w.sum() <= 0:
        sys.exit(_T['mascara_vacia'])
    orden = np.argsort(v)
    acum = np.cumsum(w[orden])
    i = int(np.searchsorted(acum, 0.5 * acum[-1]))
    return float(v[orden][min(i, len(v) - 1)])


def leer_mascara(ruta, forma):
    import tifffile
    m = tifffile.imread(ruta).astype(float)
    if m.ndim == 3:
        m = m[..., 0]
    m /= 65535.0 if m.max() > 1 else 1.0
    if m.shape != forma:
        sys.exit(_T['mascara_tamano'] % (m.shape[1], m.shape[0], forma[1], forma[0]))
    return m


def main():
    en = IDIOMA == 'en'
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    ap = argparse.ArgumentParser(description=_T['descripcion'], parents=[comun])
    sub = ap.add_subparsers(dest='orden', required=True)

    def opciones_imagen(sp, salida=False):
        sp.add_argument('entrada', metavar='INPUT' if en else 'ENTRADA', help=_T['h_entrada'])
        if salida:
            sp.add_argument('salida', metavar='OUTPUT' if en else 'SALIDA', help=_T['h_salida'])
        sp.add_argument('--region', '--zona', dest='zona', default=None,
                        metavar='X0,Y0,X1,Y1', help=_T['h_zona'])
        sp.add_argument('--space', '--espacio', dest='espacio', choices=['auto'] + list(ec.ESPACIOS),
                        default='auto', help=_T['h_espacio'])

    pm = sub.add_parser('measure', aliases=['medir'], parents=[comun], help=_T['h_medir'])
    opciones_imagen(pm)
    pm.add_argument('--mask', '--mascara', dest='mascara', default=None,
                    metavar='MASK' if en else 'MASCARA', help=_T['h_mascara_opt'])

    pk = sub.add_parser('mask', aliases=['mascara'], parents=[comun], help=_T['h_mascara'])
    pk.add_argument('negra', metavar='BLACK' if en else 'NEGRA', help=_T['h_negra'])
    pk.add_argument('blanca', metavar='WHITE' if en else 'BLANCA', help=_T['h_blanca'])
    pk.add_argument('salida', metavar='OUTPUT' if en else 'SALIDA', help=_T['h_salida_mascara'])
    pk.add_argument('--space', '--espacio', dest='espacio', choices=['auto'] + list(ec.ESPACIOS),
                    default='auto', help=_T['h_espacio'])

    pp = sub.add_parser('points', aliases=['puntos'], parents=[comun], help=_T['h_puntos'])
    pp.add_argument('--pivot', '--pivote', dest='pivote', type=float, required=True,
                    metavar='PIVOT' if en else 'PIVOTE', help=_T['h_pivote'])
    pp.add_argument('--contrast', '--contraste', dest='contraste', type=float, default=1.3,
                    metavar='C', help=_T['h_contraste'])

    pa = sub.add_parser('apply', aliases=['aplicar'], parents=[comun], help=_T['h_aplicar'])
    opciones_imagen(pa, salida=True)
    pa.add_argument('--contrast', '--contraste', dest='contraste', type=float, default=1.3,
                    metavar='C', help=_T['h_contraste'])
    pa.add_argument('--method', '--metodo', dest='metodo', default='luminancia',
                    choices=['luminance', 'luminancia', 'rgb'], help=_T['h_metodo'])
    a = ap.parse_args()
    a.orden = ORDENES.get(a.orden, a.orden)
    if getattr(a, 'metodo', None) == 'luminance':
        a.metodo = 'luminancia'

    if a.orden == 'puntos':
        for x, y in puntos_capture_one(a.pivote, a.contraste):
            print('%.3f,%.3f' % (x, y))
        return

    if a.orden == 'mascara':
        import tifffile
        e1, _, icc1 = ec.leer(a.negra)
        e2, _, _ = ec.leer(a.blanca)
        if e1.shape != e2.shape:
            sys.exit(_T['distinto_tamano'])
        esp = ec.espacio_para(icc1, a.espacio)
        _, Y1 = luminancia(e1.reshape(-1, 3), esp)
        _, Y2 = luminancia(e2.reshape(-1, 3), esp)
        w = np.clip((lstar(Y2) - lstar(Y1)) / 100.0, 0, 1).reshape(e1.shape[:2])
        w[w < 0.02] = 0.0
        tifffile.imwrite(a.salida, np.round(w * 65535).astype(np.uint16), photometric='minisblack')
        print('MASCARA_SUPERFICIE=%.4f' % float((w > 0.5).mean()))
        print(_T['mascara_info'] % (100 * float((w > 0.5).mean()), 100 * float(w.mean())))
        return

    enc, bits, icc = ec.leer(a.entrada)
    esp = ec.espacio_para(icc, a.espacio)
    if a.orden == 'medir' and a.mascara:
        w = leer_mascara(a.mascara, enc.shape[:2])
        _, Y = luminancia(enc.reshape(-1, 3), esp)
        L = lstar(Y)
        med = mediana_ponderada(L, w)
        media = float((L * w.ravel()).sum() / max(w.sum(), 1e-9))
        print('MEDIANA_LSTAR=%.4f' % med)
        print(_T['mediana_mascara'] % describir(med))
        print(_T['media_mascara'] % media)
        return
    zona = leer_zona(a.zona)
    _, Y = luminancia(recortar(enc, zona).reshape(-1, 3), esp)
    L = lstar(Y)
    med = float(np.median(L))
    media = float(L.mean())

    if a.orden == 'medir':
        print('MEDIANA_LSTAR=%.4f' % med)
        print(_T['mediana'] % describir(med))
        print(_T['media'] % media)
        return

    if a.contraste <= 0:
        sys.exit(_T['contraste_mal'])
    m = med / 100.0
    if a.metodo == 'rgb':
        # por canales la luminancia no es función monótona de una sola variable, así que
        # el pivote se busca por bisección sobre una muestra para que la mediana no cambie
        muestra = recortar(enc, zona).reshape(-1, 3)
        if len(muestra) > 300000:
            muestra = muestra[np.random.default_rng(0).choice(len(muestra), 300000, replace=False)]
        muestra = muestra[None]
        lo, hi = 0.01, 0.99
        for _ in range(30):
            mm = 0.5 * (lo + hi)
            _, Ym = luminancia(aplicar(muestra, esp, a.contraste, mm, 'rgb').reshape(-1, 3), esp)
            # con c > 1, si la mediana sube es que el pivote está por debajo: hay que subirlo
            if (np.median(lstar(Ym)) > med) == (a.contraste > 1):
                lo = mm
            else:
                hi = mm
        m = 0.5 * (lo + hi)
    res = aplicar(enc, esp, a.contraste, m, a.metodo)
    ec.escribir(a.salida, res, icc, bits=16 if a.salida.lower().endswith(('.tif', '.tiff')) else 8)
    _, Y2 = luminancia(recortar(res, zona).reshape(-1, 3), esp)
    L2 = lstar(Y2)
    print(_T['cabecera'] % (a.contraste, _T['metodos'].get(a.metodo, a.metodo)))
    print(_T['antes'] % describir(med))
    print(_T['despues'] % describir(float(np.median(L2))))
    print(_T['media2'] % (media, float(L2.mean())))
    print(_T['std'] % (float(L.std()), float(L2.std())))


if __name__ == '__main__':
    main()
