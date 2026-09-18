"""Lectura de los archivos de cartera del cliente.

Los archivos llegan con el formato regional del sistema que los generó. Aquí se
normalizan importes y fechas antes de que el motor vea un solo número.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Any, Iterable

from openpyxl import load_workbook

from backend.app.aud.pce_cxc.bandas import clasificar

_PATRON_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
_PATRON_ISO = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")


def a_numero(valor: Any) -> float:
    """Convierte a número respetando cualquier formato regional.

    - Si aparecen ambos separadores ("." y ","): el último que aparece es el
      decimal, el otro es de miles.
    - Si aparece un solo tipo de separador:
      - más de una vez -> todos son de miles ("8.917.458" -> 8917458);
      - una sola vez y le siguen exactamente tres dígitos -> es de miles
        ("1.500" -> 1500);
      - una sola vez y no le siguen exactamente tres dígitos -> es decimal
        ("1234.56" -> 1234.56).

    Los paréntesis indican negativo.
    """
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return 0.0
    negativo = s.startswith("(") and s.endswith(")") or "-" in s
    s = re.sub(r"[^0-9.,]", "", s)
    if not s:
        return 0.0
    tiene_punto = "." in s
    tiene_coma = "," in s
    entero, decimal = s, ""
    if tiene_punto and tiene_coma:
        i = max(s.rfind(","), s.rfind("."))
        entero, decimal = s[:i], s[i + 1:]
    elif tiene_punto or tiene_coma:
        sep = "." if tiene_punto else ","
        if s.count(sep) == 1:
            i = s.rfind(sep)
            cola = s[i + 1:]
            if len(cola) != 3:
                entero, decimal = s[:i], cola
    entero = re.sub(r"[.,]", "", entero)
    try:
        n = float(f"{entero}.{decimal}" if decimal else entero or "0")
    except ValueError:
        return 0.0
    return -n if negativo and n > 0 else n


def inferir_formato_fecha(valores: Iterable[Any]) -> str:
    """Deduce si las fechas del archivo son día/mes/año o mes/día/año.

    Recorre todos los valores (no se detiene en el primero) porque un Excel
    puede mezclar celdas con formato de fecha nativo y celdas de texto:

    - solo fechas nativas -> "nativo";
    - fechas nativas y además cadenas con patrón de fecha -> "inconsistente"
      (el archivo mezcla formatos);
    - solo cadenas -> "dmy"/"mdy"/"inconsistente" según qué componente supere
      12, o "ambiguo" si ninguno lo delata;
    - nada parseable -> "ambiguo" (no se sabe, no se asume "nativo").
    """
    dmy = mdy = total = 0
    hay_nativas = False
    hay_texto_con_patron = False
    for v in valores:
        if isinstance(v, (date, datetime)):
            hay_nativas = True
            continue
        m = _PATRON_DMY.match(str(v or "").strip())
        if not m:
            continue
        hay_texto_con_patron = True
        total += 1
        if int(m.group(1)) > 12:
            dmy += 1
        if int(m.group(2)) > 12:
            mdy += 1
    if hay_nativas and hay_texto_con_patron:
        return "inconsistente"
    if hay_nativas:
        return "nativo"
    if not total:
        return "ambiguo"
    if dmy and mdy:
        return "inconsistente"
    if dmy:
        return "dmy"
    if mdy:
        return "mdy"
    return "ambiguo"


def a_fecha(valor: Any, formato: str = "dmy") -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None or valor == "":
        return None
    s = str(valor).strip()
    m = _PATRON_DMY.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3))
        anio += 2000 if anio < 100 else 0
        dia, mes = (b, a) if formato == "mdy" else (a, b)
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None
    m = _PATRON_ISO.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# Pistas para reconocer cada columna en el archivo del cliente.
CAMPOS: dict[str, list[str]] = {
    "cliente": ["cliente", "razon", "razón", "nombre", "deudor"],
    "documento": ["documento", "comprobante", "factura", "numero", "número", "nro", "n°"],
    "tipo": ["tipo", "relacion", "relación", "clasif", "categoria", "categoría"],
    "emision": ["emision", "emisión", "fecha emis", "f. emis"],
    "vencimiento": ["vencimiento", "vence", "venc"],
    "saldo": ["saldo", "monto", "valor", "importe", "total", "cuentas por cobrar"],
}
_OBLIGATORIOS = ("documento", "vencimiento", "saldo")


def _detectar_encabezado(filas: list[tuple]) -> int:
    mejor, puntaje = -1, 0
    for i, fila in enumerate(filas[:45]):
        celdas = [str(c or "").lower() for c in fila]
        p = sum(1 for pistas in CAMPOS.values() if any(any(h in c for h in pistas) for c in celdas))
        if p > puntaje:
            mejor, puntaje = i, p
    return mejor if puntaje >= 3 else -1


def _mapear(encabezado: tuple) -> dict[str, int]:
    celdas = [str(c or "").lower().strip() for c in encabezado]
    mapeo: dict[str, int] = {}
    usadas: set[int] = set()
    for campo, pistas in CAMPOS.items():
        for pista in pistas:
            idx = next((j for j, c in enumerate(celdas) if pista in c and j not in usadas), None)
            if idx is not None:
                mapeo[campo] = idx
                usadas.add(idx)
                break
    return mapeo


def leer_cartera(contenido: bytes, nombre: str, corte, bandas, hoja=None, mapeo=None,
                 clave_relacionadas: str = "RELACIONAD") -> dict:
    """Lee un análisis de antigüedad y devuelve sus documentos clasificados por mora."""
    wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    ws = wb[hoja] if hoja else wb.worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    wb.close()

    i_enc = 0 if mapeo else _detectar_encabezado(filas)
    if i_enc < 0:
        raise ValueError(f"{nombre}: no se identificó la fila de encabezados")
    cols = mapeo or _mapear(filas[i_enc])
    faltantes = [c for c in _OBLIGATORIOS if c not in cols]
    if faltantes:
        raise ValueError(f"{nombre}: no se encontraron las columnas {', '.join(faltantes)}")

    cuerpo = filas[i_enc + 1:]
    formato = inferir_formato_fecha([f[cols["vencimiento"]] for f in cuerpo[:4000]
                                     if len(f) > cols["vencimiento"]])

    salida, descartados = [], []
    vistas: set[tuple] = set()
    documentos: set[str] = set()
    dup_exactos = repetidos = 0

    def valor(fila, campo):
        j = cols.get(campo)
        return fila[j] if j is not None and j < len(fila) else None

    for n, fila in enumerate(cuerpo, start=i_enc + 2):
        if fila is None or all(v is None or str(v).strip() == "" for v in fila):
            continue
        documento = str(valor(fila, "documento") or "").strip()
        saldo = a_numero(valor(fila, "saldo"))
        vencimiento = a_fecha(valor(fila, "vencimiento"), formato)
        if not documento:
            descartados.append({"fila_origen": n, "motivo": "sin número de documento", "saldo": saldo})
            continue
        if vencimiento is None:
            descartados.append({"fila_origen": n, "motivo": "sin fecha de vencimiento", "saldo": saldo})
            continue
        if abs(saldo) < 0.005:
            descartados.append({"fila_origen": n, "motivo": "saldo cero", "saldo": saldo})
            continue
        cliente = str(valor(fila, "cliente") or "").strip()
        firma = (documento, round(saldo, 2), vencimiento, cliente)
        if firma in vistas:
            dup_exactos += 1
            continue
        vistas.add(firma)
        repetido = documento in documentos
        repetidos += 1 if repetido else 0
        documentos.add(documento)
        tipo = str(valor(fila, "tipo") or "").upper()
        es_rel = clave_relacionadas in tipo and f"NO-{clave_relacionadas}" not in tipo \
            and f"NO {clave_relacionadas}" not in tipo
        dias = (corte - vencimiento).days
        salida.append({
            "fila_origen": n, "cliente": cliente, "documento": documento,
            "segmento": "RELACIONADOS" if es_rel else "NO-RELACIONADOS",
            "emision": a_fecha(valor(fila, "emision"), formato),
            "vencimiento": vencimiento, "saldo": saldo, "dias": dias,
            "banda": clasificar(dias, bandas), "repetido": repetido,
        })

    return {"filas": salida, "hoja": ws.title, "fila_encabezado": i_enc + 1, "mapeo": cols,
            "formato_fecha": formato, "duplicados_exactos": dup_exactos,
            "documentos_repetidos": repetidos, "descartados": descartados,
            "total_saldo": round(sum(f["saldo"] for f in salida), 2)}
