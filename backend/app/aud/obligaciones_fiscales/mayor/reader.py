"""Lectura de un Mayor General en Excel, agnóstica del ERP de origen.

El formato varía por cliente, así que el encabezado y las columnas se
autodetectan por sinónimos. Si no se logra el mapeo mínimo, el resultado lo
reporta en lugar de fallar: el auditor mapea las columnas a mano.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from io import BytesIO

from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales.cedulas.base import _parse_amount_sri
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    COLUMNAS_MINIMAS,
    LecturaMayor,
    Movimiento,
)

# Sinónimos por campo. Se compara por igualdad exacta sobre el encabezado
# normalizado; el "contiene" sólo se usa como respaldo y NUNCA para 'cuenta'
# (porque 'Persona Cruce Cuenta' lo capturaría por error).
SINONIMOS: dict[str, tuple[str, ...]] = {
    # 'cuenta' va AL FINAL: es un sinónimo débil de código (solo aparece en
    # encabezados de dos columnas tipo 'Cuenta | Nombre', donde 'Cuenta' es
    # el código). Cuando el encabezado real ya tiene una columna 'Cuenta'
    # propia (el nombre de la cuenta), esa se resuelve primero por su
    # propio código exacto ('cuenta contable', 'cta', ...) antes de llegar
    # a esta columna, así que el orden no la roba.
    "codigo": ("codigo", "cod", "cod cuenta", "codigo cuenta", "cuenta contable",
               "nro cuenta", "numero de cuenta", "cta", "cuenta"),
    "cuenta": ("cuenta", "nombre", "nombre cuenta", "nombre de cuenta",
               "descripcion cuenta", "detalle cuenta"),
    "fecha": ("fecha", "fecha asiento", "fecha movimiento", "f asiento"),
    "asiento": ("asiento", "comprobante", "nro asiento", "numero asiento",
                "no asiento", "diario", "nro comprobante"),
    "documento": ("documento", "doc", "nro documento", "comprobante venta",
                  "factura"),
    "identificacion": ("identificacion", "ruc", "cedula", "ruc cedula", "nit",
                       "identificacion tercero"),
    "persona": ("persona", "razon social", "tercero", "proveedor", "cliente",
                "beneficiario", "nombre tercero"),
    "descripcion": ("descripcion", "glosa", "detalle", "concepto",
                    "observacion", "observaciones"),
    "debe": ("debe", "debito", "cargo", "debitos"),
    "haber": ("haber", "credito", "abono", "creditos"),
    "saldo": ("saldo", "saldo final", "saldo acumulado"),
}

# Campos donde el respaldo por "contiene" sería peligroso.
SOLO_EXACTO = frozenset({"cuenta", "saldo"})

# Palabras que delatan la columna de débito y la de crédito. Se usan para
# reconocer (y descartar) la columna COMBINADA que algunos ERP publican: una
# sola columna con el cargo y el abono en un mismo campo, con signo
# ('Cargo/Abono (ML)', 'Débito/Crédito', 'Movimiento neto'). Esa columna NO es
# ni el debe ni el haber, es el NETO.
_TOKENS_DEBE = ("debe", "debito", "cargo")
_TOKENS_HABER = ("haber", "credito", "abono")

# Un código de cuenta: solo dígitos y puntos, al menos tres caracteres. Así
# '11010102' y '1.1.5.1.1' cuentan, pero un '0' suelto o una fecha no.
_RE_CODIGO_CUENTA = re.compile(r"^\d[\d.]{2,}$")

# Celda de cuenta FUSIONADA 'código - nombre' en un solo campo, como la exporta
# el ERP del cliente ('1.4.3.23 - 15% IVA EN COMPRAS LOCALES SERVICIOS'). El
# separador va rodeado de espacios para no partir códigos con guiones internos
# ('1-01-001'); el nombre debe tener al menos una letra.
_RE_COD_NOMBRE_FUSIONADO = re.compile(r"^\s*(\d\S*)\s+[-–:]\s+(.+?)\s*$")


def _split_codigo_nombre(raw: str) -> tuple[str, str]:
    """Separa 'código - nombre' en (código, nombre).

    Si la celda no trae el nombre fusionado (código puro, p. ej. '1.1.5.1.1'),
    devuelve (código, ''): el nombre vendrá de una columna propia, de la
    cabecera del bloque o de la glosa, según el layout.
    """
    s = (raw or "").strip()
    m = _RE_COD_NOMBRE_FUSIONADO.match(s)
    if m and any(c.isalpha() for c in m.group(2)):
        return m.group(1), m.group(2).strip()
    return s, ""

# Secciones del balance/estado de resultados que encabezan un bloque en los
# mayores tipo SAP; nunca son el nombre propio de una cuenta.
_SECCIONES_MAYOR = frozenset({
    "activos", "activo", "pasivos", "pasivo", "patrimonio", "ingresos",
    "ingreso", "gastos", "gasto", "costos", "costo", "resultados",
    "resultado", "cuentas de orden", "otros", "otras",
})

MAX_FILAS_BUSQUEDA_ENCABEZADO = 30

# Prefijos (normalizados) que delatan una fila de acumulado por cuenta
# ("TOTAL CUENTA", "SALDO ANTERIOR", ...) en vez de un movimiento real.
_PREFIJOS_FILA_ACUMULADO = (
    "total", "suma", "subtotal", "saldo anterior", "saldo inicial",
)

# Cuantas entradas de "importe no parseable" se listan en errores como
# máximo, para no inundar el reporte de lectura.
MAX_ERRORES_IMPORTES_NO_PARSEABLES = 10


def _norm(valor) -> str:
    """minúsculas, sin tildes, sin puntuación, espacios colapsados."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(s.split())


