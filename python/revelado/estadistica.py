#!/usr/bin/env python3
"""estadistica.py: which photos you end up keeping.

Reads the metadata table written by the Capture One script (one row per image,
tab separated) and crosses each variable with the rating. A photo counts as
chosen if it has at least --threshold stars (4 by default; if none reaches it,
the threshold is lowered until there are chosen photos).

For each value of each variable (focal length, aperture, exposure time, ISO,
hour, month, day of the week, crop ratio, black and white, profile, camera) it
computes the selection rate, that is, the fraction of the photos with that value
that ended up chosen, with its 95 % Wilson confidence interval, and compares it
with the rate of the whole set. Since many values are compared at once, a few
would come out different by pure chance; for the list of what stands out, the p
value of each comparison is computed (binomial test with the normal
approximation) and the Benjamini-Hochberg procedure is applied, which keeps the
expected proportion of false discoveries below 5 %. In the charts, the colour
shows whether the Wilson interval lies entirely above or below.

The result is a self-contained HTML report, with a chart per variable and a list
of what stands out.

Usage:
    python3 estadistica.py metadata.tsv report.html
    python3 estadistica.py metadata.tsv report.html --threshold 5

The report and the messages are in English or Spanish (--lang, or the LANG
environment variable). The options also have their Spanish names (--umbral,
--minimo, --origen). The column names of the table are fixed and stay in Spanish
(nombre, valoracion, etiqueta, fecha, focal, diafragma, velocidad, iso, camara,
ancho_recorte, alto_recorte, ancho, alto, bn, perfil).

Only needs the standard library.
"""
import argparse
import csv
import html
import math
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime


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
        'dias': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        'meses': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                  'September', 'October', 'November', 'December'],
        'tiempos': ['faster than 1/500', '1/500 to 1/125', '1/125 to 1/30', '1/30 to 1/8', '1/8 to 1 s',
                    '1 to 4 s', '4 to 30 s', '30 s or longer'],
        'iso_menos': '100 or less', 'iso_mas': 'over 3200',
        'horizontal': 'horizontal', 'vertical': 'vertical', 'cuadrada': 'square',
        'panoramica': 'panoramic %s', 'otra': 'other %s',
        'sin_dato': 'no data', 'perfil_camara': 'camera profile',
        'bn': 'black and white', 'color': 'colour',
        'variables': ['Focal length', 'Aperture', 'Exposure time', 'ISO', 'Hour of the day', 'Month',
                      'Day of the week', 'Year', 'Crop ratio', 'Colour or black and white', 'Film profile',
                      'Camera'],
        'pct': '%.0f%%',
        'barra': '%s: %d photos',
        'punto': '%s: %d of %d chosen (%.0f%%, interval %.0f to %.0f%%)',
        'estrella': 'star', 'estrellas': 'stars',
        'titulo': 'Your way of seeing',
        'sub': 'Which photos you end up keeping, according to %s. A photo counts as chosen if it has %d %s or more.',
        'analizadas': 'photos analysed', 'elegidas': 'chosen', 'tasa': 'selection rate', 'periodo': 'period',
        'de_a': '%s to %s',
        'destaca': 'What stands out',
        'nada': 'No value separates from the overall rate with enough certainty. '
                'With more photos or a different threshold something may show up.',
        'nota': 'Values with at least %d photos are considered, and those listed remain different from the '
                'overall rate after correcting for the number of comparisons (Benjamini-Hochberg, with an '
                'expected proportion of false discoveries of 5%%). A value that stands out shows an association '
                'in your photos and leaves the cause open: focal length and hour, for example, tend to go hand '
                'in hand with the kind of outing.',
        'ley_n': 'number of photos', 'ley_alto': 'above the whole set', 'ley_bajo': 'below',
        'ley_neutro': 'no clear difference', 'ley_poco': 'fewer than %d photos',
        'ley_linea': 'dashed line: overall rate',
        'con_dato': '%d photos with this data.',
        'descripcion': 'Which photos you end up keeping.',
        'h_entrada': 'tab-separated metadata table',
        'h_salida': 'HTML report',
        'h_umbral': 'minimum stars to count as chosen',
        'h_minimo': 'minimum photos to flag a value (by default, 2 %% of the total and at least 12)',
        'h_origen': 'where the photos come from, as said in the report',
        'h_lang': 'language of the report and the messages: en or es (default: from LANG)',
        'origen': 'your Capture One catalogue',
        'vacia': 'The table is empty.',
        'sin_valoracion': 'No photo has a rating, so there are no chosen photos to compare with.',
        'aviso': 'warning: no photo reached %d stars; using %d',
        'resumen': '%d photos, %d chosen (%d stars or more). Report in %s',
    },
    'es': {
        'dias': ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'],
        'meses': ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                  'septiembre', 'octubre', 'noviembre', 'diciembre'],
        'tiempos': ['más rápido que 1/500', '1/500 a 1/125', '1/125 a 1/30', '1/30 a 1/8', '1/8 a 1 s',
                    '1 a 4 s', '4 a 30 s', '30 s o más'],
        'iso_menos': '100 o menos', 'iso_mas': 'más de 3200',
        'horizontal': 'horizontal', 'vertical': 'vertical', 'cuadrada': 'cuadrada',
        'panoramica': 'panorámica %s', 'otra': 'otra %s',
        'sin_dato': 'sin dato', 'perfil_camara': 'perfil de cámara',
        'bn': 'blanco y negro', 'color': 'color',
        'variables': ['Focal', 'Diafragma', 'Tiempo de exposición', 'ISO', 'Hora del día', 'Mes',
                      'Día de la semana', 'Año', 'Proporción del recorte', 'Color o blanco y negro',
                      'Perfil de película', 'Cámara'],
        'pct': '%.0f %%',
        'barra': '%s: %d fotos',
        'punto': '%s: %d de %d elegidas (%.0f %%, intervalo %.0f a %.0f %%)',
        'estrella': 'estrella', 'estrellas': 'estrellas',
        'titulo': 'Tu forma de mirar',
        'sub': 'Qué fotos acabas guardando, según %s. Una foto cuenta como elegida si tiene %d %s o más.',
        'analizadas': 'fotos analizadas', 'elegidas': 'elegidas', 'tasa': 'tasa de selección', 'periodo': 'periodo',
        'de_a': '%s a %s',
        'destaca': 'Lo que destaca',
        'nada': 'Ningún valor se separa de la tasa del conjunto con suficiente seguridad. '
                'Con más fotos o un umbral distinto puede aparecer algo.',
        'nota': 'Se consideran los valores con al menos %d fotos, y se señalan los que siguen siendo '
                'distintos de la tasa del conjunto después de corregir por el número de comparaciones (Benjamini y '
                'Hochberg, con una proporción esperada de falsos descubrimientos del 5 %%). Que un valor destaque '
                'indica una asociación en tus fotos y deja abierta la causa: la focal y la hora, por ejemplo, suelen ir '
                'de la mano del tipo de salida.',
        'ley_n': 'número de fotos', 'ley_alto': 'por encima del conjunto', 'ley_bajo': 'por debajo',
        'ley_neutro': 'sin diferencia clara', 'ley_poco': 'menos de %d fotos',
        'ley_linea': 'línea discontinua: tasa del conjunto',
        'con_dato': '%d fotos con este dato.',
        'descripcion': 'Qué fotos acabas guardando.',
        'h_entrada': 'tabla de metadatos separada por tabuladores',
        'h_salida': 'informe HTML',
        'h_umbral': 'estrellas mínimas para contar como elegida',
        'h_minimo': 'fotos mínimas para señalar un valor (por defecto, el 2 %% del total y al menos 12)',
        'h_origen': 'de dónde salen las fotos, tal como lo dice el informe',
        'h_lang': 'idioma del informe y de los mensajes: en o es (por defecto, según LANG)',
        'origen': 'tu catálogo de Capture One',
        'vacia': 'La tabla está vacía.',
        'sin_valoracion': 'Ninguna foto tiene valoración, así que no hay elegidas con las que comparar.',
        'aviso': 'aviso: ninguna foto llegaba a %d estrellas; uso %d',
        'resumen': '%d fotos, %d elegidas (%d estrellas o más). Informe en %s',
    },
}[IDIOMA]

