# Photography tools for Capture One

This package adds six tools to the Scripts menu of Capture One on macOS.

“Temporal stack” combines a sequence with a temporal operator (mean, median, maximum and others) to obtain a synthetic long exposure or to remove transient things, with optional alignment for hand-held sequences.

“Film grain” adds to each image a physically scaled grain that depends on the chosen film (Tri-X, Kodachrome, Velvia, Pro 400H) and on the crop of the photo.

“Film development” applies the spectral model of peliculas.py evaluated pixel by pixel, with headroom for the shoulder of the film above diffuse white, colour filters simulated spectrally for black and white, and optional grain of the same film.

“Zone map” draws the zone system of an image, in false colour and as contour lines, to decide dodging and burning.

“Median contrast” raises or lowers the contrast while keeping fixed the tone at the median of the lightness, so the image gets neither lighter nor darker in that sense. It can write the curve into Capture One, where it stays editable, or apply it in Python.

“Parametric curve” writes into the Luma curve a curve by regions, like Lightroom's: highlights, lights, darks and shadows, with adjustable splits.

The first five export the selected variants as 16 bit TIFF and process them with a Python program, but they hand back different results. The temporal stack, the film grain and the film development import new TIFF files into the open document. The zone map opens its two images in Preview and changes nothing in the catalog. The median contrast, in its Capture One mode, writes an editable Luma curve into the image or the selected layer and creates no new file: it only exports small temporary copies to measure the median. In its Python mode it imports a new TIFF like the first three. The parametric curve exports nothing: it computes the curve in Python and writes it straight into the Luma curve.

The dialogs appear in English or Spanish. By default they follow the language of macOS; the installer can fix one or the other.

## What the package contains

```
Herramientas-Capture-One/
  README.md, README.es.md           short presentation, in English and Spanish
  INSTALL.md, INSTALL.txt           this guide, in Markdown and plain text
  INSTALACION.md, INSTALACION.txt   the same guide in Spanish
  LICENSE                           MIT licence
  instalar.sh                       automatic installer
  python/
    apilado_temporal.py             stacks the sequence in linear light, optional alignment
    grano.py                        grain model calibrated with the datasheets
    revelado/
      revelado.py                   film development pixel by pixel
      zonas.py                      zone system map
      contraste_mediana.py          contrast with the median fixed
      curva_parametrica.py          tone curve by regions
      espacio_color.py              reading of images and ICC profiles
      peliculas.py                  spectral models of the films
  applescript/
    apilado_capture_one.applescript
    grano_capture_one.applescript
    revelado_capture_one.applescript
    zonas_capture_one.applescript
    mediana_capture_one.applescript
    curva_parametrica_capture_one.applescript
```

## What you need before installing

macOS with Capture One Pro, because the scripted processing command only exists in the Pro version. You also need Python 3: by default the tools use miniforge's at `~/miniforge3/bin/python3` and, if it is not there, the system one at `/usr/bin/python3`. The required libraries are numpy, tifffile, pillow and opencv-python, and the installer takes care of them. The AppleScript compiler, `osacompile`, comes with macOS and does not need Xcode.

## Automatic installation

Download the repository from GitHub (“Code” button, “Download ZIP”), unzip it in Downloads, open Terminal and run:

```
cd ~/Downloads/Herramientas-Capture-One-main
bash instalar.sh
```

With git you can clone it instead of downloading the zip:

```
git clone https://github.com/falevian/Herramientas-Capture-One.git
cd Herramientas-Capture-One
bash instalar.sh
```

The installer creates the folders, copies the Python programs, installs the libraries, compiles the six scripts into the Capture One scripts folder and checks that everything responds. If there was already a different version of grano.py, revelado.py, zonas.py, contraste_mediana.py, curva_parametrica.py, espacio_color.py or peliculas.py in its folder, it keeps it with the suffix `_anterior` before replacing it.

Two optional variables change the installation:

```
LANGUAGE=en bash instalar.sh                                 dialogs always in English
LANGUAGE=es bash instalar.sh                                 dialogs always in Spanish
PYTHON=~/miniforge3/envs/Photo/bin/python3 bash instalar.sh  use another Python, for example a conda environment
```