def _es_columna_combinada(texto: str) -> bool:
    """True si el encabezado normalizado combina débito y crédito en una sola
    columna (p.ej. 'cargo abono ml', 'debito credito', 'debe haber').

    Esa columna trae el NETO con signo, no el débito bruto: mapearla como
    'debe' mete el crédito (que viene negativo) dentro del débito y corrompe
    los totales del mayor. Defecto detectado con el mayor SAP de ELEA, cuya
    columna 'Cargo/Abono (ML)' se colaba como 'debe' por delante de la columna
    real 'Cargo (ML)'.
    """
    tiene_debe = any(t in texto for t in _TOKENS_DEBE)
    tiene_haber = any(t in texto for t in _TOKENS_HABER)
    return tiene_debe and tiene_haber


def _mapear_encabezado(celdas: list) -> dict[str, int]:
    """Devuelve {campo: índice de columna} para una fila candidata."""
    normalizadas = [_norm(c) for c in celdas]
    mapeo: dict[str, int] = {}
    usadas: set[int] = set()

    for campo, opciones in SINONIMOS.items():
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            # La columna combinada (cargo Y abono) no es ni el debe ni el
            # haber: se salta para no robarles el índice.
            if campo in ("debe", "haber") and _es_columna_combinada(texto):
                continue
            if texto in opciones:
                mapeo[campo] = i
                usadas.add(i)
                break

    for campo, opciones in SINONIMOS.items():
        if campo in mapeo or campo in SOLO_EXACTO:
            continue
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            if campo in ("debe", "haber") and _es_columna_combinada(texto):
                continue
            if any(texto.startswith(o) for o in opciones):
                mapeo[campo] = i
                usadas.add(i)
                break

    # Último recurso (defecto 6): si 'cuenta' (nombre de la cuenta) no se
    # resolvió por NINGÚN sinónimo propio pero sí hay una columna
    # 'descripcion' mapeada, esa columna es probablemente el nombre de la
    # cuenta (ERP sin columna 'Nombre' separada, ej.
    # 'Cta | Descripción | Debe | Haber'). Solo cede cuando 'cuenta' no se
    # resolvió de ninguna otra forma, para no confundir la glosa del
    # movimiento del encabezado real de 12 columnas (donde 'Cuenta' ya se
    # mapea por su propio sinónimo antes de llegar a 'Descripción').
    if "cuenta" not in mapeo and "descripcion" in mapeo:
        mapeo["cuenta"] = mapeo.pop("descripcion")

    return mapeo


