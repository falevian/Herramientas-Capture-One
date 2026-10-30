-- Your way of seeing, for Capture One / Tu forma de mirar, para Capture One
--
-- Collects the metadata of the selected images (rating, colour tag, date and time,
-- focal length, aperture, exposure time, ISO, camera, crop, black and white and
-- colour profile), saves them in a table and makes with estadistica.py an HTML
-- report that crosses each variable with the rating: which photos you end up
-- keeping. The report opens in the browser.
--
-- First select the images you want to analyse, for example the whole catalogue or
-- a collection with Cmd+A. With thousands of images the reading takes a few minutes.
--
-- Dialogs and the report follow the system language (Spanish if the system is in
-- Spanish, English otherwise) unless instalar.sh fixed it with LANGUAGE=es or
-- LANGUAGE=en. The column names of the table stay in Spanish in both languages,
-- because estadistica.py reads them.
--
-- Requirements: estadistica.py in ~/Pictures/Revelado/ and Python 3.

property umbralPorDefecto : "4"
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
	if es then
		set idioma to "es"
	else
		set idioma to "en"
	end if
	set titulo to my t("Your way of seeing", "Tu forma de mirar")
	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaScript to carpetaBase & "estadistica.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"
	if not my existe(rutaScript) then
		display alert my t("estadistica.py is missing", "Falta estadistica.py") message my t("Copy it into the folder ", "Cópialo en la carpeta ") & carpetaBase as critical
		return
	end if
	if pythonFijo is not "" then set rutaPython to pythonFijo
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set nombreDoc to name of doc
	end tell
	set n to count of seleccion
	if n < 30 then
		display alert my t("Few images are selected", "Hay pocas imágenes seleccionadas") message my t("With ", "Con ") & n & my t(" images the statistics say little. Select the whole catalogue or a large collection (Cmd+A) and run the script again.", " imágenes la estadística no dice gran cosa. Selecciona todo el catálogo o una colección grande (Cmd+A) y vuelve a lanzar el script.") as warning
		return
	end if
	set r to display dialog my t("Minimum stars for a photo to count as chosen:", "Estrellas mínimas para que una foto cuente como elegida:") default answer umbralPorDefecto with title titulo
	set umbral to text returned of r

	set marcaTiempo to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & my t("statistics_", "estadistica_") & marcaTiempo & "/"
	do shell script "mkdir -p " & quoted form of carpetaRun
	set rutaTabla to carpetaRun & my t("metadata.tsv", "metadatos.tsv")
	set rutaInforme to carpetaRun & my t("report.html", "informe.html")

	set tabulador to ASCII character 9
	set saltoLinea to ASCII character 10
	set cabecera to {"nombre", "valoracion", "etiqueta", "fecha", "focal", "diafragma", "velocidad", "iso", "camara", "ancho_recorte", "alto_recorte", "ancho", "alto", "bn", "perfil"}
	set lineas to {my unir(cabecera, tabulador)}
	set fallos to 0
	repeat with v in seleccion
		set variante to contents of v
		try
			set fila to my datos(variante)
			set end of lineas to my unir(fila, tabulador)
		on error
			set fallos to fallos + 1
		end try
	end repeat

	-- written as UTF-8
	set texto to my unir(lineas, saltoLinea) & saltoLinea
	set f to open for access (POSIX file rutaTabla) with write permission
	try
		set eof of f to 0
		write texto to f as «class utf8»
		close access f
	on error msg
		close access f
		display alert my t("Could not save the table", "No pude guardar la tabla") message msg as critical
		return
	end try

	set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " " & quoted form of rutaTabla & " " & quoted form of rutaInforme & " --threshold " & quoted form of umbral & " --source " & quoted form of (my t("the ", "las ") & n & my t(" selected images of ", " imágenes seleccionadas de ") & nombreDoc) & " --lang " & idioma & " 2>&1"
	try
		set salida to do shell script orden
	on error msg
		display alert my t("Error making the report", "Error al generar el informe") message msg as critical
		return
	end try
	do shell script "open " & quoted form of rutaInforme
	set aviso to ""
	if fallos > 0 then set aviso to return & fallos & my t(" images could not be read and are left out.", " imágenes no se pudieron leer y quedan fuera.")
	display notification (salida & aviso) with title titulo
end run

-- One row of the table for a variant
on datos(variante)
	tell application "Capture One"
		set im to parent image of variante
		set nombre to my campo(name of im)
		set valoracion to my campo(rating of variante)
		set etiqueta to my campo(color tag of variante)
		set fechaTexto to ""
		try
			set fechaTexto to my fechaISO(EXIF capture date of im)
		end try
		set focal to ""
		set diafragma to ""
		set velocidad to ""
		set sensibilidad to ""
		set camara to ""
		try
			set focal to my campo(EXIF focal length of im)
		end try
		try
			set diafragma to my campo(EXIF aperture of im)
		end try
		try
			set velocidad to my campo(EXIF shutter speed of im)
		end try
		try
			set sensibilidad to my campo(EXIF ISO of im)
		end try
		try
			set camara to my campo(EXIF camera model of im)
		end try
		set anchoRecorte to ""
		set altoRecorte to ""
		try
			set anchoRecorte to my campo(crop width of variante)
			set altoRecorte to my campo(crop height of variante)
		end try
		set anchoImagen to ""
		set altoImagen to ""
		try
			set dims to dimensions of im
			set anchoImagen to my campo(item 1 of dims)
			set altoImagen to my campo(item 2 of dims)
		end try
		set enBN to ""
		set perfil to ""
		try
			set enBN to my campo(black and white of adjustments of variante)
		end try
		try
			set perfil to my campo(color profile of adjustments of variante)
		end try
	end tell
	return {nombre, valoracion, etiqueta, fechaTexto, focal, diafragma, velocidad, sensibilidad, camara, anchoRecorte, altoRecorte, anchoImagen, altoImagen, enBN, perfil}
end datos

-- Clean text for a cell: no tabs or line breaks, with a decimal point
on campo(valor)
	if valor is missing value then return ""
	try
		set tx to valor as text
	on error
		return ""
	end try
	set tx to my reemplazar(tx, ASCII character 9, " ")
	set tx to my reemplazar(tx, return, " ")
	set tx to my reemplazar(tx, ASCII character 10, " ")
	if class of valor is real then set tx to my reemplazar(tx, ",", ".")
	return tx
end campo

on fechaISO(d)
	set a to year of d
	set m to (month of d) as integer
	set dd to day of d
	set hh to hours of d
	set mm to minutes of d
	return (a as text) & "-" & my dos(m) & "-" & my dos(dd) & " " & my dos(hh) & ":" & my dos(mm)
end fechaISO

on dos(numero)
	return text -2 thru -1 of ("0" & (numero as text))
end dos

on unir(lista, separador)
	set AppleScript's text item delimiters to separador
	set tx to lista as text
	set AppleScript's text item delimiters to ""
	return tx
end unir

on reemplazar(tx, buscar, poner)
	set AppleScript's text item delimiters to buscar
	set partes to text items of (tx as text)
	set AppleScript's text item delimiters to poner
	set tx to partes as text
	set AppleScript's text item delimiters to ""
	return tx
end reemplazar

on existe(ruta)
	try
		do shell script "test -e " & quoted form of ruta
		return true
	on error
		return false
	end try
end existe