The installer writes the chosen language and Python into the compiled scripts, so nothing has to be edited by hand. If there was a copy of the scripts under their names in the other language, it removes it so that they do not appear twice in the menu.

When it finishes, open Capture One and refresh the Scripts menu. “Temporal stack”, “Film grain”, “Film development”, “Zone map”, “Median contrast” and “Parametric curve” should appear (“Apilado temporal”, “Grano de película”, “Revelado de película”, “Mapa de zonas”, “Contraste en la mediana” and “Curva paramétrica” when the dialogs are in Spanish).

## Step by step installation

If you prefer to do it by hand, from the unzipped folder:

```
cd ~/Downloads/Herramientas-Capture-One-main   # or the folder cloned with git

mkdir -p ~/Pictures/"Apilado temporal" ~/Pictures/Grano ~/Pictures/Revelado ~/Library/Scripts/"Capture One Scripts"

cp python/apilado_temporal.py ~/Pictures/"Apilado temporal"/
cp python/grano.py ~/Pictures/Grano/
cp python/revelado/*.py ~/Pictures/Revelado/

~/miniforge3/bin/python3 -m pip install numpy tifffile pillow opencv-python

osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Temporal stack.scpt" applescript/apilado_capture_one.applescript
osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Film grain.scpt" applescript/grano_capture_one.applescript
osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Film development.scpt" applescript/revelado_capture_one.applescript
osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Zone map.scpt" applescript/zonas_capture_one.applescript
osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Median contrast.scpt" applescript/mediana_capture_one.applescript
osacompile -o ~/Library/Scripts/"Capture One Scripts"/"Parametric curve.scpt" applescript/curva_parametrica_capture_one.applescript
```

`cp` and `osacompile` print nothing when everything goes well. Scripts compiled this way follow the language of macOS and use the default Python; to fix them, edit the `idiomaFijo` and `pythonFijo` lines at the top of each AppleScript before compiling (for example `property idiomaFijo : "en"`).

The folder names `Apilado temporal`, `Grano` and `Revelado` are the same in both languages: the scripts look for the Python programs there.

## How to check that everything is in place

```
ls ~/Pictures/"Apilado temporal" ~/Pictures/Grano ~/Pictures/Revelado
ls -l ~/Library/Scripts/"Capture One Scripts"
~/miniforge3/bin/python3 -c "import numpy, tifffile, PIL, cv2; print('Libraries OK')"
~/miniforge3/bin/python3 ~/Pictures/Revelado/revelado.py --check --film k64
```

The first command must show the Python programs, the second the six `.scpt` files with today's date, the third the libraries message and the fourth the error of the spectral table of the development, which must stay below 0.1 ΔE.

## How to use the temporal stack

First, equalise the adjustments of the whole sequence: adjust one photo and copy the adjustments to the others. Then select the sequence in the browser, open the Scripts menu and choose “Temporal stack”. A list of operators appears, in which you can tick several at once:

1. mean: the classic long exposure, with a rectangular shutter.
2. hann: mean weighted with a Hann window, which softens the start and the end and removes the side lobes of the sinc.
3. median: removes transient things, such as people, cars or birds.
4. sigma: mean that discards outliers; removes transient things with less noise than the median.
5. max: lighten mode, for light trails and star trails.
6. min: darken mode.

Next comes the alignment switch, with the buttons “Don't align” and “Align”. With a tripod there is no need to align. If you choose to align, the script asks how the photos have moved: “Tripod that has moved” uses a rotation and shift model, and “Hand-held” adds scale and full perspective (homography). Then it asks for the static region to use for the alignment: the whole image, the upper half, the lower half, a central band or a custom rectangle. Leave out water, clouds and anything that moves, because otherwise the alignment tries to follow the waves. When aligning, the borders that do not have data in all the photos are cropped, so the result comes out slightly smaller than the original.

