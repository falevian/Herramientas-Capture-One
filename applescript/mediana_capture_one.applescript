-- Median contrast for Capture One / Contraste en la mediana para Capture One
--
-- Raises or lowers the contrast keeping fixed the tone at the median of the
-- lightness, so the image gets neither lighter nor darker in that sense.
--
-- Two modes:
--   Luma curve in Capture One: writes the curve into the Curve tool, Luma channel,
--     where it stays editable. As Capture One applies the curve in its own scale,
--     the script measures: it exports a small version without curve, computes the
--     median, places the curve and exports again until the median with the curve
--     matches the one without it (in a few exports). It replaces any existing Luma
--     curve; if something fails, it leaves it as it was.
--   New TIFF with Python: exports the full image, applies the exact curve on L*
--     with contraste_mediana.py and imports the result.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements: contraste_mediana.py and espacio_color.py in ~/Pictures/Revelado/,
-- and Python with numpy, pillow and tifffile.

property valoresContraste : {"1.15", "1.3", "1.5", "0.8", ""}
property ladoMedida : 1200
property toleranciaLstar : 0.4
property maxIteraciones : 8
property minutosEspera : 10
property es : false
-- instalar.sh fills in these two: language ("es", "en" or "" = system language)
-- and the Python to use ("" = ~/miniforge3/bin/python3, or else /usr/bin/python3)
property idiomaFijo : ""
property pythonFijo : ""
-- set at run time
property nombreReceta : ""
property idioma : "en"

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
	set titulo to my t("Median contrast", "Contraste en la mediana")
	set nombreReceta to my t("Median TIFF 16", "Mediana TIFF 16")
	if es then
		set idioma to "es"
		set nombreRegistro to "registro.txt"
		set nombresContraste to {"Suave (1,15)", "Medio (1,3)", "Fuerte (1,5)", "Bajar el contraste (0,8)", "Otro valor"}
		set nombresModo to {"Curva Luma en Capture One (editable)", "TIFF nuevo con Python"}
	else
		set idioma to "en"
		set nombreRegistro to "log.txt"
		set nombresContraste to {"Soft (1.15)", "Medium (1.3)", "Strong (1.5)", "Lower the contrast (0.8)", "Other value"}
		set nombresModo to {"Luma curve in Capture One (editable)", "New TIFF with Python"}
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaScript to carpetaBase & "contraste_mediana.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"
	if not my existe(rutaScript) then
		display alert my t("contraste_mediana.py is missing", "Falta contraste_mediana.py") message my t("Copy contraste_mediana.py and espacio_color.py into the folder ", "Copia contraste_mediana.py y espacio_color.py en la carpeta ") & carpetaBase as critical
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

	set eleccion to choose from list nombresContraste with title titulo with prompt my t("Contrast at the median (slope of the curve at that point; 1 changes nothing):", "Contraste en la mediana (pendiente de la curva en ese punto; 1 no cambia nada):") default items {item 2 of nombresContraste}
	if eleccion is false then return
	set contraste to item (my indice(item 1 of eleccion, nombresContraste)) of valoresContraste
	if contraste is "" then
		set respuesta to display dialog my t("Slope of the curve at the median (above 1 raises the contrast, below 1 lowers it):", "Pendiente de la curva en la mediana (mayor que 1 sube el contraste, menor que 1 lo baja):") default answer "1.3" with title titulo
		set contraste to my reemplazar(text returned of respuesta, ",", ".")
	end if
	set eleccionModo to choose from list nombresModo with title titulo with prompt my t("How should it be applied?", "¿Cómo se aplica?") default items {item 1 of nombresModo}
	if eleccionModo is false then return
	set enCapture to (item 1 of eleccionModo) is (item 1 of nombresModo)
	set subeContraste to (((my reemplazar(contraste, ".", my separadorDecimal())) as real) > 1)

	set marcaTiempo to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("median_", "mediana_") & marcaTiempo & "/"
	set carpetaSalida to carpetaRun & my t("result/", "resultado/")
	do shell script "mkdir -p " & quoted form of carpetaSalida

	tell application "Capture One"
		set editarTodas to edit all selected variants
		set edit all selected variants to false
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
			try
				set color profile of r to "ProPhoto RGB"
			end try
			if (color profile of r) does not contain "ProPhoto" then set color profile of r to "Adobe RGB (1998)"
			set sharpening of r to no output sharpening
			if enCapture then
				set scaling method of r to Long_Edge
				try
					set scaling unit of r to pixels
				end try
				set primary scaling value of r to ladoMedida
			else
				set scaling method of r to Fixed
				set primary scaling value of r to 100
			end if
			set upscale of r to false
			set root folder type of r to output location
			set output sub folder of r to ""
			set output sub name of r to ""
			set output name format of r to "[Image Name]"
			set existing files of r to add suffix
			set salidaOriginal to output
		end tell
	end tell

	set informe to ""
	set k to 0
	repeat with v in seleccion
		set k to k + 1
		set variante to contents of v
		if enCapture then
			set resultado to my curvaEnCapture(doc, variante, k, carpetaRun, rutaPython, rutaScript, contraste, subeContraste)
		else
			set resultado to my tiffConPython(doc, variante, k, carpetaRun, carpetaSalida, rutaPython, rutaScript, contraste)
		end if
		if resultado starts with "ERROR" then
			my restaurarTodo(doc, salidaOriginal, editarTodas)
			display alert my t("Image ", "Imagen ") & k message (text 7 thru -1 of resultado) as critical
			return
		end if
		set informe to informe & my t("Image ", "Imagen ") & k & ": " & resultado & return
	end repeat
	my restaurarTodo(doc, salidaOriginal, editarTodas)
	do shell script "printf '%s' " & quoted form of informe & " > " & quoted form of (carpetaRun & nombreRegistro)

	if not enCapture then
		if not my importar(doc, carpetaSalida) then return
	end if
	display dialog informe with title titulo buttons {"OK"} default button "OK"
