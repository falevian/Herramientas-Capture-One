"""espacio_color.py: reading and writing images with their colour space.

Reads 8 or 16 bit TIFF (tifffile) and JPEG or PNG (Pillow) together with the
embedded ICC profile, and builds from that profile the exact conversion between
encoded values and XYZ D50 (the ICC connection space). It accepts matrix and
curve profiles (rXYZ, gXYZ, bXYZ and rTRC, gTRC, bTRC with 'curv' or 'para'
curves), which are the ones Capture One uses when exporting in sRGB, Adobe RGB
or ProPhoto RGB. If the image has no profile, or the profile is not a matrix
profile, the given space is used (srgb, adobergb or prophoto).

It also holds the language selection shared by revelado.py and zonas.py:
--lang/--idioma on the command line, otherwise LC_ALL, LC_MESSAGES or LANG.

Needs numpy and Pillow, and tifffile for TIFF.
"""
import os
import struct
import sys

import numpy as np

ICC_TAG = 34675


def idioma():
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


IDIOMA = idioma()
_T = {
    'en': {
        'para': 'parametric curve of type %d not supported',
        'no_matriz': 'the profile is not an RGB matrix and curves profile',
        'incrustado': 'embedded profile',
        'curva_icc': 'ICC curve of type %r not supported',
        'aviso_nombre': 'warning: %s; using %s from its name',
        'aviso_srgb': 'warning: %s; assuming sRGB',
        'tifffile': 'TIFF needs tifffile:  pip install tifffile',
        'formato': 'Unsupported image format: %s',
    },
    'es': {
        'para': 'curva paramétrica de tipo %d no admitida',
        'no_matriz': 'el perfil no es RGB de matriz y curvas',
        'incrustado': 'perfil incrustado',
        'curva_icc': 'curva ICC de tipo %r no admitida',
        'aviso_nombre': 'aviso: %s; uso %s por su nombre',
        'aviso_srgb': 'aviso: %s; supongo sRGB',
        'tifffile': 'Para TIFF hace falta tifffile:  pip install tifffile',
        'formato': 'Formato de imagen no admitido: %s',
    },
}[IDIOMA]
D50 = np.array([0.9642, 1.0, 0.8249])

# Colorantes adaptados a D50 (como figuran en los perfiles ICC estándar) y curvas
ESPACIOS = {
    'srgb': dict(nombre='sRGB IEC61966-2.1',
                 M=np.array([[0.4361, 0.3851, 0.1431],
                             [0.2225, 0.7169, 0.0606],
                             [0.0139, 0.0971, 0.7141]]),
                 trc=('para', 3, (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045))),
    'adobergb': dict(nombre='Adobe RGB (1998)',
                     M=np.array([[0.6097, 0.2053, 0.1492],
                                 [0.3111, 0.6257, 0.0632],
                                 [0.0195, 0.0609, 0.7446]]),
                     trc=('gamma', 563.0 / 256.0)),
    'prophoto': dict(nombre='ProPhoto RGB',
                     M=np.array([[0.7977, 0.1352, 0.0313],
                                 [0.2880, 0.7119, 0.0001],
                                 [0.0000, 0.0000, 0.8249]]),
                     trc=('gamma', 1.8)),
}


# ---------------------------------------------------------------- curvas de tono

def _para(tipo, p, x):
    x = np.clip(x, 0.0, 1.0)
    g = p[0]
    if tipo == 0:
        return x ** g
    a, b = p[1], p[2]
    base = np.clip(a * x + b, 0.0, None)
    if tipo == 1:
        return np.where(x >= -b / a, base ** g, 0.0)
    if tipo == 2:
        return np.where(x >= -b / a, base ** g + p[3], p[3])
    if tipo == 3:
        c, d = p[3], p[4]
        return np.where(x >= d, base ** g, c * x)
    if tipo == 4:
        c, d, e, f = p[3], p[4], p[5], p[6]
        return np.where(x >= d, base ** g + e, c * x + f)
    raise ValueError(_T['para'] % tipo)