The script exports the images in Adobe RGB (1998), waits for the queue to finish, aligns if you asked for it, combines in linear light, imports the resulting TIFF files and opens a comparison sheet with all the chosen operators in Preview. The program's messages (operators, alignment, crop) are kept in `log.txt`. Median and sigma need to keep the whole stack on disk while computing: one hundred 24 megapixel photos take about 14 GB of temporary space, deleted at the end.

## How to use the film grain

Select one or more developed images, open the Scripts menu and choose “Film grain”. The script asks for the film (trix, k64, k25, velvia50, pro400h or generic) and the intensity, where 1 is the datasheet granularity. For negative films (trix, pro400h), 1 also includes the gain of printing on paper; if it looks too strong, 0.5 to 0.75 is a good range.

Each image is exported in Adobe RGB (1998), receives the grain and is imported with the film name added, for example `L1000123_grain_trix.tif`. The grain size is computed from the crop of each variant, taking 36 mm as the long side of the sensor: a photo cropped to half is treated as half a frame and the grain looks proportionally larger, as when enlarging that part of a negative. With another camera format, change the `ladoSensorMm` line of the AppleScript.

The model works by FFT at full resolution. With 60 megapixel files each image needs several gigabytes of memory and takes a while, so try a single photo first. Grain is judged at 100 %: a viewer that downsizes the image with a poor filter turns fine grain into blotches.

## How to use the film development

The development uses the same models as the ICC profiles of peliculas.py, but evaluates them directly at each pixel. In Capture One the image must have the normal camera profile, without a film profile; if the script detects a Kodachrome, Velvia, Tri-X or PRO 400H profile it stops, because the film would be applied twice. There is no need to touch the curve: the script sets Linear Response while exporting and then puts it back as it was.

Select the images, open the Scripts menu and choose “Film development”. The script asks for the film. With Tri-X it also asks for the toning (neutral, cold, warm, sepia or selenium) and for the colour filter in front of the lens; with the slides, where the result will be viewed, because a slide was meant to be projected in the dark and on a monitor the contrast should be lowered. Then it asks for the exposure of the film in stops (0 is normal; negative values give a denser, more saturated image) and whether to add the grain of the same film.

While exporting, the script lowers the exposure two stops and gives them back in Python before the model. This way the model receives what lies up to two stops above diffuse white, which is where the shoulder of the film lives, and the highlights are compressed smoothly instead of being clipped. An ICC profile cannot do this, because its input is clipped at white.

The colour filters multiply the spectral sensitivity of Tri-X by the transmittance of the filter and fit the exposure again, compensating the filter factor on a neutral grey, as when opening the aperture by what the factor says. The transmittances approximate those of Wratten 8, 15, 21, 25, 29, 11 and 47; the resulting factors for yellow (about 1 stop), red (2.8) and deep red (3.9) match the usual ones. From Terminal a measured transmittance can be used with `--filter-csv`.

Each image is imported with the film name added, and with `_grain` if grain was requested. The grain is applied after the development, with the same film and the size computed from the crop.

The ICC profile is still useful for editing, because it shows in real time. The suggested way of working is to edit with the film's ICC profile to see where the image is going, go back to the normal camera profile and do the final development with the script.

## How to use the zone map

Select one or more images, open the Scripts menu and choose “Zone map”. There are three modes.

“The print, as developed” reads the image with all its adjustments and spreads the zones in equal steps of lightness, ten units of L* per zone, between black (zone 0) and white (zone X). With this convention zone V falls at L* 50, which corresponds to an 18 % reflectance, middle grey. This is the mode to decide dodging and burning.

“The scene, like a light meter” is the reading in linear light: one stop per zone and middle grey in zone V. The script temporarily sets Linear Response and lowers the exposure three stops so as not to clip the high zones, and then puts everything back as it was.

“What a Tri-X print at grade 2 would give” inverts a modelled print of Tri-X in D-76 printed on Multigrade IV at grade 2: it tells in which zone of the scene each tone should have been exposed to obtain it on that print. It shows how that system compresses highlights and shadows.

