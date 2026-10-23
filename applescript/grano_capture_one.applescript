-- Film grain for Capture One / Grano de película para Capture One
--
-- For each selected variant: exports it as 16 bit TIFF in Adobe RGB (1998) with all
-- its adjustments, adds grain with grano.py and imports the result back.
-- The grain size is computed from the crop: if the photo is cropped, the equivalent
-- frame is smaller and the grain looks proportionally larger.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements:
--   grano.py in ~/Pictures/Grano/
--   Python with numpy, pillow and tifffile (by default, ~/miniforge3)

property peliculas : {"trix", "k64", "k25", "velvia50", "pro400h", "generic"}
property ladoSensorMm : 36
property minutosEsperaPorFoto : 10
property es : false
-- instalar.sh fills in these two: language ("es", "en" or "" = system language)
-- and the Python to use ("" = ~/miniforge3/bin/python3, or else /usr/bin/python3)
property idiomaFijo : ""
property pythonFijo : ""

on t(textoIngles, textoEspanol)
	if es then return textoEspanol
	return textoIngles
end t

on run
	if idiomaFijo is "" then
		set es to (user locale of (system info)) starts with "es"
	else
		set es to idiomaFijo is "es"
	end if
	set nombreReceta to my t("Film grain TIFF 16", "Grano TIFF 16")
	set titulo to my t("Film grain", "Grano de película")
	if es then
		set idioma to "es"
		set nombreRegistro to "registro.txt"
	else
		set idioma to "en"
		set nombreRegistro to "log.txt"
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Grano/"
	set rutaScript to carpetaBase & "grano.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"

	if not my existe(rutaScript) then
		display alert my t("grano.py is missing", "Falta grano.py") message my t("Copy grano.py into the folder ", "Copia grano.py en la carpeta ") & carpetaBase as critical
		return
	end if
	if pythonFijo is not "" then set rutaPython to pythonFijo
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set colaActiva to processing queue enabled of doc
	end tell
	set n to count of seleccion
	if n < 1 then
		display alert my t("No image is selected", "No hay ninguna imagen seleccionada") as warning
		return
	end if
	if not colaActiva then
		display alert my t("The processing queue is paused", "La cola de procesado está en pausa") message my t("Resume it in the Process tool and run the script again.", "Reanúdala en la herramienta de procesado y vuelve a lanzar el script.") as warning
		return
	end if

	-- Film and intensity
	set eleccion to choose from list peliculas with title titulo with prompt (my t("Film for ", "Película para ") & n & my t(" image(s):", " imagen(es):")) default items {"trix"}
	if eleccion is false then return
	set pelicula to item 1 of eleccion
	set respuesta to display dialog my t("Intensity (1 = the datasheet granularity):", "Intensidad (1 = la de la hoja técnica):") default answer "1.0" with title titulo
	set intensidad to my reemplazar(text returned of respuesta, ",", ".")

	-- Folders
	set marca to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("grain_", "grano_") & marca & "/"
	set carpetaSalida to carpetaRun & my t("result/", "resultado/")
	do shell script "mkdir -p " & quoted form of carpetaSalida

	-- Recipe
	tell application "Capture One"
		tell doc
			if not (exists recipe nombreReceta) then
				try
					make new recipe at it with properties {name:nombreReceta}
				on error msg
					display alert my t("Could not create the recipe", "No pude crear la receta") message my t("Create a recipe called \"", "Crea a mano una receta llamada \"") & nombreReceta & my t("\" by hand and run the script again. Details: ", "\" y vuelve a lanzar el script. Detalle: ") & msg as critical
					return
				end try
			end if
			set r to recipe nombreReceta
			set enabled of r to true
			set output format of r to TIFF
			set bits of r to 16
			set TIFF compression of r to Uncompressed
			set color profile of r to "Adobe RGB (1998)"
			set sharpening of r to no output sharpening
			set scaling method of r to Fixed
			set primary scaling value of r to 100
			set upscale of r to false
			set root folder type of r to output location
			set output sub folder of r to ""
			set output sub name of r to ""
			set output name format of r to "[Image Name]"
			set existing files of r to add suffix
			set salidaOriginal to output
		end tell
	end tell

	-- One variant at a time: each export lands in its own folder and we know its crop
	set k to 0
	set registro to ""
	repeat with v in seleccion
		set k to k + 1
		set carpetaEntrada to carpetaRun & my t("input_", "entrada_") & k & "/"
		do shell script "mkdir -p " & quoted form of carpetaEntrada
		set carpetaEntradaA to (POSIX file carpetaEntrada) as alias

		-- Equivalent size on the film, from the crop
		set anchoMm to my anchoEquivalente(contents of v)

		tell application "Capture One"
			try
				set output of doc to carpetaEntradaA
				set resultado to process (contents of v) recipe nombreReceta
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert my t("Error sending image ", "Error al enviar la imagen ") & k & my t(" to process", " a procesar") message msg as critical
				return
			end try
		end tell
		if resultado starts with "ERROR" then
			my restaurarSalida(doc, salidaOriginal)
			display alert my t("Error processing image ", "Error al procesar la imagen ") & k message resultado as critical
			return
		end if

		-- Wait for the export
		set limite to (current date) + minutosEsperaPorFoto * 60
		repeat
			delay 1
			set tif to do shell script "find " & quoted form of carpetaEntrada & " -maxdepth 1 -iname '*.tif' | head -1"
			tell application "Capture One" to set pendientes to count of jobs of doc
			if tif is not "" and pendientes = 0 then exit repeat
			if (current date) > limite then
				my restaurarSalida(doc, salidaOriginal)
				display alert my t("The export of image ", "La exportación de la imagen ") & k & my t(" is taking too long", " está tardando demasiado") as warning
				return
			end if
		end repeat
		delay 1

		-- Grain
		set nombreBase to do shell script "basename " & quoted form of tif & " | sed 's/\\.[Tt][Ii][Ff]*$//'"
		set destino to carpetaSalida & nombreBase & my t("_grain_", "_grano_") & pelicula & ".tif"
		set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " " & quoted form of tif & " " & quoted form of destino & " --film " & pelicula & " --intensity " & quoted form of intensidad & " --space adobergb --width-mm " & anchoMm & " --lang " & idioma & " 2>&1"
		with timeout of 3600 seconds
			try
				set registro to registro & (do shell script orden) & return
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert my t("Error adding grain to image ", "Error al añadir el grano a la imagen ") & k message msg as critical
				return
			end try
		end timeout
	end repeat
	my restaurarSalida(doc, salidaOriginal)

	-- Log with the parameters of each image
	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & nombreRegistro)

	-- Import
	if not my importar(doc, carpetaSalida) then return
	display notification (my t("Grain ", "Grano ") & pelicula & my t(" on ", " en ") & n & my t(" image(s)", " imagen(es)")) with title titulo
