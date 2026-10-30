#!/usr/bin/env python3
"""curva_parametrica.py: tone curve by regions, in the style of Lightroom.

Four sliders, from -100 to +100, act on four regions of the tonal axis
separated by three adjustable splits (25, 50 and 75 by default): shadows,
darks, lights and highlights. Each slider pushes the curve up (lighter) or down
(darker) with a smooth bell that covers its region and overlaps its neighbours
by up to half its width, so the regions blend without steps. Black and white
stay fixed.

The resulting curve is y(x) = x + sum of a_k B_k(x), where B_k is a raised
cosine bell that is zero at the ends of its support and a_k is proportional to
the slider and to the width of the support. If the combination of sliders made
the curve decreasing somewhere (tone inversion), the amplitude of all the bells
is reduced equally until the minimum slope is 0.05; the script says so.

Usage:
    python3 curva_parametrica.py points --highlights -30 --shadows 30
    python3 curva_parametrica.py points --lights 15 --darks -15 --splits 20,45,70
    python3 curva_parametrica.py graph curve.png --lights 15 --darks -15

'points' prints the points (brightness, amount) from 0 to 100 for the Capture
One curve, at the ends, the splits and the centre of each region. 'graph' draws
the curve with its regions.

Messages and help are shown in English or Spanish (--lang, or the LANG
environment variable). The commands and options also have their Spanish names
(puntos, grafico; --luces, --claros, --oscuros, --sombras, --divisiones).

Only needs numpy (and Pillow for the graph).
"""
import os
import argparse
import sys

import numpy as np

AMPLITUD = 0.50          # desplazamiento máximo a +100, en fracción de la anchura del soporte
PENDIENTE_MINIMA = 0.05
NOMBRES = ['sombras', 'oscuros', 'claros', 'luces']
OPCIONES_EN = {'sombras': 'shadows', 'oscuros': 'darks', 'claros': 'lights', 'luces': 'highlights'}
ORDENES = {'points': 'puntos', 'graph': 'grafico', 'gráfico': 'grafico'}


def _idioma():
    """'en' o 'es': --lang/--idioma en la línea de órdenes; si no, LC_ALL, LC_MESSAGES o LANG."""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        for clave in ('--lang', '--idioma'):
            if a == clave and i + 1 < len(argv):
                return 'es' if argv[i + 1].lower().startswith('es') else 'en'
            if a.startswith(clave + '='):
                return 'es' if a.split('=', 1)[1].lower().startswith('es') else 'en'
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
        v = os.environ.get(var)
        if v:
            return 'es' if v.lower().startswith('es') else 'en'
    return 'en'


IDIOMA = _idioma()
_T = {
    'en': {
        'descripcion': 'Tone curve by regions.',
        'h_orden': 'points: print the curve points for Capture One; graph: draw the curve in a PNG file',
        'h_salida': 'graph only: PNG file',
        'h_region': 'from -100 to 100',
        'h_divisiones': 'the three splits between regions, from 0 to 100, in increasing order',
        'h_lang': 'language of messages and help: en or es (default: from LANG)',
        'divisiones_mal': '--splits must have three increasing values between 0 and 100, for example 25,50,75',
        'falta_png': 'the PNG file is missing',
        'aviso': 'warning: the combination inverted tones; amplitudes reduced to %.0f %%',
        'etiquetas': {'sombras': 'shadows', 'oscuros': 'darks', 'claros': 'lights', 'luces': 'highlights'},
    },
    'es': {
        'descripcion': 'Curva de tonos por regiones.',
        'h_orden': 'puntos: imprime los puntos de la curva para Capture One; grafico: dibuja la curva en un PNG',
        'h_salida': 'solo grafico: archivo PNG',
        'h_region': 'de -100 a 100',
        'h_divisiones': 'las tres divisiones entre regiones, de 0 a 100, en orden creciente',
        'h_lang': 'idioma de los mensajes y de la ayuda: en o es (por defecto, según LANG)',
        'divisiones_mal': '--divisiones debe tener tres valores crecientes entre 0 y 100, por ejemplo 25,50,75',
        'falta_png': 'falta el archivo PNG',
        'aviso': 'aviso: la combinación invertía tonos; amplitudes reducidas al %.0f %%',
        'etiquetas': {},
    },
}[IDIOMA]


def soportes(divisiones):
    b = [0.0] + [d / 100.0 for d in divisiones] + [1.0]
    sop = []
    for k in range(4):
        w = b[k + 1] - b[k]
        sop.append((max(0.0, b[k] - w / 2), min(1.0, b[k + 1] + w / 2)))
    return b, sop


