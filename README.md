# Photography tools for Capture One

*[Leer en español](README.es.md)*

Six tools for the Scripts menu of Capture One Pro on macOS:

- **Temporal stack.** Combines a sequence of photos, shot on a tripod or hand-held, with temporal operators computed pixel by pixel in linear light: mean, Hann-weighted mean, median, sigma-clipped mean, maximum and minimum. It gives a synthetic long exposure without a neutral density filter, removes transient things (people, cars, birds) or builds up light trails. If the tripod has moved or the sequence is hand-held, it first aligns the photos (pyramidal ECC registration, euclidean or homography) and crops the borders left without data.
- **Film grain.** Adds to each selected image a grain physically scaled to the chosen film (Tri-X, Kodachrome 64 and 25, Velvia 50, Pro 400H) and to the crop of the photo: an image cropped to half is treated as an enlarged half frame, and the grain looks proportionally larger. The amplitude is calibrated against the datasheet rms granularity, and the grain depends on tone as it does on slide film or on a print from a negative.
- **Film development.** Develops the image with the spectral film models of [peliculas.py](https://github.com/falevian/Photographers/tree/main/scripts/peliculas), evaluated pixel by pixel instead of through the 3D table of an ICC profile. The export keeps two stops of headroom above diffuse white, so the shoulder of the film compresses the highlights instead of clipping them. With Tri-X it adds toning and colour filters in front of the lens simulated on the spectral sensitivity, and it can finish with the grain of the same film.
- **Zone map.** Draws the zone system of an image as a false colour map with the area in each zone, and as contour lines over the grey image, to decide dodging and burning. It reads the print as developed, the scene like a light meter, or the tones a modelled Tri-X print at grade 2 would give.
- **Median contrast.** Raises or lowers the contrast with a logistic curve pivoting on the median of the lightness. Since the median commutes with any increasing curve, the median of the image stays exactly where it was. The curve can be written into Capture One's Luma curve, where it stays editable (the script measures and adjusts the pivot to Capture One's own scale), or applied in Python on L* keeping chromaticity. With an adjustment layer selected, it works out the layer's mask and fixes the median inside the mask only.
- **Parametric curve.** Lightroom's curve by regions, which Capture One lacks: four sliders for highlights, lights, darks and shadows, with three adjustable splits, each pushing the curve with a smooth bell that blends into its neighbours. Black and white stay fixed and the curve is kept increasing. It is written into the Luma curve of the image or of the selected layer, stays editable, and needs no export.

The first five export the selected variants as 16 bit TIFF and process them with a Python program, but they hand back different results. The temporal stack, the film grain and the film development import new TIFF files into the open document. The zone map opens its two images in Preview and changes nothing in the catalog. The median contrast, in its Capture One mode, writes an editable Luma curve into the image or the selected layer and creates no new file: it only exports small temporary copies to measure the median. In its Python mode it imports a new TIFF like the first three. The parametric curve exports nothing: it computes the curve and writes it straight into the Luma curve. The dialogs follow the macOS language, English or Spanish.

## Requirements

- macOS with Capture One Pro: the scripted processing command only exists in the Pro version.
- Python 3 with numpy, tifffile, pillow and opencv-python. By default the tools use miniforge's Python at `~/miniforge3/bin/python3`, or else the system one; the installer takes care of the libraries and accepts any other Python.

## Installation

```
git clone https://github.com/falevian/Herramientas-Capture-One.git
cd Herramientas-Capture-One
bash instalar.sh
```

The installer copies the Python programs to `~/Pictures/Apilado temporal`, `~/Pictures/Grano` and `~/Pictures/Revelado`, installs the libraries, compiles the six AppleScripts into `~/Library/Scripts/Capture One Scripts` and checks that everything responds. Then, in Capture One, refresh the Scripts menu: “Temporal stack”, “Film grain”, “Film development”, “Zone map”, “Median contrast” and “Parametric curve” should appear. `LANGUAGE=es` or `LANGUAGE=en` in front of the command fixes the language of the dialogs, and `PYTHON=/path/to/python3` selects another Python.

The full guide is in [INSTALL.md](INSTALL.md) (plain text in [INSTALL.txt](INSTALL.txt)): step by step installation, how to use each tool, where the files end up, known problems and how to uninstall.

## Contents

```
instalar.sh                          automatic installer
python/
  apilado_temporal.py                stacks the sequence in linear light, optional alignment
  grano.py                           grain model calibrated with the datasheets
  revelado/
    revelado.py                      film development pixel by pixel
    zonas.py                         zone system map
    contraste_mediana.py             contrast with the median fixed
    curva_parametrica.py             tone curve by regions
    espacio_color.py                 reading of images and ICC profiles
    peliculas.py                     spectral models of the films
applescript/
  apilado_capture_one.applescript    “Temporal stack” in the Scripts menu
  grano_capture_one.applescript      “Film grain”
  revelado_capture_one.applescript   “Film development”
  zonas_capture_one.applescript      “Zone map”
  mediana_capture_one.applescript    “Median contrast”
  curva_parametrica_capture_one.applescript   “Parametric curve”
INSTALL.md, INSTALL.txt              full guide
INSTALACION.md, INSTALACION.txt      full guide in Spanish
```

## Use from Terminal

The programs work on their own, without Capture One, on any TIFF, JPEG or PNG file:

```
python3 apilado_temporal.py sequence -o result --ops mean,median,max,hann --curve 2.2 --comparison
python3 apilado_temporal.py sequence -o result --ops median --align --align-model homography --align-region 0,0,1,0.5
python3 grano.py input.tif output.tif --film trix --space auto
python3 revelado.py linear.tif output.tif --film trix --toning selenium --filter red --headroom 2
python3 zonas.py photo.tif --mode scene --headroom 3
python3 contraste_mediana.py apply photo.tif output.tif --contrast 1.3
python3 curva_parametrica.py graph curve.png --highlights -40 --shadows 40
```

With `-h` any of them shows all its options. Messages follow the `LANG` variable or `--lang en|es`, and every option also accepts its Spanish name.

## Background

These tools accompany the site [Fotografía para científicos](https://falevian.github.io/Photographers/) (Photography for scientists), whose source is in [falevian/Photographers](https://github.com/falevian/Photographers). The site is bilingual:

- The film models and the grain are described in [Classic films as ICC profiles](https://falevian.github.io/Photographers/peliculas-icc.html). peliculas.py is the same file as in that repository; the grano.py here adds 16 bit TIFF input and output, keeps the ICC profile and has the `--space` option (sRGB, Adobe RGB, ProPhoto or auto).
- The theory of temporal stacking is in the [long exposure tool](https://falevian.github.io/Photographers/exposicion-larga.html) and its [manual](https://falevian.github.io/Photographers/manual-exposicion-larga.html).

## Licence

MIT. See [LICENSE](LICENSE).
