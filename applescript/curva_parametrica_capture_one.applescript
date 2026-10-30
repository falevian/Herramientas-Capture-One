-- Parametric curve by regions for Capture One / Curva paramétrica por regiones
--
-- Writes into the Luma curve a tone curve defined by four sliders, like the
-- parametric curve of Lightroom: highlights, lights, darks and shadows, from -100 to
-- +100, with three adjustable splits between regions. The curve stays editable in
-- the Curve tool.
--
-- It works on the selected layer of each variant: if it is the image layer, on the
-- whole photo; if it is an adjustment layer with a mask, on that layer. It replaces
-- any Luma curve the layer had.
--
-- Dialogs follow the system language (Spanish if the system is in Spanish, English
-- otherwise) unless instalar.sh fixed it with LANGUAGE=es or LANGUAGE=en.
--
-- Requirements: curva_parametrica.py in ~/Pictures/Revelado/ and Python with numpy.

property valoresPreajustes : {"0;20;-20;0", "0;40;-40;0", "-40;0;0;40", "-30;-10;0;0", "0;0;10;40", ""}
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
	set titulo to my t("Parametric curve", "Curva paramétrica")
	if es then
		set idioma to "es"
		set nombresPreajustes to {"Contraste en S suave (claros +20, oscuros -20)", "Contraste en S fuerte (claros +40, oscuros -40)", "Recuperar luces y abrir sombras (luces -40, sombras +40)", "Luces suaves (luces -30, claros -10)", "Sombras abiertas (sombras +40, oscuros +10)", "Personalizado"}
	else
		set idioma to "en"
		set nombresPreajustes to {"Soft S contrast (lights +20, darks -20)", "Strong S contrast (lights +40, darks -40)", "Recover highlights and open shadows (highlights -40, shadows +40)", "Soft highlights (highlights -30, lights -10)", "Open shadows (shadows +40, darks +10)", "Custom"}
	end if

	set carpetaBase to (POSIX path of (path to pictures folder)) & "Revelado/"
	set rutaScript to carpetaBase & "curva_parametrica.py"
	set rutaPython to (POSIX path of (path to home folder)) & "miniforge3/bin/python3"
	if not my existe(rutaScript) then
		display alert my t("curva_parametrica.py is missing", "Falta curva_parametrica.py") message my t("Copy it into the folder ", "Cópialo en la carpeta ") & carpetaBase as critical
		return
	end if
	if pythonFijo is not "" then set rutaPython to pythonFijo
	if not my existe(rutaPython) then set rutaPython to "/usr/bin/python3"

	tell application "Capture One"
		set seleccion to selected variants
	end tell
	set n to count of seleccion
	if n < 1 then
		display alert my t("No image is selected", "No hay ninguna imagen seleccionada") as warning
		return
	end if

	set eleccion to choose from list nombresPreajustes with title titulo with prompt my t("Curve by regions (highlights, lights, darks, shadows):", "Curva por regiones (luces, claros, oscuros, sombras):") default items {item 1 of nombresPreajustes}
	if eleccion is false then return
	set valores to item (my indice(item 1 of eleccion, nombresPreajustes)) of valoresPreajustes
	set divisiones to "25;50;75"
	if valores is "" then
		set respuesta to display dialog my t("Highlights, lights, darks and shadows, from -100 to 100, separated by semicolons:", "Luces, claros, oscuros y sombras, de -100 a 100, separados por punto y coma:") default answer "0; 0; 0; 0" with title titulo
		set valores to text returned of respuesta
		set respuesta to display dialog my t("Splits between shadows and darks, darks and lights, and lights and highlights, from 0 to 100:", "Divisiones entre sombras y oscuros, oscuros y claros, y claros y luces, de 0 a 100:") default answer "25; 50; 75" with title titulo
		set divisiones to text returned of respuesta
	end if
	set listaValores to my numeros(valores)
	set listaDivisiones to my numeros(divisiones)
	if (count of listaValores) is not 4 or (count of listaDivisiones) is not 3 then
		display alert my t("Invalid format", "Formato no válido") message my t("Four values are needed for the regions and three for the splits, separated by semicolons.", "Hacen falta cuatro valores para las regiones y tres para las divisiones, separados por punto y coma.") as warning
		return
	end if

	set orden to quoted form of rutaPython & " " & quoted form of rutaScript & " points --highlights " & item 1 of listaValores & " --lights " & item 2 of listaValores & " --darks " & item 3 of listaValores & " --shadows " & item 4 of listaValores & " --splits " & (item 1 of listaDivisiones) & "," & (item 2 of listaDivisiones) & "," & (item 3 of listaDivisiones) & " --lang " & idioma & " 2>&1"
	try
		set salida to do shell script orden
	on error msg
		display alert my t("Error computing the curve", "Error al calcular la curva") message msg as critical
		return
	end try
	set puntos to {}
	set aviso to ""
	set sep to my separadorDecimal()
	repeat with l in paragraphs of salida
		set linea to contents of l
		if linea starts with "aviso" or linea starts with "warning" then
			set aviso to linea
		else if linea is not "" then
			set AppleScript's text item delimiters to ","
			set partes to text items of linea
			set AppleScript's text item delimiters to ""
			if (count of partes) is 2 then
				try
					set end of puntos to {(my reemplazar(item 1 of partes, ".", sep)) as real, (my reemplazar(item 2 of partes, ".", sep)) as real}
				end try
			end if
		end if
	end repeat
	if (count of puntos) < 3 then
		display alert my t("The curve could not be computed", "No se pudo calcular la curva") message salida as critical
		return
	end if

	set informe to ""
	set k to 0
	repeat with v in seleccion
		set k to k + 1
		set variante to contents of v
		tell application "Capture One"
			set capa to current layer of variante
			set esFondo to (kind of capa is background)
			set esRetoque to (kind of capa is heal) or (kind of capa is clone)
			set nombreCapa to name of capa
		end tell
		if esRetoque then
			set informe to informe & my t("Image ", "Imagen ") & k & my t(": the selected layer is a clone or heal layer; left untouched.", ": la capa seleccionada es de clonar o reparar; no se ha tocado.") & return
		else
			if esFondo then
				set objetivo to variante
				set dondeTexto to my t("the whole image", "toda la imagen")
			else
				set objetivo to capa
				set dondeTexto to my t("the layer \"", "la capa \"") & nombreCapa & "\""
			end if
			set originales to my leerCurva(objetivo)
			if my ponerCurva(objetivo, puntos) then
				set informe to informe & my t("Image ", "Imagen ") & k & my t(": curve written into ", ": curva escrita en ") & dondeTexto & "." & return
			else
				my restaurarCurva(objetivo, originales)
				set informe to informe & my t("Image ", "Imagen ") & k & my t(": could not write the curve into ", ": no pude escribir la curva en ") & dondeTexto & "." & return
			end if
		end if
	end repeat
	if aviso is not "" then set informe to informe & return & my t("The combination of sliders inverted tones somewhere, so the amplitudes have been reduced equally (", "La combinación de deslizadores invertía tonos en algún tramo, así que las amplitudes se han reducido por igual (") & aviso & ")."
	display dialog informe with title titulo buttons {"OK"} default button "OK"