For each image two files open in Preview. The false colour map has below it the legend with the percentage of the area in each zone; zone V is neutral grey so that middle grey is recognised at a glance, and clipped highlights and shadows are marked in magenta and blue. The second file is the grey image with the boundaries between zones drawn as contour lines, one colour per boundary. The text in the images follows the language of the dialogs.

## How to use the median contrast

The idea rests on a simple property: the median commutes with any increasing function. If a curve leaves the tone at the median fixed, the median of the resulting image is exactly the same, so the contrast changes without the image getting lighter or darker in that sense. The mean does move a little, and the report says so.

The curve is a logistic with its pivot at the median: in normalised lightness x = L*/100, with the median at m, logit(y) = logit(m) + c (logit(x) − logit(m)). It leaves black, white and the median fixed, it is increasing for any value of c, and its slope at the median is exactly c: with c above 1 the contrast rises in an S shape, and with c below 1 it falls.

Select the images, open the Scripts menu and choose “Median contrast”. The script asks for the contrast (soft 1.15, medium 1.3, strong 1.5, lower to 0.8, or another value) and how to apply it.

The script works on the layer you have selected. If it is the image layer, the contrast applies to the whole photo. If it is an adjustment layer with a mask (drawn, gradient, luminosity or AI generated), the median is measured only inside the mask and the curve is written into the Luma curve of that layer. Capture One does not allow the mask to be exported, so the script works it out: it exports two small versions with the curve of the layer flattened, one to black and one to white, and the difference between them gives the weight of the mask at each pixel, feathering included. The median is computed weighted by that weight. Clone and heal layers do not accept curves, and the Python mode always works on the whole image.

“Luma curve in Capture One” writes the curve into the Curve tool, Luma channel, which changes lightness without touching saturation, and leaves it editable. As Capture One applies its curves in its own scale, the script measures instead of assuming: it exports a small version without curve, computes the median, places the curve with the pivot and exports again until the median with the curve matches the one without it, usually in three or four exports. It replaces any Luma curve the image had; if something fails, it leaves it as it was.

“New TIFF with Python” exports the full image, applies the exact curve on L* keeping chromaticity and imports the result with `_contrast` in the name.

At the end a report shows the median kept, the remaining error and, in the Capture One mode, where the pivot ended up on the scale of its curve.

## How to use the parametric curve

It is Lightroom's curve by regions, which Capture One does not have. Four sliders, from -100 to +100, act on four regions of the tonal axis: shadows, darks, lights and highlights, separated by three splits that are at 25, 50 and 75 by default. Each slider raises or lowers the curve with a smooth bell that covers its region and overlaps its neighbours by up to half its width, so the regions blend without steps. Black and white stay fixed. If an extreme combination were to invert tones somewhere, the script reduces all the amplitudes equally until the curve is increasing again, and says so.

Select the images, open the Scripts menu and choose “Parametric curve”. There are presets (soft and strong S contrast, recover highlights and open shadows, soft highlights, open shadows) and a custom option that asks for the four values and the three splits separated by semicolons. The curve is written into the Luma curve of the selected layer, or of the image if the image layer is selected, replacing any curve there, and it stays editable. It exports nothing, so it is instant.

The splits are on the scale of Capture One's curve. If you want the central split to fall on the median of the photo, the median contrast script tells you where the median lies on that scale.

## Where the files end up

Each run creates its own folder with the date and time:

```
~/Pictures/Apilado temporal/stack_YYYYMMDD_HHMMSS/
    input/            TIFF files exported by Capture One
    result/           stacked TIFF files, the ones that are imported
    comparison.jpg    comparison sheet
    log.txt           program output, with the crop applied if aligned

~/Pictures/Grano/grain_YYYYMMDD_HHMMSS/
    input_1/, input_2/ ...       exported TIFF files
    result/                      TIFF files with grain, the ones that are imported
    log.txt                      parameters used for each image

~/Pictures/Revelado/development_YYYYMMDD_HHMMSS/
    input_1/, input_2/ ...       TIFF files exported in linear light
    work/                        intermediate developments, before the grain
    result/                      final TIFF files, the ones that are imported
    log.txt                      development and grain parameters

~/Pictures/Revelado/zones_YYYYMMDD_HHMMSS/
    input_1/, input_2/ ...       exported TIFF files
    *_zones_map.jpg, *_zones_contours.jpg
    log.txt                      percentage of each zone

~/Pictures/Revelado/median_YYYYMMDD_HHMMSS/
    measure_*/                   small exports used to measure (Capture One mode)
    mask_*                       black and white exports and the mask worked out from the layer
    input_*/                     full exports (Python mode)
    result/                      TIFF files with the contrast applied (Python mode)
    log.txt                      report for each image
```