DIAS = _T['dias']
MESES = _T['meses']
DIAFRAGMAS = [0.95, 1.0, 1.2, 1.4, 1.7, 2.0, 2.4, 2.8, 3.4, 4.0, 4.8, 5.6, 6.7, 8.0, 9.5, 11, 13, 16, 19, 22]
PELICULAS = ['Kodachrome 64', 'Kodachrome 25', 'Velvia', 'Tri-X', 'TriX', 'PRO 400H', 'Pro400H']


# ---------------------------------------------------------------- lectura y limpieza

def numero(texto):
    if texto is None:
        return None
    t = str(texto).replace(',', '.')
    m = re.search(r'-?\d+(?:\.\d+)?', t)
    return float(m.group()) if m else None


def tiempo_exposicion(texto):
    """'1/125', '1/125 s', '30', '2.5 s', '30"' -> segundos."""
    if not texto:
        return None
    t = str(texto).replace(',', '.').replace('"', '').strip()
    m = re.search(r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)', t)
    if m:
        d = float(m.group(2))
        return float(m.group(1)) / d if d else None
    return numero(t)


def fecha(texto):
    if not texto:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y:%m:%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(texto.strip(), fmt)
        except ValueError:
            continue
    return None


def leer(ruta):
    with open(ruta, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


# ---------------------------------------------------------------- variables

def tramo_tiempo(s):
    if s is None:
        return None
    for i, limite in enumerate((1 / 500, 1 / 125, 1 / 30, 1 / 8, 1, 4, 30)):
        if s < limite:
            return ORDEN_TIEMPO[i]
    return ORDEN_TIEMPO[-1]


ORDEN_TIEMPO = _T['tiempos']


def tramo_iso(v):
    if v is None:
        return None
    for lim, nombre in ((100, _T['iso_menos']), (200, '200'), (400, '400'), (800, '800'), (1600, '1600'),
                        (3200, '3200')):
        if v <= lim * 1.19:
            return nombre
    return _T['iso_mas']


ORDEN_ISO = [_T['iso_menos'], '200', '400', '800', '1600', '3200', _T['iso_mas']]


def tramo_diafragma(v):
    if v is None or v <= 0:
        return None
    mejor = min(DIAFRAGMAS, key=lambda d: abs(math.log(v / d)))
    completos = [1.0, 1.4, 2.0, 2.8, 4.0, 5.6, 8.0, 11, 16, 22]
    pleno = min(completos, key=lambda d: abs(math.log(mejor / d)))
    return 'f/%g' % pleno


def proporcion(w, h):
    if not w or not h or w <= 0 or h <= 0:
        return None
    r = max(w, h) / min(w, h)
    orient = _T['horizontal'] if w > h else _T['vertical']
    if r < 1.04:
        return _T['cuadrada']
    for valor, nombre in ((1.25, '4:5'), (4 / 3, '3:4'), (1.5, '2:3'), (16 / 9, '16:9'), (2.0, '1:2')):
        if abs(r / valor - 1) < 0.035:
            return '%s %s' % (nombre, orient)
    if r > 2.1:
        return _T['panoramica'] % orient
    return _T['otra'] % orient


def perfil_pelicula(p):
    if not p:
        return _T['sin_dato']
    for nombre in PELICULAS:
        if nombre.lower() in p.lower():
            return nombre.replace('TriX', 'Tri-X').replace('Pro400H', 'PRO 400H')
    return _T['perfil_camara']


def preparar(filas):
    datos = []
    for f in filas:
        d = {}
        d['valoracion'] = int(numero(f.get('valoracion')) or 0)
        d['etiqueta'] = f.get('etiqueta', '')
        fl = numero(f.get('focal'))
        d['focal'] = ('%d mm' % round(fl)) if fl else None
        d['diafragma'] = tramo_diafragma(numero(f.get('diafragma')))
        d['tiempo'] = tramo_tiempo(tiempo_exposicion(f.get('velocidad')))
        d['iso'] = tramo_iso(numero(f.get('iso')))
        fe = fecha(f.get('fecha'))
        d['hora'] = ('%02d h' % fe.hour) if fe else None
        d['mes'] = MESES[fe.month - 1] if fe else None
        d['dia'] = DIAS[fe.weekday()] if fe else None
        d['anio'] = str(fe.year) if fe else None
        w, h = numero(f.get('ancho_recorte')), numero(f.get('alto_recorte'))
        if not w or not h:
            w, h = numero(f.get('ancho')), numero(f.get('alto'))
        d['proporcion'] = proporcion(w, h)
        bn = (f.get('bn') or '').strip().lower()
        d['bn'] = _T['bn'] if bn in ('true', 'verdadero', '1', 'yes', 'sí', 'si') else (_T['color'] if bn else None)
        d['perfil'] = perfil_pelicula(f.get('perfil'))
        d['camara'] = (f.get('camara') or '').strip() or None
        datos.append(d)
    return datos


VARIABLES = OrderedDict(zip(
    ['focal', 'diafragma', 'tiempo', 'iso', 'hora', 'mes', 'dia', 'anio', 'proporcion', 'bn', 'perfil', 'camara'],
    zip(_T['variables'], [None, None, ORDEN_TIEMPO, ORDEN_ISO, None, MESES, DIAS, None, None, None, None, None])))


def clave_orden(v):
    n = numero(v)
    return (0, n, v) if n is not None else (1, 0, v)


# ---------------------------------------------------------------- estadística

def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    medio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centro - medio), min(1.0, centro + medio)


