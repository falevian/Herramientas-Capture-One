#!/usr/bin/env python3
"""revelado.py: film development evaluating the spectral model pixel by pixel.

Uses the models of peliculas.py (Kodachrome 64 and 25, Velvia 50, PRO 400H on
Endura and Tri-X in D-76 on Multigrade IV), the same ones that generate the ICC
profiles for Capture One, but without going through the 3D table of the profile.

How it is evaluated. Each model has two very different parts. The first are the
characteristic curves, one per layer: they are steep (toe, shoulder, high local
gammas) and here they are evaluated exactly at each pixel by interpolation on
the repaired curve. The second is the spectral integral that turns the dye
amounts (or the toned silver density) into XYZ: it is a smooth function, nearly
linear in logarithm, and it is tabulated once per image on a grid of 48^3 dye
amounts (or 4096 densities in black and white) and interpolated in log XYZ. An
ICC profile, instead, tabulates the whole composition, steep curves included,
on a 33^3 or 45^3 grid over the camera RGB. --check measures the error of the
spectral table against the full integral, and --exact computes the full
integral at every pixel (slow, for verification).

Colour filters for black and white. With Tri-X, --filter simulates a filter in
front of the lens spectrally: the panchromatic sensitivity of the film is
multiplied by the transmittance of the filter and the exposure is fitted again
as a function of XYZ, compensating the filter factor on a neutral grey, as a
photographer would open the aperture. The transmittances approximate those of
Wratten filters; --filter-csv accepts a measurement of your own (columns
wavelength in nm and transmittance).

Input. A scene-referred image: in Capture One, normal camera profile (no film
profile) and the Linear Response curve, exported as 16 bit TIFF. The value 1.0
is diffuse white, as in the ICC profile. An integer TIFF clips at 1.0, like the
input of the ICC profile, and the model has one to three stops of shoulder
above diffuse white. To use them, lower the exposure when exporting and give
it with --headroom (the Capture One script lowers it two stops and gives them
back here); highlights above white are then compressed smoothly instead of
being clipped. The colour space is read from the embedded profile (sRGB, Adobe
RGB or ProPhoto RGB); ProPhoto is best, so that saturated colours are not
clipped before the model. The output is written in the same space and with the
same profile.

Messages and help are shown in English or Spanish (--lang, or the LANG
environment variable). Every option and value also has its Spanish spelling
(--pelicula, --virado selenio, --filtro rojo, --sala tenue...).

Usage:
    python3 revelado.py input.tif output.tif --film k64
    python3 revelado.py input.tif output.tif --film trix --toning selenium --filter red
    python3 revelado.py input.tif output.tif --film pro400h --ev 1.5 --print 0.55
    python3 revelado.py --check --film velvia50

Needs numpy, Pillow and tifffile, and peliculas.py and espacio_color.py in the
same folder.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import espacio_color as ec  # noqa: E402

IDIOMA = ec.IDIOMA
_T = {
    'en': {
        'falta_peliculas': 'peliculas.py is missing from the folder of revelado.py',
        'filtro_desconocido': 'unknown filter: %s',
        'solo_bn': 'colour filters only apply to black and white (trix)',
        'comprobar': '%s: ΔE*ab of the table against the full integral over %d colours: '
                     'mean %.4f  p99 %.4f  maximum %.4f',
        'tiempo': '  time: table %.2f s, full integral %.2f s (%.0f times faster)',
        'descripcion': 'Film development with the spectral model of peliculas.py, evaluated pixel by pixel.',
        'h_entrada': 'input image, scene-referred (Linear Response), preferably 16 bit TIFF in ProPhoto RGB',
        'h_salida': 'output image; same colour space and profile as the input',
        'h_pelicula': 'film: k64, k25, velvia50, pro400h or trix',
        'h_ev': 'exposure of the film in stops; negative = denser and more saturated',
        'h_ganancia': 'dye gain; below 1 lowers contrast and chroma',
        'h_copia': 'pro400h and trix: stops by which the print is lightened from the balance',
        'h_virado': 'trix only: toning of the print (neutral, cold, warm, sepia, selenium)',
        'h_filtro': 'trix only: colour filter in front of the lens, simulated spectrally '
                    '(yellow, deep_yellow, orange, red, deep_red, green, blue)',
        'h_filtro_csv': 'trix only: measured transmittance, CSV with wavelength (nm) and transmittance',
        'h_sala': 'slides only: viewing surround (dark = projection, dim = monitor in a dim room, '
                  'average = lit room)',
        'h_margen': 'stops by which the exposure was lowered when exporting so as not to clip the '
                    'highlights; they are undone before the model, so that the shoulder of the film '
                    'receives what lies above diffuse white',
        'h_blanco': 'diffuse: scene diffuse white goes to white (like the ICC profile); '
                    'paper: the base of the paper or slide goes to white',
        'h_curvas': 'smooth: repaired characteristic curves (default); raw: as digitised',
        'h_espacio': 'input space if it has no profile (auto = that of the embedded profile)',
        'h_exacto': 'full spectral integral at every pixel (slow; for verification)',
        'h_comprobar': 'measure the error of the spectral table against the full integral',
        'h_lang': 'language of messages and help: en or es (default: from LANG)',
        'faltan': 'the input and the output are missing',
        'extra_filtro': '  filter %s (factor %.1f stops, compensated)',
        'extra_virado': '  toning %s',
        'resumen': 'development %s: %s  ev %+g  gain %g  headroom %g  white %s%s  space %s  %dx%d  %.1f s',
        'nombres': {'neutro': 'neutral', 'frio': 'cold', 'calido': 'warm', 'sepia': 'sepia',
                    'selenio': 'selenium', 'difuso': 'diffuse', 'papel': 'paper',
                    'amarillo': 'yellow', 'amarillo_intenso': 'deep_yellow', 'naranja': 'orange',
                    'rojo': 'red', 'rojo_intenso': 'deep_red', 'verde': 'green', 'azul': 'blue'},
    },
    'es': {
        'falta_peliculas': 'Falta peliculas.py en la carpeta de revelado.py',
        'filtro_desconocido': 'filtro desconocido: %s',
        'solo_bn': 'los filtros de color solo se aplican al blanco y negro (trix)',
        'comprobar': '%s: ΔE*ab tabla frente a integral completa sobre %d colores: '
                     'media %.4f  p99 %.4f  máximo %.4f',
        'tiempo': '  tiempo: tabla %.2f s, integral completa %.2f s (%.0f veces más rápida)',
        'descripcion': 'Revelado de película con el modelo espectral de peliculas.py, evaluado píxel a píxel.',
        'h_entrada': 'imagen de entrada referida a escena (Respuesta lineal), mejor TIFF de 16 bits en ProPhoto RGB',
        'h_salida': 'imagen de salida; mismo espacio de color y perfil que la entrada',
        'h_pelicula': 'película: k64, k25, velvia50, pro400h o trix',
        'h_ev': 'exposición del film en pasos; negativo = más denso y saturado',
        'h_ganancia': 'ganancia de colorante; menor que 1 rebaja contraste y croma',
        'h_copia': 'pro400h y trix: pasos de aclarado de la copia respecto al balance',
        'h_virado': 'solo trix: virado de la copia (neutro, frio, calido, sepia, selenio)',
        'h_filtro': 'solo trix: filtro de color delante del objetivo, simulado espectralmente '
                    '(amarillo, amarillo_intenso, naranja, rojo, rojo_intenso, verde, azul)',
        'h_filtro_csv': 'solo trix: transmitancia medida, CSV con longitud de onda (nm) y transmitancia',
        'h_sala': 'solo diapositivas: entorno de visión (oscura = proyección, tenue = monitor en '
                  'penumbra, media = habitación iluminada)',
        'h_margen': 'pasos que se bajó la exposición al exportar para no recortar las luces; '
                    'se deshacen antes del modelo, de modo que el hombro de la película '
                    'recibe lo que hay por encima del blanco difuso',
        'h_blanco': 'difuso: el blanco difuso de la escena va al blanco (como el perfil ICC); '
                    'papel: va al blanco la base del papel o de la diapositiva',
        'h_curvas': 'suaves: curvas características reparadas (por defecto); crudas: tal como se digitalizaron',
        'h_espacio': 'espacio de la entrada si no trae perfil (auto = el del perfil incrustado)',
        'h_exacto': 'integral espectral completa en cada píxel (lento; para verificar)',
        'h_comprobar': 'mide el error de la tabla espectral frente a la integral completa',
        'h_lang': 'idioma de los mensajes y de la ayuda: en o es (por defecto, según LANG)',
        'faltan': 'faltan la entrada y la salida',
        'extra_filtro': '  filtro %s (factor %.1f pasos, compensado)',
        'extra_virado': '  virado %s',
        'resumen': 'revelado %s: %s  ev %+g  ganancia %g  margen %g  blanco %s%s  espacio %s  %dx%d  %.1f s',
        'nombres': {},
    },
}[IDIOMA]

try:
    import peliculas as P  # noqa: E402
except ImportError:
    sys.exit(_T['falta_peliculas'])

# nombres aceptados en la línea de órdenes -> valor interno
ALIAS = {
    'neutral': 'neutro', 'cold': 'frio', 'warm': 'calido', 'selenium': 'selenio',
    'frío': 'frio', 'cálido': 'calido',
    'yellow': 'amarillo', 'deep_yellow': 'amarillo_intenso', 'orange': 'naranja', 'red': 'rojo',
    'deep_red': 'rojo_intenso', 'green': 'verde', 'blue': 'azul',
    'dark': 'oscura', 'dim': 'tenue', 'average': 'media',
    'diffuse': 'difuso', 'paper': 'papel', 'smooth': 'suaves', 'raw': 'crudas',
}

LOG2 = np.log10(2.0)

# Filtros: (tipo, parámetros). paso_largo(l50, ancho) deja pasar por encima de l50.
FILTROS = {
    'amarillo':          'Wratten 8 (K2), approximate',
    'amarillo_intenso':  'Wratten 15 (G), approximate',
    'naranja':           'Wratten 21, approximate',
    'rojo':              'Wratten 25 (A), approximate',
    'rojo_intenso':      'Wratten 29 (F), approximate',
    'verde':             'Wratten 11 (X1), approximate',
    'azul':              'Wratten 47, approximate',
}


def _paso_largo(wl, l50, ancho):
    return 1.0 / (1.0 + np.exp(-(wl - l50) / ancho))


def transmitancia_filtro(nombre, wl, csv=None):
    if csv:
        datos = np.loadtxt(csv, delimiter=',', comments='#')
        t = np.interp(wl, datos[:, 0], datos[:, 1], left=datos[0, 1], right=datos[-1, 1])
        return np.clip(t / max(t.max(), 1e-9), 0, 1)
    if nombre == 'amarillo':
        return 0.02 + 0.98 * _paso_largo(wl, 495, 8)
    if nombre == 'amarillo_intenso':
        return 0.01 + 0.99 * _paso_largo(wl, 525, 7)
    if nombre == 'naranja':
        return 0.005 + 0.995 * _paso_largo(wl, 552, 7)
    if nombre == 'rojo':
        return 0.002 + 0.998 * _paso_largo(wl, 597, 6)
    if nombre == 'rojo_intenso':
        return 0.001 + 0.999 * _paso_largo(wl, 618, 6)
    if nombre == 'verde':
        return _paso_largo(wl, 485, 10) * (0.35 + 0.65 * (1 - _paso_largo(wl, 605, 12)))
    if nombre == 'azul':
        return 0.01 + 0.99 * _paso_largo(wl, 405, 8) * (1 - _paso_largo(wl, 500, 12))
    raise ValueError(_T['filtro_desconocido'] % nombre)


def _reflectancias_entrenamiento(wl, n=4000, semilla=7):
    """Reflectancias suaves y acotadas: escalones logísticos y campanas al azar sobre
    una base, más algunas formas naturales (follaje con su borde rojo, piel, cielo)."""
    rng = np.random.default_rng(semilla)
    R = np.empty((n, len(wl)))
    for i in range(n):
        r = rng.uniform(0.03, 0.5) * np.ones(len(wl))
        for _ in range(rng.integers(1, 4)):
            if rng.random() < 0.5:
                r += rng.uniform(-0.5, 0.6) * _paso_largo(wl, rng.uniform(420, 680), rng.uniform(8, 40))
            else:
                r += rng.uniform(-0.3, 0.6) * np.exp(-0.5 * ((wl - rng.uniform(400, 700)) / rng.uniform(15, 70)) ** 2)
        R[i] = np.clip(r, 0.02, 0.95)
    follaje = 0.05 + 0.08 * np.exp(-0.5 * ((wl - 550) / 30) ** 2) + 0.45 * _paso_largo(wl, 705, 10)
    piel = 0.18 + 0.35 * _paso_largo(wl, 590, 25) - 0.05 * np.exp(-0.5 * ((wl - 545) / 15) ** 2)
    cielo = 0.6 - 0.45 * _paso_largo(wl, 520, 40)
    return np.vstack([R, np.clip(np.vstack([follaje, piel, cielo]), 0.02, 0.95)])


class Modelo:
    """Envuelve un modelo de peliculas.py y lo evalúa de forma rápida y exacta."""

    def __init__(self, pelicula, ev=0.0, ganancia=1.0, copia=0.0, virado='neutro',
                 sala='oscura', filtro=None, filtro_csv=None, curvas='suaves',
                 margen=0.0, blanco='difuso', n_lut=48):
        P.CURVAS = curvas
        m = P.cargar(pelicula)
        if hasattr(m, 'PRINT_STOPS'):
            m.PRINT_STOPS = copia
        if hasattr(m, 'VIRADO'):
            m.VIRADO = virado
        self.m = m
        self.pelicula = pelicula
        self.nombre = P.FILMS[pelicula]['nombre']
        self.ev = float(ev)
        self.ganancia = float(ganancia)
        self.kw = dict(exposure_stops=self.ev, dye_gain=(self.ganancia,) * 3)
        if hasattr(m, 'CC'):
            self.tipo = 'diapositiva'
        elif hasattr(m, 'CCN'):
            self.tipo = 'negativo_color'
        else:
            self.tipo = 'bn'
        self.g_sala = P.SALAS.get(sala, 1.0) if hasattr(m, 'PROJ') else 1.0
        self.filtro = None
        if filtro or filtro_csv:
            if self.tipo != 'bn':
                raise ValueError(_T['solo_bn'])
            self._aplicar_filtro(filtro, filtro_csv)

        # posproceso lineal común: pantalla o papel -> blanco relativo -> D50
        self.C1 = self._mcat(m.XYZ_SCREEN, m.SRGB_W)
        self.C2 = self._mcat(m.SRGB_W, m.XYZ_D50)
        # el margen deshace la bajada de exposición hecha al exportar
        self.C_in = self._mcat(m.XYZ_D50, m.W_D55) * 2.0 ** float(margen)
        # blanco 'difuso': el blanco difuso de la escena va al blanco de salida (como el
        # perfil ICC); 'papel': va al blanco la base del papel o de la diapositiva, y el
        # blanco difuso queda algo por debajo, como en una copia de verdad
        ref = m.W_D55[None] * (64.0 if blanco == 'papel' else 1.0)
        w = m.film(ref, **self.kw) @ self.C1.T
        self.w1 = max(float(w[0, 1]), 1e-6)
        self.margen = float(margen)
        self.blanco = blanco

        if self.tipo == 'negativo_color':
            pb = m._pbal_for(self.ev) if m.AUTO_BALANCE else m.PBAL
            self.pb = pb - m.PRINT_STOPS * LOG2
        elif self.tipo == 'bn':
            self.pb = m._pbal_for(self.ev) - m.PRINT_STOPS * LOG2
        self._preparar_tabla(n_lut)

    # ---------------------------------------------------------- utilidades
    def _mcat(self, src, dst):
        return self.m.cat(np.eye(3), src, dst).T

    def _aplicar_filtro(self, filtro, csv):
        """Reajusta V_PAN (XYZ -> exposición de la Tri-X) para la sensibilidad filtrada,
        por mínimos cuadrados con error relativo sobre un conjunto de reflectancias
        iluminadas con D55. El factor de filtro se compensa igualando la exposición de
        un gris neutro, como al abrir el diafragma lo que indica el factor."""
        import io
        z = np.load(io.BytesIO(P._B(P.FILMS['trix']['npz'])))
        wl, sp, xb = z['WL'], z['SP'], z['XB']
        d55 = np.load(io.BytesIO(P._B(P.FILMS['k64']['npz'])))['D55']
        F = transmitancia_filtro(filtro, wl, csv)
        R = _reflectancias_entrenamiento(wl)
        E = R * d55[None]
        XYZ = E @ xb
        XYZ /= (d55 @ xb)[1]

        def ajusta(sens):
            H = E @ sens
            w = 1.0 / np.maximum(H, 0.05 * np.median(H))
            v, *_ = np.linalg.lstsq(XYZ * w[:, None], H * w, rcond=None)
            return v
        vf = ajusta(sp * F)
        gris = self.m.W_D55
        V = vf * float(gris @ self.m.V_PAN) / float(gris @ vf)
        self.m.V_PAN = V
        self.ajuste_sin_filtro = ajusta(sp) * float(gris @ self.m.V_PAN) / float(gris @ ajusta(sp))
        self.filtro = filtro if not csv else os.path.basename(csv)
        self.factor_filtro = float(np.log2((d55 * sp).sum() / max((d55 * sp * F).sum(), 1e-12)))

    # ---------------------------------------------------------- partes del modelo
    def _variables(self, XYZ55):
        """Parte abrupta, exacta: XYZ de escena -> cantidades de colorante (3) o
        densidad de la copia en blanco y negro (1)."""
        m = self.m
        if self.tipo == 'diapositiva':
            H = np.clip(XYZ55 @ m.M_XYZ2H.T, 1e-7, None)
            logh = np.log10(H) + m.LOGH_WHITE + self.ev * LOG2
            a = np.clip(m.status_a(logh) - m.DMIN, 0, None) @ m.JINV.T * m.KBAL * self.ganancia
            return np.clip(a, 0, None)
        if self.tipo == 'negativo_color':
            H = np.clip(XYZ55 @ m.M_XYZ2H.T, 1e-9, None)
            logh = np.log10(H) + m.LOGH_WHITE + self.ev * LOG2
            Dm = m._interp3(logh, m.LHN, m.CCN)
            Da = m._interp3(self.pb[None, :] - Dm, m.LEP, m.CCP)
            return np.clip((Da - m.DMINP) @ m.JINVP.T, 0, None) * self.ganancia
        H = np.clip(XYZ55 @ m.V_PAN, 1e-9, None)
        logh = np.log10(H) + m.LOGH_WHITE + self.ev * LOG2
        Dp = m._pap_D(self.pb - m._neg_D(logh))
        return m.DMINP + np.clip(Dp - m.DMINP, 0, None) * self.ganancia

    def _espectral(self, v):
        """Parte suave: integral espectral exacta de las variables a XYZ del film."""
        m = self.m
        if self.tipo == 'diapositiva':
            T = 10.0 ** (-(v @ m.DYE.T + m.DBASE))
            return (T * m.PROJ[None]) @ m.XB * m.K_NORM
        if self.tipo == 'negativo_color':
            Rf = 10.0 ** (-(v @ m.DYEP.T + m.DBASEP))
            return m._KK50 * ((Rf * m.D50[None]) @ m.XB) * m.K_NORM
        k1, k2 = m.K_PRESETS.get(m.VIRADO, m.K_PRESETS['neutro'])
        f = 1.0 + k1 * m.R1 + k2 * m.R2
        Dl = m.DMINP + (np.atleast_1d(v)[:, None] - m.DMINP) * f[None, :]
        Rf = 10.0 ** (-np.clip(Dl, 0, None))
        return m._KK50 * ((Rf * m.D50[None]) @ m.XB) * m.K_NORM

    def _preparar_tabla(self, n):
        m = self.m
        if self.tipo == 'bn':
            dmax = m.DMINP + (float(m.CPAP.max()) - m.DMINP) * self.ganancia
            self.ejes = np.linspace(m.DMINP, dmax * 1.02 + 0.02, 4096)
            self.tabla = np.log10(np.clip(self._espectral(self.ejes), 1e-12, None))
            return
        if self.tipo == 'diapositiva':
            dmax = np.array([m.CC[:, c].max() for c in range(3)]) - m.DMIN
            J = m.JINV
            esc = m.KBAL * self.ganancia
        else:
            dmax = np.array([m.CCP[:, c].max() for c in range(3)]) - m.DMINP
            J = m.JINVP
            esc = np.full(3, self.ganancia)
        esquinas = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]) * dmax
        amax = np.clip(esquinas @ J.T, 0, None).max(0) * esc * 1.02 + 1e-3
        self.lo = np.zeros(3)
        self.paso = amax / (n - 1)
        g = [np.linspace(0, amax[c], n) for c in range(3)]
        A = np.stack(np.meshgrid(*g, indexing='ij'), -1).reshape(-1, 3)
        trozos = [self._espectral(A[i:i + 20000]) for i in range(0, len(A), 20000)]
        self.tabla = np.log10(np.clip(np.vstack(trozos), 1e-12, None)).reshape(n, n, n, 3)

    def _interp_tabla(self, v):
        if self.tipo == 'bn':
            out = np.empty((len(v), 3))
            for c in range(3):
                out[:, c] = np.interp(v, self.ejes, self.tabla[:, c])
            return 10.0 ** out
        n = self.tabla.shape[0]
        t = np.clip((v - self.lo) / self.paso, 0, n - 1 - 1e-9)
        i = t.astype(np.int64)
        f = t - i
        plano = self.tabla.reshape(-1, 3)
        s0, s1 = n * n, n
        b = i[:, 0] * s0 + i[:, 1] * s1 + i[:, 2]
        fx, fy, fz = f[:, 0:1], f[:, 1:2], f[:, 2:3]
        c00 = plano[b] * (1 - fz) + plano[b + 1] * fz
        c01 = plano[b + s1] * (1 - fz) + plano[b + s1 + 1] * fz
        c10 = plano[b + s0] * (1 - fz) + plano[b + s0 + 1] * fz
        c11 = plano[b + s0 + s1] * (1 - fz) + plano[b + s0 + s1 + 1] * fz
        c0 = c00 * (1 - fy) + c01 * fy
        c1 = c10 * (1 - fy) + c11 * fy
        return 10.0 ** (c0 * (1 - fx) + c1 * fx)

    def _pos(self, XYZf):
        rel = XYZf @ self.C1.T / self.w1
        if self.g_sala != 1.0:
            Y = np.clip(rel[:, 1:2], 1e-9, None)
            rel = rel * Y ** (self.g_sala - 1.0)
        return rel @ self.C2.T

    # ---------------------------------------------------------- interfaz
    def xyz50(self, XYZ50, exacto=False):
        """XYZ D50 de escena (blanco difuso Y=1) -> XYZ D50 del film, blanco relativo."""
        XYZ55 = np.clip(XYZ50, 0, None) @ self.C_in.T
        if exacto:
            return self._pos(self.m.film(XYZ55, **self.kw))
        return self._pos(self._interp_tabla(self._variables(XYZ55)))

    def referencia(self, XYZ50):
        """La misma transformación usando film() de peliculas.py tal cual."""
        return self.xyz50(XYZ50, exacto=True)


# ---------------------------------------------------------------- gama y color

def compresion_gama(rgb, pesos, rodilla=0.85):
    """Lleva los colores fuera de gama hacia el gris de su misma luminancia y comprime
    las luces por encima de la rodilla con una tangente hiperbólica (como soft_gamut de
    peliculas.py, con los pesos de luminancia del espacio de salida)."""
    Y = np.clip((rgb * pesos).sum(-1, keepdims=True), 0, None)
    mn = rgb.min(-1, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        f = np.where(mn < 0, Y / np.maximum(Y - mn, 1e-9), 1.0)
    rgb = Y + (rgb - Y) * np.clip(f, 0, 1)
    hi = rgb.max(-1, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        s = np.where(hi > rodilla, (rodilla + (1 - rodilla) * np.tanh((hi - rodilla) / (1 - rodilla)))
                     / np.maximum(hi, 1e-9), 1.0)
    return np.clip(rgb * s, 0, 1)


def xyz_a_lab(XYZ, blanco=ec.D50):
    r = XYZ / blanco
    f = np.where(r > (6 / 29) ** 3, np.cbrt(np.clip(r, 0, None)), r / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def revelar(enc, espacio, modelo, exacto=False, filas=None):
    h, w, _ = enc.shape
    out = np.empty_like(enc)
    filas = filas or max(1, (400000 if exacto else 1500000) // w)
    if exacto:
        filas = max(1, 40000 // w)
    for y0 in range(0, h, filas):
        y1 = min(h, y0 + filas)
        bloque = enc[y0:y1].reshape(-1, 3)
        XYZ = espacio.a_xyz(bloque)
        XYZf = modelo.xyz50(XYZ, exacto=exacto)
        lin = compresion_gama(espacio.lineal_desde_xyz(XYZf), espacio.pesos_y)
        out[y0:y1] = espacio.desde_lineal(lin).reshape(y1 - y0, w, 3)
    return out


def comprobar(modelo, n=200000, semilla=3):
    """Error de la tabla espectral frente a la integral completa, en ΔE*ab, sobre
    colores al azar en ProPhoto lineal (incluye colores muy saturados) entre -8 y +2 EV."""
    rng = np.random.default_rng(semilla)
    pp = ec.Espacio.predefinido('prophoto')
    croma = rng.random((n, 3)) ** 2
    nivel = 0.18 * 2.0 ** rng.uniform(-8, 2, (n, 1))
    lin = croma / np.maximum(croma @ pp.pesos_y, 1e-6)[:, None] * nivel
    XYZ = lin @ pp.M.T
    t0 = time.time()
    a = modelo.xyz50(XYZ)
    t1 = time.time()
    b = np.vstack([modelo.referencia(XYZ[i:i + 20000]) for i in range(0, n, 20000)])
    t2 = time.time()
    dE = np.linalg.norm(xyz_a_lab(a) - xyz_a_lab(b), axis=1)
    print(_T['comprobar'] % (modelo.nombre, n, dE.mean(), np.percentile(dE, 99), dE.max()))
    print(_T['tiempo'] % (t1 - t0, t2 - t1, (t2 - t1) / max(t1 - t0, 1e-6)))
    return dE


def _opcion(valor, validos):
    """Pasa un valor de la línea de órdenes a su nombre interno y comprueba que existe."""
    if valor is None:
        return None
    v = ALIAS.get(valor.lower(), valor.lower())
    if v not in validos:
        en = {interno: ingles for ingles, interno in ALIAS.items() if ingles.isascii()}
        lista = ', '.join(sorted({en.get(x, x) for x in validos} | set(validos)))
        raise argparse.ArgumentTypeError('%s: %s' % (valor, lista))
    return v


def main():
    ap = argparse.ArgumentParser(description=_T['descripcion'])
    en = IDIOMA == 'en'
    ap.add_argument('entrada', nargs='?', metavar='INPUT' if en else 'ENTRADA', help=_T['h_entrada'])
    ap.add_argument('salida', nargs='?', metavar='OUTPUT' if en else 'SALIDA', help=_T['h_salida'])
    ap.add_argument('--film', '--pelicula', dest='pelicula', choices=list(P.FILMS), default='k64',
                    help=_T['h_pelicula'])
    ap.add_argument('--ev', type=float, default=0.0, help=_T['h_ev'])
    ap.add_argument('--gain', '--ganancia', dest='ganancia', type=float, default=1.0, help=_T['h_ganancia'])
    ap.add_argument('--print', '--copia', dest='copia', type=float, default=0.0, help=_T['h_copia'])
    ap.add_argument('--toning', '--virado', dest='virado', default='neutro', help=_T['h_virado'])
    ap.add_argument('--filter', '--filtro', dest='filtro', default=None, help=_T['h_filtro'])
    ap.add_argument('--filter-csv', '--filtro-csv', dest='filtro_csv', default=None, help=_T['h_filtro_csv'])
    ap.add_argument('--room', '--sala', dest='sala', default='oscura', help=_T['h_sala'])
    ap.add_argument('--headroom', '--margen', dest='margen', type=float, default=0.0, help=_T['h_margen'])
    ap.add_argument('--white', '--blanco', dest='blanco', default='difuso', help=_T['h_blanco'])
    ap.add_argument('--curves', '--curvas', dest='curvas', default='suaves', help=_T['h_curvas'])
    ap.add_argument('--space', '--espacio', dest='espacio', choices=['auto'] + list(ec.ESPACIOS),
                    default='auto', help=_T['h_espacio'])
    ap.add_argument('--exact', '--exacto', dest='exacto', action='store_true', help=_T['h_exacto'])
    ap.add_argument('--check', '--comprobar', dest='comprobar', action='store_true', help=_T['h_comprobar'])
    ap.add_argument('--lang', '--idioma', dest='lang', choices=['en', 'es'], default=IDIOMA, help=_T['h_lang'])
    for acc in ap._actions:
        if acc.option_strings and acc.nargs is None and acc.choices is None and acc.dest != 'help':
            nombres = [o for o in acc.option_strings if o.startswith('--')]
            nombre = nombres[0] if en or len(nombres) < 2 else nombres[1]
            acc.metavar = nombre.lstrip('-').upper().replace('-', '_')
    a = ap.parse_args()
    try:
        a.virado = _opcion(a.virado, ['neutro', 'frio', 'calido', 'sepia', 'selenio'])
        a.filtro = _opcion(a.filtro, list(FILTROS))
        a.sala = _opcion(a.sala, list(P.SALAS))
        a.blanco = _opcion(a.blanco, ['difuso', 'papel'])
        a.curvas = _opcion(a.curvas, ['suaves', 'crudas'])
    except argparse.ArgumentTypeError as e:
        ap.error(str(e))

    try:
        modelo = Modelo(a.pelicula, a.ev, a.ganancia, a.copia, a.virado, a.sala,
                        a.filtro, a.filtro_csv, a.curvas, a.margen, a.blanco)
    except ValueError as e:
        sys.exit(str(e))

    if a.comprobar:
        comprobar(modelo)
        if not a.entrada:
            return
    if not a.entrada or not a.salida:
        ap.error(_T['faltan'])

    nom = lambda x: _T['nombres'].get(x, x)  # noqa: E731
    t0 = time.time()
    enc, bits, icc = ec.leer(a.entrada)
    esp = ec.espacio_para(icc, a.espacio)
    res = revelar(enc, esp, modelo, exacto=a.exacto)
    ec.escribir(a.salida, res, icc, bits=16 if a.salida.lower().endswith(('.tif', '.tiff')) else 8)
    extra = ''
    if modelo.filtro:
        extra = _T['extra_filtro'] % (nom(modelo.filtro), modelo.factor_filtro)
    if modelo.tipo == 'bn' and modelo.m.VIRADO != 'neutro':
        extra += _T['extra_virado'] % nom(modelo.m.VIRADO)
    print(_T['resumen'] % (a.pelicula, modelo.nombre, a.ev, a.ganancia, a.margen, nom(a.blanco), extra,
                           esp.nombre, enc.shape[1], enc.shape[0], time.time() - t0))


if __name__ == '__main__':
    main()
