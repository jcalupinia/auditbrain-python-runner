"""Procesadores especializados de pruebas NIIF.

Una ficha cuya definición declara ``processor`` no corre en el motor
declarativo (fila por fila): su cálculo compara años, agrega por cliente o
aplica límites sobre totales, y lo hace el módulo registrado aquí. El resto del
ciclo (programa, requerimientos, evidencia, revisión) es el mismo.
"""
from backend.app.aud.niif.procesadores import perdidas_incurridas_s11

PROCESADORES = {"perdidas_incurridas_s11": perdidas_incurridas_s11}


def de(definicion: dict):
    """El módulo del procesador de la definición, o None si es declarativa."""
    nombre = (definicion or {}).get("processor")
    if not nombre:
        return None
    if nombre not in PROCESADORES:
        raise ValueError(f"Procesador desconocido: {nombre}.")
    return PROCESADORES[nombre]
