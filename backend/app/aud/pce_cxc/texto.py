"""Texto que viene del cliente y termina en una celda del papel de trabajo.

Todo lo que el papel imprime de nombre de cliente, nombre de archivo, número de
documento, entidad, justificación o sustento lo escribe el CLIENTE. Excel (y
`openpyxl`) tratan como fórmula cualquier texto que empiece por «=», y Excel
vuelve a interpretar la entrada al PEGAR una celda, donde «+», «-» y «@»
también abren una fórmula. Un nombre de cliente como ``=cmd|' /C calc'!A0``
tiene por eso dos caras y las dos son graves:

1. **Inyección de fórmula o DDE** en un libro que el auditor abre en su máquina.
2. **El libro pide reparación**: una fórmula inválida es justo lo que hace que
   Excel ofrezca «recuperar» el archivo, y que el libro abra sin pedir
   reparación es la garantía central de este papel de trabajo.

La política de este módulo, en dos piezas:

- **El dato no se modifica.** El nombre del cliente se imprime EXACTAMENTE como
  vino: un papel de trabajo que cambia el nombre del deudor deja de ser
  evidencia. Lo que cambia es el TIPO de la celda: se escribe como texto y se
  marca con el prefijo de literal de Excel (`quotePrefix`), que es lo que
  impide que se evalúe ni al abrir ni al pegar.
- **Lo que no es representable se quita.** Los caracteres de control que el XML
  de Excel prohíbe hacen que `openpyxl` levante una excepción al guardar (un
  500 por un dato de entrada), así que se eliminan en la lectura -no llegan ni
  al resultado guardado-.

`exporter._celda` aplica esto a TODO texto por defecto: las fórmulas del papel
son las únicas que se marcan aparte (`exporter._Formula`). Así, un sumidero
nuevo queda saneado sin que nadie se acuerde de sanearlo.
"""
from __future__ import annotations

import re
from typing import Any

#: Caracteres de control que la especificación de OOXML no admite. Son los
#: mismos que `openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE`: si llegan a una celda,
#: guardar el libro levanta `IllegalCharacterError`.
CARACTERES_ILEGALES = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")

#: Con qué caracteres empieza una fórmula. «=» la abre dentro del propio .xlsx;
#: «+», «-», «@», el tabulador y el retorno de carro la abren cuando Excel
#: reinterpreta la ENTRADA, que es lo que pasa al pegar la celda en otra hoja.
INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def limpiar_texto(valor: Any) -> str:
    """Texto listo para una celda: el mismo dato, sin caracteres ilegales.

    No recorta, no cambia mayúsculas y no antepone nada: el contenido que
    devuelve es el que el cliente escribió. Lo único que desaparece son los
    caracteres de control que el XML de Excel no admite, porque con ellos el
    libro no se puede ni guardar.
    """
    return CARACTERES_ILEGALES.sub("", str(valor))


def empieza_como_formula(valor: Any) -> bool:
    """¿Este texto abriría una fórmula si Excel lo interpretara como entrada?"""
    return str(valor)[:1] in INICIOS_DE_FORMULA
