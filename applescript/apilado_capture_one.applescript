-- Temporal stacking for Capture One / Apilado temporal para Capture One
--
-- Takes the selected variants, exports them as 16 bit TIFF in Adobe RGB (1998) with
-- its own recipe, combines them with apilado_temporal.py and imports the result back
-- into the open document. The comparison sheet opens in Preview. A switch lets you
-- align the photos before stacking (tripod moved, or hand-held) and choose the static
-- region used for the alignment.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements:
--   apilado_temporal.py in ~/Pictures/Apilado temporal/
--   Python with numpy, tifffile, pillow and opencv-python (by default, ~/miniforge3)
--
-- Before running it, copy the same adjustments to the whole sequence.

property minutosEsperaMaxima : 60
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
	set nombreReceta to my t("Temporal stack TIFF 16", "Apilado temporal TIFF 16")
	set titulo to my t("Temporal stack", "Apilado temporal")
	if es then
		set operadoresDisponibles to {"media", "hann", "mediana", "sigma", "maximo", "minimo"}
		set operadoresDefecto to {"media", "mediana"}
		set idioma to "es"
		set nombreRegistro to "registro.txt"
	else
		set operadoresDisponibles to {"mean", "hann", "median", "sigma", "max", "min"}
		set operadoresDefecto to {"mean", "median"}
		set idioma to "en"
		set nombreRegistro to "log.txt"
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Apilado temporal/"
	set rutaScript to carpetaBase & "apilado_temporal.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"

	if not my existe(rutaScript) then
		display alert my t("The stacking program is missing", "Falta el programa de apilado") message my t("Copy apilado_temporal.py into the folder ", "Copia apilado_temporal.py en la carpeta ") & carpetaBase as critical
		return
	end if
	if pythonFijo is not "" then set rutaPython to pythonFijo
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	-- Current selection
	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set colaActiva to processing queue enabled of doc
	end tell
	set n to count of seleccion
	if n < 2 then
		display alert my t("Select at least two images", "Selecciona al menos dos imágenes") message my t("Choose the sequence you want to combine in the browser and run the script again.", "Elige en el navegador la secuencia que quieres combinar y vuelve a lanzar el script.") as warning
		return
	end if
	if not colaActiva then
		display alert my t("The processing queue is paused", "La cola de procesado está en pausa") message my t("Resume it in the Process tool and run the script again.", "Reanúdala en la herramienta de procesado y vuelve a lanzar el script.") as warning
		return
	end if

	-- Operators
	set eleccion to choose from list operadoresDisponibles with title titulo with prompt (my t("Operators for the ", "Operadores para las ") & n & my t(" selected images:", " imágenes seleccionadas:")) default items operadoresDefecto with multiple selections allowed
	if eleccion is false then return
	set AppleScript's text item delimiters to ","
	set ops to eleccion as text
	set AppleScript's text item delimiters to ""

	-- Alignment switch
	set opcionesAlineado to ""
	set textoAlineado to my t("not aligned", "sin alinear")
	set botonNo to my t("Don't align", "No alinear")
	set botonSi to my t("Align", "Alinear")
	set botonCancelar to my t("Cancel", "Cancelar")
	set respuestaAlineado to display dialog my t("Align the photos before combining them?", "¿Alinear las fotos antes de combinarlas?") & return & return & my t("Not needed with a tripod. Hand-held, or if the tripod has moved, yes.", "Con trípode no hace falta. A pulso, o si el trípode se ha movido, sí.") buttons {botonCancelar, botonNo, botonSi} default button botonNo cancel button botonCancelar with title titulo
	if button returned of respuestaAlineado is botonSi then
		set tipoTripode to my t("Tripod that has moved (rotation and shift)", "Trípode que se ha movido (giro y desplazamiento)")
		set tipoPulso to my t("Hand-held (full perspective)", "A pulso (perspectiva completa)")
		set tipoElegido to choose from list {tipoTripode, tipoPulso} with title titulo with prompt my t("How have the photos moved?", "¿Cómo se han movido las fotos?") default items {tipoTripode}
		if tipoElegido is false then return
		if (item 1 of tipoElegido) is tipoPulso then
			set modelo to "homography"
		else
			set modelo to "euclidean"
		end if

		set zonaToda to my t("Whole image", "Toda la imagen")
		set zonaSuperior to my t("Upper half (water or movement below)", "Mitad superior (agua o movimiento abajo)")
		set zonaInferior to my t("Lower half (clouds above)", "Mitad inferior (nubes arriba)")
		set zonaCentral to my t("Central band", "Franja central")
		set zonaMedida to my t("Custom", "Personalizada")
		set zonaElegida to choose from list {zonaToda, zonaSuperior, zonaInferior, zonaCentral, zonaMedida} with title titulo with prompt my t("Static region used for the alignment. Leave out water, clouds and anything that moves:", "Zona estática que se usará para alinear. Deja fuera el agua, las nubes y todo lo que se mueva:") default items {zonaToda}
		if zonaElegida is false then return
		set z to item 1 of zonaElegida
		set zonaTexto to ""
		if z is zonaSuperior then
			set zonaTexto to "0,0,1,0.5"
		else if z is zonaInferior then
			set zonaTexto to "0,0.5,1,1"
		else if z is zonaCentral then
			set zonaTexto to "0,0.33,1,0.67"
		else if z is zonaMedida then
			set respuestaZona to display dialog my t("Rectangle as x0,y0,x1,y1 in fractions of the image (0,0 is the top left corner and 1,1 the bottom right):", "Rectángulo como x0,y0,x1,y1 en fracciones de la imagen (0,0 es la esquina superior izquierda y 1,1 la inferior derecha):") default answer "0,0,1,0.5" with title titulo
			set zonaTexto to text returned of respuestaZona
		end if

		set opcionesAlineado to " --align --align-model " & modelo
		if zonaTexto is not "" then set opcionesAlineado to opcionesAlineado & " --align-region " & quoted form of zonaTexto
		set textoAlineado to my t("aligned ", "alineado ") & modelo
	end if

	-- Folders for this stack
	set marca to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("stack_", "apilado_") & marca & "/"
	set carpetaEntrada to carpetaRun & my t("input/", "entrada/")
	set carpetaSalida to carpetaRun & my t("result/", "resultado/")
	do shell script "mkdir -p " & quoted form of carpetaEntrada & " " & quoted form of carpetaSalida
	set carpetaEntradaA to (POSIX file carpetaEntrada) as alias

	-- Export recipe
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
			-- Capture One validates the general output folder of the document when processing,
			-- and in a catalog it may be relative or missing. It is pointed temporarily at our
			-- folder, the recipe uses that location, and the original is restored at the end.
			set salidaOriginal to output
			try
				set output to carpetaEntradaA
			on error msg
				display alert my t("Could not change the output folder of the document", "No pude cambiar la carpeta de salida del documento") message msg as critical
				return
			end try
			set root folder type of r to output location
			set output sub folder of r to ""
			set output sub name of r to ""
			set output name format of r to "[Image Name]"
			set existing files of r to add suffix
		end tell

		-- Processing
		repeat with v in seleccion
			try
				set resultado to process (contents of v) recipe nombreReceta
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert my t("Error sending the images to process", "Error al enviar las imágenes a procesar") message msg & return & my t("Output folder: ", "Carpeta de salida: ") & carpetaEntrada as critical
				return
			end try
			if resultado starts with "ERROR" then
				my restaurarSalida(doc, salidaOriginal)
				display alert my t("Processing error", "Error al procesar") message resultado as critical
				return
			end if
		end repeat
	end tell

	-- Wait until all jobs are done and all the TIFF files are there
	set limite to (current date) + minutosEsperaMaxima * 60
	repeat
		delay 2
		set nTif to (do shell script "ls " & quoted form of carpetaEntrada & " | grep -ci '\\.tif$' || true") as integer
		tell application "Capture One" to set pendientes to count of jobs of doc
		if nTif ≥ n and pendientes = 0 then exit repeat
		if (current date) > limite then
			my restaurarSalida(doc, salidaOriginal)
			display alert my t("Processing is taking too long", "El procesado está tardando demasiado") message (nTif as text) & my t(" of ", " de ") & n & my t(" images exported in ", " imágenes exportadas en ") & carpetaEntrada as warning
			return
		end if
	end repeat
	delay 2
	my restaurarSalida(doc, salidaOriginal)

	-- Stacking
	set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " " & quoted form of carpetaEntrada & " -o " & quoted form of carpetaSalida & " --ops " & ops & opcionesAlineado & " --curve 2.2 --comparison --lang " & idioma & " --temp " & quoted form of carpetaRun & " 2>&1"
	with timeout of 7200 seconds
		try
			set registro to do shell script orden
		on error msg
			display alert my t("Stacking error", "Error en el apilado") message msg as critical
			return
		end try
	end timeout

	-- The comparison sheet stays out of the folder that is imported
	do shell script "mv " & quoted form of (carpetaSalida & "comparison.jpg") & " " & quoted form of carpetaRun & " 2>/dev/null || true"

	-- Import of the result: several ways of giving the source are tried
	set rutaSinBarra to text 1 thru -2 of carpetaSalida
	set listaTif to paragraphs of (do shell script "find " & quoted form of rutaSinBarra & " -maxdepth 1 -iname '*.tif' | sort")
	set importado to false
	set errores to ""
	tell application "Capture One"
		try
			import doc source rutaSinBarra
			set importado to true
		on error m1
			set errores to errores & my t("Folder as text: ", "Carpeta como texto: ") & m1 & return
		end try
		if not importado then
			try
				import doc source listaTif
				set importado to true
			on error m2
				set errores to errores & my t("List of files: ", "Lista de archivos: ") & m2 & return
			end try
		end if
		if not importado then
			try
				repeat with f in listaTif
					import doc source (contents of f)
				end repeat
				set importado to true
			on error m3
				set errores to errores & my t("File by file: ", "Archivo a archivo: ") & m3 & return
			end try
		end if
	end tell
	if not importado then
		do shell script "open " & quoted form of carpetaSalida
		display alert my t("The stack is done, but I could not import it", "El apilado está hecho, pero no pude importarlo") message my t("I am opening the folder so you can import it by hand.", "Te abro la carpeta para que lo importes a mano.") & return & return & errores as warning
	end if

	do shell script "open " & quoted form of (carpetaRun & "comparison.jpg") & " 2>/dev/null || true"
	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & nombreRegistro)
	display notification (my t("Stack of ", "Apilado de ") & n & my t(" images with ", " imágenes con ") & ops & ", " & textoAlineado) with title titulo
end run

on restaurarSalida(doc, salidaOriginal)
	try
		tell application "Capture One" to set output of doc to salidaOriginal
	end try
end restaurarSalida

on existe(ruta)
	try
		do shell script "test -e " & quoted form of ruta
		return true
	on error
		return false
	end try
end existe