def campana(x, a, b):
    t = np.clip((x - a) / max(b - a, 1e-9), 0, 1)
    return 0.5 * (1 - np.cos(2 * np.pi * t)) * ((x > a) & (x < b))


def curva(x, valores, divisiones, escala=1.0):
    _, sop = soportes(divisiones)
    y = np.array(x, float)
    for v, (a, b) in zip(valores, sop):
        y = y + escala * (v / 100.0) * AMPLITUD * (b - a) * campana(x, a, b)
    return y


def escala_monotona(valores, divisiones):
    """Mayor factor <= 1 que deja la curva con pendiente >= PENDIENTE_MINIMA."""
    x = np.linspace(0, 1, 4001)
    lo, hi = 0.0, 1.0
    if np.diff(curva(x, valores, divisiones, 1.0)).min() / (x[1] - x[0]) >= PENDIENTE_MINIMA:
        return 1.0
    for _ in range(40):
        m = 0.5 * (lo + hi)
        if np.diff(curva(x, valores, divisiones, m)).min() / (x[1] - x[0]) >= PENDIENTE_MINIMA:
            lo = m
        else:
            hi = m
    return lo


def puntos(valores, divisiones):
    b, _ = soportes(divisiones)
    xs = [0.0]
    for k in range(4):
        xs += [0.5 * (b[k] + b[k + 1]), b[k + 1]]
    esc = escala_monotona(valores, divisiones)
    ys = np.clip(curva(np.array(xs), valores, divisiones, esc), 0, 1)
    ys[0], ys[-1] = 0.0, 1.0
    return [(100 * x, 100 * float(y)) for x, y in zip(xs, ys)], esc


def grafico(ruta, valores, divisiones):
    from PIL import Image, ImageDraw
    n = 600
    m = 50
    im = Image.new('RGB', (n + 2 * m, n + 2 * m), (24, 24, 24))
    d = ImageDraw.Draw(im)
    b, _ = soportes(divisiones)
    grises = [(40, 40, 40), (52, 52, 52)]
    for k in range(4):
        d.rectangle([m + b[k] * n, m, m + b[k + 1] * n, m + n], fill=grises[k % 2])
    d.line([m, m + n, m + n, m], fill=(90, 90, 90), width=1)
    esc = escala_monotona(valores, divisiones)
    x = np.linspace(0, 1, 600)
    y = curva(x, valores, divisiones, esc)
    pts = [(m + xi * n, m + n - yi * n) for xi, yi in zip(x, y)]
    d.line(pts, fill=(235, 235, 235), width=3)
    for (px, py) in puntos(valores, divisiones)[0]:
        cx, cy = m + px / 100 * n, m + n - py / 100 * n
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(255, 200, 0), width=2)
    for k, nombre in enumerate(NOMBRES):
        d.text((m + 0.5 * (b[k] + b[k + 1]) * n - 22, m + n + 14), '%s %+d' % (_T['etiquetas'].get(nombre, nombre), valores[k]),
               fill=(220, 220, 220))
    im.save(ruta)
    return esc


def main():
    en = IDIOMA == 'en'
    ap = argparse.ArgumentParser(description=_T['descripcion'])
    ap.add_argument('orden', choices=['points', 'graph', 'puntos', 'grafico'],
                    metavar='{points,graph}' if en else '{puntos,grafico}', help=_T['h_orden'])
    ap.add_argument('salida', nargs='?', metavar='PNG', help=_T['h_salida'])
    for nombre in reversed(NOMBRES):
        ap.add_argument('--' + OPCIONES_EN[nombre], '--' + nombre, dest=nombre, type=float, default=0.0,
                        metavar='V', help=_T['h_region'])
    ap.add_argument('--splits', '--divisiones', dest='divisiones', default='25,50,75',
                    metavar='D1,D2,D3', help=_T['h_divisiones'])
    ap.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    a = ap.parse_args()
    a.orden = ORDENES.get(a.orden, a.orden)
    try:
        div = [float(v) for v in a.divisiones.split(',')]
        assert len(div) == 3 and 0 < div[0] < div[1] < div[2] < 100
    except (ValueError, AssertionError):
        sys.exit(_T['divisiones_mal'])
    valores = [float(np.clip(getattr(a, nm), -100, 100)) for nm in NOMBRES]

    if a.orden == 'grafico':
        if not a.salida:
            ap.error(_T['falta_png'])
        esc = grafico(a.salida, valores, div)
    else:
        pts, esc = puntos(valores, div)
        for x, y in pts:
            print('%.3f,%.3f' % (x, y))
    if esc < 1.0:
        print(_T['aviso'] % (100 * esc), file=sys.stderr)


if __name__ == '__main__':
    main()