def tabla(datos, var, umbral, orden=None):
    cuentas = {}
    for d in datos:
        v = d.get(var)
        if v is None:
            continue
        n, k = cuentas.get(v, (0, 0))
        cuentas[v] = (n + 1, k + (1 if d['valoracion'] >= umbral else 0))
    if orden:
        claves = [c for c in orden if c in cuentas] + sorted([c for c in cuentas if c not in orden], key=clave_orden)
    else:
        claves = sorted(cuentas, key=clave_orden)
    return [(c,) + cuentas[c] + wilson(cuentas[c][1], cuentas[c][0]) for c in claves]


def valor_p(k, n, p0):
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 1.0
    z = (abs(k - n * p0) - 0.5) / math.sqrt(n * p0 * (1 - p0))
    return math.erfc(max(z, 0.0) / math.sqrt(2))


def hallazgos(datos, umbral, tasa, n_min, q=0.05):
    candidatos = []
    for var, (nombre, orden) in VARIABLES.items():
        if len(set(d.get(var) for d in datos if d.get(var))) < 2:
            continue
        for valor, n, k, p, lo, hi in tabla(datos, var, umbral, orden):
            if n < n_min:
                continue
            candidatos.append((valor_p(k, n, tasa), var, nombre, valor, n, k, p))
    # Benjamini y Hochberg
    candidatos.sort(key=lambda c: c[0])
    m = len(candidatos)
    corte = 0
    for i, c in enumerate(candidatos, 1):
        if c[0] <= q * i / m:
            corte = i
    out = []
    for pv, var, nombre, valor, n, k, p in candidatos[:corte]:
        sentido = 'arriba' if p > tasa else 'abajo'
        out.append((math.log(max(p, 1e-4) / tasa), var, nombre, valor, n, k, p, sentido))
    out.sort(key=lambda t: -abs(t[0]))
    return out[:10]


