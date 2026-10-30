#!/usr/bin/env python3
"""tira.py: test strip as in the darkroom, with the model of peliculas.py.

Develops the same image several times changing a single parameter and puts the
results side by side in strips across the photo, like the test strip exposed under
the enlarger by covering the sheet step by step, or as a mosaic, one full image per
variant.

Three kinds of strip:

    print       print exposure, from -1 to +1 stop in thirds (Tri-X and PRO 400H).
                More exposure gives a darker print, as under the enlarger.
    grade       Multigrade paper grade, from the 00 filter to 5 (Tri-X only), with the
                exposure balanced so that mid grey stays the same in all of them.
                The grade comes from the ISO R range in Ilford's data sheet.
    exposure    film exposure, from -2 to +2 stops (every film).

The print is rendered with the paper base as white, like a real print, so that the
exposure changes also show in the whites. The input is the same as for the
development: a linear light export (Linear Response in Capture One), with
--headroom if the exposure was lowered when exporting.

Usage:
    python3 tira.py input.tif strip.jpg --film trix --type grade --headroom 2
    python3 tira.py input.tif strip.jpg --film trix --type print --grade 3
    python3 tira.py input.tif strip.jpg --film k64 --type exposure --layout mosaic

Messages, help and the labels of the strip are in English or Spanish (--lang, or
the LANG environment variable). The options and values also have their Spanish
names (--pelicula, --tipo copia|grado|exposicion, --disposicion tiras|mosaico,
--grado, --virado, --margen, --sala, --lado, --espacio).

Needs numpy, Pillow and tifffile, and revelado.py, peliculas.py and espacio_color.py
in the same folder.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import espacio_color as ec  # noqa: E402
import revelado as R  # noqa: E402

IDIOMA = ec.IDIOMA
_T = {
    'en': {
        'descripcion': 'Test strip with the film model.',
        'h_entrada': 'linear light export (Linear Response), preferably 16 bit TIFF in ProPhoto RGB',
        'h_salida': 'strip image (JPEG)',
        'h_pelicula': 'film: k64, k25, velvia50, pro400h or trix',
        'h_tipo': 'what changes from one strip to the next: print (print exposure), '
                  'grade (paper grade) or exposure (film exposure)',
        'h_disposicion': 'strips across the image, or mosaic, one full image per variant',
        'h_grado': 'trix only: fixed paper grade for the print or film strips',
        'h_virado': 'trix only: toning of the print (neutral, cold, warm, sepia, selenium)',
        'h_margen': 'stops by which the exposure was lowered when exporting',
        'h_sala': 'slides only: viewing surround (dark, dim, average)',
        'h_lado': 'long side of the strip in pixels',
        'h_espacio': 'input space if it has no profile (auto = that of the embedded profile)',
        'h_lang': 'language of messages, help and labels: en or es (default: from LANG)',
        'solo_copia': 'The print exposure strip is for Tri-X and PRO 400H.',
        'solo_grado': 'The paper grade strip is for Tri-X only.',
        'grado_trix': '--grade is for Tri-X only.',
        'paso': '%s stop',
        'equilibrada': '0 (balanced)',
        'grado': 'grade %s',
        'pelicula': 'film %s',
        'titulos': {'copia': 'print exposure', 'grado': 'paper grade', 'exposicion': 'film exposure'},
        'titulo': 'Test strip, %s, %s',
        'titulo_grado': ', grade %g',
        'titulo_virado': ', toning %s',
        'guardado': 'Saved %s',
    },
    'es': {
        'descripcion': 'Tira de pruebas con el modelo de película.',
        'h_entrada': 'exportación en luz lineal (Respuesta lineal), mejor TIFF de 16 bits en ProPhoto RGB',
        'h_salida': 'imagen de la tira (JPEG)',
        'h_pelicula': 'película: k64, k25, velvia50, pro400h o trix',
        'h_tipo': 'qué cambia de una banda a otra: copia (exposición de la copia), '
                  'grado (grado del papel) o exposicion (exposición de la película)',
        'h_disposicion': 'bandas sobre la imagen (tiras) o mosaico, una imagen completa por variante',
        'h_grado': 'solo trix: grado de papel fijo para las tiras de copia o de película',
        'h_virado': 'solo trix: virado de la copia (neutro, frio, calido, sepia, selenio)',
        'h_margen': 'pasos que se bajó la exposición al exportar',
        'h_sala': 'solo diapositivas: entorno de visión (oscura, tenue, media)',
        'h_lado': 'lado largo de la tira en píxeles',
        'h_espacio': 'espacio de la entrada si no trae perfil (auto = el del perfil incrustado)',
        'h_lang': 'idioma de los mensajes, la ayuda y las etiquetas: en o es (por defecto, según LANG)',
        'solo_copia': 'La tira de exposición de copia es para Tri-X y PRO 400H.',
        'solo_grado': 'La tira de grados de papel es solo para Tri-X.',
        'grado_trix': '--grado es solo para Tri-X.',
        'paso': '%s paso',
        'equilibrada': '0 (equilibrada)',
        'grado': 'grado %s',
        'pelicula': 'película %s',
        'titulos': {'copia': 'exposición de la copia', 'grado': 'grado del papel',
                    'exposicion': 'exposición de la película'},
        'titulo': 'Tira de pruebas, %s, %s',
        'titulo_grado': ', grado %g',
        'titulo_virado': ', virado %s',
        'guardado': 'Guardado %s',
    },
}[IDIOMA]

ALIAS = dict(R.ALIAS, **{'print': 'copia', 'grade': 'grado', 'exposure': 'exposicion',
                         'exposición': 'exposicion', 'strips': 'tiras', 'bands': 'tiras',
                         'bandas': 'tiras', 'mosaic': 'mosaico'})

TERCIOS = {-1.0: '-1', -2 / 3: '-2/3', -1 / 3: '-1/3', 0.0: '0', 1 / 3: '+1/3', 2 / 3: '+2/3', 1.0: '+1'}
GRADOS = [(-0.5, '00'), (0.0, '0'), (1.0, '1'), (2.0, '2'), (3.0, '3'), (4.0, '4'), (5.0, '5')]


def variantes(tipo, pelicula, grado_base):
    """Lista de (etiqueta, parámetros de Modelo)."""
    if tipo == 'copia':
        if pelicula not in ('trix', 'pro400h'):
            sys.exit(_T['solo_copia'])
        out = []
        for d, et in sorted(TERCIOS.items()):
            # PRINT_STOPS positivo aclara: más exposición de copia es PRINT_STOPS negativo
            out.append((_T['paso'] % et if d else _T['equilibrada'], dict(copia=-d, grado=grado_base)))
        return out
    if tipo == 'grado':
        if pelicula != 'trix':
            sys.exit(_T['solo_grado'])
        return [(_T['grado'] % et, dict(grado=g)) for g, et in GRADOS]
    pasos = [-2, -4 / 3, -2 / 3, 0, 2 / 3, 4 / 3, 2]
    nombres = ['-2', '-1 1/3', '-2/3', '0', '+2/3', '+1 1/3', '+2']
    return [(_T['pelicula'] % nm, dict(ev=p, grado=grado_base)) for p, nm in zip(pasos, nombres)]


def reducir(enc, lado):
    from PIL import Image
    h, w, _ = enc.shape
    if not lado or max(h, w) <= lado:
        return enc
    f = lado / max(h, w)
    nw, nh = max(1, round(w * f)), max(1, round(h * f))
    return np.stack([np.asarray(Image.fromarray(enc[..., c].astype(np.float32), 'F').resize((nw, nh), Image.BOX))
                     for c in range(3)], -1).astype(np.float64)


def a_srgb(enc, esp, modelo):
    """Revela un bloque y lo devuelve en sRGB codificado, para ver la tira en pantalla."""
    srgb = ec.Espacio.predefinido('srgb')
    XYZ = esp.a_xyz(enc.reshape(-1, 3))
    XYZf = modelo.xyz50(XYZ)
    lin = R.compresion_gama(srgb.lineal_desde_xyz(XYZf), srgb.pesos_y)
    return srgb.desde_lineal(lin).reshape(enc.shape)


def _opcion(valor, validos):
    """Pasa un valor de la línea de órdenes a su nombre interno y comprueba que existe."""
    v = ALIAS.get(valor.lower(), valor.lower())
    if v not in validos:
        en = {interno: ingles for ingles, interno in ALIAS.items() if ingles.isascii()}
        lista = ', '.join(sorted({en.get(x, x) for x in validos} | set(validos)))
        raise argparse.ArgumentTypeError('%s: %s' % (valor, lista))
    return v


def main():
    ap = argparse.ArgumentParser(description=_T['descripcion'])
    en = IDIOMA == 'en'
    ap.add_argument('entrada', metavar='INPUT' if en else 'ENTRADA', help=_T['h_entrada'])
    ap.add_argument('salida', metavar='OUTPUT' if en else 'SALIDA', help=_T['h_salida'])
    ap.add_argument('--film', '--pelicula', dest='pelicula', choices=list(R.P.FILMS), default='trix',
                    help=_T['h_pelicula'])
    ap.add_argument('--type', '--tipo', dest='tipo', default='copia', help=_T['h_tipo'])
    ap.add_argument('--layout', '--disposicion', dest='disposicion', default='tiras', help=_T['h_disposicion'])
    ap.add_argument('--grade', '--grado', dest='grado', type=float, default=None, help=_T['h_grado'])
    ap.add_argument('--toning', '--virado', dest='virado', default='neutro', help=_T['h_virado'])
    ap.add_argument('--headroom', '--margen', dest='margen', type=float, default=0.0, help=_T['h_margen'])
    ap.add_argument('--room', '--sala', dest='sala', default='oscura', help=_T['h_sala'])
    ap.add_argument('--size', '--lado', dest='lado', type=int, default=2400, help=_T['h_lado'])
    ap.add_argument('--space', '--espacio', dest='espacio', choices=['auto'] + list(ec.ESPACIOS),
                    default='auto', help=_T['h_espacio'])
    ap.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    for acc in ap._actions:
        if acc.option_strings and acc.nargs is None and acc.choices is None and acc.dest != 'help':
            nombres = [o for o in acc.option_strings if o.startswith('--')]
            nombre = nombres[0] if en or len(nombres) < 2 else nombres[1]
            acc.metavar = nombre.lstrip('-').upper().replace('-', '_')
    a = ap.parse_args()
    try:
        a.tipo = _opcion(a.tipo, ['copia', 'grado', 'exposicion'])
        a.disposicion = _opcion(a.disposicion, ['tiras', 'mosaico'])
        a.virado = _opcion(a.virado, ['neutro', 'frio', 'calido', 'sepia', 'selenio'])
        a.sala = _opcion(a.sala, list(R.P.SALAS))
    except argparse.ArgumentTypeError as e:
        ap.error(str(e))
    if a.grado is not None and a.pelicula != 'trix':
        sys.exit(_T['grado_trix'])

    enc, _, icc = ec.leer(a.entrada)
    esp = ec.espacio_para(icc, a.espacio)
    lista = variantes(a.tipo, a.pelicula, a.grado)
    n = len(lista)
    if a.disposicion == 'mosaico':
        enc = reducir(enc, max(400, a.lado // 3))
    else:
        enc = reducir(enc, a.lado)
    h, w, _ = enc.shape

    piezas = []
    for etiqueta, kw in lista:
        mod = R.Modelo(a.pelicula, virado=a.virado, sala=a.sala, margen=a.margen, blanco='papel', **kw)
        if a.disposicion == 'tiras':
            i = len(piezas)
            x0, x1 = round(i * w / n), round((i + 1) * w / n)
            piezas.append((etiqueta, a_srgb(enc[:, x0:x1], esp, mod)))
        else:
            piezas.append((etiqueta, a_srgb(enc, esp, mod)))
        print('  %s' % etiqueta)

    from PIL import Image, ImageDraw
    nombre = R.P.FILMS[a.pelicula]['nombre']
    if a.pelicula == 'trix' and (a.tipo == 'grado' or a.grado is not None):
        nombre = nombre.replace(' g2', '')
    titulo = _T['titulo'] % (nombre, _T['titulos'][a.tipo])
    if a.grado is not None and a.tipo != 'grado':
        titulo += _T['titulo_grado'] % a.grado
    if a.virado != 'neutro':
        titulo += _T['titulo_virado'] % R._T['nombres'].get(a.virado, a.virado)

    if a.disposicion == 'tiras':
        img = np.concatenate([p for _, p in piezas], axis=1)
        ancho_total, alto_img = img.shape[1], img.shape[0]
        posiciones = []
        x = 0
        for _, p in piezas:
            posiciones.append((x, p.shape[1]))
            x += p.shape[1]
    else:
        cols = 4 if n > 6 else 3
        filas = int(np.ceil(n / cols))
        sep = max(8, w // 60)
        ancho_total = cols * w + (cols - 1) * sep
        alto_img = filas * (h + int(0.09 * h) + sep)
        img = None

    u = ancho_total / 1600.0
    cab, pie = int(70 * u), int(64 * u)
    lienzo = Image.new('RGB', (ancho_total, alto_img + cab + (pie if a.disposicion == 'tiras' else 0)), (22, 22, 22))
    d = ImageDraw.Draw(lienzo)
    d.text((int(16 * u), int(20 * u)), titulo, fill=(235, 235, 235), font=ec.fuente(int(28 * u)))
    f = ec.fuente(int(22 * u))
    if a.disposicion == 'tiras':
        lienzo.paste(Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)), (0, cab))
        for (x, ancho), (etiqueta, _) in zip(posiciones, piezas):
            if x > 0:
                d.line([x, cab, x, cab + alto_img], fill=(22, 22, 22), width=max(1, int(2 * u)))
            try:
                tw = d.textbbox((0, 0), etiqueta, font=f)[2]
            except AttributeError:
                tw = len(etiqueta) * 11 * u
            d.text((x + (ancho - tw) / 2, cab + alto_img + int(18 * u)), etiqueta, fill=(225, 225, 225), font=f)
    else:
        sep = max(8, w // 60)
        for i, (etiqueta, p) in enumerate(piezas):
            c, r = i % cols, i // cols
            x = c * (w + sep)
            y = cab + r * (h + int(0.09 * h) + sep)
            lienzo.paste(Image.fromarray((np.clip(p, 0, 1) * 255 + 0.5).astype(np.uint8)), (x, y))
            d.text((x + int(8 * u), y + h + int(8 * u)), etiqueta, fill=(225, 225, 225), font=f)
    lienzo.save(a.salida, quality=93)
    print(_T['guardado'] % a.salida)


if __name__ == '__main__':
    main()
