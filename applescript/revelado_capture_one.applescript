-- Film development for Capture One / Revelado de película para Capture One
--
-- For each selected variant: temporarily sets the Linear Response curve and lowers
-- the exposure two stops (headroom for the shoulder of the film), exports it as 16 bit
-- TIFF in ProPhoto RGB, puts the variant back as it was, develops it with revelado.py
-- using the spectral model of peliculas.py and, if asked, adds the grain of the same
-- film with grano.py. The result is imported into the document.
--
-- The variant must have the normal camera profile, not a film profile.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements:
--   revelado.py, peliculas.py and espacio_color.py in ~/Pictures/Revelado/
--   grano.py in ~/Pictures/Grano/ (only for the grain)
--   Python with numpy, pillow and tifffile (by default, ~/miniforge3)

property clavesPeliculas : {"k64", "k25", "velvia50", "pro400h", "trix"}
property clavesFiltros : {"", "yellow", "deep_yellow", "orange", "red", "deep_red", "green", "blue"}
property clavesSalas : {"dim", "average", "dark"}
property valoresGrados : {"", "-0.5", "0", "1", "1.5", "2.5", "3", "3.5", "4", "5"}
property curvasLineales : {"Linear Response", "Respuesta lineal"}
property marcasPelicula : {"Kodachrome", "Velvia", "Tri-X", "TriX", "PRO 400H", "Pro400H"}
property margenPasos : 2
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
	set titulo to my t("Film development", "Revelado de película")
	set nombreReceta to my t("Film development TIFF 16", "Revelado TIFF 16")
	if es then
		set idioma to "es"
		set nombreRegistro to "registro.txt"
		set nombresPeliculas to {"Kodachrome 64", "Kodachrome 25", "Velvia 50", "PRO 400H sobre Endura", "Tri-X 400 sobre Multigrade"}
		set virados to {"neutro", "frio", "calido", "sepia", "selenio"}
		set nombresFiltros to {"Sin filtro", "Amarillo (Wratten 8)", "Amarillo intenso (Wratten 15)", "Naranja (Wratten 21)", "Rojo (Wratten 25)", "Rojo intenso (Wratten 29)", "Verde (Wratten 11)", "Azul (Wratten 47)"}
		set nombresGrados to {"Grado 2 (el del modelo)", "00", "0", "1", "1½", "2½", "3", "3½", "4", "5"}
		set nombresSalas to {"Monitor en penumbra", "Habitación iluminada", "Proyección en sala oscura"}
	else
		set idioma to "en"
		set nombreRegistro to "log.txt"
		set nombresPeliculas to {"Kodachrome 64", "Kodachrome 25", "Velvia 50", "PRO 400H on Endura", "Tri-X 400 on Multigrade"}
		set virados to {"neutral", "cold", "warm", "sepia", "selenium"}
		set nombresFiltros to {"No filter", "Yellow (Wratten 8)", "Deep yellow (Wratten 15)", "Orange (Wratten 21)", "Red (Wratten 25)", "Deep red (Wratten 29)", "Green (Wratten 11)", "Blue (Wratten 47)"}
		set nombresGrados to {"Grade 2 (the model's)", "00", "0", "1", "1½", "2½", "3", "3½", "4", "5"}
		set nombresSalas to {"Monitor in a dim room", "Lit room", "Projection in a dark room"}
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaRevelado to carpetaBase & "revelado.py"
	set rutaGrano to (POSIX path of (path to pictures folder)) & "Grano/grano.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"

	if not my existe(rutaRevelado) then
		display alert my t("revelado.py is missing", "Falta revelado.py") message my t("Copy revelado.py, peliculas.py and espacio_color.py into the folder ", "Copia revelado.py, peliculas.py y espacio_color.py en la carpeta ") & carpetaBase as critical
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

	-- No variant may already carry a film profile
	repeat with v in seleccion
		tell application "Capture One" to set perfilActual to color profile of adjustments of (contents of v)
		repeat with marca in marcasPelicula
			if perfilActual contains (contents of marca) then
				display alert my t("An image has a film profile", "Hay una imagen con perfil de película") message my t("The image has the profile \"", "La imagen tiene el perfil \"") & perfilActual & my t("\". For the Python development set the normal camera profile and run the script again; otherwise the film would be applied twice.", "\". Para el revelado en Python pon el perfil de cámara normal y vuelve a lanzar el script; si no, la película se aplicaría dos veces.") as warning
				return
			end if
		end repeat
	end repeat

	-- Film and options
	set eleccion to choose from list nombresPeliculas with title titulo with prompt (my t("Film for ", "Película para ") & n & my t(" image(s):", " imagen(es):")) default items {item 1 of nombresPeliculas}
	if eleccion is false then return
	set pelicula to item (my indice(item 1 of eleccion, nombresPeliculas)) of clavesPeliculas
	set opciones to ""
	set descripcion to item 1 of eleccion

	if pelicula is "trix" then
		set vir to choose from list virados with title titulo with prompt my t("Toning of the print:", "Virado de la copia:") default items {item 1 of virados}
		if vir is false then return
		set opciones to opciones & " --toning " & (item 1 of vir)
		if (item 1 of vir) is not (item 1 of virados) then set descripcion to descripcion & my t(", toning ", ", virado ") & (item 1 of vir)
		set fe to choose from list nombresFiltros with title titulo with prompt my t("Filter in front of the lens (simulated spectrally on the sensitivity of Tri-X):", "Filtro delante del objetivo (simulado espectralmente sobre la sensibilidad de la Tri-X):") default items {item 1 of nombresFiltros}
		if fe is false then return
		set ge to choose from list nombresGrados with title titulo with prompt my t("Multigrade paper grade (from the ISO R range in Ilford's data sheet):", "Grado del papel Multigrade (del rango ISO R de la hoja técnica de Ilford):") default items {item 1 of nombresGrados}
		if ge is false then return
		set valorGrado to item (my indice(item 1 of ge, nombresGrados)) of valoresGrados
		if valorGrado is not "" then
			set opciones to opciones & " --grade " & valorGrado
			set descripcion to descripcion & my t(", grade ", ", grado ") & (item 1 of ge)
		end if
		set claveFiltro to item (my indice(item 1 of fe, nombresFiltros)) of clavesFiltros
		if claveFiltro is not "" then
			set opciones to opciones & " --filter " & claveFiltro
			set descripcion to descripcion & my t(", filter ", ", filtro ") & (item 1 of fe)
		end if
	else if pelicula is in {"k64", "k25", "velvia50"} then
		set se to choose from list nombresSalas with title titulo with prompt my t("Where will it be viewed? Slides were meant to be projected in the dark, and in other surroundings the contrast should be lowered:", "¿Dónde se va a mirar? La diapositiva se pensó para proyectarse a oscuras, y en otros entornos conviene bajar el contraste:") default items {item 1 of nombresSalas}
		if se is false then return
		set opciones to opciones & " --room " & (item (my indice(item 1 of se, nombresSalas)) of clavesSalas)
	end if

	set respuesta to display dialog my t("Film exposure in stops (0 = normal; negative = denser and more saturated):", "Exposición del film en pasos (0 = normal; negativo = más denso y saturado):") default answer "0" with title titulo
	set evFilm to my reemplazar(text returned of respuesta, ",", ".")
	set opciones to opciones & " --ev " & quoted form of evFilm

	set conGrano to false
	set botonCon to my t("With grain", "Con grano")
	set botonSin to my t("No grain", "Sin grano")
	set botonCancelar to my t("Cancel", "Cancelar")
	set respuestaGrano to display dialog my t("Add the grain of the same film?", "¿Añadir el grano de la misma película?") buttons {botonCancelar, botonSin, botonCon} default button botonCon cancel button botonCancelar with title titulo
	if button returned of respuestaGrano is botonCon then
		if my existe(rutaGrano) then
			set conGrano to true
			set descripcion to descripcion & my t(", with grain", ", con grano")
		else
			display alert my t("Cannot find grano.py", "No encuentro grano.py") message my t("Going on without grain. It should be in ", "Sigo sin grano. Debería estar en ") & rutaGrano as warning
		end if
	end if

	-- Folders
	set marcaTiempo to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("development_", "revelado_") & marcaTiempo & "/"
	set carpetaTrabajo to carpetaRun & my t("work/", "trabajo/")
	set carpetaSalida to carpetaRun & my t("result/", "resultado/")
	do shell script "mkdir -p " & quoted form of carpetaTrabajo & " " & quoted form of carpetaSalida

	-- Recipe and state of the document
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
	set registro to ""
	repeat with v in seleccion
		set k to k + 1
		set variante to contents of v
		set carpetaEntrada to carpetaRun & my t("input_", "entrada_") & k & "/"
		do shell script "mkdir -p " & quoted form of carpetaEntrada
		set carpetaEntradaA to (POSIX file carpetaEntrada) as alias
		set anchoMm to my anchoEquivalente(variante)

		-- Linear Response and highlight headroom, only while exporting
		tell application "Capture One"
			set exposicionOriginal to exposure of adjustments of variante
			set curvaOriginal to film curve of adjustments of variante
		end tell
		if not my ponerCurvaLineal(variante) then
			my restaurarTodo(doc, salidaOriginal, editarTodas)
			display alert my t("Could not set the Linear Response curve", "No pude poner la curva Respuesta lineal") message my t("Set it by hand on image ", "Ponla a mano en la imagen ") & k & my t(" (Base Characteristics tool) and run the script again.", " (herramienta Curva básica) y vuelve a lanzar el script.") as critical
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
		if resultado starts with "ERROR" then
			my restaurarVariante(variante, exposicionOriginal, curvaOriginal)
			my restaurarTodo(doc, salidaOriginal, editarTodas)
			display alert my t("Error processing image ", "Error al procesar la imagen ") & k message resultado as critical
			return
		end if

		set tif to my esperarTif(doc, carpetaEntrada, minutosEsperaPorFoto)
		my restaurarVariante(variante, exposicionOriginal, curvaOriginal)
		if tif is "" then
			my restaurarTodo(doc, salidaOriginal, editarTodas)
			display alert my t("The export of image ", "La exportación de la imagen ") & k & my t(" is taking too long", " está tardando demasiado") as warning
			return
		end if

		-- Development and grain
		set nombreBase to do shell script "basename " & quoted form of tif & " | sed 's/\\.[Tt][Ii][Ff]*$//'"
		set revelada to carpetaTrabajo & nombreBase & "_" & pelicula & ".tif"
		set orden to quoted form of rutaPython & " " & quoted form of rutaRevelado & " " & quoted form of tif & " " & quoted form of revelada & " --film " & pelicula & " --headroom " & (margenPasos as text) & opciones & " --lang " & idioma & " 2>&1"
		with timeout of 3600 seconds
			try
				set registro to registro & (do shell script orden) & return
			on error msg
				my restaurarTodo(doc, salidaOriginal, editarTodas)
				display alert my t("Development error on image ", "Error en el revelado de la imagen ") & k message msg as critical
				return
			end try
			if conGrano then
				set final to carpetaSalida & nombreBase & "_" & pelicula & my t("_grain.tif", "_grano.tif")
				set orden to quoted form of rutaPython & " " & quoted form of rutaGrano & " " & quoted form of revelada & " " & quoted form of final & " --film " & pelicula & " --space auto --width-mm " & anchoMm & " --lang " & idioma & " 2>&1"
				try
					set registro to registro & (do shell script orden) & return
				on error msg
					my restaurarTodo(doc, salidaOriginal, editarTodas)
					display alert my t("Error adding grain to image ", "Error al añadir el grano a la imagen ") & k message msg as critical
					return
				end try
			else
				do shell script "mv " & quoted form of revelada & " " & quoted form of carpetaSalida
			end if
		end timeout
	end repeat
	my restaurarTodo(doc, salidaOriginal, editarTodas)

	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & nombreRegistro)
	if not my importar(doc, carpetaSalida) then return
	display notification (my t("Developed ", "Revelado ") & descripcion & my t(" on ", " en ") & n & my t(" image(s)", " imagen(es)")) with title titulo
end run

-- Sets the Linear Response curve trying the known names; returns whether it worked
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
	display alert my t("The development is done, but I could not import it", "El revelado está hecho, pero no pude importarlo") message my t("I am opening the folder so you can import it by hand.", "Te abro la carpeta para que lo importes a mano.") & return & return & errores as warning
	return false
end importar

on indice(elemento, lista)
	repeat with i from 1 to count of lista
		if (item i of lista) is elemento then return i
	end repeat
	return 1
end indice

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
