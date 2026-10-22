#!/usr/bin/env python3
"""grano.py: grano fotografico fisicamente escalado y dependiente del tono.

Modelo, en cuatro pasos:

1. Nitidez del material. Antes de nada, la imagen pasa por la MTF de la
   pelicula (gaussiana con el 50 % en --mtf50 ciclos/mm, valor tipico de la
   hoja tecnica de cada material): una diapositiva de 35 mm nunca es tan nitida
   como un sensor de 60 Mpx, y el grano añadido sobre una imagen mas nitida
   que la pelicula se lee como pegado. --mtf50 0 lo desactiva.

2. Textura. El grano es una superposicion de conglomerados de plata (o de
   nubes de colorante) colocados al azar: un modelo booleano de discos. Los
   tamaños no son todos iguales: siguen una distribucion log-normal de
   mediana --grano-um y anchura --poli (0.35 por defecto; 0 = un solo
   tamaño). Cada poblacion es independiente, asi que sus espectros de
   potencia se suman (teorema de Campbell) y el espectro resultante decae sin
   los anillos del disco unico, como el espectro de Wiener medido en pelicula.
   Las nubes de colorante llevan el borde difuminado (difusion del colorante
   al revelar); los conglomerados de plata del B/N, no. --textura gauss
   reproduce la textura de la primera version (ruido gaussiano filtrado).

3. Amplitud. La granularidad rms de la hoja tecnica esta medida con apertura
   de 48 um a densidad 1.0. La amplitud por pixel se calibra MIDIENDO sobre el
   propio campo de ruido cuanto vale su rms al promediarlo en un disco de
   48 um, y escalandolo para que coincida con la del datasheet. Esto es
   exacto para cualquier textura y resolucion. (La version anterior aplicaba
   la ley de Selwyn como si el ruido fuera blanco; con grano correlado a
   10-14 um eso sobrestimaba la amplitud entre 3.8 y 4.7 veces.)

4. Dependencia con el tono. --pelicula selecciona el perfil sigma(densidad
   mostrada) calculado sobre el eje neutro del modelo espectral de cada
   material (tabla embebida): en las diapositivas la fluctuacion sigue la
   estadistica binomial de cobertura de colorante (crece con la densidad y
   decae al saturar cerca de Dmax); en los sistemas de negativo mas papel
   (pro400h, trix) el grano nace en el negativo y llega a la copia
   multiplicado por la pendiente local del papel, que lo anula en los blancos
   y en los negros: el grano vive en los medios, como en una copia real.

El ruido se suma en el dominio de densidad, por capa, con correlacion parcial
entre capas y la componente cromatica escalada aparte (--croma), y se vuelve
al espacio de entrada (--espacio srgb o adobergb, que fija la curva y los pesos
de luminancia). Los TIFF de 16 bits se leen y se escriben a 16 bits con
tifffile, y el perfil ICC de la entrada se conserva en la salida. Requiere numpy
y Pillow, y tifffile para TIFF.

Como mirarlo. El grano esta escalado a la pelicula: a la resolucion del M11
cada pixel son 3.8 um, y un pixel de 3.8 um se juzga al 100 %. Reducir la
imagen con un filtro pobre (muchos visores a "ajustar a ventana") o
recomprimirla en JPEG a calidad media convierte el grano fino en manchas.
Para una version reducida, o se aplica el grano directamente a la imagen ya
reducida (la calibracion vale para cualquier paso de pixel) o se usa
--ancho-salida, que reduce con filtro Lanczos despues de añadir el grano. El
script guarda los JPEG a calidad 95 sin submuestreo de croma.

Uso:
    python3 grano.py entrada.jpg salida.jpg --pelicula trix
    python3 grano.py entrada.jpg salida.jpg --pelicula k64 --intensidad 1.3
    python3 grano.py entrada.jpg salida.jpg --rms 16          # ley generica
    python3 grano.py recorte.jpg salida.jpg --pelicula k64 --ancho-mm 9.1
        (un recorte: se indica cuanto mide sobre el fotograma su lado largo)
    python3 grano.py entrada.jpg web.jpg --pelicula trix --ancho-salida 2000
        (grano a resolucion completa y reduccion con filtro para la web)
"""
import argparse
import base64
import io
import sys
import zlib

import numpy as np
from numpy.fft import rfft2, irfft2

try:
    from PIL import Image
except ImportError:
    sys.exit('Falta Pillow:  pip install pillow')