With the dialogs in Spanish the names are `apilado_…`, `grano_…`, `revelado_…`, `zonas_…`, `mediana_…`, `entrada`, `trabajo`, `medida`, `mascara`, `resultado` and `registro.txt`. The input and work folders can be deleted once you have checked the result.

## Use from Terminal, without Capture One

The programs work on their own with any TIFF, JPEG or PNG file. With `-h` any of them shows all its options. Messages and help follow the `LANG` variable, or `--lang en` / `--lang es`. Every option also accepts its Spanish spelling (`--curva`, `--alinear`, `--pelicula`, `--intensidad`, `--virado`…).

```
cd ~/Pictures/"Apilado temporal"
~/miniforge3/bin/python3 apilado_temporal.py sequence_folder -o result --ops mean,median,max,hann --curve 2.2 --comparison
~/miniforge3/bin/python3 apilado_temporal.py handheld_sequence -o result --ops median,mean --align --align-model homography --align-region 0,0,1,0.6 --comparison
```

`--curve` gives the encoding of the input images: 2.2 for Adobe RGB, 1.8 for ProPhoto, srgb for sRGB. `--align` aligns each photo with the first one (pyramidal ECC, with an initial estimate by phase correlation). `--align-model` selects the transformation: `euclidean` (rotation and shift, the default), `translation`, `affine` or `homography` for hand-held sequences. If there is moving water or clouds, add `--align-region 0,0,1,0.5` (fractions x0,y0,x1,y1) so that only a static region is used. `--no-crop` keeps the original size instead of cropping the borders without data. The results are written as `stack_<operator>_n<N>.tif`; the operators also accept the Spanish names `media`, `mediana`, `maximo` and `minimo`.

```
cd ~/Pictures/Grano
~/miniforge3/bin/python3 grano.py input.tif output.tif --film trix --space auto
~/miniforge3/bin/python3 grano.py input.jpg web.jpg --film k64 --output-width 2000
```

In grano.py, `--space auto` takes the colour space (sRGB, Adobe RGB or ProPhoto) from the embedded profile.

```
cd ~/Pictures/Revelado
~/miniforge3/bin/python3 revelado.py input.tif output.tif --film k64 --room dim
~/miniforge3/bin/python3 revelado.py input.tif output.tif --film trix --toning selenium --filter red --headroom 2
~/miniforge3/bin/python3 revelado.py --check --film velvia50
```

In revelado.py the input must be in linear light (Linear Response in Capture One). `--headroom` gives how many stops the exposure was lowered when exporting. `--white paper` sends the base of the paper or slide to white instead of diffuse white, as on a real print. `--exact` computes the full spectral integral at every pixel (slow, for verification) and `--check` measures the error of the spectral table.

```
~/miniforge3/bin/python3 zonas.py photo.tif
~/miniforge3/bin/python3 zonas.py photo.tif --mode scene --headroom 3 --smoothing 2
~/miniforge3/bin/python3 zonas.py photo.tif --mode film --reference pro400h --size 0
```

In zonas.py, `--size` sets the long side of the generated images (3000 pixels by default, 0 for the original size) and `--smoothing` simplifies the contour lines. The images are named `<photo>_zones_map.jpg` and `<photo>_zones_contours.jpg`.

