"""Procesadores especializados de pruebas NIIF.

Una ficha cuya definición declara ``processor`` no corre en el motor
declarativo (fila por fila): su cálculo compara años, agrega por cliente o
aplica límites sobre totales, y lo hace el módulo registrado aquí. El resto del
ciclo (programa, requerimientos, evidencia, revisión) es el mismo.

Los módulos con ``RUBRO`` son herramientas del catálogo del módulo AUD: aparecen
directamente en la tarjeta de su rubro (contrato en docs/niif/CONTRATO_PROCESADOR.md).
"""
import importlib

# Orden = matriz del socio (1–18) tras los dos procesadores instalados por ficha.
_MODULOS = [
    "perdidas_incurridas_s11",
    "pce_simplificada_niif9",
    "efectivo_equivalentes",
    "cxc_cartera",
    "inversiones_instrumentos",
    "inventarios_costos",
    "ppe_propiedad_planta",
    "propiedades_inversion",
    "arrendamientos",
    "intangibles_goodwill",
    "activos_biologicos",
    "seguros_cobertura",
    "proveedores_cxp",
    "prestamos_obligaciones",
    "nomina_beneficios",
    "ingresos_contratos",
    "gastos_analisis",
    "provisiones_contingencias",
    "impuesto_corriente_diferido",
    "patrimonio",
    "planificacion_nia",
]

PROCESADORES = {
    nombre: importlib.import_module(f"backend.app.aud.niif.procesadores.{nombre}") for nombre in _MODULOS
}


def de(definicion: dict):
    """El módulo del procesador de la definición, o None si es declarativa."""
    nombre = (definicion or {}).get("processor")
    if not nombre:
        return None
    if nombre not in PROCESADORES:
        raise ValueError(f"Procesador desconocido: {nombre}.")
    return PROCESADORES[nombre]
