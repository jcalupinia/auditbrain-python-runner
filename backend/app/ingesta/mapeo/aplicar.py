"""Aplica un mapeo CONFIRMADO por el auditor y normaliza (Fase A3).

Etapa 2 del flujo (tras la confirmación humana, M07/M17): toma el mapeo
`campo_canonico → índice de columna` que el auditor aprobó y produce un
``DatasetNormalizado`` con trazabilidad por celda. Reglas duras:

- **M22**: un campo obligatorio con celda vacía → ``normalized_value=None`` y a
  revisión. NUNCA cero.
- Normalización fallida (valor presente pero no parseable) → ese campo baja a
  REVIEW; no se descarta ni se inventa.
- La máquina no calcula: solo normaliza tipo/moneda/fecha con el normalizador
  canónico del motor.
"""
from __future__ import annotations

from typing import Any

from backend.app.ingesta.confidence import NivelConfianza
from backend.app.ingesta.confidence_live import consolidar_confianza
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    TipoDato,
    TipoDocumento,
)
from backend.app.ingesta.mapeo.esquemas import EsquemaCanonico
from backend.app.ingesta.mapeo.perfilador import PerfilTabla
from backend.app.ingesta.normalizer import normalizar_valor


def _vacio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _col_letra(indice: int) -> str:
    try:
        from openpyxl.utils import get_column_letter
        return get_column_letter(indice + 1)
    except Exception:
        return str(indice + 1)


def aplicar_mapeo(
    tabla_cruda: list[list[Any]],
    perfil: PerfilTabla,
    mapeo_confirmado: dict[str, int],
    esquema: EsquemaCanonico,
    *,
    source_file: str,
    document_type: TipoDocumento,
) -> DatasetNormalizado:
    """Construye el ``DatasetNormalizado`` a partir del mapeo confirmado."""
    h = perfil.fila_encabezado
    datos = tabla_cruda[h + 1:] if h is not None else list(tabla_cruda)

    # Campos del esquema efectivamente mapeados, en el orden del esquema.
    orden_campos = [c.nombre for c in esquema.campos if c.nombre in mapeo_confirmado]
    campos: list[CampoExtraido] = []
    rows: list[dict[str, Any]] = []

    for j, fila in enumerate(datos):
        fila_excel = (h + 2 + j) if h is not None else (j + 1)
        registro: dict[str, Any] = {}
        for nombre in orden_campos:
            col_idx = mapeo_confirmado[nombre]
            campo_def = esquema.campo(nombre)
            crudo = fila[col_idx] if col_idx < len(fila) else None
            raw_str = None if _vacio(crudo) else str(crudo).strip()

            valor, _tipo = (None, campo_def.tipo)
            if raw_str is not None:
                valor, _tipo = normalizar_valor(raw_str, campo_def.tipo)

            warnings: list[str] = []
            if _vacio(crudo):
                # M22: obligatorio vacío → None y revisión; opcional vacío → se omite.
                if campo_def.obligatorio:
                    nivel = NivelConfianza.REVIEW_REQUIRED
                    warnings.append("campo obligatorio vacío (M22): no se asume cero")
                else:
                    registro[nombre] = None
                    continue
            elif valor is None:
                nivel = NivelConfianza.REVIEW_REQUIRED
                warnings.append(f"no se pudo normalizar {raw_str!r} como {campo_def.tipo.value}")
            else:
                nivel = NivelConfianza.HIGH

            registro[nombre] = valor
            campos.append(CampoExtraido(
                document_id=source_file,
                document_type=document_type,
                field=nombre,
                raw_value=raw_str,
                normalized_value=valor,
                data_type=campo_def.tipo,
                currency="USD" if campo_def.tipo is TipoDato.MONEDA and valor is not None else None,
                confidence=nivel,
                extraction_method=MetodoExtraccion.TABLA,
                evidence=Evidencia(
                    source_file=source_file,
                    source_sheet=perfil.hoja,
                    source_row=fila_excel,
                    source_cell=f"{_col_letra(col_idx)}{fila_excel}",
                ),
                warnings=warnings,
            ))
        rows.append(registro)

    nombres_col = {c.indice: c.nombre_crudo for c in perfil.columnas}
    ds = DatasetNormalizado(
        dataset_id=source_file,
        source_file=source_file,
        document_type=document_type,
        schema_detected=[c.nombre_crudo for c in perfil.columnas],
        schema_normalized=orden_campos,
        mapping={nombre: nombres_col.get(mapeo_confirmado[nombre], f"col_{mapeo_confirmado[nombre]}")
                 for nombre in orden_campos},
        rows=rows,
        row_count=len(rows),
        campos=campos,
        extraction_method=MetodoExtraccion.TABLA,
    )
    consolidar_confianza(ds)
    return ds.sellar()