def _sujeto_es(var, valor):
    if var == 'focal':
        return 'Con el %s' % valor
    if var == 'diafragma':
        return 'A %s' % valor
    if var == 'tiempo':
        return ('Con exposiciones de %s' % valor) if not valor.startswith('más') else 'Con tiempos %s' % valor
    if var == 'iso':
        return 'A ISO %s' % valor
    if var == 'hora':
        return 'A las %s' % valor.replace(' h', ':00')
    if var == 'mes':
        return 'En %s' % valor
    if var == 'dia':
        return 'Los %s' % (valor if valor.endswith('s') else valor + 's')
    if var == 'anio':
        return 'En %s' % valor
    if var == 'proporcion':
        return 'Con recorte %s' % valor
    if var == 'bn':
        return 'En %s' % valor
    if var == 'perfil':
        return 'Con %s' % ('el perfil de cámara' if valor == 'perfil de cámara' else 'el perfil %s' % valor)
    if var == 'camara':
        return 'Con la %s' % valor
    return valor


def _frase_es(h, tasa, umbral):
    _, var, nombre, valor, n, k, p, sentido = h
    estrellas = 'estrella' if umbral == 1 else 'estrellas'
    cociente = p / tasa if tasa else 0
    quien = _sujeto_es(var, valor)
    if sentido == 'arriba':
        cuanto = ('el doble' if 1.8 <= cociente < 2.3 else 'el triple' if 2.7 <= cociente < 3.4
                  else '%.1f veces más' % cociente).replace('.', ',')
        return ('%s, el %.0f %% de las fotos acaba con %d %s o más, frente al %.0f %% del conjunto, %s (%d de %d).'
                % (quien, 100 * p, umbral, estrellas, 100 * tasa, cuanto, k, n))
    return ('%s solo el %.0f %% de las fotos acaba con %d %s o más, frente al %.0f %% del conjunto (%d de %d).'
            % (quien, 100 * p, umbral, estrellas, 100 * tasa, k, n))