class Curva:
    """Curva de tono de un canal: valor codificado [0,1] -> lineal [0,1], y su inversa."""

    def __init__(self, desc):
        self.desc = desc
        if desc[0] == 'gamma':
            self.g = float(desc[1])
            self.tabla = None
        else:
            xs = np.linspace(0.0, 1.0, 65536)
            if desc[0] == 'tabla':
                t = np.asarray(desc[1], float)
                ys = np.interp(xs, np.linspace(0, 1, len(t)), t)
            else:
                ys = _para(desc[1], desc[2], xs)
            ys = np.maximum.accumulate(ys)
            self.g = None
            self.tabla = (xs, ys)

    def a_lineal(self, v):
        if self.g is not None:
            return np.power(np.clip(v, 0, 1), self.g)
        xs, ys = self.tabla
        return np.interp(v, xs, ys)

    def desde_lineal(self, y):
        if self.g is not None:
            return np.power(np.clip(y, 0, 1), 1.0 / self.g)
        xs, ys = self.tabla
        return np.interp(y, ys, xs)


# ---------------------------------------------------------------- perfil ICC

def _u32(b, o):
    return struct.unpack('>I', b[o:o + 4])[0]


def _s15(b, o):
    return struct.unpack('>i', b[o:o + 4])[0] / 65536.0


def _etiquetas(icc):
    n = _u32(icc, 128)
    t = {}
    for i in range(n):
        o = 132 + 12 * i
        t[icc[o:o + 4].decode('latin1')] = (_u32(icc, o + 4), _u32(icc, o + 8))
    return t


def descripcion_icc(icc):
    """Texto de la etiqueta 'desc' (tipos desc de ICC v2 y mluc de v4), o ''."""
    try:
        t = _etiquetas(icc)
        if 'desc' not in t:
            return ''
        off, _ = t['desc']
        tipo = icc[off:off + 4]
        if tipo == b'desc':
            n = _u32(icc, off + 8)
            return icc[off + 12:off + 12 + n].split(b'\0')[0].decode('latin1', 'replace')
        if tipo == b'mluc':
            largo, desp = _u32(icc, off + 20), _u32(icc, off + 24)
            return icc[off + desp:off + desp + largo].decode('utf-16-be', 'replace').strip('\0')
    except Exception:
        pass
    return ''


def _curva_icc(icc, off):
    tipo = icc[off:off + 4]
    if tipo == b'curv':
        n = _u32(icc, off + 8)
        if n == 0:
            return ('gamma', 1.0)
        if n == 1:
            return ('gamma', struct.unpack('>H', icc[off + 12:off + 14])[0] / 256.0)
        t = np.frombuffer(icc[off + 12:off + 12 + 2 * n], dtype='>u2').astype(float) / 65535.0
        return ('tabla', t)
    if tipo == b'para':
        ft = struct.unpack('>H', icc[off + 8:off + 10])[0]
        np_ = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}[ft]
        p = [_s15(icc, off + 12 + 4 * i) for i in range(np_)]
        if ft == 0:
            return ('gamma', p[0])
        return ('para', ft, p)
    raise ValueError(_T['curva_icc'] % tipo)


class Espacio:
    """Conversión entre valores codificados y XYZ D50 para un espacio RGB de matriz."""

    def __init__(self, M, curvas, nombre, icc=None):
        self.M = np.asarray(M, float)
        self.Minv = np.linalg.inv(self.M)
        self.curvas = [Curva(c) for c in curvas]
        self.nombre = nombre
        self.icc = icc
        self.pesos_y = self.M[1] / self.M[1].sum()

    @classmethod
    def predefinido(cls, clave):
        e = ESPACIOS[clave]
        return cls(e['M'], [e['trc']] * 3, e['nombre'])

    @classmethod
    def desde_icc(cls, icc):
        t = _etiquetas(icc)
        if icc[16:20] != b'RGB ' or not all(k in t for k in ('rXYZ', 'gXYZ', 'bXYZ', 'rTRC')):
            raise ValueError(_T['no_matriz'])
        cols = []
        for k in ('rXYZ', 'gXYZ', 'bXYZ'):
            off = t[k][0]
            cols.append([_s15(icc, off + 8 + 4 * i) for i in range(3)])
        M = np.array(cols).T
        curvas = [_curva_icc(icc, t[k][0]) for k in ('rTRC', 'gTRC', 'bTRC') if k in t]
        if len(curvas) == 1:
            curvas *= 3
        return cls(M, curvas, descripcion_icc(icc) or _T['incrustado'], icc)

    def a_lineal(self, enc):
        out = np.empty_like(enc, dtype=np.float64)
        for c in range(3):
            out[..., c] = self.curvas[c].a_lineal(enc[..., c])
        return out

    def desde_lineal(self, lin):
        out = np.empty_like(lin, dtype=np.float64)
        for c in range(3):
            out[..., c] = self.curvas[c].desde_lineal(lin[..., c])
        return out

    def a_xyz(self, enc):
        return self.a_lineal(enc) @ self.M.T

    def lineal_desde_xyz(self, XYZ):
        return XYZ @ self.Minv.T


