-- Grano de película para Capture One
--
-- Para cada variante seleccionada: la exporta como TIFF de 16 bits en Adobe RGB (1998)
-- con todos sus ajustes, le añade grano con grano.py y vuelve a importar el resultado.
-- El tamaño del grano se calcula a partir del recorte: si la foto está recortada,
-- el fotograma equivalente es más pequeño y el grano se ve proporcionalmente mayor.
--
-- Requisitos:
--   grano.py en ~/Pictures/Grano/
--   Python con numpy, pillow y tifffile (por defecto, el de ~/miniforge3)

property nombreReceta : "Grano TIFF 16"
property peliculas : {"trix", "k64", "k25", "velvia50", "pro400h", "generico"}
property ladoSensorMm : 36
property minutosEsperaPorFoto : 10

on run
	set carpetaBase to (POSIX path of (path to pictures folder)) & "Grano/"
	set rutaScript to carpetaBase & "grano.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"

	if not my existe(rutaScript) then
		display alert "Falta grano.py" message "Copia grano.py en la carpeta " & carpetaBase as critical
		return
	end if
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set colaActiva to processing queue enabled of doc
	end tell
	set n to count of seleccion
	if n < 1 then
		display alert "No hay ninguna imagen seleccionada" as warning
		return
	end if
	if not colaActiva then
		display alert "La cola de procesado está en pausa" message "Reanúdala en la herramienta de procesado y vuelve a lanzar el script." as warning
		return
	end if

	-- Película e intensidad
	set eleccion to choose from list peliculas with title "Grano de película" with prompt ("Película para " & n & " imagen(es):") default items {"trix"}
	if eleccion is false then return
	set pelicula to item 1 of eleccion
	set respuesta to display dialog "Intensidad (1 = la de la hoja técnica):" default answer "1.0" with title "Grano de película"
	set intensidad to my reemplazar(text returned of respuesta, ",", ".")

	-- Carpetas
	set marca to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & "grano_" & marca & "/"
	set carpetaSalida to carpetaRun & "resultado/"
	do shell script "mkdir -p " & quoted form of carpetaSalida

	-- Receta
	tell application "Capture One"
		tell doc
			if not (exists recipe nombreReceta) then
				try
					make new recipe at it with properties {name:nombreReceta}
				on error msg
					display alert "No pude crear la receta" message "Crea a mano una receta llamada \"" & nombreReceta & "\" y vuelve a lanzar el script. Detalle: " & msg as critical
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

	-- Una variante cada vez: así cada exportación cae en su carpeta y sabemos su recorte
	set k to 0
	set registro to ""
	repeat with v in seleccion
		set k to k + 1
		set carpetaEntrada to carpetaRun & "entrada_" & k & "/"
		do shell script "mkdir -p " & quoted form of carpetaEntrada
		set carpetaEntradaA to (POSIX file carpetaEntrada) as alias

		-- Tamaño equivalente sobre la película según el recorte
		set anchoMm to my anchoEquivalente(contents of v)

		tell application "Capture One"
			try
				set output of doc to carpetaEntradaA
				set resultado to process (contents of v) recipe nombreReceta
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert "Error al enviar la imagen " & k & " a procesar" message msg as critical
				return
			end try
		end tell
		if resultado starts with "ERROR" then
			my restaurarSalida(doc, salidaOriginal)
			display alert "Error al procesar la imagen " & k message resultado as critical
			return
		end if

		-- Espera a la exportación
		set limite to (current date) + minutosEsperaPorFoto * 60
		repeat
			delay 1
			set tif to do shell script "find " & quoted form of carpetaEntrada & " -maxdepth 1 -iname '*.tif' | head -1"
			tell application "Capture One" to set pendientes to count of jobs of doc
			if tif is not "" and pendientes = 0 then exit repeat
			if (current date) > limite then
				my restaurarSalida(doc, salidaOriginal)
				display alert "La exportación de la imagen " & k & " está tardando demasiado" as warning
				return
			end if
		end repeat
		delay 1

		-- Grano
		set nombreBase to do shell script "basename " & quoted form of tif & " | sed 's/\\.[Tt][Ii][Ff]*$//'"
		set destino to carpetaSalida & nombreBase & "_grano_" & pelicula & ".tif"
		set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " " & quoted form of tif & " " & quoted form of destino & " --pelicula " & pelicula & " --intensidad " & quoted form of intensidad & " --espacio adobergb --ancho-mm " & anchoMm & " 2>&1"
		with timeout of 3600 seconds
			try
				set registro to registro & (do shell script orden) & return
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert "Error al añadir el grano a la imagen " & k message msg as critical
				return
			end try
		end timeout
	end repeat
	my restaurarSalida(doc, salidaOriginal)

	-- Registro con los parámetros de cada imagen
	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & "registro.txt")

	-- Importación
	if not my importar(doc, carpetaSalida) then return
	display notification ("Grano " & pelicula & " en " & n & " imagen(es)") with title "Grano de película"
end run

-- Lado largo del recorte expresado en milímetros de película, como texto con punto decimal
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
		if ladoRecorte ≤ 0 or ladoImagen ≤ 0 or ladoRecorte > ladoImagen then error "fuera de rango"
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
			set errores to errores & "Carpeta como texto: " & m1 & return
		end try
		try
			import doc source listaTif
			return true
		on error m2
			set errores to errores & "Lista de archivos: " & m2 & return
		end try
		try
			repeat with t in listaTif
				import doc source (contents of t)
			end repeat
			return true
		on error m3
			set errores to errores & "Archivo a archivo: " & m3 & return
		end try
	end tell
	do shell script "open " & quoted form of carpetaSalida
	display alert "El grano está hecho, pero no pude importarlo" message "Te abro la carpeta para que lo importes a mano." & return & return & errores as warning
	return false
end importar

on restaurarSalida(doc, salidaOriginal)
	try
		tell application "Capture One" to set output of doc to salidaOriginal
	end try
end restaurarSalida

on reemplazar(t, buscar, poner)
	set AppleScript's text item delimiters to buscar
	set partes to text items of t
	set AppleScript's text item delimiters to poner
	set t to partes as text
	set AppleScript's text item delimiters to ""
	return t
end reemplazar

on existe(ruta)
	try
		do shell script "test -e " & quoted form of ruta
		return true
	on error
		return false
	end try
end existe