def _fecha(valor) -> datetime.date | None:
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if valor is None:
        return None
    texto = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _limpiar_importe(texto: str) -> str:
    """Normaliza formatos habituales de exportaciones de ERP antes de
    delegar el parseo a `_parse_amount_sri`: quita símbolos de moneda
    ('$', 'USD') y espacios, convierte el negativo contable entre
    paréntesis ('(150.00)') en '-150.00', y trata un guion solo ('-') o
    una celda vacía como cero.
    """
    t = (texto or "").strip()
    if not t:
        return t
    for simbolo in ("$", "USD", "usd"):
        t = t.replace(simbolo, "")
    t = t.strip()
    negativo = t.startswith("(") and t.endswith(")")
    if negativo:
        t = t[1:-1].strip()
    t = t.replace(" ", "")
    if t in ("-", ""):
        return "0"
    if negativo and not t.startswith("-"):
        t = "-" + t
    return t


def _importe(valor, *, lectura: LecturaMayor, fila_num: int, campo: str) -> float:
    """Convierte una celda de importe a float.

    Si tras limpiar el texto sigue sin poder parsearse, NO desaparece en
    silencio como 0.00: se cuenta en `lectura.importes_no_parseables` y se
    deja rastro (fila y texto original) en `lectura.errores`, hasta un
    máximo de entradas para no inundar el reporte.
    """
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = _texto(valor)
    limpio = _limpiar_importe(texto)
    if not limpio:
        return 0.0
    parsed = _parse_amount_sri(limpio)
    if parsed is not None:
        return parsed
    lectura.importes_no_parseables += 1
    if len(lectura.errores) < MAX_ERRORES_IMPORTES_NO_PARSEABLES:
        lectura.errores.append(
            f"Fila {fila_num}: importe no parseable en '{campo}': {texto!r}"
        )
    return 0.0


def _es_fila_acumulado(cuenta: str, descripcion: str) -> bool:
    """Filas de TOTAL/SUBTOTAL/SALDO que un ERP emite al cierre de cada
    cuenta: llevan código pero no son un movimiento (defecto 2). El texto
    delator puede venir en el nombre de la cuenta o en la glosa/descripción.
    """
    for texto in (cuenta, descripcion):
        n = _norm(texto)
        if any(n.startswith(p) for p in _PREFIJOS_FILA_ACUMULADO):
            return True
    return False


def _celda_tiene_importe(celdas, mapeo: dict[str, int], campo: str) -> bool:
    """True si la celda del campo trae un importe distinto de cero."""
    i = mapeo.get(campo)
    if i is None or i >= len(celdas):
        return False
    val = celdas[i]
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return float(val) != 0.0
    limpio = _limpiar_importe(_texto(val))
    if not limpio:
        return False
    parsed = _parse_amount_sri(limpio)
    return parsed is not None and parsed != 0.0


