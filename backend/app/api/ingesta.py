"""API v1 del Motor de Ingesta y Normalización (Fase 7).

Expone el motor transversal (clasificación → extracción determinista →
normalización → confianza) por HTTP, con subida de archivos. Reutiliza
`backend/app/ingesta` sin modificar nada de las fases anteriores.

Acceso: admin (JWT) o X-API-Key (server-to-server), igual que `/python` y
`/router` (``require_runner_access``). Determinístico primero: el OCR y la IA
no se disparan salvo que haga falta / se pidan.
"""
# Sin `from __future__ import annotations`: los modelos de respuesta
# (IngerirResponse) referencian DatasetNormalizado/ItemRevision como tipos
# reales para que Pydantic los resuelva al definir la clase (si fueran strings
# diferidas requeriría model_rebuild()).
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.auth.deps import require_runner_access
from backend.app.ingesta import (
    DatasetNormalizado,
    ItemRevision,
    ResultadoClasificacion,
    TipoDocumento,
    clasificar_documento,
    cola_de_revision,
    extraer_narrativo,
    ingerir,
    resoluble,
    resolver_dataset,
)
from backend.app.ingesta.mapeo import (
    aplicar_mapeo,
    cola_revision_mapeo,
    perfilar,
    preparar_mapeo,
    resolver_esquema,
)

router = APIRouter(
    prefix="/ingesta",
    tags=["ingesta"],
    dependencies=[Depends(require_runner_access)],
)

# Tamaño máximo del archivo aceptado (MB). Barrera simple contra abusos.
_MAX_MB = 25


class TiposResponse(BaseModel):
    tipos: list[str]
    nota: str


class IngerirResponse(BaseModel):
    dataset: DatasetNormalizado
    cola_revision: list[ItemRevision]


class ResolverResponse(BaseModel):
    dataset: DatasetNormalizado
    cola_revision: list[ItemRevision]
    resolubles: int   # campos de texto dudosos candidatos a IA
    resueltos: int    # cuántos cambiaron a método IA


async def _leer(file: UploadFile) -> bytes:
    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(contenido) > _MAX_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"Archivo supera el límite de {_MAX_MB} MB."
        )
    return contenido


@router.get("/tipos", response_model=TiposResponse)
def tipos() -> TiposResponse:
    """Lista los tipos de documento que el clasificador reconoce."""
    return TiposResponse(
        tipos=[t.value for t in TipoDocumento],
        nota=(
            "El tipo se puede declarar en 'tipo_declarado' (manda) o se detecta "
            "automáticamente por firma de contenido y nombre del archivo."
        ),
    )


@router.post("/clasificar", response_model=ResultadoClasificacion)
async def clasificar(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
) -> ResultadoClasificacion:
    """Clasifica el documento sin extraer (determinista, barato)."""
    contenido = await _leer(file)
    return clasificar_documento(
        file.filename or "documento",
        contenido=contenido,
        tipo_declarado=tipo_declarado,
    )


@router.post("/ingerir", response_model=IngerirResponse)
async def ingerir_endpoint(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
    ocr: bool = Form(default=True),
    consolidar: bool = Form(default=True),
) -> IngerirResponse:
    """Ingiere el documento y devuelve el dataset normalizado + cola de revisión.

    La IA (AI Semantic Resolver) NO se dispara aquí: es un paso aparte y opcional.
    """
    contenido = await _leer(file)
    ds = ingerir(
        file.filename or "documento",
        contenido,
        tipo_declarado=tipo_declarado,
        ocr=ocr,
        consolidar=consolidar,
    )
    return IngerirResponse(dataset=ds, cola_revision=cola_de_revision([ds]))


@router.post("/narrativo", response_model=IngerirResponse)
async def narrativo_endpoint(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
    usar_ia: bool = Form(default=False),
) -> IngerirResponse:
    """Extrae datos puntuales de un documento narrativo (contrato, carta, informe).

    Determinístico primero: fechas, montos, RUCs y porcentajes salen por regex
    con trazabilidad al origen. ``usar_ia`` (opcional, por defecto apagado) suma
    la enumeración por IA de obligaciones/partes/cláusulas —solo texto, nunca
    cifras— con disclaimer y degradación graciosa.
    """
    contenido = await _leer(file)
    ds = extraer_narrativo(
        file.filename or "documento",
        contenido,
        tipo_declarado=tipo_declarado,
        usar_ia=usar_ia,
    )
    return IngerirResponse(dataset=ds, cola_revision=cola_de_revision([ds]))