_PERFILES_B64 = (
    "eNrtWns8VWu3Xu6XChVCaUtFpE1FFDUkKtckKkpSya2Qe7lFhdiSW1EokZCoVIR0Uy7ZIrmU+2Wx7mvOpUIq57Vb2jvrfOd853z/"
    "7O/8zuu3PL815jPeNcda4x3PeOec5sY8vCsI38ciguK1u1wT7MFPECc46v/q5nGciyBGcOL+zpnCBDMrU3NrLoIvIUDxkIPXQU/F"
    "dXKKOoe1FFXkFA+7e3p72rvZuXsecpi0b7Y/4uWA7F5O9h4O6P2yNStVlFTkguT+90OYfcqESymTIxe+40NQXz05nrPf18B3VgPb"
    "3gSOhydHC/v4O/i9bnJ0sHk9bHsvm9/PPj7A9htk80hsHpnNo7J5NDaPweZhbDvG5uPs4yy23zCb94HN+8DmfWTzPrF5I2zeKJs3"
    "yuaNsXmf2bxxNu8Lm/eFzfvK5n1j8ybYPILudztB9zufoPvH4dVcut/9uHS/07jZPG42j1v3+zw8bB4Pm8fL5vGyebxsHh+bx8fm"
    "8bN5/GweP5snwOYJsHmCuuY/5Wcyt//nqfwUQPnpukZ9KkG1+L+TpvBfTVC51f9Sigpv0x0LUPjFAwpvfb651tYdZukfrC4LsAe1"
    "5I2Gd/NRQo6NLMkTaIQrVEvPR02N8C6rZmWpQissbqykBza3gpKhVf861TaIJG8b9ZDqAKJ8phAF7wDjuSnp6bM7ITck3itgfg/E"
    "KyWVfErsgeFwPenuuz3AU7r+wkRPL7zZpp7ad6gP+lPWb5aM7YOZ7RE51zz6wUx2Y/3br/2glcmrNbpqAJ4ndguONw/A4xWCccJH"
    "iFCzoFrD9CYROls+M8ykByHe71NPVPEg1O9rMHAhDMFZa4r9MAzB076FQhhxCGadGzWR0SLB1u2JzzRMSZB3MdPD/zMJHl+v60ra"
    "SYbboUoM501k4K1I/b2SQQZLvTNJznspUNu+5vVxBQqoX48pW9dEgbuxwVdijKlwxHOxt+8oBXz2Xw12uEUFUZeKKpNlNGh25D18"
    "sJQKO2zGnjzxp4HJxuj7Ap9oUFbcyj1yhAav1kgXuGnQIU5Q1GL5PTqI2SrTLojRQSstui1rgA5vjT65X3BggFh8uERjNh1CS4dv"
    "LIhgQDuJKPNiBhNqTWqrPFUZMCix4kixLBNun3O623mdCTm223q23WRA0MLSj/y5TNhZhgtkyWAwftEi4OB8JpwgNvYeF8cgsv70"
    "/re2GDyyakgzCmFC5M0NRprbMPC5IHPTJhUD/YKdVdmtTKiqyTgweBoD39PfPou3YPD2q5VP1BwMtkScdkq5j4F38iKT/Bk4hKiW"
    "2o2txiDHURDcejEoUm/G167HIWbsnIG6OQYTfYUNxwVxKIlpk9/pikM9b4W2jCMGsTuH1MjKOCg5pFK6k3DIjwqdfc8fg1aXHA/S"
    "VhxMf7U2OF6OQ87rgsckdB4POxexLA/gILffUdq0G4f9z6Ki70Rj0DZwTsrVD4cliYu+8X/DoY01cJIvBoNlM5UNrSJx2HKHdbVf"
    "igWMhbWCtEhkbw6cK48+T8T1jnewKgsiezOwXSEYbB87cDs7DQcpq9ExXT1k//Q6fYMHBiIdc4aJGTj4JKqX2W1nwVn/0M60PRic"
    "OUbtkL2Gw7dP8sTAvSwwK5zxu/NGDEpFL87H0TwGDmJf1xxiQfbyEeETizA4cszRKRh9bnlU/AuCEwsOJa8TyP7EhOK+WXbd6Dwv"
    "a7QvPoTshxcdcnFMZ8K6iK86oSguV9XYwnE0j3IWBedaxwQ+odS+cXscrjffvDp3Hws2mFJvjlYz4P72zIcXtuAQaRETsmMHC5zz"
    "pLuzjBgQEhVJurQMB5249lvCBizIfHY56kUFHeZfrj9bwovDG14d3rerWBB2zmRR/hI6lAh/rc5vR79j+zJz0gIWvNzdaeYYQIOV"
    "+hNRT29hYKVbF9/JzYKOvIDKh0+pYDmzTYt6HINibtuk0QEc4lq1AwLRutD/bb5omi4GzAsb5h97hoPox1NeiQso8LuBvX4QFwaM"
    "mSkBfKk4FMlFhKxXJcNr/q3OoX5MOGoZEuPhgcOAxd2iw7+S4Nz1Y2VW3Qx4T6syO62L8gULC34pOQQPc3xz2rQY8LHTUMcQ5eG+"
    "0OHyxF4iRHZc8TkSRgfr8t5Hio0YYLWWuQFnkDAeeitCL6OBb7XsgrQ4DPJ2SI2Y4X3g8t40fk0fFbxF64WsTTH4LXCxbo1EL8Rf"
    "KhidGKaApMa5DX7cGAx7ZUXb/tYJK8JKXfmZZHjF1y7rdZAJMelWExJ+72DrM914vkYSVK66aD1yn/HDbpxqIfPhwhCoFNw493qc"
    "/sMuSIu6u0VnECoqF7g0qP9p7/br7QqvGID1ewRnz7Sl/bC3xRYufjunH6IrK2W3+VDhZ8Gxdvb88JPgrNL4uwrOVEe0P6a+jCpz"
    "GF5v0u5eHaq2QUDpviee3gAFXYwg7ZEG4PKMD9V/1wCy9eKCPOat0Lo+r7ulqRX2RXwsS/utFcoSDHhp+zogJoFkHT/cAVJ1TQsf"
    "VndAccbdLH+DHtDYz1pfm9QD4+7A1xLVA5Jqox4Fon0QkGizMfRwH+ipNq7nPdgH185UJBlk9oO6xCaumYQBMFpfo2vIPQCXeSri"
    "ImYSob5bZEWfGxEy115asd2XCCob/K+0WAzCzQ/zfpEsG4S90rO4bF4OgsH8Y4HPA4bgvOU8ZyXKEOibLLplNDYExZUYhESTQHvM"
    "VnkPgQxxWToWp+eQgap4vgI/TYa+mya8lwgUSMutu1crQYFv2SmH1V0o8H7Zc0s/OgW27OG5Z8RHBQU11wrF9VSY8Trr04NqKlT5"
    "zfkm2k8FHtLtpzsnqLD36nsqTyIN7hGleKpu00Db84rj0B0amF7j3RZtTgdhsViVcHc6GDgKDzZY0aGWC1/jPEEHE9uK2Q/kGHAh"
    "Jy7vNJ0Ol61PHQ/IYIDFyW39LZUMKKnPXfvYnwHiWJKLsToTVGOX5LzYw4QW26SozSMMuK4TfWNfCRM2x5jrqhKZkMazcfdsZyZo"
    "rMtrN5LG4NsmDX+VVRjIX5xv0lrHBDfKqkL6DgwaL2s+K3TFoEFCT7plNgaUeecuvIhChURv9rHcKxiMBCwUO6GJQaddRuabcgws"
    "4k+M5NVjYGzt03B5FwaGOo++jZAx0H5ySTp/DAPxxeaVvp4YkO1VzIzm4PB6d2Su9iJUSFiMJcQIDKKG9c/PXoODTcW7bH0DHMZX"
    "NI/2XUR8k1lfLljhoBJKE7J2wME8f/1w8jVUyCVSdAJQIeK+DWVjoahQbSjaPH4DCQ53yQfNCBy+SIS/PnoZh9OPYmMFczA4v8nw"
    "USHqnN2O2+kzbuPwyuyx0Cs0z/DDZsGXN5AAapdblaNCmK4dO3NpMgauSx0VWXdwSKjnv6TUiEO1px1JEgnUutJe/uDiyYK9IvhV"
    "Ow7uRbGvXVBcK5p3MeUe4tCcXBI01ofD2h1N4uvR9zDzUBnPxgc48C2QNtEcxKFyUM/Deg0GdxTDuowKcfBuPJ/bTMSBwOey6oEo"
    "KnDia317M5G/rQqc68XBl/a11+YlE1K/OiXLJSIBWe7u5vwOh9QWab5V9kw4KRywcDwEh9UbChdv+B2H/rrelCIGA7xDxoQVHXEI"
    "0rnpKPYICYmLctnoEQZMLPu4edgQzcu/qbcxB4fs9NBjZ97TwQFlbKIiDmc0cEfL8zjQjg+HzlhLh2Ptl26kEHDwCyLGe3jhsP3F"
    "aNZgOA30jBKpuW9Rw1Hhp7rEAkcN0UzHxU+oIHiGSyQhEwMiz6ue1So4ROT42KwiUkDJ+IZ52lEMNomvXk1C82k8/JAOH8joe7fX"
    "WYjy77nNfmIcEoQdLb21ilQSjK7UfeHRy4RF8v7OrmkYiJ7KDX5bNQQB71VrdlkwYSisuvLWAdQAiHRnCkag9d2LaV8uZsCVa3ox"
    "8kjQpeouKIgoEEFQt1rpgigD0tOetjXeYQLZesHY2/R+GDCp6h3bTQd8KGHdDnEm1G8pFxoh98Jtbakx0QQa0PZSNZY7M0ChTKNH"
    "ia8HThzoCOAup8JT8WhLy0I6XOcxaE1obgeeppEmh0YKREZTRr2INMjZ6bHZJOMdRNTFv0xqJEPD67yYGUJ/2i3u26zSfEiCeo2n"
    "u47KUH/YVa+RveNPDUH7nl7yaynKD/tJp2/yVisGIf2LAaOHm/zD/jny2VB4PhKihnmtci1D0wTn4MEw4pTgzESC4+twxNfZXkPt"
    "7646EnldDxa+PwBgaBp/0HgfRH8z2pfC/wa81t7ZqzdcD4aCtXsdkhsg56WYrL3pO6iiNzpJVDTDQmUX+VqzVqje82LW/sddcEFN"
    "K2ynz3vYeuDRKyObDogLihWTTkW/7vYDS8ttuoAW84CgptcDVm4hHxUj+kFvd8q5E+098HJWM5N/Vh/YS0q6SGoSwSrU3XDr7j4Y"
    "eOiqm32tHy7e8Vg9t2QQHEY++zBu9cNLdTxSXoQIc+4cOhwsTgKuDBKuSRyA2t9Hq07tHgTJWyXyX83JMLvgkp4e9yBYjoUzA8OH"
    "wO6yiGiAJwX67fpJqkJDoHHjGdE7lQTDe4LlzQOp0GBDojV+GQLM6Nwj5zQy2K/cy1Q4RoPMaski124S+LzCpKqj0fZnifCzYgvU"
    "Tu3jCdl5lwyL5BRL3zlRIdR/xF1wMWovBc6bnPWjgFDdXBq3Jg1uts7Yrt3PgAA7CZnnqlTIq+5tq0bbnxwz8bjORCZcVqYXnOhA"
    "KmYWN9GTS4cTE7sqly9A7bR/1snPQTSIN3bgSjFnwKMTRw7qom0CSU0Ml5Kgw7f8Y++aqAxIyOq5CPkYDKiG7y+6Rgdn1ZxNRwOZ"
    "kLfI88M6Kqry4ouURhUYMNvy66etqM006Vb2SFqCqu5hvyeJ1xjQ1fuk/SSgKnCl9Ej4blRtJERe0ySYEOXAkzkbtbFPu53WaqPq"
    "fuSJ1dUdoUy41X/db2kBBnv2isk2oqr+8tzBh1xI5ZqWHTFt6cJgn+b7lsBmHAK21nHly2FQKegnsQu1o+ZnF3Rt/YjDKqsDhVrG"
    "GAQX/JaauRrNqyP5TlOMBZ/m3RxTRlVdI7GO0r0LVUnL3zOyFVgQu32b0NskDIwSkjLW++MwtPwYxU+LBfO6Wucve4DB0ct6ymWo"
    "SpfvaeavQu38+HN9J80mDLRODXpY38LhPDVtMNSMBVsdH3ur0zHI9hFfuRupjtwT7piHFixI2b2d3syDw6PiB91nm5DKnLl9qQjZ"
    "F5eqknzm4SC5cb92Tw9Sva0W9b2mLJhFJIiLoe3DiokSiTYK+tx3Kypp+ixY+2X7jTgNHGK/peSUYjhslD5oK6/JgnAbLZBEbbpL"
    "aOlSm2EcLp5eky20lAUiyzeVXUPbk2++whaDONoejVgJzxJhwXL1Yq+ZJjgEbxzS5KLj8DxLZ8VVFg7a5bSdT0xxsCs27ZvoR6pk"
    "FsuT+gZH24++F0sRf4P/CjG3Vhz0nn5KDUFxq7sqCT1E8xOutj0Uq8Lhdlyxk/spHEaDbkXpoPMRUMy4V3EXh5Wnh85qWuJAKbh4"
    "PwudP3Zg/wOLSzgUh1U33PkFh450lXQFFG/NBaJ1YxAOhzc3siQHMbDMvWGhjb6f6yU9K41tcTCcLV/rnY2BM3/WOxf0fRpSPUr3"
    "aqG4AuNE8/ajvJWpRCKGQWr+Ce4eERyu9BYs6Ubb7zusF2dmvEEqLJgeqYO2y7bGrrypZ5hQLqVhq38Pg6F85sQulG9HVpPXbHrD"
    "gNqmazTbBKROmj3ON3wxEDteqG8ixgBzrlapZjcMMuNGdUnaqHvaeexZzXo6RAbNWiiAtl1hxj0ZWwgY5Bve6jbXp4F8cufaXCEM"
    "HDQv6qgdY0L1lkQFFzUq5B9uiC7KQtv9pivVkmgbaZh5r4ZXdvKyRt+buVuZ0JVVcE9OkAFf4+cufzqXDI5rfxE51saA5OacsuY3"
    "aP3tPxlxhpsEWNGlgw0bGbBXfHs1F9BhhjO5frxxEA7lR8bNP0cH395QpzleNFBjHdE/tRep5sGJ50JdNFg/NE9WJYYK1gQLy7Y9"
    "/cDFU+b0aBkNXlA1Tl+JpUxTnb3S8X5TqjMDqY6Hp7u6mprT31V0xigWt8sVmiBI/ri27/Fm8CZtbiarVMJ0e9DXeS99b72Bsr75"
    "bfyOXdBluby9QKAHGpTiO3s3dIDAHu0DrmeQGLiHyXJJDICKbEbuE0ofPBIpmUXnHYKUk7TGPvsh8N/g+2bRxiFwNbnF2kYlw4zs"
    "OobeSgqYpnckyPxChZUXZy4XOEwD2/wKtfarNHj17peKofMMqAl54yYYzoBo448vJB8wQHCDfOmJ16ioEN2S9H7FIC7uTPJVAwxy"
    "agYSLr5Ci+rL47tXvmLwSL3l22spHEo/tHzpzEctb6iMgsU5HK5GBu7TSMKBbLShhxCGg3O+MdddbxyEWGvkJtxRcbHb7vcYFV/t"
    "X0XvBqJFy3QboPNuQkXELktXZSUOyxNkO8ZlcNj/VieoDC0644FeCytUVFuJ1fe8MAxOCAoZi6Li9rYzdJ0SEQN1zZCc8pcYxLBM"
    "LJej7ZZbT3xyTgUG3GJfHftQa/d0Xa3zh8sYjDk6lpFR6z3wW5AuwwcDniDlr1u8UJzjH82HEUrHsqjZpuh4kKZBsAlqxbOIjkVm"
    "GJwNqyizVMAg2WlNpA/CrUoPM0SWYT8unk/HEpfnmfV3mWBCYezKuceE+NCUcb1CJuRmS/BIOzDhyjxZKdyFCdY6n05cQluptTPM"
    "evokmSDTqNntKseErB7h5H5eJnga3aA01jLgfiBDU6KZAduspGen5TCgqstFAj/JgN0EbvGAaAbMzGDwnNrMADHnvA0jqxlQXWOx"
    "cT5ajDKreLq1u+hgrut+6swgHYlNjb3dMB3uCTtpByvSIUWnKsjwMh1EVVJN/W7QwfHoI1G++VRIMAuwTt5Gh5fN/kq/29CB0Uhz"
    "mUsnwZXVgvPvE+ggnSu+vViYDm9iwry8ng9Cj6myVHwBDTqjrvsvKkb5dalAo6dwALQKVhP79tAgKiCB94sdDZ7sEvDeVtwHR6tP"
    "j1wXpEFA8QeJ1Xw0WBy487kOsQd+oRpdnXGXCnSPjyPF2VTY8rjqjuLRLmjq5LnOt5sKDr03XbM2UmEiqLM8fU87nC0/LBT2mQIV"
    "+7P3fHlDgQw/bdLZtDb4pWqdumcKBcKUqrYE7KSAK2GO/SexFvg2XNH6XJ0CtFe8CW9PkeCVodTmwowmqNXprPWuIUPE0MlP1blE"
    "eFCjKxCo2gj7Ht2r1LUkw2br7k3DRX1g8rrtrGFrHSxNXyN1pZUEGqQ11Dt7uuG8hOoFt+CXEPxero7ryRCsdNXf9k74HfSu6Y0P"
    "tqyADyZalu3HiCBe4hluk/Tmh33X2R25F/j6oWhhYK372uqpmx2EJwdUEyWjUPMou+bUx6iSH3a3HXdl3XraOexx4Se56gJbfryf"
    "Gn3JoilkoUYOe0T2Tidp2ksO+4GVTV3q9Af/tP3/6vhZdNbLLC2fEh1BJDrens7+f1fF2XFKNTJUow6mo7exj8gO2SYOLLEXEI72"
    "auXA0yIG9+8Yt3Og8unB4rlS3RzIei7hEn6slwMPL+CRdLfq58D1ac/Dlq8kcmDn+d9qCCODHJiqGIq75ZI4UPVEu6X3FgoH+hjZ"
    "5e99SuXAPBUxKQkZOgda2ey23LyDwYHNzsoZuDOTA7Gb7xJbFTEOtHezTqqJ4MRgZV7yghxO9KkJElBy50QscNX4fE1O/EeK86BN"
    "65ZuApMD1RRa+ZSUObHQ5s3as5UMDjT1K6l5ZceJ2ZfCmX5jdA6U9fOe4ZXIiZcGjIjjapxYwi/boFxF48DTfg6C1dacuDz7uE4J"
    "icqBZrNlKc0enFiaE/ehgkHhwMDtd7SMX5A4sDT8bdWRWQMcaH/LasQtsYMDD7llLjB2f/VPI+H/x/+P/7HiZF/fnTmlOMKTd3Ps"
    "/qo5yWzeFP5LmrP6X33CRU7YWr2ooO8En+50/DmmN1U2alMxzfojpmmbt79bWL8+3rjt8j4e3c15HloqTjy661xCipJW8UwLq3Bz"
    "ouNUWEJ/hPWXZz3+biH9I/X4b0P6827iv39IIn+ENP169b9PXFzcK3h+fhJu8lm3yRf/XwrKSa7J/9+fi5vuM/l00mTDOvkS+Mnn"
    "KpqFnb/TnSbvMP/nTrOFCFP3m6c7Td4lmHKa+ZNTmCjhp3sG0z0nr/RMec74yXNUgvDX6z7THSe79SlHwZ8cjy4g/Ojdp3tNVtxk"
    "9s8v/JNXtzzhL/V3ut9kVZvym/WTX9Fiws81brrrZE5OuQr95Bq1hPBnHfnn3WyXEv5cq/+Vm8hPbmoKhGnrwdyY749UmoH+DqGM"
    "EFScfPcf0arxaQ==")