def _cabecera_de_bloque(celdas, mapeo: dict[str, int]) -> tuple[str, str] | None:
    """Detecta la fila que ENCABEZA un bloque de cuenta en mayores tipo SAP.

    En ese layout cada cuenta abre con una fila que trae la sección, el código
    y el NOMBRE de la cuenta, pero SIN importes de débito/crédito (esos vienen
    en las filas de movimiento siguientes). El nombre de la cuenta solo aparece
    en esta cabecera, nunca en cada movimiento, así que sin capturarlo aquí la
    clasificación se queda con todas las cuentas sin nombre.

    Devuelve (codigo, nombre) o None si la fila no es una cabecera de bloque.
    """
    # Con débito o crédito distinto de cero es un movimiento o una fila de
    # total, no una cabecera de bloque.
    if _celda_tiene_importe(celdas, mapeo, "debe") or _celda_tiene_importe(
        celdas, mapeo, "haber"
    ):
        return None

    codigo = ""
    nombre = ""
    for val in celdas:
        s = _texto(val)
        if not s:
            continue
        if _RE_CODIGO_CUENTA.match(s):
            if not codigo:
                codigo = s
            continue
        n = _norm(s)
        if not n or n in _SECCIONES_MAYOR or n in SINONIMOS["codigo"]:
            continue
        if _fecha(val) is not None:
            continue
        # El nombre de la cuenta tiene letras; ante varios candidatos se queda
        # con el más largo (el descriptivo suele ser el más extenso).
        if sum(c.isalpha() for c in s) >= 2 and len(s) > len(nombre):
            nombre = s

    if codigo and nombre:
        return codigo, nombre
    return None


def _leer_hoja(ws, mapeo: dict[str, int], fila_encabezado: int, lectura: LecturaMayor) -> None:
    """Lee los movimientos de UNA hoja ya mapeada y los agrega a `lectura`."""
    col = mapeo

    def celda(fila, campo):
        i = col.get(campo)
        return fila[i] if i is not None and i < len(fila) else None

    # Nombre de cada cuenta tomado de la cabecera de su bloque (mayores tipo
    # SAP donde el nombre no viaja en cada movimiento).
    nombres_por_codigo: dict[str, str] = {}

    for n, fila in enumerate(
        ws.iter_rows(min_row=fila_encabezado + 1, values_only=True),
        start=fila_encabezado + 1,
    ):
        codigo_raw = _texto(celda(fila, "codigo"))
        if not codigo_raw:
            cabecera = _cabecera_de_bloque(fila, mapeo)
            if cabecera:
                nombres_por_codigo[cabecera[0]] = cabecera[1]
            lectura.filas_descartadas += 1
            continue
        if _norm(codigo_raw) in SINONIMOS["codigo"]:
            # Encabezado repetido a mitad del listado (paginación del ERP).
            lectura.filas_descartadas += 1
            continue

        # La celda de código puede traer el nombre fusionado ('1.4.3.23 - 15%
        # IVA EN COMPRAS'); se separa para que Código quede limpio y Cuenta
        # tenga el NOMBRE, nunca el concepto del asiento.
        codigo, nombre_fusionado = _split_codigo_nombre(codigo_raw)

        fecha = _fecha(celda(fila, "fecha"))
        asiento = _texto(celda(fila, "asiento"))
        col_cuenta = _texto(celda(fila, "cuenta"))
        col_desc = _texto(celda(fila, "descripcion"))
        if nombre_fusionado:
            # El nombre vino fusionado en el código: la columna de cuenta/
            # descripción es en realidad la glosa del movimiento (concepto).
            cuenta = nombre_fusionado
            descripcion = col_desc or col_cuenta
        else:
            # Código puro: el nombre viene de su propia columna, de la cabecera
            # del bloque (mayores tipo SAP) o queda vacío.
            cuenta = col_cuenta or nombres_por_codigo.get(codigo, "")
            descripcion = col_desc

        if not fecha and not asiento and _es_fila_acumulado(cuenta, descripcion):
            # Fila de TOTAL/SUBTOTAL/SALDO ANTERIOR/INICIAL: son los
            # acumulados de la cuenta, no un movimiento; si se cargara
            # duplicaría exactamente el debe y el haber de la cuenta.
            lectura.filas_descartadas += 1
            continue

        lectura.movimientos.append(
            Movimiento(
                codigo=codigo,
                cuenta=cuenta,
                fecha=fecha,
                asiento=asiento,
                documento=_texto(celda(fila, "documento")),
                identificacion=_texto(celda(fila, "identificacion")),
                persona=_texto(celda(fila, "persona")),
                descripcion=descripcion,
                # Débito y crédito como MAGNITUDES positivas: algunos ERP
                # exportan el haber en negativo ('-102.828,45'), lo que
                # invertiría el neto (debe − haber) y el signo de ventas,
                # retenciones y la sumaria. Se normalizan a positivo (igual que
                # el motor de referencia); la naturaleza (deudor/acreedor) la
                # decide la categoría, no el signo del archivo.
                debe=abs(_importe(celda(fila, "debe"), lectura=lectura, fila_num=n, campo="debe")),
                haber=abs(_importe(celda(fila, "haber"), lectura=lectura, fila_num=n, campo="haber")),
                saldo=_importe(celda(fila, "saldo"), lectura=lectura, fila_num=n, campo="saldo"),
                fila=n,
            )
        )