@router.post("/resolver", response_model=ResolverResponse)
async def resolver_endpoint(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
    ocr: bool = Form(default=True),
) -> ResolverResponse:
    """Resolución semántica por IA (Fase 6) como paso explícito y opcional.

    A diferencia de ``/ingerir`` (que NO usa IA), aquí el auditor pide que la IA
    desambigüe los campos de TEXTO que quedaron en la cola de revisión. Reglas
    duras del resolutor: el LLM no calcula (no toca números ni fechas), tope de
    confianza MEDIUM, disclaimer y degradación graciosa. Si no hay campos de
    texto dudosos, no hace nada (``resolubles=0``).
    """
    contenido = await _leer(file)
    ds = ingerir(file.filename or "documento", contenido, tipo_declarado=tipo_declarado, ocr=ocr)
    resolubles = sum(1 for c in ds.campos if resoluble(c))
    resolver_dataset(ds)  # usa el proveedor compartido (local-first); nunca lanza
    resueltos = sum(1 for c in ds.campos if c.extraction_method.value == "ia")
    return ResolverResponse(
        dataset=ds,
        cola_revision=cola_de_revision([ds]),
        resolubles=resolubles,
        resueltos=resueltos,
    )


# ---------------------------------------------------------------------------
# Capa de Mapeo Universal (Fase A3/B): flujo en dos tiempos sin estado.
#   /mapeo/preparar  → perfila y PROPONE (la máquina propone, M07)
#   [el auditor confirma o corrige en la UI — M07/M17]
#   /mapeo/aplicar   → normaliza con el mapeo CONFIRMADO (el auditor dispone)
# Sin estado en el servidor: el cliente reenvía el mismo archivo en «aplicar»
# y el backend lo re-perfila (determinista ⇒ idéntico) antes de aplicar.
# ---------------------------------------------------------------------------


class ColumnaPerfilOut(BaseModel):
    indice: int
    nombre_crudo: str
    tipo_inferido: str
    muestra: list[str]
    n_no_vacios: int
    n_total: int


class PerfilTablaOut(BaseModel):
    columnas: list[ColumnaPerfilOut]
    n_filas: int
    fila_encabezado: Optional[int]
    hoja: Optional[str]
    # Nota: NO se devuelve la matriz cruda (`filas`): no hay que eco del archivo
    # completo; para «aplicar» el cliente reenvía el archivo.


class PropuestaMapeoOut(BaseModel):
    columna_indice: int
    columna_nombre_crudo: str
    campo_canonico: str
    score: float
    confianza: str
    motivo: str


class MapeoPropuestoOut(BaseModel):
    tipo_documento: str
    propuestas: list[PropuestaMapeoOut]
    campos_sin_cubrir: list[str]
    review_required: bool


class CampoEsquemaOut(BaseModel):
    nombre: str
    tipo: str
    obligatorio: bool
    sinonimos: list[str]
    descripcion: str


class PrepararMapeoResponse(BaseModel):
    perfil: PerfilTablaOut
    esquema: list[CampoEsquemaOut]  # todos los campos canónicos del tipo
    propuesta: MapeoPropuestoOut
    cola_revision: list[ItemRevision]


class AplicarMapeoResponse(BaseModel):
    dataset: DatasetNormalizado
    cola_revision: list[ItemRevision]


def _resolver_esquema_o_400(tipo_documento: Optional[str]):
    """Resuelve el esquema de mapeo o 400 con mensaje claro."""
    if not tipo_documento:
        raise HTTPException(
            status_code=400,
            detail="Indique 'tipo_documento' (mayor, asiento_diario, balance, ventas, compras).",
        )
    try:
        return resolver_esquema(tipo_documento)
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{tipo_documento}' no es un tipo con esquema de mapeo. "
                "Use: mayor, asiento_diario, balance, ventas, compras."
            ),
        )


