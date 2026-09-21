"""Estudio de la prueba: cobertura del requerimiento y corrida del motor.

Es la mitad del ciclo del sitio que faltaba en el portal. En el sitio, una
prueba recorre: requerimiento → cobertura → motor → cédulas → Excel. La ficha
del Command Center cubría solo el diseño (qué se pide y qué se produce); aquí
se agregan los dos pasos que verifican que ese diseño funciona.

**Lo que la ficha NO trae, y hay que saberlo.** La ficha describe el
requerimiento (bloque 2) y las salidas (bloque 4). No describe la *definición
del motor* —campos, reglas, series—: eso es lo que el auditor obtiene con el
botón «generar código para Claude» y lo que Claude escribe. Por eso el motor
se ejecuta contra una definición que se le pasa, no contra la ficha. Es el
orden correcto: la ficha se puede marcar «probada» recién cuando su definición
corrió aquí y dio los números esperados.

**Limitación declarada.** El bloque 2 de la ficha guarda los componentes como
un *número* (`componentes: 12`), no como nombres. La cobertura entonces
informa «faltan 3 de 12», no «falta abril». Cubre el fallo que de verdad
importa —un archivo no tapa doce meses— pero nombrarlos es mejor, y exige
cambiar el diseñador de fichas. No se hizo aquí para no mezclar dos cambios.
"""
from __future__ import annotations

from backend.app.aud.niif.motor import calculate
from backend.app.aud.niif.requerimiento import coverage, gaps, parse_items


def items_de_ficha(ficha_items) -> list[dict]:
    """Traduce el bloque 2 de la ficha a ítems de requerimiento.

    Un ítem con `componentes: 12` se expande a doce componentes con nombre
    genérico: lo que hace falta para que la cobertura cuente doce entregas y
    no una.
    """
    entradas = []
    for it in ficha_items or []:
        texto = str(it.get("que_se_pide") or "").strip()
        if not texto:
            continue
        cuantos = int(it.get("componentes") or 1)
        entradas.append({
            "text": texto,
            "formats": it.get("formatos") or [],
            "required": it.get("obligatorio") is not False,
            "components": [f"Componente {n}" for n in range(1, cuantos + 1)] if cuantos > 1 else [],
            "group": it.get("grupo_alternativas") or "",
        })
    if not entradas:
        raise ValueError("La ficha no tiene ningún ítem de requerimiento con texto.")
    return parse_items(entradas)


def cobertura_de_ficha(ficha_items, documentos) -> dict:
    """Estado de cobertura y lista de huecos de una ficha."""
    items = items_de_ficha(ficha_items)
    estado = coverage(items, documentos or [])
    return {
        "items": items,
        "cobertura": estado,
        "huecos": gaps(items, documentos or []),
        "recibidos": sum(c["received"] for c in estado),
        "esperados": sum(c["expected"] for c in estado),
    }


def ejecutar_definicion(definicion, filas, parametros=None, flujos=None) -> dict:
    """Corre el motor sobre una definición, como lo haría el sitio.

    Se limita a traducir la entrada al contrato de `calculate` y a dejar que
    el motor valide. No se replica ninguna validación aquí: cualquier regla
    duplicada sería una regla que puede divergir del sitio.
    """
    if not isinstance(definicion, dict) or not definicion:
        raise ValueError("Adjunte la definición de la prueba (campos, reglas y series).")
    if not isinstance(filas, list) or not filas:
        raise ValueError("Adjunte al menos una fila de datos para correr el motor.")
    payload = {"definition": definicion, "rows": filas, "parameters": parametros or {}}
    if flujos:
        payload["flows"] = flujos
    return calculate(payload)
