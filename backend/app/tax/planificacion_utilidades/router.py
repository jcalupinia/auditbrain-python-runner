"""Endpoints HTTP de TAX.PLANIFICACION_UTILIDADES (ingesta + exportación).

Stateless: no hay jobs ni base de datos. El frontend mantiene el estado y
recalcula en vivo; aquí solo parseamos archivos y armamos el Excel.
"""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.core.config import settings
from backend.app.tax.planificacion_utilidades import exporter
from backend.app.tax.planificacion_utilidades.parsers import (
    balance_resumido,
    f101,
)
from backend.app.tax.planificacion_utilidades import pptx_builder
import json
import urllib.error
import urllib.request

from backend.app.tax.planificacion_utilidades.schemas import (
    ExportRequest,
    ExtractResponse,
    PresentacionRequest,
    SriRucResponse,
)

router = APIRouter(
    prefix="/tax/planificacion-utilidades",
    tags=["tax-planificacion-utilidades"],
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ALLOWED = {
    "f101": {"application/pdf"},
    "resumido": {XLSX_MIME, "application/vnd.ms-excel"},
}


@router.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(
    kind: str = Form(...),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    if kind not in _ALLOWED:
        raise HTTPException(400, detail="kind debe ser 'f101' o 'resumido'.")
    allowed = _ALLOWED[kind]
    if file.content_type and file.content_type not in allowed:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo {file.content_type} no permitido para {kind}.",
        )
    data = await file.read()
    max_bytes = settings.AUD_OF_MAX_FILE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo excede {settings.AUD_OF_MAX_FILE_MB} MB.",
        )
    if not data:
        raise HTTPException(400, detail="Archivo vacío.")

    if kind == "f101":
        result = f101.extract_f101(data)
    else:
        result = balance_resumido.extract_balance_resumido(data)
    return ExtractResponse(**result)


@router.post("/export")
def export_endpoint(
    body: ExportRequest,
    current: User = Depends(get_current_user),
):
    ctrl = [c.model_dump() for c in body.ctrl]
    xlsx = exporter.build_workbook(body.data, ctrl, body.params)
    empresa = str(body.params.get("empresa", "cliente")) or "cliente"
    safe = empresa.replace(" ", "_").replace("/", "_")
    filename = f"Planificacion_Utilidades_{safe}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Fuente alterna (agregador que espeja el catastro del SRI en JSON). Se usa
# PRIMERO porque el endpoint directo del SRI rechaza las consultas
# automatizadas: su WAF anti-bot cierra la conexión (TCP RST) tras el handshake
# TLS, para cualquier cliente y desde cualquier red (verificado 2026-06 con
# urllib/requests/curl/Chromium). El agregador devuelve el mismo esquema de
# campos que el SRI + el código CIIU, y es alcanzable desde cualquier IP.
_CIPHERBYTE_URL = "https://aggregator.cipherbyte.ec/company/"

# Respaldo: endpoint oficial del SRI. Suele rechazar a clientes automatizados,
# pero se intenta por si responde (p. ej. cuando el WAF está relajado o desde
# una IP de Ecuador) y para no depender de un único proveedor.
_SRI_URL = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/"
    "rest/ConsolidadoContribuyente/obtenerPorNumerosRuc?ruc="
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _http_json(url: str, timeout: int = 15):
    """GET con headers de navegador que devuelve el JSON parseado."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-EC,es;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _map_contribuyente(c: dict, fuente: str) -> SriRucResponse:
    """Mapea la respuesta (esquema SRI/CipherByte) al modelo del frontend."""
    return SriRucResponse(
        ruc=c.get("numeroRuc"),
        razon_social=c.get("razonSocial"),
        actividad=c.get("actividadEconomicaPrincipal"),
        estado=c.get("estadoContribuyenteRuc"),
        tipo=c.get("tipoContribuyente"),
        regimen=c.get("regimen"),
        ciiu=c.get("ciiu"),
        fuente=fuente,
    )


@router.get("/sri/{ruc}", response_model=SriRucResponse)
def consultar_sri(ruc: str, current: User = Depends(get_current_user)):
    """Devuelve razón social + actividad económica (y CIIU) a partir del RUC.

    Intenta primero el agregador alterno (JSON, accesible desde cualquier red) y,
    como respaldo, el endpoint oficial del SRI. Se usa para auto-poblar el cliente
    y sugerir el sector (CIIU) del que sale la tasa de crecimiento sectorial.
    """
    digits = "".join(ch for ch in (ruc or "") if ch.isdigit())
    if len(digits) != 13:
        raise HTTPException(400, "RUC inválido (deben ser 13 dígitos).")

    # 1) Fuente alterna (CipherByte): JSON limpio, alcanzable desde cualquier IP.
    try:
        data = _http_json(_CIPHERBYTE_URL + digits)
        c = data[0] if isinstance(data, list) else data
        if c and c.get("razonSocial"):
            return _map_contribuyente(c, fuente="cipherbyte")
    except urllib.error.HTTPError:
        pass  # 404/5xx del agregador -> probamos el SRI
    except Exception:  # noqa: BLE001
        pass  # error de red -> probamos el SRI

    # 2) Respaldo: SRI oficial (funciona cuando no está bloqueado / desde EC).
    try:
        data = _http_json(_SRI_URL + digits)
        if data:
            c = data[0] if isinstance(data, list) else data
            if c and c.get("razonSocial"):
                return _map_contribuyente(c, fuente="sri")
    except Exception:  # noqa: BLE001
        pass

    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "No se pudo obtener el RUC en este momento: el servicio de consulta "
            "del SRI no está respondiendo. Ingresa la razón social y la sección "
            "CIIU manualmente — esta consulta es solo un respaldo."
        ),
    )


@router.get("/plantilla")
def plantilla_endpoint(current: User = Depends(get_current_user)):
    xlsx = exporter.build_plantilla()
    return StreamingResponse(
        BytesIO(xlsx),
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": 'attachment; filename="Balance_resumido_plantilla.xlsx"'
        },
    )


PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


@router.post("/presentacion")
def presentacion_endpoint(
    body: PresentacionRequest,
    current: User = Depends(get_current_user),
):
    """Genera la presentación ejecutiva (.pptx) premium. Requiere JWT.

    Se construye en el servidor con python-pptx replicando la estética aprobada
    (tema oscuro, DM Sans, KPIs grandes). No depende de servicios externos.
    """
    try:
        pptx = pptx_builder.build_deck(body.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, detail=f"Error generando la presentación: {exc}") from exc

    empresa = str(body.content.get("empresa", "cliente")) or "cliente"
    safe = empresa.replace(" ", "_").replace("/", "_")
    filename = f"Presentacion_Utilidades_{safe}.pptx"
    return StreamingResponse(
        BytesIO(pptx),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
