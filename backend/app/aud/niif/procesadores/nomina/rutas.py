# -*- coding: utf-8 -*-
"""Contexto de rutas de la herramienta de nómina.

Reemplaza las rutas fijas (``/home/claude/nomina``, ``/mnt/user-data/...``) de los
generadores de referencia: el orquestador fija ``CTX`` a la carpeta de trabajo de
la prueba antes de ejecutar cada generador, y los generadores leen de ``CTX``.
No hay estado compartido entre pruebas: cada corrida usa su propia carpeta.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Rutas:
    home: str          # carpeta de trabajo (pickles intermedios, logo, mayores/)
    out: str           # carpeta de salida de las cédulas .xlsx
    anexo: str         # RQ-002 Anexo de nómina .xlsx
    rol: str           # RQ-006 Rol histórico .xlsx (un combinado; o el último de los mensuales)
    consolidado: str   # RQ-003 Consolidado IESS .xlsx (ya convertido de .xls)
    exclusiones: str = ""   # RQ-003 Exclusiones (opcional)
    lm_gasto: str = ""      # RQ-004 Mayor de gastos
    lm_iess: str = ""       # RQ-004 Mayor IESS por pagar (5BS.21203) — plan de referencia
    lm_bs: str = ""         # RQ-004 Mayor beneficios por pagar (5BS.21204) — plan de referencia
    lm_pasivo: str = ""     # RQ-004 Mayor de pasivo COMBINADO (otros clientes: un solo archivo);
                            #        se adapta al plan del motor en perfil_cuentas
    roles_mensuales: list = field(default_factory=list)  # RQ-006 por mes: [(ruta, nombre), …]
    comprobantes_dir: str = ""  # RQ-005 carpeta con los PDF
    papel: str = ""         # papel del equipo (transitorio; se elimina en la ola B)
    logo: str = ""          # logo de la firma del encargo (marca.py)
    # --- ficha del encargo (de GET /proyectos/{id}/ficha); nada de PROPHAR por defecto
    cliente: str = ""       # razón social del cliente auditado
    ruc: str = ""
    ejercicio: int = 0      # año auditado
    corte: str = ""         # fecha de corte ISO (YYYY-MM-DD)
    preparado: str = "[auditor]"
    revisado: str = "[socio]"
    marco: str = ""
    visit: str = ""         # visita del encargo: "preliminar" | "final" (de la ficha)

    # --- derivados del corte (período auditado = 1-ene … mes de corte del ejercicio) ---
    @property
    def anio_corte(self) -> int:
        """Año del ejercicio auditado: el de la ficha o, si falta, el del corte."""
        if self.ejercicio:
            return self.ejercicio
        if self.corte and len(self.corte) >= 4 and self.corte[:4].isdigit():
            return int(self.corte[:4])
        return 2025

    @property
    def mes_corte(self) -> int:
        """Mes de corte (1-12). Diciembre (12) = cierre calendario; otro = visita preliminar."""
        if self.corte and len(self.corte) >= 7 and self.corte[5:7].isdigit():
            m = int(self.corte[5:7])
            if 1 <= m <= 12:
                return m
        return 12

    @property
    def es_preliminar(self) -> bool:
        """True cuando el corte no es diciembre (período parcial del ejercicio)."""
        return self.mes_corte != 12


# Contexto vigente (lo fija el orquestador en cada corrida).
CTX: Rutas | None = None
SUJETOS: dict = {}   # sujetos de hallazgos derivados de los datos (lo fija el orquestador)
CIFRAS: dict = {}    # importes de hallazgos derivados de los datos (lo fija el orquestador)
