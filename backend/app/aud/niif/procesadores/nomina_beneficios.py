# -*- coding: utf-8 -*-
"""Nómina — «Pasivos Acumulados y Gastos de Nómina» (envoltorio 2.0).

Reemplaza la herramienta actuarial 1.0 (PAY-01..PAY-20). Conserva el id
``nomina_beneficios``. La parte actuarial (jubilación patronal y desahucio) sale
del catálogo y queda pendiente.

Es una herramienta **bespoke**: su cara es el panel propio (no ``libro.html``) y
su motor son los generadores del paquete ``procesadores/nomina/``. Este módulo:
  - publica ``definicion()`` para el catálogo (requerimientos RQ-001..RQ-008);
  - resuelve los archivos de la prueba a un objeto ``Rutas`` (``resolver``);
  - corre el orquestador y devuelve las 15 cédulas (``correr_prueba``).
El panel y el enganche de endpoints viven en el servicio/router (ficha, logos,
descargas), como ``papel-bancos``/``papel_artefacto_html``.
"""
from __future__ import annotations
import os, shutil, subprocess, tempfile, zipfile, glob

from backend.app.aud.niif.procesadores.base import MARCO_COMPLETAS, MARCO_PYMES, req
from backend.app.aud.niif.procesadores import marca
from backend.app.aud.niif.procesadores.nomina import orquestador
from backend.app.aud.niif.procesadores.nomina.rutas import Rutas

VERSION = "nomina_beneficios 2.0"
RUBRO = "NOMINA"
ESTADO = "en desarrollo"   # QA con cliente piloto; la actuarial sale del catálogo
# Marca la herramienta como bespoke a nivel del MÓDULO VIVO (no solo en el flag
# congelado de ``definicion()``). ``procesadores.es_bespoke`` lo usa para enrutar
# correctamente incluso pruebas creadas antes de que el flag existiera.
BESPOKE = True

# Las 15 cédulas que produce el motor (orden del papel).
CEDULAS = [
    "DO-0_Programa_Auditoria_Nomina.xlsx", "DO-2_Cedula_Sumaria_Nomina.xlsx",
    "DO-3_Resumen_Planillas_IESS.xlsx", "DO-3.1_Resumen_Roles_de_Pago.xlsx",
    "DO-4_Reproceso_Beneficios_Sociales.xlsx", "DO-4C_DO-5_Cruce_Pasivo_Beneficios.xlsx",
    "DO-6_DO-7_Cruce_Gasto_Beneficios.xlsx", "DO-8_Base_Imponible_IESS_vs_Libros.xlsx",
    "DO-9_IESS_por_Pagar_Comprobantes.xlsx", "DO-10_Roles_vs_Libros.xlsx",
    "DO-12_Hallazgos_y_Ajustes.xlsx", "RQ-004_Mayores_Nomina.xlsx",
    "RQ-007_Muestreo_Solicitudes_Decimos.xlsx", "RQ-008_Kardex_Vacaciones.xlsx",
    "VAC_Calculadora_Vacaciones_No_Gozadas.xlsx",
]


