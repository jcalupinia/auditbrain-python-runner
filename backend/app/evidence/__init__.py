"""Evidence engine (Agente E) — Document AI y evidencia.

Cierra las capacidades DOC-005/006/007/008/009/010/011, DQ-006 y ANA-020 de la
arquitectura de convergencia (`docs/ARQUITECTURA_CONVERGENCIA_v1.md`, capa 7).

Cuatro módulos:

  - ``matcher``   — emparejar registros (exacto/normalizado/fuzzy/semántico)
                    con tolerancia numérica y de fecha (DOC-005/006/007, DQ-006,
                    ANA-020).
  - ``citation``  — ``SourceReference`` (contrato §2) + captura de página y
                    bounding-box desde pdfplumber y Google Vision (DOC-008/009).
  - ``confidence``— score 0..1 por campo, extracción vs interpretación (DOC-011).
  - ``crossref``  — matriz de evidencia dato→fuente→cita con validación humana
                    (DOC-010).

SCAFFOLD: firmas + contratos tipados; la lógica se implementa a verde en el
servidor (dependencias FastAPI/SQLAlchemy/rapidfuzz no corren en este
contenedor). Ver ``docs/superpowers/plans/2026-09-24-p1e-evidence-engine.md``.
"""

from __future__ import annotations

from backend.app.evidence.citation import (
    BoundingBox,
    PaginaTexto,
    PaginaVision,
    PalabraUbicada,
    PalabraVision,
    SourceReference,
    extraer_paginas_pdfplumber,
    hash_de_archivo,
    localizar_en_pagina,
    ocr_pdf_con_geometria,
    source_reference_desde_pdfplumber,
    source_reference_desde_vision,
    source_reference_tabular,
)
from backend.app.evidence.confidence import (
    AporteConfianza,
    ConfianzaCampo,
    NivelConfianza,
    confianza_extraccion,
    confianza_interpretacion,
    evaluar_campo,
)
from backend.app.evidence.crossref import (
    EntradaEvidencia,
    EstadoValidacion,
    MatrizEvidencia,
)
from backend.app.evidence.matcher import (
    CampoEmparejamiento,
    Coincidencia,
    CriterioEmparejamiento,
    EstadoEmparejamiento,
    ModoEmparejamiento,
    ResultadoEmparejamiento,
    TipoCampo,
    emparejar,
    emparejar_lotes,
)

__all__ = [
    # matcher
    "emparejar",
    "emparejar_lotes",
    "ModoEmparejamiento",
    "TipoCampo",
    "EstadoEmparejamiento",
    "CampoEmparejamiento",
    "CriterioEmparejamiento",
    "Coincidencia",
    "ResultadoEmparejamiento",
    # citation
    "SourceReference",
    "BoundingBox",
    "PaginaTexto",
    "PalabraUbicada",
    "PaginaVision",
    "PalabraVision",
    "hash_de_archivo",
    "extraer_paginas_pdfplumber",
    "localizar_en_pagina",
    "ocr_pdf_con_geometria",
    "source_reference_desde_pdfplumber",
    "source_reference_desde_vision",
    "source_reference_tabular",
    # confidence
    "ConfianzaCampo",
    "NivelConfianza",
    "AporteConfianza",
    "confianza_extraccion",
    "confianza_interpretacion",
    "evaluar_campo",
    # crossref
    "MatrizEvidencia",
    "EntradaEvidencia",
    "EstadoValidacion",
]
