-- Zone map for Capture One / Mapa de zonas para Capture One
--
-- For each selected variant it writes two images with zonas.py: the false colour map
-- with the percentage of the area in each zone, and the grey image with the boundaries
-- between zones as contour lines. They open in Preview.
--
-- Modes:
--   print: the image as developed, ten units of L* per zone
--   scene: light meter reading, one stop per zone and middle grey in zone V. The script
--          temporarily sets the Linear Response curve and lowers the exposure three
--          stops so as not to clip the high zones, and then puts everything back
--   film: inverts a modelled Tri-X print at grade 2
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements: zonas.py, revelado.py, peliculas.py and espacio_color.py in
-- ~/Pictures/Revelado/, and Python with numpy, pillow and tifffile.

property clavesModos : {"print", "scene", "film"}
property curvasLineales : {"Linear Response", "Respuesta lineal"}
property margenPasos : 3
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
	set titulo to my t("Zone map", "Mapa de zonas")
	set nombreReceta to my t("Zones TIFF 16", "Zonas TIFF 16")
	if es then
		set idioma to "es"
		set nombreRegistro to "registro.txt"
		set nombresModos to {"La copia, tal como está revelada", "La escena, como un fotómetro (luz lineal)", "Lo que daría una copia de Tri-X a grado 2"}
	else
		set idioma to "en"
		set nombreRegistro to "log.txt"
		set nombresModos to {"The print, as developed", "The scene, like a light meter (linear light)", "What a Tri-X print at grade 2 would give"}
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaZonas to carpetaBase & "zonas.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"
	if not my existe(rutaZonas) then
		display alert my t("zonas.py is missing", "Falta zonas.py") message my t("Copy zonas.py and the other development programs into the folder ", "Copia zonas.py y los demás programas de revelado en la carpeta ") & carpetaBase as critical
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

	set eleccion to choose from list nombresModos with title titulo with prompt my t("Which zones do you want to see?", "¿Qué zonas quieres ver?") default items {item 1 of nombresModos}
	if eleccion is false then return
	set modo to item (my indice(item 1 of eleccion, nombresModos)) of clavesModos

	set marcaTiempo to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("zones_", "zonas_") & marcaTiempo & "/"
	do shell script "mkdir -p " & quoted form of carpetaRun

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

	set k to 0
	set abrir to {}
	repeat with v in seleccion
		set k to k + 1
		set variante to contents of v
		set carpetaEntrada to carpetaRun & my t("input_", "entrada_") & k & "/"
		do shell script "mkdir -p " & quoted form of carpetaEntrada
		set carpetaEntradaA to (POSIX file carpetaEntrada) as alias

		if modo is "scene" then
			tell application "Capture One"
				set exposicionOriginal to exposure of adjustments of variante
				set curvaOriginal to film curve of adjustments of variante
			end tell
			if not my ponerCurvaLineal(variante) then
				my restaurarTodo(doc, salidaOriginal, editarTodas)
				display alert my t("Could not set the Linear Response curve", "No pude poner la curva Respuesta lineal") message my t("Set it by hand on image ", "Ponla a mano en la imagen ") & k & my t(" and run the script again.", " y vuelve a lanzar el script.") as critical
				return
			end if
			tell application "Capture One" to set exposure of adjustments of variante to exposicionOriginal - margenPasos
		end if

		tell application "Capture One"
			try
				set output of doc to carpetaEntradaA
				set resultado to process variante recipe nombreReceta
			on error msg
				set resultado to "ERROR " & msg
			end try
		end tell
		set tif to ""
		if resultado does not start with "ERROR" then set tif to my esperarTif(doc, carpetaEntrada, minutosEsperaPorFoto)
		if modo is "scene" then my restaurarVariante(variante, exposicionOriginal, curvaOriginal)
		if resultado starts with "ERROR" or tif is "" then
			my restaurarTodo(doc, salidaOriginal, editarTodas)
			display alert my t("Could not export image ", "No pude exportar la imagen ") & k message resultado as critical
			return
		end if

		set opciones to " --mode " & modo
		if modo is "scene" then set opciones to opciones & " --headroom " & (margenPasos as text)
		set orden to quoted form of rutaPython & " " & quoted form of rutaZonas & " " & quoted form of tif & " -o " & quoted form of carpetaRun & opciones & " --lang " & idioma & " 2>&1"
		with timeout of 1800 seconds
			try
				set salidaTexto to do shell script orden
			on error msg
				my restaurarTodo(doc, salidaOriginal, editarTodas)
				display alert my t("Zone map error on image ", "Error en el mapa de zonas de la imagen ") & k message msg as critical
				return
			end try
		end timeout
		do shell script "printf '%s\\n' " & quoted form of salidaTexto & " >> " & quoted form of (carpetaRun & nombreRegistro)
		set nombreBase to do shell script "basename " & quoted form of tif & " | sed 's/\\.[Tt][Ii][Ff]*$//'"
		set end of abrir to carpetaRun & nombreBase & "_zones_map.jpg"
		set end of abrir to carpetaRun & nombreBase & "_zones_contours.jpg"
	end repeat
	my restaurarTodo(doc, salidaOriginal, editarTodas)

	set lista to ""
	repeat with f in abrir
		set lista to lista & " " & quoted form of (contents of f)
	end repeat
	do shell script "open -a Preview" & lista
end run

on ponerCurvaLineal(variante)
	repeat with nombre in curvasLineales
		try
			tell application "Capture One"
				set film curve of adjustments of variante to (contents of nombre)
				set actual to film curve of adjustments of variante
			end tell
			if actual is (contents of nombre) then return true
		end try
	end repeat
	return false
end ponerCurvaLineal

on restaurarVariante(variante, exposicionOriginal, curvaOriginal)
	try
		tell application "Capture One"
			set exposure of adjustments of variante to exposicionOriginal
			set film curve of adjustments of variante to curvaOriginal
		end tell
	end try
end restaurarVariante

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
		delay 1
		set tif to do shell script "find " & quoted form of carpeta & " -maxdepth 1 -iname '*.tif' | head -1"
		tell application "Capture One" to set pendientes to count of jobs of doc
		if tif is not "" and pendientes = 0 then
			delay 1
			return tif
		end if
		if (current date) > limite then return ""
	end repeat
end esperarTif

on indice(elemento, lista)
	repeat with i from 1 to count of lista
		if (item i of lista) is elemento then return i
	end repeat
	return 1
end indice

on existe(ruta)
	try
		do shell script "test -e " & quoted form of ruta
		return true
	on error
		return false
	end try
end existe