end run

-- ---------------------------------------------------------------- Luma curve mode

on curvaEnCapture(doc, variante, k, carpetaRun, rutaPython, rutaScript, contraste, subeContraste)
	set errorEscritura to my t("ERROR Could not write the Luma curve by script. Try the New TIFF with Python mode.", "ERROR No pude escribir la curva Luma por script. Prueba el modo TIFF nuevo con Python.")
	set puntosOriginales to my leerCurva(variante)
	if not my ponerCurva(variante, {{0, 0}, {100, 100}}) then
		my restaurarCurva(variante, puntosOriginales)
		return errorEscritura
	end if

	-- median without curve
	set m to my medirExportando(doc, variante, carpetaRun & my t("measure_", "medida_") & k & "_0/", rutaPython, rutaScript)
	if m is missing value then
		my restaurarCurva(variante, puntosOriginales)
		return my t("ERROR Could not export and measure the image.", "ERROR No pude exportar y medir la imagen.")
	end if

	-- search for the pivot: first at the median itself, then in steps until the
	-- value is bracketed, and then by false position inside the interval
	set lo to missing value
	set hi to missing value
	set errLo to 0
	set errHi to 0
	set p to m
	set mejorP to m
	set mejorErr to 1.0E+9
	repeat with iter from 1 to maxIteraciones
		if p < 2 then set p to 2
		if p > 98 then set p to 98
		if not my ponerCurva(variante, my puntosCurva(rutaPython, rutaScript, p, contraste)) then
			my restaurarCurva(variante, puntosOriginales)
			return errorEscritura
		end if
		set mp to my medirExportando(doc, variante, carpetaRun & my t("measure_", "medida_") & k & "_" & iter & "/", rutaPython, rutaScript)
		if mp is missing value then
			my restaurarCurva(variante, puntosOriginales)
			return my t("ERROR Could not export and measure the image with the curve.", "ERROR No pude exportar y medir la imagen con la curva.")
		end if
		set e to mp - m
		if my absoluto(e) < mejorErr then
			set mejorErr to my absoluto(e)
			set mejorP to p
		end if
		if my absoluto(e) < toleranciaLstar then exit repeat
		-- with more contrast, if the median goes up the pivot is below it
		if (e > 0) is subeContraste then
			set lo to p
			set errLo to e
		else
			set hi to p
			set errHi to e
		end if
		if lo is missing value then
			set p to p - 8
		else if hi is missing value then
			set p to p + 8
		else
			set p to lo - errLo * (hi - lo) / (errHi - errLo)
			set ancho to hi - lo
			if p < lo + 0.1 * ancho then set p to lo + 0.1 * ancho
			if p > hi - 0.1 * ancho then set p to hi - 0.1 * ancho
		end if
	end repeat
	if mejorP is not p then my ponerCurva(variante, my puntosCurva(rutaPython, rutaScript, mejorP, contraste))
	return my t("median L* ", "mediana L* ") & my redondear(m, 1) & my t(" kept with an error of ", " conservada con un error de ") & my redondear(mejorErr, 2) & my t(" (contrast ", " (contraste ") & contraste & my t(", curve pivot at ", ", pivote de la curva en ") & my redondear(mejorP, 1) & my t(" on the Capture One scale)", " en la escala de Capture One)")