def _perfil_out(perfil) -> PerfilTablaOut:
    return PerfilTablaOut(
        columnas=[
            ColumnaPerfilOut(
                indice=c.indice,
                nombre_crudo=c.nombre_crudo,
                tipo_inferido=c.tipo_inferido.value,
                muestra=list(c.muestra),
                n_no_vacios=c.n_no_vacios,
                n_total=c.n_total,
            )
            for c in perfil.columnas
        ],
        n_filas=perfil.n_filas,
        fila_encabezado=perfil.fila_encabezado,
        hoja=perfil.hoja,
    )


@router.post("/mapeo/preparar", response_model=PrepararMapeoResponse)
async def mapeo_preparar(
    file: UploadFile = File(...),
    tipo_documento: Optional[str] = Form(default=None),
) -> PrepararMapeoResponse:
    """Etapa 1 de la Capa de Mapeo: perfila la tabla y PROPONE el mapeo.

    No normaliza nada ni avanza: devuelve el perfil de columnas, los campos
    canónicos del tipo, la propuesta (columna→campo con score y confianza) y la
    cola de revisión. El auditor la revisa y confirma antes de normalizar (M07).
    """
    esquema = _resolver_esquema_o_400(tipo_documento)
    contenido = await _leer(file)
    perfil, propuesta = preparar_mapeo(contenido, file.filename or "tabla", tipo_documento)
    return PrepararMapeoResponse(
        perfil=_perfil_out(perfil),
        esquema=[
            CampoEsquemaOut(
                nombre=c.nombre,
                tipo=c.tipo.value,
                obligatorio=c.obligatorio,
                sinonimos=list(c.sinonimos),
                descripcion=c.descripcion,
            )
            for c in esquema.campos
        ],
        propuesta=MapeoPropuestoOut(
            tipo_documento=propuesta.tipo_documento,
            propuestas=[
                PropuestaMapeoOut(
                    columna_indice=p.columna_indice,
                    columna_nombre_crudo=p.columna_nombre_crudo,
                    campo_canonico=p.campo_canonico,
                    score=p.score,
                    confianza=p.confianza.value,
                    motivo=p.motivo,
                )
                for p in propuesta.propuestas
            ],
            campos_sin_cubrir=propuesta.campos_sin_cubrir,
            review_required=propuesta.review_required,
        ),
        cola_revision=cola_revision_mapeo(propuesta),
    )


@router.post("/mapeo/aplicar", response_model=AplicarMapeoResponse)
async def mapeo_aplicar(
    file: UploadFile = File(...),
    tipo_documento: Optional[str] = Form(default=None),
    mapeo_confirmado: str = Form(...),
) -> AplicarMapeoResponse:
    """Etapa 2 de la Capa de Mapeo: aplica el mapeo CONFIRMADO por el auditor.

    ``mapeo_confirmado`` es un JSON ``{campo_canonico: indice_columna}`` que el
    auditor aprobó en la UI. El backend re-perfila el archivo (determinista) y
    normaliza. M22: un obligatorio con celda vacía queda ``None`` y a revisión,
    nunca cero.
    """
    esquema = _resolver_esquema_o_400(tipo_documento)
    try:
        confirmado_raw = json.loads(mapeo_confirmado)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="'mapeo_confirmado' debe ser JSON válido.")
    if not isinstance(confirmado_raw, dict) or not confirmado_raw:
        raise HTTPException(
            status_code=400,
            detail="'mapeo_confirmado' debe ser un objeto {campo: indice_columna} no vacío.",
        )

    contenido = await _leer(file)
    perfil = perfilar(contenido, file.filename or "tabla")
    ancho = len(perfil.columnas)

    mapeo: dict[str, int] = {}
    for campo, idx in confirmado_raw.items():
        if esquema.campo(campo) is None:
            raise HTTPException(
                status_code=400,
                detail=f"'{campo}' no es un campo de {esquema.tipo_documento.value}.",
            )
        try:
            col = int(idx)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail=f"El índice de columna de '{campo}' debe ser entero."
            )
        if not (0 <= col < ancho):
            raise HTTPException(
                status_code=400,
                detail=f"El índice {col} de '{campo}' está fuera de rango (0..{ancho - 1}).",
            )
        mapeo[campo] = col

    ds = aplicar_mapeo(
        perfil.filas,
        perfil,
        mapeo,
        esquema,
        source_file=file.filename or "tabla",
        document_type=esquema.tipo_documento,
    )
    return AplicarMapeoResponse(dataset=ds, cola_revision=cola_de_revision([ds]))