_P = np.load(io.BytesIO(zlib.decompress(base64.b64decode(_PERFILES_B64))))
GD = _P['gD']
# ganancia de copia: en los sistemas negativo+papel la rms del datasheet es la del
# NEGATIVO, y la copia la multiplica por la pendiente local del papel; k es ese factor
# en la densidad mostrada 1.0 (por canal), calculado con las curvas reparadas y con la
# gamma del papel acotada a 3.0 (la curva digitalizada del MG IV llega a 4.0 y un
# grado 2 real ronda 3): x2.7 en Tri-X, x2.4 en PRO 400H. --intensidad lo escala:
# 0.75 equivale a gamma 2.3, 0.37 quita la ganancia de copia del Tri-X
K_COPIA = {k[2:]: np.asarray(_P[k], float) for k in _P.files if k.startswith('k_')}

# rms: granularidad difusa rms de la hoja tecnica (x1000, apertura 48 um, D=1.0)
# grano_um: diametro caracteristico del conglomerado
# textura: 'nube' (colorante, borde difuso) o 'disco' (plata, borde neto)
# mtf50: frecuencia (ciclos/mm) a la que la MTF del material cae al 50 %, valor
#        tipico de la hoja tecnica; se puede afinar con --mtf50
# poli: anchura (sigma del logaritmo) de la distribucion de tamaños de los
#        conglomerados; 0 = todos del mismo tamaño
PRESETS = {
    'k64':      dict(rms=10, grano_um=11.0, corr=0.35, croma=0.45, textura='nube',  mtf50=40.0, poli=0.35),
    'k25':      dict(rms=9,  grano_um=10.0, corr=0.35, croma=0.45, textura='nube',  mtf50=45.0, poli=0.35),
    'velvia50': dict(rms=9,  grano_um=10.0, corr=0.35, croma=0.45, textura='nube',  mtf50=50.0, poli=0.35),
    'pro400h':  dict(rms=4,  grano_um=12.0, corr=0.35, croma=0.45, textura='nube',  mtf50=30.0, poli=0.35),
    'trix':     dict(rms=17, grano_um=14.0, corr=1.0,  croma=1.0,  textura='disco', mtf50=40.0, poli=0.35),
}
GENERICO = dict(rms=10, grano_um=11.0, corr=0.35, croma=0.45, textura='nube', mtf50=0.0, poli=0.35)