end curvaEnCapture

on medirExportando(doc, variante, carpeta, rutaPython, rutaScript)
	do shell script "mkdir -p " & quoted form of carpeta
	set carpetaA to (POSIX file carpeta) as alias
	tell application "Capture One"
		try
			set output of doc to carpetaA
			set resultado to process variante recipe nombreReceta
		on error msg
			return missing value
		end try
	end tell
	if resultado starts with "ERROR" then return missing value
	set tif to my esperarTif(doc, carpeta, minutosEspera)
	if tif is "" then return missing value
	try
		set salida to do shell script quoted form of rutaPython & " " & quoted form of rutaScript & " measure " & quoted form of tif & " | grep MEDIANA_LSTAR= | cut -d= -f2"
		return (my reemplazar(salida, ".", my separadorDecimal())) as real
	on error
		return missing value
	end try
end medirExportando

on puntosCurva(rutaPython, rutaScript, p, contraste)
	set pTexto to my reemplazar(my redondear(p, 3) as text, ",", ".")
	set lineas to paragraphs of (do shell script quoted form of rutaPython & " " & quoted form of rutaScript & " points --pivot " & pTexto & " --contrast " & contraste)
	set lista to {}
	set sep to my separadorDecimal()
	repeat with l in lineas
		set AppleScript's text item delimiters to ","
		set partes to text items of (contents of l)
		set AppleScript's text item delimiters to ""
		if (count of partes) is 2 then
			set end of lista to {(my reemplazar(item 1 of partes, ".", sep)) as real, (my reemplazar(item 2 of partes, ".", sep)) as real}
		end if
	end repeat
	return lista
end puntosCurva

on leerCurva(variante)
	set lista to {}
	try
		tell application "Capture One"
			set pts to curve points of luma curve of adjustments of variante
			repeat with cp in pts
				set end of lista to {brightness of cp, amount of cp}
			end repeat
		end tell
	end try
	return lista
end leerCurva

-- Replaces the points of the Luma curve; returns whether it worked
on ponerCurva(variante, puntos)
	tell application "Capture One"
		try
			delete every curve point of luma curve of adjustments of variante
		end try
		set restantes to count of curve points of luma curve of adjustments of variante
	end tell
	-- if Capture One keeps the end points, they are adjusted instead of created
	repeat with pt in puntos
		set valorBrillo to item 1 of pt
		set valorCantidad to item 2 of pt
		set hecho to false
		if restantes > 0 then
			tell application "Capture One"
				repeat with cp in (curve points of luma curve of adjustments of variante)
					if my absoluto((brightness of cp) - valorBrillo) < 0.01 then
						set amount of cp to valorCantidad
						set hecho to true
						exit repeat
					end if
				end repeat
			end tell
		end if
		if not hecho then
			try
				tell application "Capture One" to make new curve point at end of curve points of luma curve of adjustments of variante with properties {brightness:valorBrillo, amount:valorCantidad}
			on error
				try
					tell application "Capture One" to tell (luma curve of adjustments of variante) to make new curve point with properties {brightness:valorBrillo, amount:valorCantidad}
				on error
					return false
				end try
			end try
		end if
	end repeat
	-- check: the pivot (or the central point) must be in place
	set central to item (((count of puntos) + 1) div 2) of puntos
	try
		tell application "Capture One"
			repeat with cp in (curve points of luma curve of adjustments of variante)
				if my absoluto((brightness of cp) - (item 1 of central)) < 0.05 and my absoluto((amount of cp) - (item 2 of central)) < 0.05 then return true
			end repeat
		end tell
	end try
	return false
