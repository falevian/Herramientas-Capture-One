# Tools for Capture One

*[Leer en español](README.es.md)*

Two tools for the Scripts menu of Capture One Pro on macOS:

- **Temporal stack.** Combines a sequence of photos, shot on a tripod or hand-held, with temporal operators computed pixel by pixel in linear light: mean, Hann-weighted mean, median, sigma-clipped mean, maximum and minimum. It gives a synthetic long exposure without a neutral density filter, removes transient things (people, cars, birds) or builds up light trails. If the tripod has moved or the sequence is hand-held, it first aligns the photos (pyramidal ECC registration, euclidean or homography) and crops the borders left without data.
- **Film grain.** Adds to each selected image a grain physically scaled to the chosen film (Tri-X, Kodachrome 64 and 25, Velvia 50, Pro 400H) and to the crop of the photo: an image cropped to half is treated as an enlarged half frame, and the grain looks proportionally larger. The amplitude is calibrated against the datasheet rms granularity, and the grain depends on tone as it does on slide film or on a print from a negative.

Both work the same way: they export the selected variants with all their adjustments as 16 bit TIFF in Adobe RGB (1998), process them with a Python program and import the result back into the open document. The dialogs follow the macOS language, English or Spanish.

## Requirements

- macOS with Capture One Pro: the scripted processing command only exists in the Pro version.
- Python 3 with numpy, tifffile, pillow and opencv-python. By default the tools use miniforge's Python at `~/miniforge3/bin/python3`, or else the system one; the installer takes care of the libraries and accepts any other Python.

## Installation

```
git clone https://github.com/falevian/Herramientas-Capture-One.git
cd Herramientas-Capture-One
bash instalar.sh
```

The installer copies the Python programs to `~/Pictures/Apilado temporal` and `~/Pictures/Grano`, installs the libraries, compiles the two AppleScripts into `~/Library/Scripts/Capture One Scripts` and checks that everything responds. Then, in Capture One, refresh the Scripts menu: “Temporal stack” and “Film grain” should appear. `LANGUAGE=es` or `LANGUAGE=en` in front of the command fixes the language of the dialogs, and `PYTHON=/path/to/python3` selects another Python.

The full guide is in [INSTALL.md](INSTALL.md) (plain text in [INSTALL.txt](INSTALL.txt)): step by step installation, how to use each tool, where the files end up, known problems and how to uninstall.

## Contents

```
instalar.sh                        automatic installer
python/
  apilado_temporal.py              stacks the sequence in linear light, optional alignment
  grano.py                         grain model calibrated with the datasheets
applescript/
  apilado_capture_one.applescript  “Temporal stack” in the Scripts menu
  grano_capture_one.applescript    “Film grain” in the Scripts menu
INSTALL.md, INSTALL.txt            full guide
INSTALACION.md, INSTALACION.txt    full guide in Spanish
```

## Use from Terminal

Both programs work on their own, without Capture One, on any folder of TIFF, JPEG or PNG files:

```
python3 apilado_temporal.py sequence -o result --ops mean,median,max,hann --curve 2.2 --comparison
python3 apilado_temporal.py sequence -o result --ops median --align --align-model homography --align-region 0,0,1,0.5
python3 grano.py input.tif output.tif --film trix --space adobergb
python3 grano.py input.jpg web.jpg --film k64 --output-width 2000
```

With `-h` either program shows all its options. Messages follow the `LANG` variable or `--lang en|es`, and every option also accepts its Spanish name.

## Background

These tools accompany the site [Fotografía para científicos](https://falevian.github.io/Photographers/) (Photography for scientists), whose source is in [falevian/Photographers](https://github.com/falevian/Photographers). The site is bilingual:

- The grain model is described in [Classic films as ICC profiles](https://falevian.github.io/Photographers/peliculas-icc.html). The version in this repository adds 16 bit TIFF input and output, keeps the ICC profile and has the `--space` option to work in Adobe RGB.
- The theory of temporal stacking is in the [long exposure tool](https://falevian.github.io/Photographers/exposicion-larga.html) and its [manual](https://falevian.github.io/Photographers/manual-exposicion-larga.html).

## Licence

MIT. See [LICENSE](LICENSE).