def srgb_eotf(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def srgb_oetf(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055)


# ---------- espacios de color de trabajo ----------
# Cada espacio define su curva de codificacion y los pesos de luminancia (fila Y de
# su matriz RGB->XYZ, D65), que son los que reparten el grano entre luminancia y croma.
GAMMA_ADOBE = 563.0 / 256.0
ESPACIOS = {
    'srgb': dict(eotf=srgb_eotf, oetf=srgb_oetf,
                 wv=np.array([0.2126, 0.7152, 0.0722])),
    'adobergb': dict(eotf=lambda v: np.clip(v, 0, 1) ** GAMMA_ADOBE,
                     oetf=lambda v: np.clip(v, 0, 1) ** (1 / GAMMA_ADOBE),
                     wv=np.array([0.2973769, 0.6273491, 0.0752741])),
}

ICC_TAG = 34675


def leer_imagen(ruta):
    """Devuelve (rgb en [0,1] float64, escala original 255 o 65535, perfil ICC o None).
    Los TIFF se leen con tifffile para conservar los 16 bits: Pillow los reduce a 8
    sin avisar."""
    icc = None
    if ruta.lower().endswith(('.tif', '.tiff')):
        try:
            import tifffile
        except ImportError:
            sys.exit('Para TIFF de 16 bits hace falta tifffile:  pip install tifffile')
        with tifffile.TiffFile(ruta) as t:
            pag = t.pages[0]
            arr = pag.asarray()
            tag = pag.tags.get(ICC_TAG)
            if tag is not None:
                icc = bytes(tag.value)
        if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[-1] not in (3, 4):
            arr = np.moveaxis(arr, 0, -1)
        if arr.ndim == 2:
            arr = np.repeat(arr[..., None], 3, axis=2)
        arr = arr[..., :3]
        if arr.dtype == np.uint16:
            escala = 65535.0
        elif arr.dtype == np.uint8:
            escala = 255.0
        else:
            sys.exit('Formato TIFF no admitido: %s' % arr.dtype)
        return arr.astype(np.float64) / escala, escala, icc
    im = Image.open(ruta)
    icc = im.info.get('icc_profile')
    arr = np.asarray(im.convert('RGB')).astype(np.float64)
    return arr / 255.0, 255.0, icc


def reducir(res, ancho):
    """Lanczos canal a canal en coma flotante, valido para 8 y 16 bits"""
    h, w, _ = res.shape
    alto = max(1, round(h * ancho / w))
    canales = [np.asarray(Image.fromarray(res[..., c].astype(np.float32), 'F')
                          .resize((ancho, alto), Image.LANCZOS)) for c in range(3)]
    return np.clip(np.stack(canales, -1) + 0.5, 0, np.iinfo(res.dtype).max).astype(res.dtype)


def guardar_imagen(ruta, res, icc):
    """res: uint8 o uint16, H x W x 3. Conserva el perfil ICC de la entrada."""
    if ruta.lower().endswith(('.tif', '.tiff')):
        import tifffile
        extra = [(ICC_TAG, 7, len(icc), icc, True)] if icc else []
        tifffile.imwrite(ruta, res, photometric='rgb', compression='zlib', extratags=extra)
        return
    if res.dtype == np.uint16:
        res = (res.astype(np.float64) / 257.0 + 0.5).astype(np.uint8)
    im = Image.fromarray(res, 'RGB')
    opciones = {'icc_profile': icc} if icc else {}
    if ruta.lower().endswith(('.jpg', '.jpeg')):
        im.save(ruta, quality=95, subsampling=0, **opciones)
    else:
        im.save(ruta, **opciones)


# ---------- nucleos de convolucion (por FFT, con envoltura circular) ----------

def _nucleo_fft(shape, k):
    h, w = shape
    K = np.zeros((h, w))
    kh, kw = k.shape
    K[:kh, :kw] = k
    K = np.roll(K, (-(kh // 2), -(kw // 2)), (0, 1))
    return rfft2(K)


def _disco(r_px):
    """disco de radio r_px con bordes antialias (supermuestreo 4x4)"""
    n = int(np.ceil(r_px)) * 2 + 3
    c = n // 2
    yy, xx = np.mgrid[:n, :n] - c
    acc = np.zeros((n, n))
    for dy in (-.375, -.125, .125, .375):
        for dx in (-.375, -.125, .125, .375):
            acc += ((xx + dx) ** 2 + (yy + dy) ** 2 <= r_px ** 2)
    return acc / 16.0


def _gauss(sigma_px):
    n = int(np.ceil(3 * sigma_px)) * 2 + 1
    c = n // 2
    yy, xx = np.mgrid[:n, :n] - c
    g = np.exp(-(xx ** 2 + yy ** 2) / (2 * sigma_px ** 2))
    return g / g.sum()


def _filtro_textura(shape, textura, grano_um, pitch_um, poli=0.35):
    """respuesta en frecuencia del filtro que da la correlacion espacial del grano.
    Con poli > 0 los conglomerados tienen tamaños log-normales (mediana grano_um,
    sigma del logaritmo poli); como las poblaciones son independientes, se suman
    sus espectros de potencia (Campbell) y se devuelve la raiz, un filtro de fase
    cero con el espectro de la mezcla."""
    if textura == 'gauss':
        return _nucleo_fft(shape, _gauss(max(0.35, (grano_um / pitch_um) / 2.355)))
    if poli > 0:
        s = np.linspace(-2.5 * poli, 2.5 * poli, 9)
        w = np.exp(-0.5 * (s / poli) ** 2)
        w /= w.sum()
    else:
        s, w = np.array([0.0]), np.array([1.0])
    P = 0.0
    for sk, wk in zip(s, w):
        r = max(0.6, 0.5 * grano_um * np.exp(sk) / pitch_um)
        Hk = _nucleo_fft(shape, _disco(r))
        if textura == 'nube':        # nube de colorante: disco con el borde difundido
            Hk = Hk * _nucleo_fft(shape, _gauss(max(0.35, r / 3.0)))
        P = P + wk * np.abs(Hk) ** 2
    return np.sqrt(P)


def campo(shape, H, rng):
    """campo de ruido de varianza unidad por pixel con la correlacion de H"""
    h, w = shape
    f = irfft2(rfft2(rng.standard_normal((h, w))) * H, s=(h, w))
    return f / max(f.std(), 1e-12)


def rms_en_apertura(f, pitch_um, diametro_um=48.0):
    """desviacion tipica del campo promediado en un disco de `diametro_um`"""
    r = 0.5 * diametro_um / pitch_um
    if r < 0.5:
        return float(f.std()) * (2 * r)  # apertura menor que el pixel: Selwyn
    K = _disco(r)
    K /= K.sum()
    return float(irfft2(rfft2(f) * _nucleo_fft(f.shape, K), s=f.shape).std())


def escala_por_pixel(textura, grano_um, pitch_um, rms, poli=0.35):
    """sigma de densidad por pixel a D=1 que deja la rms de la hoja tecnica en 48 um.
    Se mide sobre un campo de referencia con la misma textura y el mismo paso."""
    shape = (768, 768)
    H = _filtro_textura(shape, textura, grano_um, pitch_um, poli)
    f = campo(shape, H, np.random.default_rng(20240912))
    s48 = rms_en_apertura(f, pitch_um)
    return (rms / 1000.0) / max(s48, 1e-9), s48


def desenfoque_mtf(lin, mtf50, pitch_um):
    """MTF gaussiana con el 50 % en mtf50 ciclos/mm, aplicada en luz lineal"""
    if not mtf50 or mtf50 <= 0:
        return lin, 0.0
    sigma_um = 1000.0 * np.sqrt(np.log(2) / 2.0) / (np.pi * mtf50)
    sigma_px = sigma_um / pitch_um
    if sigma_px < 0.25:
        return lin, sigma_px
    h, w, _ = lin.shape
    H = _nucleo_fft((h, w), _gauss(sigma_px))
    out = np.empty_like(lin)
    for c in range(3):
        out[..., c] = irfft2(rfft2(lin[..., c]) * H, s=(h, w))
    return np.clip(out, 0, 1), sigma_px


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('entrada')
    ap.add_argument('salida')
    ap.add_argument('--pelicula', choices=list(PRESETS) + ['generico'],
                    default='generico',
                    help='usa el perfil sigma(D) y los valores del material')
    ap.add_argument('--rms', type=float, default=None,
                    help='granularidad rms del datasheet (anula el preset)')
    ap.add_argument('--grano-um', type=float, default=None,
                    help='diametro caracteristico del conglomerado en micras')
    ap.add_argument('--textura', choices=['nube', 'disco', 'gauss'], default=None,
                    help='nube = colorante (borde difuso), disco = plata, '
                         'gauss = textura de la version anterior')
    ap.add_argument('--mtf50', type=float, default=None,
                    help='MTF del material: ciclos/mm al 50 %%; 0 la desactiva')
    ap.add_argument('--poli', type=float, default=None,
                    help='anchura de la distribucion de tamaños de conglomerado '
                         '(sigma del logaritmo); 0 = un solo tamaño; 0.35 por defecto')
    ap.add_argument('--ancho-salida', type=int, default=0,
                    help='si se indica, reduce el resultado a este ancho en px con '
                         'filtro Lanczos (para la web); 0 = tamaño original')
    ap.add_argument('--ancho-mm', type=float, default=36.0,
                    help='cuanto mide sobre la pelicula el lado largo de la '
                         'imagen (36 = fotograma entero de 24x36)')
    ap.add_argument('--intensidad', type=float, default=1.0)
    ap.add_argument('--correlacion', type=float, default=None,
                    help='correlacion entre capas; 1.0 = monocroma')
    ap.add_argument('--croma', type=float, default=None,
                    help='ganancia de la componente cromatica del grano '
                         '(0 = grano acromatico, 1 = capas plenamente '
                         'independientes); por defecto 0.45 en color')
    ap.add_argument('--espacio', choices=list(ESPACIOS), default='srgb',
                    help='espacio de color de la entrada: srgb o adobergb (curva y '
                         'pesos de luminancia); el perfil ICC se conserva en la salida')
    ap.add_argument('--semilla', type=int, default=None)
    ap.add_argument('--dmax-vis', type=float, default=2.6)
    a = ap.parse_args()

    pre = PRESETS.get(a.pelicula, GENERICO)
    rms = a.rms if a.rms is not None else pre['rms']
    gum = a.grano_um if a.grano_um is not None else pre['grano_um']
    corr = a.correlacion if a.correlacion is not None else pre['corr']
    croma = a.croma if a.croma is not None else pre['croma']
    textura = a.textura or pre['textura']
    mtf50 = a.mtf50 if a.mtf50 is not None else pre['mtf50']
    poli = a.poli if a.poli is not None else pre.get('poli', 0.35)

    esp = ESPACIOS[a.espacio]
    rgb, escala, icc = leer_imagen(a.entrada)
    h, w, _ = rgb.shape
    pitch_um = 1000.0 * a.ancho_mm / max(h, w)

    # 1. nitidez del material
    lin, sigma_mtf = desenfoque_mtf(esp['eotf'](rgb), mtf50, pitch_um)
    D = -np.log10(np.clip(lin, 10 ** (-a.dmax_vis), 1.0))

    # 2. textura y 3. amplitud calibrada en 48 um
    sigma_D1, s48 = escala_por_pixel(textura, gum, pitch_um, rms, poli)
    k_copia = K_COPIA.get(a.pelicula, np.ones(3))
    # la rms de la hoja tecnica es granularidad de densidad VISUAL (luminancia); con
    # capas solo parcialmente correladas, la luminancia de tres capas de sigma s vale
    # s*f_lum (0.845 para corr 0.35), asi que la sigma por capa se escala con 1/f_lum
    WV = esp['wv']
    f_lum = np.sqrt((WV ** 2).sum() + 2 * corr * (WV[0] * WV[1] + WV[0] * WV[2] + WV[1] * WV[2]))
    sigma_D1 = sigma_D1 / f_lum
    rng = np.random.default_rng(a.semilla)
    H = _filtro_textura((h, w), textura, gum, pitch_um, poli)
    comun = campo((h, w), H, rng)
    campos = []
    for _ in range(3):
        propio = campo((h, w), H, rng)
        n = np.sqrt(corr) * comun + np.sqrt(max(0.0, 1 - corr)) * propio
        campos.append(n / max(n.std(), 1e-9))
    ruido = np.stack(campos, -1)

    # 4. dependencia con el tono
    if a.pelicula != 'generico':
        T = _P[a.pelicula]
        rel = np.stack([np.interp(D[..., c], GD, T[:, c]) for c in range(3)], -1)
    else:
        rel = np.sqrt(np.clip(D, 0.0, None))
    sig = sigma_D1 * k_copia[None, None, :] * rel * a.intensidad

    # descomponer el ruido de densidad en luminancia y croma: la calibracion
    # rms del datasheet es de densidad visual, asi que se conserva integra en
    # la componente de luminancia y el croma se escala aparte
    dn = ruido * sig
    lum = (dn * WV).sum(-1, keepdims=True)
    dn = lum + croma * (dn - lum)
    # la densidad macroscopica de la hoja tecnica esta definida sobre la
    # transmitancia MEDIA: un ruido de media cero en densidad aclararia la zona
    # granulada en exp((sigma ln10)^2/2) (1-3 %); se compensa con el sesgo
    # log-normal, calculado con la sigma efectiva de cada canal tras el reparto
    var_lum = ((WV * sig) ** 2).sum(-1, keepdims=True) + 2 * corr * (
        WV[0] * WV[1] * sig[..., 0:1] * sig[..., 1:2] + WV[0] * WV[2] * sig[..., 0:1] * sig[..., 2:3]
        + WV[1] * WV[2] * sig[..., 1:2] * sig[..., 2:3])
    var_ef = np.clip(var_lum + croma ** 2 * (sig ** 2 - var_lum), 0, None)
    sesgo = 0.5 * np.log(10.0) * var_ef
    Dg = np.clip(D + dn + sesgo, 0.0, a.dmax_vis)
    out = esp['oetf'](10.0 ** (-Dg))
    res = np.clip(out * escala + 0.5, 0, escala).astype(
        np.uint16 if escala > 255 else np.uint8)
    if a.ancho_salida and a.ancho_salida < w:
        res = reducir(res, a.ancho_salida)
    guardar_imagen(a.salida, res, icc)
    ancho_final = res.shape[1]
    kv = float(np.dot(WV, k_copia))
    print('grano %s: rms=%g  pitch=%.2f um  textura=%s  grano=%g um (poli %g)  '
          'sigma por pixel (D=1)=%.4f%s  [rms medida a 48 um: %.1f]  '
          'MTF50=%g c/mm (sigma %.2f px)  croma=%g%s'
          % (a.pelicula, rms, pitch_um, textura, gum, poli,
             sigma_D1 * kv * a.intensidad,
             '' if abs(kv - 1) < 1e-6 else '  (ganancia de copia x%.2f)' % kv,
             1000 * sigma_D1 * s48 * a.intensidad,
             mtf50, sigma_mtf, croma,
             '  salida reducida a %d px' % ancho_final if a.ancho_salida else ''))


if __name__ == '__main__':
    main()