end ponerCurva

on restaurarCurva(variante, puntos)
	if (count of puntos) < 2 then set puntos to {{0, 0}, {100, 100}}
	try
		my ponerCurva(variante, puntos)
	end try
end restaurarCurva

-- ---------------------------------------------------------------- Python TIFF mode

on tiffConPython(doc, variante, k, carpetaRun, carpetaSalida, rutaPython, rutaScript, contraste)
	set carpeta to carpetaRun & my t("input_", "entrada_") & k & "/"
	do shell script "mkdir -p " & quoted form of carpeta
	set carpetaA to (POSIX file carpeta) as alias
	tell application "Capture One"
		try
			set output of doc to carpetaA
			set resultado to process variante recipe nombreReceta
		on error msg
			return "ERROR " & msg
		end try
	end tell
	if resultado starts with "ERROR" then return resultado
	set tif to my esperarTif(doc, carpeta, minutosEspera)
	if tif is "" then return my t("ERROR The export is taking too long.", "ERROR La exportación está tardando demasiado.")
	set nombreBase to do shell script "basename " & quoted form of tif & " | sed 's/\\.[Tt][Ii][Ff]*$//'"
	set destino to carpetaSalida & nombreBase & my t("_contrast.tif", "_contraste.tif")
	try
		set salida to do shell script quoted form of rutaPython & " " & quoted form of rutaScript & " apply " & quoted form of tif & " " & quoted form of destino & " --contrast " & contraste & " --lang " & idioma & " 2>&1"
	on error msg
		return "ERROR " & msg
	end try
	return salida
end tiffConPython

-- ---------------------------------------------------------------- utilities

on restaurarTodo(doc, salidaOriginal, editarTodas)
	try
		tell application "Capture One"
			set output of doc to salidaOriginal
			set edit all selected variants to editarTodas
		end tell
	end try
end restaurarTodo

on esperarTif(doc, carpeta, minutos)
	set limite to (current date) + minutos * 60
	repeat
		delay 0.5
		set tif to do shell script "find " & quoted form of carpeta & " -maxdepth 1 -iname '*.tif' | head -1"
		tell application "Capture One" to set pendientes to count of jobs of doc
		if tif is not "" and pendientes = 0 then
			delay 0.5
			return tif
		end if
		if (current date) > limite then return ""
	end repeat
end esperarTif

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
	display alert my t("The contrast is applied, but I could not import it", "El contraste está aplicado, pero no pude importarlo") message my t("I am opening the folder so you can import it by hand.", "Te abro la carpeta para que lo importes a mano.") & return & return & errores as warning
	return false
end importar

on separadorDecimal()
	-- the decimal separator of the system, to turn text into a number
	return text 2 of ((1 / 2) as text)
end separadorDecimal

on redondear(valor, decimales)
	set f to 10 ^ decimales
	return (round (valor * f)) / f
end redondear

on absoluto(valor)
	if valor < 0 then return -valor
	return valor
end absoluto

on indice(elemento, lista)
	repeat with i from 1 to count of lista
		if (item i of lista) is elemento then return i
	end repeat
	return 1
end indice

on reemplazar(textoOriginal, buscar, poner)
	set AppleScript's text item delimiters to buscar
	set partes to text items of (textoOriginal as text)
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