def _sujeto_en(var, valor):
    if var in ('focal', 'diafragma'):
        return 'At %s' % valor
    if var == 'tiempo':
        return 'With exposures %s' % valor if valor.startswith('faster') else 'With exposures of %s' % valor
    if var == 'iso':
        return 'At ISO %s' % valor
    if var == 'hora':
        return 'At %s' % valor.replace(' h', ':00')
    if var in ('mes', 'anio', 'bn'):
        return 'In %s' % valor
    if var == 'dia':
        return 'On %ss' % valor
    if var == 'proporcion':
        return 'With %s crops' % valor
    if var == 'perfil':
        return 'With %s' % ('the camera profile' if valor == 'camera profile' else 'the %s profile' % valor)
    if var == 'camara':
        return 'With the %s' % valor
    return valor


def _frase_en(h, tasa, umbral):
    _, var, nombre, valor, n, k, p, sentido = h
    estrellas = 'star' if umbral == 1 else 'stars'
    cociente = p / tasa if tasa else 0
    quien = _sujeto_en(var, valor)
    if sentido == 'arriba':
        cuanto = ('twice the overall rate' if 1.8 <= cociente < 2.3 else 'three times the overall rate'
                  if 2.7 <= cociente < 3.4 else '%.1f times the overall rate' % cociente)
        return ('%s, %.0f%% of the photos end up with %d %s or more, against %.0f%% of the whole set, %s (%d of %d).'
                % (quien, 100 * p, umbral, estrellas, 100 * tasa, cuanto, k, n))
    return ('%s, only %.0f%% of the photos end up with %d %s or more, against %.0f%% of the whole set (%d of %d).'
            % (quien, 100 * p, umbral, estrellas, 100 * tasa, k, n))


frase = _frase_en if IDIOMA == 'en' else _frase_es


# ---------------------------------------------------------------- gráficos SVG

def grafico(filas, tasa, n_min):
    """Barras grises con el número de fotos y, encima, la tasa de selección con su
    intervalo de Wilson; la línea discontinua es la tasa del conjunto."""
    m = len(filas)
    ancho_barra = 50
    ancho = max(420, 70 + m * ancho_barra)
    alto, base, arriba = 300, 230, 24
    nmax = max(f[1] for f in filas)
    pmax = max(0.05, min(1.0, max(max(f[5] for f in filas), tasa) * 1.15))
    escala_p = lambda p: base - (base - arriba) * p / pmax
    partes = ['<svg viewBox="0 0 %d %d" role="img" class="g" style="max-width:%dpx">' % (ancho, alto, ancho)]
    # rejilla de porcentajes
    for i in range(5):
        p = pmax * i / 4
        y = escala_p(p)
        partes.append('<line x1="56" y1="%.1f" x2="%d" y2="%.1f" class="rej"/>' % (y, ancho - 8, y))
        partes.append(('<text x="50" y="%.1f" class="eje" text-anchor="end">' + _T['pct'] + '</text>') % (y + 4, 100 * p))
    yt = escala_p(tasa)
    partes.append('<line x1="56" y1="%.1f" x2="%d" y2="%.1f" class="tasa"/>' % (yt, ancho - 8, yt))
    for i, (valor, n, k, p, lo, hi) in enumerate(filas):
        x = 64 + i * ancho_barra
        hb = (base - arriba) * 0.45 * n / nmax
        partes.append(('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" class="barra"><title>' + _T['barra'] + '</title></rect>')
                      % (x, base - hb, ancho_barra - 10, hb, html.escape(valor), n))
        cx = x + (ancho_barra - 10) / 2
        poco = n < n_min
        clase = 'punto poco' if poco else ('punto alto' if lo > tasa else 'punto bajo' if hi < tasa else 'punto')
        partes.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="ic"/>' % (cx, escala_p(lo), cx, escala_p(hi)))
        partes.append(('<circle cx="%.1f" cy="%.1f" r="5" class="%s"><title>' + _T['punto'] + '</title></circle>')
                      % (cx, escala_p(p), clase, html.escape(valor), k, n, 100 * p, 100 * lo, 100 * hi))
        etiqueta = valor if len(valor) <= 12 else valor[:11] + '…'
        partes.append('<text x="%.1f" y="%d" class="eje" text-anchor="end" transform="rotate(-40 %.1f %d)">%s</text>'
                      % (cx + 4, base + 16, cx + 4, base + 16, html.escape(etiqueta)))
        partes.append('<text x="%.1f" y="%.1f" class="n" text-anchor="middle">%d</text>' % (cx, base - hb - 4, n))
    partes.append('</svg>')
    return '\n'.join(partes)