```
~/miniforge3/bin/python3 contraste_mediana.py measure photo.tif
~/miniforge3/bin/python3 contraste_mediana.py apply photo.tif output.tif --contrast 1.3
~/miniforge3/bin/python3 contraste_mediana.py apply photo.tif output.tif --contrast 1.3 --method rgb --region 0,0.4,1,1
~/miniforge3/bin/python3 contraste_mediana.py mask black.tif white.tif mask.tif
~/miniforge3/bin/python3 contraste_mediana.py measure photo.tif --mask mask.tif
```

In contraste_mediana.py, `--method rgb` applies the curve channel by channel, which saturates like a film; the pivot is readjusted so that the median of the lightness does not change either. `--region` restricts the computation of the median to a rectangle, for example to leave out a white sky or a black frame, while the curve is applied to the whole image. `points --pivot 46.5 --contrast 1.3` prints the points of the curve for Capture One's Luma curve. `mask` works out the mask of a layer from the two exports with its curve flattened to black and to white, and `measure --mask` gives the weighted median inside it. The commands also have Spanish names: `medir`, `puntos`, `aplicar` and `mascara`.

```
~/miniforge3/bin/python3 curva_parametrica.py points --lights 20 --darks -20
~/miniforge3/bin/python3 curva_parametrica.py graph curve.png --highlights -40 --shadows 40 --splits 20,45,70
```

curva_parametrica.py prints the points of the curve or draws a graph with the regions. In Spanish the commands are `puntos` and `grafico`, and the options `--luces`, `--claros`, `--oscuros`, `--sombras` and `--divisiones`.

## Known problems and how to solve them

The first time each script runs, macOS asks for permission for it to control Capture One. Accept it. If it was refused by mistake, it can be enabled in System Settings, Privacy & Security, Automation.

The message “Invalid process output folder” appears when the catalog has no valid output folder. The scripts avoid it by pointing the document's output temporarily at their own folder and restoring it at the end, but it is worth setting a real output folder in the catalog's output location tool, because any other recipe will give the same error.

If the import fails, the scripts do not stop: they open the result folder and show what Capture One answered, so you can import it by hand. Note that when importing, Capture One applies the document's import settings, so in a catalog it may copy the files to the location you have defined.

If the processing queue is paused, the scripts warn and do nothing. Just resume it.

If the development or the zone map in scene mode warn that they cannot set the Linear Response curve, Capture One uses another name for it in your language. Set it by hand before running the script, or add the name you see to the `curvasLineales` list of the AppleScript and install again.

The development and zone recipes export in ProPhoto RGB so as not to clip saturated colours before the model. If your Capture One does not have that profile under that name, they use Adobe RGB (1998); the programs read the space from the embedded profile, so they work the same.

If the median contrast warns that it cannot write the Luma curve, your version of Capture One does not allow curve points to be created by script; use the New TIFF with Python mode.

## How to update or uninstall

To update, download the new version (or run `git pull` in the cloned folder) and run `bash instalar.sh` again; it replaces the programs and recompiles the scripts.

To uninstall:

```
rm ~/Library/Scripts/"Capture One Scripts"/"Temporal stack.scpt"
rm ~/Library/Scripts/"Capture One Scripts"/"Film grain.scpt"
rm ~/Library/Scripts/"Capture One Scripts"/"Film development.scpt"
rm ~/Library/Scripts/"Capture One Scripts"/"Zone map.scpt"
rm ~/Library/Scripts/"Capture One Scripts"/"Median contrast.scpt"
rm ~/Library/Scripts/"Capture One Scripts"/"Parametric curve.scpt"
rm -r ~/Pictures/"Apilado temporal" ~/Pictures/Grano ~/Pictures/Revelado
```

With the dialogs in Spanish, the scripts are called “Apilado temporal.scpt”, “Grano de película.scpt”, “Revelado de película.scpt”, “Mapa de zonas.scpt”, “Contraste en la mediana.scpt” and “Curva paramétrica.scpt”. The last command also deletes the results saved in those folders, so check them first. The recipes “Temporal stack TIFF 16”, “Film grain TIFF 16”, “Film development TIFF 16”, “Zones TIFF 16” and “Median TIFF 16” (or their Spanish equivalents) can be deleted in Capture One's recipe tool.
