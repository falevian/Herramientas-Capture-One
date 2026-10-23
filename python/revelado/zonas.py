#!/usr/bin/env python3
"""zonas.py: zone system map of an image.

Three modes.

print (default). For an image already developed, as it will be seen or
printed. The zones of the print are spread in equal steps of lightness L*
between black (zone 0) and paper white (zone X), ten units of L* per zone. With
this convention zone V falls at L* 50, which corresponds to an 18 % reflectance,
middle grey.

film. Also for a developed image, but the zone of each tone is found by
inverting the curve of a real, modelled print: which zone of the scene should
have been exposed for the print to come out with that tone. By default the
reference is Tri-X in D-76 printed on Multigrade IV at grade 2 (from the model
in peliculas.py), with white at the paper base. It shows how that system
compresses highlights and shadows; with that reference, for example, zones 0 to
II end up almost at the maximum black of the paper. --reference selects another
film.

scene. For a linear light export (Linear Response in Capture One), it is the
light meter reading: one stop per zone, with middle grey (--grey, 0.18 by
default) in zone V. --headroom gives the stops by which the exposure was
lowered when exporting, to recover the high zones without clipping.

It writes two images: the false colour map with the legend and the percentage
of the area in each zone, and the grey image with the boundaries between zones
drawn as contour lines, which is the useful view to decide dodging and burning.
Clipped pixels (pure white or black in some channel) are marked separately.
The files are named <image>_zones_map.jpg and <image>_zones_contours.jpg.

Messages, help and the text in the images are in English or Spanish (--lang,
or the LANG environment variable). Every option and mode also has its Spanish
spelling (--modo copia, pelicula, escena; --margen; --lado...).

Usage:
    python3 zonas.py photo.tif
    python3 zonas.py photo.tif --mode scene --headroom 3 -o folder
    python3 zonas.py photo.tif --mode film --reference pro400h --size 0

Needs numpy, Pillow and tifffile, and espacio_color.py in the same folder
(and revelado.py and peliculas.py for the film mode).
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
        'luces': 'highlights', 'sombras': 'shadows', 'recortadas': 'clipped',
        't_pelicula': 'Zones of the print, inverting a print on %s',
        't_copia': 'Zones of the print, ten units of L* per zone, zone V at L* 50',
        't_escena': 'Zones of the scene, one stop per zone, %.0f %% grey in zone V',
        'zona': '  zone %-4s %5.1f %%%s',
        'en_copia': '   (on the print: L* %5.1f, density %.2f)',
        'lstar': '   (L* %3d, reflectance %5.1f %%, density %.2f)',
        'recortes': '  clipped highlights %.2f %%, clipped shadows %.2f %%',
        'guardado': 'Saved %s',
        'descripcion': 'Zone system map of an image.',
        'h_entrada': 'image to analyse (TIFF, JPEG or PNG)',
        'h_salida': 'output folder (default: that of the input)',
        'h_modo': 'print: the developed image, ten L* units per zone (default); film: inverting a '
                  'modelled print; scene: light meter reading of a linear export',
        'h_referencia': 'film mode: reference film (trix, k64, k25, velvia50, pro400h)',
        'h_gris': 'scene mode: luminance that goes to zone V',
        'h_margen': 'scene mode: stops by which the exposure was lowered when exporting',
        'h_lado': 'long side of the generated images, in pixels (0 = original size)',
        'h_suavizado': 'smoothing factor of the contour lines (0 = none, 2 = twice as much)',
        'h_espacio': 'input space if it has no profile (auto = that of the embedded profile)',
        'h_lang': 'language of messages, help and image text: en or es (default: from LANG)',
    },
    'es': {
        'luces': 'luces', 'sombras': 'sombras', 'recortadas': 'recortadas',
        't_pelicula': 'Zonas de la copia, invirtiendo una copia de %s',
        't_copia': 'Zonas de la copia, diez unidades de L* por zona, zona V en L* 50',
        't_escena': 'Zonas de la escena, un paso por zona, gris %.0f %% en la zona V',
        'zona': '  zona %-4s %5.1f %%%s',
        'en_copia': '   (en la copia: L* %5.1f, densidad %.2f)',
        'lstar': '   (L* %3d, reflectancia %5.1f %%, densidad %.2f)',
        'recortes': '  luces recortadas %.2f %%, sombras recortadas %.2f %%',
        'guardado': 'Guardado %s',
        'descripcion': 'Mapa del sistema de zonas de una imagen.',
        'h_entrada': 'imagen que se analiza (TIFF, JPEG o PNG)',
        'h_salida': 'carpeta de salida (por defecto, la de la entrada)',
        'h_modo': 'copia: la imagen revelada, diez unidades de L* por zona (por defecto); pelicula: '
                  'invirtiendo una copia modelada; escena: lectura de fotómetro de una exportación lineal',
        'h_referencia': 'modo pelicula: película de referencia (trix, k64, k25, velvia50, pro400h)',
        'h_gris': 'modo escena: luminancia que va a la zona V',
        'h_margen': 'modo escena: pasos que se bajó la exposición al exportar',
        'h_lado': 'lado largo de las imágenes generadas, en píxeles (0 = tamaño original)',
        'h_suavizado': 'factor del suavizado de las curvas de nivel (0 = sin suavizar, 2 = el doble)',
        'h_espacio': 'espacio de la entrada si no trae perfil (auto = el del perfil incrustado)',
        'h_lang': 'idioma de los mensajes, la ayuda y el texto de las imágenes: en o es (por defecto, según LANG)',
    },
}[IDIOMA]
MODOS_ALIAS = {'print': 'copia', 'film': 'pelicula', 'película': 'pelicula', 'scene': 'escena'}

ROMANOS = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']

# Falso color: luminosidad creciente con la zona y tono distinto en cada una; la V es
# un gris neutro para que el gris medio se reconozca de un vistazo
PALETA = np.array([
    [8, 8, 10], [40, 14, 82], [32, 52, 168], [22, 112, 196], [28, 160, 160],
    [128, 128, 128], [120, 190, 70], [228, 210, 60], [245, 158, 50], [238, 98, 70],
    [252, 246, 240]], dtype=float) / 255.0
COLOR_ALTAS = np.array([255, 0, 200]) / 255.0     # recorte en las luces
COLOR_BAJAS = np.array([0, 60, 255]) / 255.0      # recorte en las sombras
# Fronteras: la línea entre la zona k y la k+1
LINEAS = np.array([
    [70, 90, 255], [60, 150, 255], [0, 200, 255], [0, 230, 170], [80, 255, 80],
    [200, 255, 0], [255, 220, 0], [255, 150, 0], [255, 70, 40], [255, 0, 160]], dtype=float) / 255.0


class CurvaCopia:
    """Tabla zona de la escena -> luminancia relativa de la copia de referencia."""

    def __init__(self, pelicula='trix'):
        import revelado as R
        self.R = R
        self.modelo = R.Modelo(pelicula, blanco='papel')
        self.nombre = self.modelo.nombre
        k = np.linspace(-3.0, 14.0, 1701)
        Y = 0.18 * 2.0 ** (k - 5.0)
        XYZ = Y[:, None] * ec.D50[None, :]
        Yc = self.modelo.xyz50(XYZ)[:, 1]
        Yc = R.compresion_gama(np.repeat(Yc[:, None], 3, 1), np.ones(3) / 3)[:, 0]
        Yc = np.maximum.accumulate(Yc)
        # quita las mesetas para poder invertir
        ok = np.r_[True, np.diff(Yc) > 1e-7]
        self.k, self.Y = k[ok], Yc[ok]

    def zona(self, Y):
        return np.interp(Y, self.Y, self.k, left=self.k[0], right=self.k[-1])

    def luminancia(self, zona):
        return np.interp(zona, self.k, self.Y)


def reducir(enc, lado):
    from PIL import Image
    h, w, _ = enc.shape
    if not lado or max(h, w) <= lado:
        return enc
    f = lado / max(h, w)
    nw, nh = max(1, round(w * f)), max(1, round(h * f))
    canales = [np.asarray(Image.fromarray(enc[..., c].astype(np.float32), 'F').resize((nw, nh), Image.BOX))
               for c in range(3)]
    return np.stack(canales, -1).astype(np.float64)


def suavizar(a, sigma):
    if sigma <= 0:
        return a
    r = int(np.ceil(3 * sigma))
    x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode='edge')
    p = np.apply_along_axis(lambda v: np.convolve(v, k, 'valid'), 1, p)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, 'valid'), 0, p)
    return p


def lstar(Y):
    Y = np.asarray(Y, float)
    return np.where(Y > (6 / 29) ** 3, 116 * np.cbrt(np.clip(Y, 0, None)) - 16, Y * (29 / 3) ** 3)


def lum_desde_lstar(L):
    L = np.asarray(L, float)
    f = (L + 16) / 116
    return np.where(f > 6 / 29, f ** 3, (L / (29 / 3) ** 3))


def analizar(enc, espacio, modo, curva=None, gris=0.18, margen=0.0):
    lin = espacio.a_lineal(enc)
    Y = np.clip(lin @ espacio.M[1], 0, None) / espacio.M[1].sum()
    if modo == 'escena':
        z = 5.0 + np.log2(np.maximum(Y * 2.0 ** margen, 1e-12) / gris)
    elif modo == 'pelicula':
        z = curva.zona(Y)
    else:
        z = lstar(np.clip(Y, 0, 1)) / 10.0
    altas = (enc >= 0.998).any(-1)
    bajas = (enc <= 0.002).all(-1)
    return z, Y, altas, bajas


def porcentajes(z, altas, bajas):
    zi = np.clip(np.floor(z + 0.5), 0, 10).astype(int)
    total = z.size
    p = np.array([(zi == k).sum() for k in range(11)]) / total * 100
    return p, altas.mean() * 100, bajas.mean() * 100


def _titulo(dib, s, w, u):
    tam = int(26 * u)
    f = ec.fuente(8)  # imágenes estrechas: el bucle no llega a ejecutarse
    while tam > 8:
        f = ec.fuente(tam)
        try:
            ancho = dib.textbbox((0, 0), s, font=f)[2]
        except AttributeError:
            ancho = len(s) * tam * 0.55
        if ancho <= w - 32 * u:
            break
        tam -= 1
    dib.text((int(16 * u), int(14 * u)), s, fill=(235, 235, 235), font=f)


def _texto(dib, xy, s, f, color=(235, 235, 235), centro=False):
    if centro:
        try:
            x0, y0, x1, y1 = dib.textbbox((0, 0), s, font=f)
            xy = (xy[0] - (x1 - x0) / 2, xy[1])
        except AttributeError:
            pass
    dib.text(xy, s, fill=color, font=f)


def imagen_mapa(z, altas, bajas, titulo, pct, pa, pb):
    from PIL import Image, ImageDraw
    h, w = z.shape
    zi = np.clip(np.floor(z + 0.5), 0, 10).astype(int)
    rgb = PALETA[zi]
    rgb[altas] = COLOR_ALTAS
    rgb[bajas] = COLOR_BAJAS
    u = w / 1200.0
    alto_ley = int(175 * u)
    lienzo = Image.new('RGB', (w, h + alto_ley + int(60 * u)), (22, 22, 22))
    lienzo.paste(Image.fromarray((rgb * 255).astype(np.uint8)), (0, int(60 * u)))
    d = ImageDraw.Draw(lienzo)
    _titulo(d, titulo, w, u)
    y0 = h + int(60 * u) + int(18 * u)
    ancho = (w - int(32 * u)) / 13.0
    fz, fp = ec.fuente(int(24 * u)), ec.fuente(int(17 * u))
    for k in range(11):
        x = int(16 * u + k * ancho)
        c = tuple(int(v * 255) for v in PALETA[k])
        d.rectangle([x, y0, x + int(ancho) - int(6 * u), y0 + int(70 * u)], fill=c)
        tc = (20, 20, 20) if PALETA[k].mean() > 0.45 else (240, 240, 240)
        _texto(d, (x + (ancho - 6 * u) / 2, y0 + int(20 * u)), ROMANOS[k], fz, tc, centro=True)
        _texto(d, (x + (ancho - 6 * u) / 2, y0 + int(82 * u)), '%.1f %%' % pct[k], fp, centro=True)
    for j, (nombre, col, v) in enumerate(((_T['luces'], COLOR_ALTAS, pa),
                                          (_T['sombras'], COLOR_BAJAS, pb))):
        x = int(16 * u + (11 + j) * ancho)
        d.rectangle([x, y0, x + int(ancho) - int(6 * u), y0 + int(70 * u)], fill=tuple(int(c * 255) for c in col))
        _texto(d, (x + (ancho - 6 * u) / 2, y0 + int(82 * u)), '%.2f %%' % v, fp, centro=True)
        _texto(d, (x + (ancho - 6 * u) / 2, y0 + int(108 * u)), nombre, ec.fuente(int(15 * u)), centro=True)
        _texto(d, (x + (ancho - 6 * u) / 2, y0 + int(126 * u)), _T['recortadas'], ec.fuente(int(15 * u)),
               centro=True)
    return lienzo


def imagen_contornos(z, Y, titulo, grosor, suavizado=1.0):
    from PIL import Image, ImageDraw
    h, w = z.shape
    base = np.clip(Y, 0, 1) ** (1 / 2.2) * 0.82 + 0.06
    rgb = np.repeat(base[..., None], 3, -1)
    zs = suavizar(z, suavizado * max(1.5, max(h, w) / 700.0))
    zi = np.clip(np.floor(zs + 0.5), 0, 10).astype(int)
    frontera = np.full((h, w), -1)
    dh = zi[:, 1:] != zi[:, :-1]
    frontera[:, 1:][dh] = np.minimum(zi[:, 1:], zi[:, :-1])[dh]
    dv = zi[1:, :] != zi[:-1, :]
    frontera[1:, :][dv] = np.maximum(frontera[1:, :][dv], np.minimum(zi[1:, :], zi[:-1, :])[dv])
    for _ in range(max(0, grosor - 1)):
        f2 = frontera.copy()
        f2[1:] = np.maximum(f2[1:], frontera[:-1])
        f2[:, 1:] = np.maximum(f2[:, 1:], frontera[:, :-1])
        frontera = f2
    m = frontera >= 0
    rgb[m] = LINEAS[np.clip(frontera[m], 0, 9)]
    u = w / 1200.0
    alto_ley = int(110 * u)
    lienzo = Image.new('RGB', (w, h + alto_ley + int(60 * u)), (22, 22, 22))
    lienzo.paste(Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)), (0, int(60 * u)))
    d = ImageDraw.Draw(lienzo)
    _titulo(d, titulo, w, u)
    y0 = h + int(60 * u) + int(24 * u)
    ancho = (w - int(32 * u)) / 10.0
    f = ec.fuente(int(20 * u))
    for k in range(10):
        x = int(16 * u + k * ancho)
        c = tuple(int(v * 255) for v in LINEAS[k])
        d.rectangle([x, y0 + int(14 * u), x + int(ancho) - int(12 * u), y0 + int(22 * u)], fill=c)
        _texto(d, (x + (ancho - 12 * u) / 2, y0 + int(36 * u)), '%s | %s' % (ROMANOS[k], ROMANOS[k + 1]), f,
               centro=True)
    return lienzo


def main():
    ap = argparse.ArgumentParser(description=_T['descripcion'])
    en = IDIOMA == 'en'
    ap.add_argument('entrada', metavar='INPUT' if en else 'ENTRADA', help=_T['h_entrada'])
    ap.add_argument('-o', '--output', '--salida', dest='salida', default=None,
                    metavar='FOLDER' if en else 'CARPETA', help=_T['h_salida'])
    ap.add_argument('--mode', '--modo', dest='modo', default='copia',
                    choices=['print', 'film', 'scene', 'copia', 'pelicula', 'escena'], help=_T['h_modo'])
    ap.add_argument('--reference', '--referencia', dest='referencia', default='trix', help=_T['h_referencia'])
    ap.add_argument('--grey', '--gray', '--gris', dest='gris', type=float, default=0.18, help=_T['h_gris'])
    ap.add_argument('--headroom', '--margen', dest='margen', type=float, default=0.0, help=_T['h_margen'])
    ap.add_argument('--size', '--lado', dest='lado', type=int, default=3000, help=_T['h_lado'])
    ap.add_argument('--smoothing', '--suavizado', dest='suavizado', type=float, default=1.0,
                    help=_T['h_suavizado'])
    ap.add_argument('--space', '--espacio', dest='espacio', choices=['auto'] + list(ec.ESPACIOS),
                    default='auto', help=_T['h_espacio'])
    ap.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    for acc in ap._actions:
        if acc.option_strings and acc.nargs is None and acc.choices is None and acc.dest not in ('help', 'salida'):
            nombres = [o for o in acc.option_strings if o.startswith('--')]
            nombre = nombres[0] if en or len(nombres) < 2 else nombres[-1]
            acc.metavar = nombre.lstrip('-').upper().replace('-', '_')
    a = ap.parse_args()
    a.modo = MODOS_ALIAS.get(a.modo, a.modo)

    enc, _, icc = ec.leer(a.entrada)
    esp = ec.espacio_para(icc, a.espacio)
    enc = reducir(enc, a.lado)
    curva = None
    if a.modo == 'pelicula':
        curva = CurvaCopia(a.referencia)
        titulo = _T['t_pelicula'] % curva.nombre
    elif a.modo == 'copia':
        titulo = _T['t_copia']
    else:
        titulo = _T['t_escena'] % (a.gris * 100)
    z, Y, altas, bajas = analizar(enc, esp, a.modo, curva, a.gris, a.margen)
    pct, pa, pb = porcentajes(z, altas, bajas)

    carpeta = a.salida or os.path.dirname(os.path.abspath(a.entrada))
    os.makedirs(carpeta, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.entrada))[0]
    r_mapa = os.path.join(carpeta, base + '_zones_map.jpg')
    r_cont = os.path.join(carpeta, base + '_zones_contours.jpg')
    grosor = max(1, round(max(z.shape) / 1500))
    imagen_mapa(z, altas, bajas, titulo, pct, pa, pb).save(r_mapa, quality=92)
    imagen_contornos(z, Y, titulo, grosor, a.suavizado).save(r_cont, quality=92)

    print(titulo)
    for k in range(11):
        extra = ''
        if curva is not None:
            Yk = float(curva.luminancia(k))
            extra = _T['en_copia'] % (float(lstar(Yk)), -np.log10(max(Yk, 1e-6)))
        elif a.modo == 'copia':
            Yk = float(lum_desde_lstar(10.0 * k))
            extra = _T['lstar'] % (10 * k, 100 * Yk, -np.log10(max(Yk, 1e-4)))
        print(_T['zona'] % (ROMANOS[k], pct[k], extra))
    print(_T['recortes'] % (pa, pb))
    print(_T['guardado'] % r_mapa)
    print(_T['guardado'] % r_cont)


if __name__ == '__main__':
    main()