def definicion() -> dict:
    return {
        "name": "Pasivos Acumulados y Gastos de Nómina",
        "area": "Nómina",
        "processor": "nomina_beneficios",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "bespoke": True,   # cara propia (panel); no usa el flujo genérico libro.html
        "summary": (
            "Audita los pasivos acumulados laborales y el gasto de nómina sobre el 100% de la población: "
            "recálculo de aportes IESS, décimo tercero, décimo cuarto, vacaciones y fondos de reserva; "
            "conciliación del rol de pagos y los mayores con el Consolidado del IESS y los comprobantes de pago; "
            "y hoja de hallazgos y ajustes. Entrega 15 cédulas (DO-0..DO-12, RQ-004/007/008 y la calculadora de "
            "vacaciones) y un panel propio. La parte actuarial (jubilación patronal y desahucio) queda pendiente."),
        "legal": (
            "Ecuador: Código del Trabajo arts. 69 (vacaciones), 71 (valor 1/24), 76, 95 (base del décimo tercero), "
            "111 (décimo tercero), 113 (décimo cuarto), 196 (fondo de reserva), 308 (mandatario); Ley de Seguridad "
            "Social (materia gravada, art. 11) y tabla de tasas del IESS; Ley de Pasantías en el Sector Empresarial "
            "art. 7; SBU por acuerdo ministerial del MDT. Todas las tasas y el SBU van como parámetro: confirmar que "
            "siguen vigentes al corte."),
        "program": [
            {"code": "DO-1", "objective": "Evaluación de control interno laboral (cuestionario IESS/MDT)", "assertion": "Control interno"},
            {"code": "DO-2", "objective": "Sumaria de nómina (anexo vs mayor vs EEFF)", "assertion": "Integridad / Exactitud"},
            {"code": "DO-3", "objective": "Resumen de planillas de aportes IESS", "assertion": "Exactitud / Integridad"},
            {"code": "DO-3.1", "objective": "Resumen de roles de pago (fuente base)", "assertion": "Integridad / Exactitud"},
            {"code": "DO-4", "objective": "Reproceso de beneficios sociales por pagar", "assertion": "Valoración / Integridad / Corte"},
            {"code": "DO-4 V08", "objective": "Muestreo de solicitudes de acumulación de décimos", "assertion": "Cumplimiento / Ocurrencia"},
            {"code": "DO-4V", "objective": "Vacaciones no gozadas (liquidación hipotética)", "assertion": "Valoración / Corte"},
            {"code": "DO-4C/DO-5", "objective": "Cruce global y mensual del pasivo de beneficios", "assertion": "Existencia / Valoración"},
            {"code": "DO-6/DO-7", "objective": "Reproceso de gastos y beneficios sociales", "assertion": "Exactitud / Ocurrencia"},
            {"code": "DO-8", "objective": "Análisis de base imponible IESS vs libros", "assertion": "Integridad / Cumplimiento"},
            {"code": "DO-9", "objective": "IESS por pagar: libros vs comprobantes de pago", "assertion": "Existencia / Exactitud"},
            {"code": "DO-10", "objective": "Roles de pago vs libros: gastos y provisiones", "assertion": "Ocurrencia / Integridad"},
            {"code": "DO-12", "objective": "Hallazgos y ajustes de auditoría", "assertion": "Todas"},
        ],
        "requests": [
            req("RQ-001", "Cuestionario laboral IESS–MDT (lo ejecuta el auditor en campo)", None, "DO-1",
                "Evaluación de control interno laboral", required=False, formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-002", "Anexo de nómina: saldos comparativos por cuenta (pasivos y gastos)", None, "DO-2",
                "Sumaria y cuadre de saldos", formats=("xlsx",), use="soporte"),
            req("RQ-003", "Consolidado de planillas del IESS por región (Sierra/Amazonía y Costa/Galápagos); exclusiones opcionales del auditor", None, "DO-3",
                "Fuente base del reproceso y de la base imponible", formats=("xls", "xlsx"), use="soporte"),
            req("RQ-004", "Mayores de nómina: mayor de gastos y mayores de pasivos (IESS por pagar y beneficios por pagar)", None, "DO-2",
                "Clasificación por concepto y cuadre de saldos", formats=("xlsx",), use="soporte"),
            req("RQ-005", "Comprobantes de pago del IESS (PDF): aportes, fondos de reserva y préstamos", None, "DO-9",
                "Pago oportuno y sustento de saldos", formats=("pdf", "zip"), use="soporte"),
            req("RQ-006", "Rol de pagos (pestañas «normal» y «pasantes»)", None, "DO-3.1",
                "Fuente de mensualización, fechas, goces, finiquitos y provisiones del cliente", formats=("xlsx",), use="soporte"),
            req("RQ-007", "Solicitudes escritas de acumulación de décimos (muestra DO-4 V08)", None, "DO-4 V08",
                "Prueba de atributos de acumulación", required=False, formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-008", "Kárdex de vacaciones por trabajador", None, "DO-4V",
                "Liquidación hipotética de vacaciones al corte", required=False, formats=("xlsx",), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    """Validación mínima de la herramienta bespoke. NO usa el esquema genérico de plan
    (datasets/CAMPOS/PRINCIPAL): el cálculo vive en el motor (``correr_prueba``) y la cara
    es el panel propio. Solo se exige lo imprescindible para crear la prueba."""
    if d.get("processor") != "nomina_beneficios":
        raise ValueError("La definición no corresponde a la herramienta de nómina.")
    if not str(d.get("name") or "").strip() or not str(d.get("area") or "").strip():
        raise ValueError("Indique nombre y rubro de la herramienta de nómina.")
    if not d.get("requests"):
        raise ValueError("La herramienta de nómina necesita sus requerimientos (RQ-001..RQ-008).")
    return d


# ------------------------------------------------------------------ resolver
def _logo_firma(ficha: dict) -> str:
    """Logo de la firma del encargo para las cédulas (fondo claro). Elige según la firma de
    la ficha: «Partner Auditing» o, por defecto, AuditConsulting (decisión del dueño: ambas)."""
    f = str((ficha or {}).get("firm") or (ficha or {}).get("firma") or "").strip().lower()
    clave = "partner_auditing" if "partner" in f else "auditconsulting_oscuro"
    try:
        return os.path.join(marca.ASSETS, marca.ARCHIVOS[clave])
    except Exception:
        return ""


def _a_xlsx(ruta: str, destino_dir: str) -> str:
    """Convierte un .xls a .xlsx con LibreOffice; devuelve la ruta .xlsx (o la original si ya lo es)."""
    if ruta.lower().endswith(".xlsx"):
        return ruta
    os.makedirs(destino_dir, exist_ok=True)
    subprocess.run(["soffice", f"-env:UserInstallation=file://{destino_dir}/_lo",
                    "--headless", "--calc", "--convert-to", "xlsx", "--outdir", destino_dir, ruta],
                   capture_output=True, timeout=180)
    base = os.path.splitext(os.path.basename(ruta))[0] + ".xlsx"
    dest = os.path.join(destino_dir, base)
    return dest if os.path.exists(dest) else ruta


def resolver(archivos: list[dict], ficha: dict, home: str, out: str) -> Rutas:
    """Mapea los archivos de la prueba (requerimiento/componente/ruta/nombre) al objeto Rutas.

    ``archivos``: lista de dicts con al menos ``requerimiento``, ``ruta`` y ``nombre``
    (``componente`` opcional). Resuelve el Consolidado (.xls→.xlsx), los tres mayores
    por nombre, y arma la carpeta de comprobantes (PDF sueltos o .zip)."""
    os.makedirs(home, exist_ok=True)
    r = Rutas(home=home, out=out, anexo="", rol="", consolidado="")
    comp_dir = os.path.join(home, "comprobantes")
    for a in archivos:
        rq = (a.get("requerimiento") or "").upper()
        comp = (a.get("componente") or "")
        ruta = a.get("ruta") or ""
        nom = (a.get("nombre") or os.path.basename(ruta)).upper()
        if not ruta:
            continue
        if rq == "RQ-002":
            r.anexo = ruta
        elif rq == "RQ-003":
            if "exclusi" in comp.lower() or "exclusi" in nom.lower():
                r.exclusiones = ruta
            else:
                r.consolidado = _a_xlsx(ruta, home)
        elif rq == "RQ-004":
            if "GASTO" in nom:
                r.lm_gasto = ruta
            elif "IESS" in nom:
                r.lm_iess = ruta
            elif "BENEFICIO" in nom or "_BS" in nom or "BENEF" in nom:
                r.lm_bs = ruta
            elif "PASIVO" in nom:
                # Otros clientes traen el pasivo en UN solo mayor combinado (IESS + beneficios):
                # se adapta al plan del motor en perfil_cuentas.
                r.lm_pasivo = ruta
        elif rq == "RQ-005":
            os.makedirs(comp_dir, exist_ok=True)
            if ruta.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(ruta) as z:
                        z.extractall(comp_dir)
                except Exception:
                    pass
            elif ruta.lower().endswith(".pdf"):
                shutil.copy(ruta, os.path.join(comp_dir, os.path.basename(ruta)))
        elif rq == "RQ-006":
            r.rol = ruta
    if os.path.isdir(comp_dir) and glob.glob(os.path.join(comp_dir, "**", "*.pdf"), recursive=True):
        r.comprobantes_dir = comp_dir
    # ficha del encargo
    r.cliente = ficha.get("client") or ficha.get("cliente") or ""
    r.ruc = ficha.get("ruc") or ""
    r.ejercicio = int(ficha.get("year") or ficha.get("ejercicio") or 0) or 0
    r.corte = ficha.get("cutoff") or ficha.get("corte") or ""
    r.preparado = ficha.get("preparer") or ficha.get("preparado") or "[auditor]"
    r.revisado = ficha.get("reviewer") or ficha.get("revisado") or "[socio]"
    r.marco = ficha.get("framework") or ficha.get("marco") or ""
    r.logo = _logo_firma(ficha)
    return r


def datos_minimos(archivos: list[dict]) -> bool:
    """¿Hay lo mínimo para procesar? Anexo (RQ-002), Consolidado (RQ-003), mayores (RQ-004) y rol (RQ-006)."""
    rqs = {(a.get("requerimiento") or "").upper() for a in archivos if a.get("ruta")}
    return {"RQ-002", "RQ-003", "RQ-004", "RQ-006"}.issubset(rqs)


def correr_prueba(archivos: list[dict], ficha: dict, home: str, out: str) -> dict:
    """Corre el motor y devuelve {nombre_cédula: bytes} con las 15 cédulas."""
    r = resolver(archivos, ficha, home, out)
    return orquestador.correr(r, ficha)