end run

-- Long side of the crop in millimetres of film, as text with a decimal point
on anchoEquivalente(v)
	try
		tell application "Capture One"
			set cw to crop width of v
			set ch to crop height of v
			set dims to dimensions of parent image of v
		end tell
		set ladoRecorte to cw
		if ch > ladoRecorte then set ladoRecorte to ch
		set ladoImagen to item 1 of dims
		if (item 2 of dims) > ladoImagen then set ladoImagen to item 2 of dims
		if ladoRecorte ≤ 0 or ladoImagen ≤ 0 or ladoRecorte > ladoImagen then error "out of range"
		set milis to round (ladoSensorMm * ladoRecorte / ladoImagen * 1000)
	on error
		set milis to ladoSensorMm * 1000
	end try
	set parteEntera to milis div 1000
	set parteDecimal to text -3 thru -1 of ("000" & (milis mod 1000))
	return (parteEntera as text) & "." & parteDecimal
end anchoEquivalente

on importar(doc, carpetaSalida)
	set rutaSinBarra to text 1 thru -2 of carpetaSalida
	set listaTif to paragraphs of (do shell script "find " & quoted form of rutaSinBarra & " -maxdepth 1 -iname '*.tif' | sort")
	set errores to ""
	tell application "Capture One"
		try
			import doc source rutaSinBarra
			return true
		on error m1
			set errores to errores & my t("Folder as text: ", "Carpeta como texto: ") & m1 & return
		end try
		try
			import doc source listaTif
			return true
		on error m2
			set errores to errores & my t("List of files: ", "Lista de archivos: ") & m2 & return
		end try
		try
			repeat with f in listaTif
				import doc source (contents of f)
			end repeat
			return true
		on error m3
			set errores to errores & my t("File by file: ", "Archivo a archivo: ") & m3 & return
		end try
	end tell
	do shell script "open " & quoted form of carpetaSalida
	display alert my t("The grain is done, but I could not import it", "El grano está hecho, pero no pude importarlo") message my t("I am opening the folder so you can import it by hand.", "Te abro la carpeta para que lo importes a mano.") & return & return & errores as warning
	return false
end importar

on restaurarSalida(doc, salidaOriginal)
	try
		tell application "Capture One" to set output of doc to salidaOriginal
	end try
end restaurarSalida

on reemplazar(textoOriginal, buscar, poner)
	set AppleScript's text item delimiters to buscar
	set partes to text items of textoOriginal
	set AppleScript's text item delimiters to poner
	set textoOriginal to partes as text
	set AppleScript's text item delimiters to ""
	return textoOriginal
end reemplazar

on existe(ruta)
	try
		do shell script "test -e " & quoted form of ruta
		return true
	on error
		return false
	end try
end existe
