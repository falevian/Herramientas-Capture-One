-- Test strip for Capture One / Tira de pruebas para Capture One
--
-- With the first selected variant, makes a test strip as in the darkroom: the same
-- image developed with the model of peliculas.py changing a single parameter (print
-- exposure, paper grade or film exposure), in strips across the photo or as a
-- mosaic. The strip opens in Preview; with what you choose, the final development
-- is done with the Film development script.
--
-- Like the development, it temporarily sets the Linear Response curve and lowers the
-- exposure two stops to export, and then puts the variant back as it was. The
-- variant must have the normal camera profile, not a film profile.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements: tira.py, revelado.py, peliculas.py and espacio_color.py in
-- ~/Pictures/Revelado/, and Python with numpy, pillow and tifffile.

property clavesPeliculas : {"trix", "pro400h", "k64", "k25", "velvia50"}
property valoresGrados : {"2", "-0.5", "0", "1", "1.5", "2.5", "3", "3.5", "4", "5"}
property nombresGrados : {"2", "00", "0", "1", "1½", "2½", "3", "3½", "4", "5"}
property curvasLineales : {"Linear Response", "Respuesta lineal"}
property marcasPelicula : {"Kodachrome", "Velvia", "Tri-X", "TriX", "PRO 400H", "Pro400H"}
property margenPasos : 2
property minutosEspera : 10
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
	set titulo to my t("Test strip", "Tira de pruebas")
	set nombreReceta to my t("Film development TIFF 16", "Revelado TIFF 16")
	if es then
		set idioma to "es"
		set nombreRegistro to "registro.txt"
		set nombresPeliculas to {"Tri-X 400 sobre Multigrade", "PRO 400H sobre Endura", "Kodachrome 64", "Kodachrome 25", "Velvia 50"}
		set virados to {"neutro", "frio", "calido", "sepia", "selenio"}
	else
		set idioma to "en"
		set nombreRegistro to "log.txt"
		set nombresPeliculas to {"Tri-X 400 on Multigrade", "PRO 400H on Endura", "Kodachrome 64", "Kodachrome 25", "Velvia 50"}
		set virados to {"neutral", "cold", "warm", "sepia", "selenium"}
	end if
	set tipoGrado to my t("Paper grade", "Grado del papel")
	set tipoCopia to my t("Print exposure", "Exposición de la copia")
	set tipoPelicula to my t("Film exposure", "Exposición de la película")

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaTira to carpetaBase & "tira.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"
	if not my existe(rutaTira) then
		display alert my t("tira.py is missing", "Falta tira.py") message my t("Copy tira.py and the other development programs into the folder ", "Copia tira.py y los demás programas de revelado en la carpeta ") & carpetaBase as critical
		return
	end if
	if pythonFijo is not "" then set rutaPython to pythonFijo
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set colaActiva to processing queue enabled of doc
	end tell
	if (count of seleccion) < 1 then
		display alert my t("No image is selected", "No hay ninguna imagen seleccionada") as warning
		return
	end if
	if not colaActiva then
		display alert my t("The processing queue is paused", "La cola de procesado está en pausa") message my t("Resume it in the Process tool and run the script again.", "Reanúdala en la herramienta de procesado y vuelve a lanzar el script.") as warning
		return
	end if
	set variante to item 1 of seleccion
	tell application "Capture One" to set perfilActual to color profile of adjustments of variante
	repeat with marca in marcasPelicula
		if perfilActual contains (contents of marca) then
			display alert my t("The image has a film profile", "La imagen tiene un perfil de película") message my t("Set the normal camera profile for the strip; otherwise the film would be applied twice.", "Pon el perfil de cámara normal para la tira; si no, la película se aplicaría dos veces.") as warning
			return
		end if
	end repeat

	set eleccion to choose from list nombresPeliculas with title titulo with prompt my t("Film:", "Película:") default items {item 1 of nombresPeliculas}
	if eleccion is false then return
	set pelicula to item (my indice(item 1 of eleccion, nombresPeliculas)) of clavesPeliculas

	if pelicula is "trix" then
		set tipos to {tipoGrado, tipoCopia, tipoPelicula}
	else if pelicula is "pro400h" then
		set tipos to {tipoCopia, tipoPelicula}
	else
		set tipos to {tipoPelicula}
	end if
	set te to choose from list tipos with title titulo with prompt my t("Which parameter changes from one strip to the next?", "¿Qué parámetro cambia de una banda a otra?") default items {item 1 of tipos}
	if te is false then return
	set tipoTexto to item 1 of te
	if tipoTexto is tipoGrado then
		set tipo to "grade"
		set nombreTipo to my t("grade", "grado")
	else if tipoTexto is tipoCopia then
		set tipo to "print"
		set nombreTipo to my t("print", "copia")
	else
		set tipo to "exposure"
		set nombreTipo to my t("exposure", "exposicion")
	end if

	set opciones to ""
	if pelicula is "trix" then
		set vir to choose from list virados with title titulo with prompt my t("Toning of the print:", "Virado de la copia:") default items {item 1 of virados}
		if vir is false then return
		set opciones to opciones & " --toning " & (item 1 of vir)
		if tipo is not "grade" then
			set ge to choose from list nombresGrados with title titulo with prompt my t("Paper grade for the whole strip:", "Grado del papel para toda la tira:") default items {item 1 of nombresGrados}
			if ge is false then return
			set opciones to opciones & " --grade " & (item (my indice(item 1 of ge, nombresGrados)) of valoresGrados)
		end if
	end if
	set botonCancelar to my t("Cancel", "Cancelar")
	set botonMosaico to my t("Mosaic", "Mosaico")
	set botonBandas to my t("Strips", "Bandas")
	set de to display dialog my t("How is the strip laid out?", "¿Cómo se monta la tira?") buttons {botonCancelar, botonMosaico, botonBandas} default button botonBandas cancel button botonCancelar with title titulo
	if button returned of de is botonMosaico then
		set opciones to opciones & " --layout mosaic"
	end if

	set marcaTiempo to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("strip_", "tira_") & marcaTiempo & "/"
	set carpetaEntrada to carpetaRun & my t("input/", "entrada/")
	do shell script "mkdir -p " & quoted form of carpetaEntrada
	set carpetaEntradaA to (POSIX file carpetaEntrada) as alias

	tell application "Capture One"
		set editarTodas to edit all selected variants
		set edit all selected variants to false
		tell doc
			if not (exists recipe nombreReceta) then
				try
					make new recipe at it with properties {name:nombreReceta}
				on error msg
					display alert my t("Could not create the recipe", "No pude crear la receta") message msg as critical
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
		set exposicionOriginal to exposure of adjustments of variante
		set curvaOriginal to film curve of adjustments of variante
	end tell

	if not my ponerCurvaLineal(variante) then
		my restaurarTodo(doc, salidaOriginal, editarTodas)
		display alert my t("Could not set the Linear Response curve", "No pude poner la curva Respuesta lineal") message my t("Set it by hand and run the script again.", "Ponla a mano y vuelve a lanzar el script.") as critical
		return
	end if
	tell application "Capture One"
		set exposure of adjustments of variante to exposicionOriginal - margenPasos
		try
			set output of doc to carpetaEntradaA
			set resultado to process variante recipe nombreReceta
		on error msg
			set resultado to "ERROR " & msg
		end try
	end tell
	set tif to ""
	if resultado does not start with "ERROR" then set tif to my esperarTif(doc, carpetaEntrada, minutosEspera)
	my restaurarVariante(variante, exposicionOriginal, curvaOriginal)
	my restaurarTodo(doc, salidaOriginal, editarTodas)
	if resultado starts with "ERROR" or tif is "" then
		display alert my t("Could not export the image", "No pude exportar la imagen") message resultado as critical
		return
	end if

	set salidaTira to carpetaRun & my t("strip_", "tira_") & pelicula & "_" & nombreTipo & ".jpg"
	set orden to quoted form of rutaPython & " " & quoted form of rutaTira & " " & quoted form of tif & " " & quoted form of salidaTira & " --film " & pelicula & " --type " & tipo & " --headroom " & (margenPasos as text) & opciones & " --lang " & idioma & " 2>&1"
	with timeout of 1800 seconds
		try
			set registro to do shell script orden
		on error msg
			display alert my t("Error making the strip", "Error al montar la tira") message msg as critical
			return
		end try
	end timeout
	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & nombreRegistro)
	do shell script "open -a Preview " & quoted form of salidaTira
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