def leer_mayor(contenido: bytes) -> LecturaMayor:
    """Lee un mayor en .xlsx/.xlsm y devuelve sus movimientos normalizados.

    Si el mayor viene repartido en varias hojas con el mismo encabezado
    (habitual cuando el ERP exporta una hoja por mes o por tipo de
    comprobante), se leen TODAS las que alcancen el mapeo mínimo: elegir
    solo la de mejor puntaje perdería los movimientos de las demás sin
    avisar.
    """
    try:
        wb = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        return LecturaMayor(errores=[f"No se pudo abrir el Excel: {e}"])

    # Defecto 4: cualquier excepción durante el barrido de hojas o la
    # lectura de filas debe dejar el workbook (y su ZipFile/handles)
    # cerrado igual, para no acumular archivos abiertos en un backend de
    # larga vida. try/finally garantiza el cierre en TODOS los caminos,
    # incluida una excepción que se propaga hacia arriba.
    try:
        candidatos = []  # [(hoja, fila_encabezado, mapeo, puntaje), ...]
        for nombre in wb.sheetnames:
            ws = wb[nombre]
            mejor_de_hoja = None  # (fila, mapeo, puntaje)
            for fila_idx, fila in enumerate(
                ws.iter_rows(max_row=MAX_FILAS_BUSQUEDA_ENCABEZADO, values_only=True),
                start=1,
            ):
                mapeo = _mapear_encabezado(list(fila))
                puntaje = len(mapeo)
                if mejor_de_hoja is None or puntaje > mejor_de_hoja[2]:
                    mejor_de_hoja = (fila_idx, mapeo, puntaje)
            if mejor_de_hoja is not None:
                fila_idx, mapeo, puntaje = mejor_de_hoja
                candidatos.append((nombre, fila_idx, mapeo, puntaje))

        if not candidatos or max(c[3] for c in candidatos) == 0:
            return LecturaMayor(
                errores=["No se detectó una fila de encabezado reconocible."],
                columnas_faltantes=list(COLUMNAS_MINIMAS),
            )

        # Hoja de referencia para reportar columnas detectadas/faltantes
        # cuando NINGUNA hoja alcanza el mapeo mínimo (el auditor mapea a
        # mano).
        mejor = max(candidatos, key=lambda c: c[3])
        mapeo_mejor = mejor[2]
        columnas_faltantes = [c for c in COLUMNAS_MINIMAS if c not in mapeo_mejor]
        if columnas_faltantes:
            return LecturaMayor(
                columnas_detectadas=mapeo_mejor,
                columnas_faltantes=columnas_faltantes,
                hoja=mejor[0],
                fila_encabezado=mejor[1],
            )

        lectura = LecturaMayor()
        for nombre, fila_encabezado, mapeo, _puntaje in candidatos:
            if any(c not in mapeo for c in COLUMNAS_MINIMAS):
                continue  # esta hoja concreta no alcanza el mapeo mínimo
            if not lectura.hojas_leidas:
                lectura.hoja = nombre
                lectura.fila_encabezado = fila_encabezado
                lectura.columnas_detectadas = mapeo
            lectura.hojas_leidas.append(nombre)
            _leer_hoja(wb[nombre], mapeo, fila_encabezado, lectura)

        return lectura
    finally:
        wb.close()