ESTILO = """
:root { --fondo:#f6f5f2; --texto:#1f1f1f; --suave:#6b6b6b; --rejilla:#e2e0db; --barra:#d6d3cc;
        --alto:#1f7a5c; --bajo:#b0413e; --neutro:#3a3a3a; --tarjeta:#ffffff; }
@media (prefers-color-scheme: dark) {
  :root { --fondo:#161616; --texto:#ecebe8; --suave:#9a9a9a; --rejilla:#2b2b2b; --barra:#3a3a3a;
          --alto:#4fbf94; --bajo:#e07a74; --neutro:#cfcfcf; --tarjeta:#1f1f1f; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--fondo); color:var(--texto);
       font:16px/1.55 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; }
main { max-width:980px; margin:0 auto; padding:40px 16px 80px; }
h1 { font-size:30px; margin:0 0 6px; font-weight:600; letter-spacing:-0.01em; }
h2 { font-size:19px; margin:42px 0 4px; font-weight:600; }
.sub { color:var(--suave); margin:0 0 28px; }
.cifras { display:flex; flex-wrap:wrap; gap:12px; margin:18px 0 8px; }
.cifra { background:var(--tarjeta); border-radius:10px; padding:12px 16px; min-width:150px; }
.cifra b { display:block; font-size:24px; font-weight:600; }
.cifra span { color:var(--suave); font-size:13px; }
ul.h { padding-left:20px; } ul.h li { margin:6px 0; }
.nota { color:var(--suave); font-size:14px; }
.g { width:100%; height:auto; background:var(--tarjeta); border-radius:10px; margin-top:8px; }
.g .rej { stroke:var(--rejilla); stroke-width:1; }
.g .tasa { stroke:var(--suave); stroke-dasharray:5 4; stroke-width:1.2; }
.g .barra { fill:var(--barra); }
.g .ic { stroke:var(--neutro); stroke-width:1.5; }
.g .punto { fill:var(--neutro); } .g .alto { fill:var(--alto); } .g .bajo { fill:var(--bajo); }
.g .poco { fill:none; stroke:var(--suave); stroke-width:1.5; }
.g .eje { fill:var(--suave); font-size:11px; } .g .n { fill:var(--suave); font-size:10px; }
.leyenda span { display:inline-block; margin-right:16px; }
.leyenda i { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:-1px; }
"""