def espacio_para(icc, preferido='auto'):
    """Elige el espacio: el del perfil incrustado si es de matriz, o el indicado."""
    if preferido != 'auto':
        return Espacio.predefinido(preferido)
    if icc:
        try:
            return Espacio.desde_icc(icc)
        except Exception as e:
            d = descripcion_icc(icc).lower()
            for clave, nombre in (('prophoto', 'prophoto'), ('adobe', 'adobergb'), ('srgb', 'srgb')):
                if clave in d:
                    print(_T['aviso_nombre'] % (e, nombre), file=sys.stderr)
                    return Espacio.predefinido(nombre)
            print(_T['aviso_srgb'] % e, file=sys.stderr)
    return Espacio.predefinido('srgb')


# ---------------------------------------------------------------- ficheros

def leer(ruta):
    """Devuelve (valores codificados en [0,1] float64 H x W x 3, bits 8 o 16, ICC o None)."""
    icc = None
    if ruta.lower().endswith(('.tif', '.tiff')):
        try:
            import tifffile
        except ImportError:
            sys.exit(_T['tifffile'])
        with tifffile.TiffFile(ruta) as t:
            pag = t.pages[0]
            arr = pag.asarray()
            tag = pag.tags.get(ICC_TAG)
            if tag is not None:
                icc = bytes(tag.value)
        if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[-1] not in (3, 4):
            arr = np.moveaxis(arr, 0, -1)
    else:
        from PIL import Image
        with Image.open(ruta) as im:
            icc = im.info.get('icc_profile')
            arr = np.asarray(im.convert('RGB'))
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    arr = arr[..., :3]
    if arr.dtype == np.uint16:
        return arr.astype(np.float64) / 65535.0, 16, icc
    if arr.dtype == np.uint8:
        return arr.astype(np.float64) / 255.0, 8, icc
    if np.issubdtype(arr.dtype, np.floating):
        return np.clip(arr.astype(np.float64), 0, 1), 16, icc
    sys.exit(_T['formato'] % arr.dtype)


def escribir(ruta, enc, icc=None, bits=16):
    """enc: valores codificados en [0,1], H x W x 3."""
    if ruta.lower().endswith(('.tif', '.tiff')):
        import tifffile
        if bits == 16:
            datos = np.round(np.clip(enc, 0, 1) * 65535).astype(np.uint16)
        else:
            datos = np.round(np.clip(enc, 0, 1) * 255).astype(np.uint8)
        extra = [(ICC_TAG, 7, len(icc), icc, True)] if icc else []
        tifffile.imwrite(ruta, datos, photometric='rgb', compression='zlib', extratags=extra)
        return
    from PIL import Image
    im = Image.fromarray(np.round(np.clip(enc, 0, 1) * 255).astype(np.uint8), 'RGB')
    opciones = {'icc_profile': icc} if icc else {}
    if ruta.lower().endswith(('.jpg', '.jpeg')):
        im.save(ruta, quality=95, subsampling=0, **opciones)
    else:
        im.save(ruta, **opciones)


def fuente(tamano):
    from PIL import ImageFont
    tamano = max(8, int(tamano))
    for c in ('/System/Library/Fonts/Helvetica.ttc',
              '/System/Library/Fonts/Supplemental/Arial.ttf',
              '/Library/Fonts/Arial.ttf',
              'C:/Windows/Fonts/arial.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(c, tamano)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:
        return ImageFont.load_default()
