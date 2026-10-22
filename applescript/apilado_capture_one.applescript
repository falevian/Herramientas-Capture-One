-- Apilado temporal para Capture One
--
-- Toma las variantes seleccionadas, las exporta como TIFF de 16 bits en Adobe RGB (1998)
-- con una receta propia, las combina con apilado_temporal.py y vuelve a importar el
-- resultado en el documento abierto. La hoja comparativa se abre en Vista Previa.
-- Un interruptor permite alinear las fotos antes de combinarlas (trípode movido o a
-- pulso) e indicar la zona estática que se usa para alinear.
--
-- Requisitos:
--   apilado_temporal.py en ~/Pictures/Apilado temporal/
--   Python con numpy, tifffile y pillow (por defecto, el de ~/miniforge3)
--
-- Antes de lanzarlo, conviene copiar los mismos ajustes a toda la secuencia.

property nombreReceta : "Apilado temporal TIFF 16"
property operadoresDisponibles : {"media", "hann", "mediana", "sigma", "maximo", "minimo"}
property minutosEsperaMaxima : 60

on run
	set carpetaBase to (POSIX path of (path to pictures folder)) & "Apilado temporal/"
	set rutaScript to carpetaBase & "apilado_temporal.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"

	if not my existe(rutaScript) then
		display alert "Falta el programa de apilado" message "Copia apilado_temporal.py en la carpeta " & carpetaBase as critical
		return
	end if
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	-- Selección actual
	tell application "Capture One"
		set doc to current document
		set seleccion to selected variants
		set colaActiva to processing queue enabled of doc
	end tell
	set n to count of seleccion
	if n < 2 then
		display alert "Selecciona al menos dos imágenes" message "Elige en el navegador la secuencia que quieres combinar y vuelve a lanzar el script." as warning
		return
	end if
	if not colaActiva then
		display alert "La cola de procesado está en pausa" message "Reanúdala en la herramienta de procesado y vuelve a lanzar el script." as warning
		return
	end if

	-- Operadores
	set eleccion to choose from list operadoresDisponibles with title "Apilado temporal" with prompt ("Operadores para las " & n & " imágenes seleccionadas:") default items {"media", "mediana"} with multiple selections allowed
	if eleccion is false then return
	set AppleScript's text item delimiters to ","
	set ops to eleccion as text
	set AppleScript's text item delimiters to ""

	-- Interruptor de alineado
	set opcionesAlineado to ""
	set textoAlineado to "sin alinear"
	set respuestaAlineado to display dialog "¿Alinear las fotos antes de combinarlas?" & return & return & "Con trípode no hace falta. A pulso, o si el trípode se ha movido, sí." buttons {"Cancelar", "No alinear", "Alinear"} default button "No alinear" cancel button "Cancelar" with title "Apilado temporal"
	if button returned of respuestaAlineado is "Alinear" then
		set tipos to {"Trípode que se ha movido (giro y desplazamiento)", "A pulso (perspectiva completa)"}
		set tipoElegido to choose from list tipos with title "Apilado temporal" with prompt "¿Cómo se han movido las fotos?" default items {item 1 of tipos}
		if tipoElegido is false then return
		if (item 1 of tipoElegido) starts with "A pulso" then
			set modelo to "homografia"
		else
			set modelo to "euclideo"
		end if

		set zonas to {"Toda la imagen", "Mitad superior (agua o movimiento abajo)", "Mitad inferior (nubes arriba)", "Franja central", "Personalizada"}
		set zonaElegida to choose from list zonas with title "Apilado temporal" with prompt "Zona estática que se usará para alinear. Deja fuera el agua, las nubes y todo lo que se mueva:" default items {item 1 of zonas}
		if zonaElegida is false then return
		set z to item 1 of zonaElegida
		set zonaTexto to ""
		if z starts with "Mitad superior" then
			set zonaTexto to "0,0,1,0.5"
		else if z starts with "Mitad inferior" then
			set zonaTexto to "0,0.5,1,1"
		else if z starts with "Franja central" then
			set zonaTexto to "0,0.33,1,0.67"
		else if z starts with "Personalizada" then
			set respuestaZona to display dialog "Rectángulo como x0,y0,x1,y1 en fracciones de la imagen (0,0 es la esquina superior izquierda y 1,1 la inferior derecha):" default answer "0,0,1,0.5" with title "Apilado temporal"
			set zonaTexto to text returned of respuestaZona
		end if

		set opcionesAlineado to " --alinear --modelo-alineado " & modelo
		if zonaTexto is not "" then set opcionesAlineado to opcionesAlineado & " --zona-alineado " & quoted form of zonaTexto
		set textoAlineado to "alineado " & modelo
	end if

	-- Carpetas de este apilado
	set marca to do shell script "date +%Y%m%d_%H%M%S"
	set carpetaRun to carpetaBase & "apilado_" & marca & "/"
	set carpetaEntrada to carpetaRun & "entrada/"
	set carpetaSalida to carpetaRun & "resultado/"
	do shell script "mkdir -p " & quoted form of carpetaEntrada & " " & quoted form of carpetaSalida
	set carpetaEntradaA to (POSIX file carpetaEntrada) as alias
	set carpetaSalidaA to (POSIX file carpetaSalida) as alias

	-- Receta de exportación
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
			-- Capture One valida la carpeta de salida general del documento al procesar, y en un
			-- catálogo puede ser relativa o no existir. La apuntamos temporalmente a nuestra
			-- carpeta, la receta usa esa ubicación y al terminar se restaura la original.
			set salidaOriginal to output
			try
				set output to carpetaEntradaA
			on error msg
				display alert "No pude cambiar la carpeta de salida del documento" message msg as critical
				return
			end try
			set root folder type of r to output location
			set output sub folder of r to ""
			set output sub name of r to ""
			set output name format of r to "[Image Name]"
			set existing files of r to add suffix
		end tell

		-- Procesado
		repeat with v in seleccion
			try
				set resultado to process (contents of v) recipe nombreReceta
			on error msg
				my restaurarSalida(doc, salidaOriginal)
				display alert "Error al enviar las imágenes a procesar" message msg & return & "Carpeta de salida: " & carpetaEntrada as critical
				return
			end try
			if resultado starts with "ERROR" then
				my restaurarSalida(doc, salidaOriginal)
				display alert "Error al procesar" message resultado as critical
				return
			end if
		end repeat
	end tell

	-- Espera a que terminen los trabajos y estén todos los TIFF
	set limite to (current date) + minutosEsperaMaxima * 60
	repeat
		delay 2
		set nTif to (do shell script "ls " & quoted form of carpetaEntrada & " | grep -ci '\\.tif$' || true") as integer
		tell application "Capture One" to set pendientes to count of jobs of doc
		if nTif ≥ n and pendientes = 0 then exit repeat
		if (current date) > limite then
			my restaurarSalida(doc, salidaOriginal)
			display alert "El procesado está tardando demasiado" message "Hay " & nTif & " de " & n & " imágenes exportadas en " & carpetaEntrada as warning
			return
		end if
	end repeat
	delay 2
	my restaurarSalida(doc, salidaOriginal)

	-- Apilado
	set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " " & quoted form of carpetaEntrada & " -o " & quoted form of carpetaSalida & " --ops " & ops & opcionesAlineado & " --curva 2.2 --comparativa --temporal " & quoted form of carpetaRun & " 2>&1"
	with timeout of 7200 seconds
		try
			set registro to do shell script orden
		on error msg
			display alert "Error en el apilado" message msg as critical
			return
		end try
	end timeout

	-- La comparativa se queda fuera de la carpeta que se importa
	do shell script "mv " & quoted form of (carpetaSalida & "comparativa.jpg") & " " & quoted form of carpetaRun & " 2>/dev/null || true"

	-- Importación del resultado: se prueban varias formas de indicar el origen
	set rutaSinBarra to text 1 thru -2 of carpetaSalida
	set listaTif to paragraphs of (do shell script "find " & quoted form of rutaSinBarra & " -maxdepth 1 -iname '*.tif' | sort")
	set importado to false
	set errores to ""
	tell application "Capture One"
		try
			import doc source rutaSinBarra
			set importado to true
		on error m1
			set errores to errores & "Carpeta como texto: " & m1 & return
		end try
		if not importado then
			try
				import doc source listaTif
				set importado to true
			on error m2
				set errores to errores & "Lista de archivos: " & m2 & return
			end try
		end if
		if not importado then
			try
				repeat with t in listaTif
					import doc source (contents of t)
				end repeat
				set importado to true
			on error m3
				set errores to errores & "Archivo a archivo: " & m3 & return
			end try
		end if
	end tell
	if not importado then
		do shell script "open " & quoted form of carpetaSalida
		display alert "El apilado está hecho, pero no pude importarlo" message "Te abro la carpeta para que lo importes a mano." & return & return & errores as warning
	end if

	do shell script "open " & quoted form of (carpetaRun & "comparativa.jpg") & " 2>/dev/null || true"
	do shell script "printf '%s' " & quoted form of registro & " > " & quoted form of (carpetaRun & "registro.txt")
	display notification ("Apilado de " & n & " imágenes con " & ops & ", " & textoAlineado) with title "Apilado temporal"
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