def informe(datos, umbral, n_min, origen):
    n = len(datos)
    elegidas = sum(1 for d in datos if d['valoracion'] >= umbral)
    tasa = elegidas / n if n else 0
    fechas = sorted(d['anio'] for d in datos if d['anio'])
    estrellas = _T['estrella'] if umbral == 1 else _T['estrellas']
    coma = (lambda x: x.replace('.', ',')) if IDIOMA == 'es' else (lambda x: x)  # noqa: E731
    h = hallazgos(datos, umbral, tasa, n_min)

    trozos = ['<!doctype html><html lang="%s"><head><meta charset="utf-8">' % IDIOMA,
              '<meta name="viewport" content="width=device-width, initial-scale=1">',
              '<title>%s</title><style>%s</style></head><body><main>' % (_T['titulo'], ESTILO),
              '<h1>%s</h1>' % _T['titulo'],
              '<p class="sub">%s</p>' % (_T['sub'] % (html.escape(origen), umbral, estrellas)),
              '<div class="cifras">',
              '<div class="cifra"><b>%d</b><span>%s</span></div>' % (n, _T['analizadas']),
              '<div class="cifra"><b>%d</b><span>%s</span></div>' % (elegidas, _T['elegidas']),
              '<div class="cifra"><b>%s</b><span>%s</span></div>'
              % (coma(_T['pct'].replace('.0f', '.1f') % (100 * tasa)), _T['tasa'])]
    if fechas:
        trozos.append('<div class="cifra"><b>%s</b><span>%s</span></div>'
                      % (fechas[0] if fechas[0] == fechas[-1] else _T['de_a'] % (fechas[0], fechas[-1]), _T['periodo']))
    trozos.append('</div>')

    trozos.append('<h2>%s</h2>' % _T['destaca'])
    if h:
        trozos.append('<ul class="h">' + ''.join('<li>%s</li>' % html.escape(frase(x, tasa, umbral)) for x in h) + '</ul>')
    else:
        trozos.append('<p>%s</p>' % _T['nada'])
    trozos.append('<p class="nota">%s</p>' % (_T['nota'] % n_min))

    trozos.append('<p class="leyenda nota"><span><i style="background:var(--barra);border-radius:2px"></i>%s</span>'
                  '<span><i style="background:var(--alto)"></i>%s</span>'
                  '<span><i style="background:var(--bajo)"></i>%s</span>'
                  '<span><i style="background:var(--neutro)"></i>%s</span>'
                  '<span><i style="border:1.5px solid var(--suave)"></i>%s</span>'
                  '<span>%s</span></p>' % (_T['ley_n'], _T['ley_alto'], _T['ley_bajo'], _T['ley_neutro'],
                                           _T['ley_poco'] % n_min, _T['ley_linea']))
    for var, (nombre, orden) in VARIABLES.items():
        filas = tabla(datos, var, umbral, orden)
        if len(filas) < 2:
            continue
        con_dato = sum(f[1] for f in filas)
        trozos.append('<h2>%s</h2><p class="nota">%s</p>' % (nombre, _T['con_dato'] % con_dato))
        trozos.append(grafico(filas, tasa, n_min))
    trozos.append('</main></body></html>')
    return '\n'.join(trozos)


def main():
    ap = argparse.ArgumentParser(description=_T['descripcion'])
    en = IDIOMA == 'en'
    ap.add_argument('entrada', metavar='INPUT' if en else 'ENTRADA', help=_T['h_entrada'])
    ap.add_argument('salida', metavar='OUTPUT' if en else 'SALIDA', help=_T['h_salida'])
    ap.add_argument('--threshold', '--umbral', dest='umbral', type=int, default=4, help=_T['h_umbral'])
    ap.add_argument('--minimum', '--minimo', dest='minimo', type=int, default=0, help=_T['h_minimo'])
    ap.add_argument('--source', '--origen', dest='origen', default=_T['origen'], help=_T['h_origen'])
    ap.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    for acc in ap._actions:
        if acc.option_strings and acc.nargs is None and acc.choices is None and acc.dest != 'help':
            nombres = [o for o in acc.option_strings if o.startswith('--')]
            nombre = nombres[0] if en or len(nombres) < 2 else nombres[1]
            acc.metavar = nombre.lstrip('-').upper().replace('-', '_')
    a = ap.parse_args()
    datos = preparar(leer(a.entrada))
    if not datos:
        sys.exit(_T['vacia'])
    umbral = a.umbral
    while umbral > 1 and not any(d['valoracion'] >= umbral for d in datos):
        umbral -= 1
    if not any(d['valoracion'] >= umbral for d in datos):
        sys.exit(_T['sin_valoracion'])
    if umbral != a.umbral:
        print(_T['aviso'] % (a.umbral, umbral))
    n_min = a.minimo or max(12, int(0.02 * len(datos)))
    open(a.salida, 'w', encoding='utf-8').write(informe(datos, umbral, n_min, a.origen))
    elegidas = sum(1 for d in datos if d['valoracion'] >= umbral)
    print(_T['resumen'] % (len(datos), elegidas, umbral, a.salida))


if __name__ == '__main__':
    main()