end run

-- Turns "a; b; c" into a list of texts with a decimal point
on numeros(textoOriginal)
	set AppleScript's text item delimiters to ";"
	set partes to text items of textoOriginal
	set AppleScript's text item delimiters to ""
	set lista to {}
	repeat with p in partes
		set s to my reemplazar(my reemplazar(contents of p, " ", ""), ",", ".")
		if s is not "" then set end of lista to s
	end repeat
	return lista
end numeros

on leerCurva(objetivo)
	set lista to {}
	try
		tell application "Capture One"
			set pts to curve points of luma curve of adjustments of objetivo
			repeat with cp in pts
				set end of lista to {brightness of cp, amount of cp}
			end repeat
		end tell
	end try
	return lista
end leerCurva

-- Replaces the points of the Luma curve; returns whether it worked
on ponerCurva(objetivo, puntos)
	tell application "Capture One"
		try
			delete every curve point of luma curve of adjustments of objetivo
		end try
		set restantes to count of curve points of luma curve of adjustments of objetivo
	end tell
	-- if Capture One keeps the end points, they are adjusted instead of created
	repeat with pt in puntos
		set valorBrillo to item 1 of pt
		set valorCantidad to item 2 of pt
		set hecho to false
		if restantes > 0 then
			tell application "Capture One"
				repeat with cp in (curve points of luma curve of adjustments of objetivo)
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
				tell application "Capture One" to make new curve point at end of curve points of luma curve of adjustments of objetivo with properties {brightness:valorBrillo, amount:valorCantidad}
			on error
				try
					tell application "Capture One" to tell (luma curve of adjustments of objetivo) to make new curve point with properties {brightness:valorBrillo, amount:valorCantidad}
				on error
					return false
				end try
			end try
		end if
	end repeat
	-- check: the central point must be in place
	set central to item (((count of puntos) + 1) div 2) of puntos
	try
		tell application "Capture One"
			repeat with cp in (curve points of luma curve of adjustments of objetivo)
				if my absoluto((brightness of cp) - (item 1 of central)) < 0.05 and my absoluto((amount of cp) - (item 2 of central)) < 0.05 then return true
			end repeat
		end tell
	end try
	return false
end ponerCurva

on restaurarCurva(objetivo, puntos)
	if (count of puntos) < 2 then set puntos to {{0, 0}, {100, 100}}
	try
		my ponerCurva(objetivo, puntos)
	end try
end restaurarCurva


on separadorDecimal()
	return text 2 of ((1 / 2) as text)
end separadorDecimal

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
