"""NIIF 18 Studio — endpoints del portal del cliente.

Sirve la herramienta ``NIIF_18_STUDIO``: el catálogo de la Biblioteca Normativa
NIIF, las normas navegables y los modelos de estados financieros de las firmas.

Acceso (``require_client_with_device``, la misma dependencia del resto del portal):

* ``client`` con la herramienta concedida (``UserToolEntitlement``): ve el
  catálogo y las normas NIIF.
* ``admin`` / ``user`` (operadores): además, los modelos de estados financieros
  de EY, KPMG, PwC, Deloitte y Grant Thornton, que son de uso interno.

El bloqueo de los modelos es **del servidor**, no de la vista: los directorios
``modelos-*`` no se publican como estáticos y solo se entregan por
``/client/niif18/modelos/{grupo}/{archivo}`` tras comprobar el rol. Conocer el
nombre exacto del archivo no basta.

La biblioteca vive fuera del repositorio (son ~40 MB de normas y PDF). Su ruta
se configura con la variable de entorno ``NIIF18_BIBLIOTECA_DIR``; si no está
definida o no existe, los endpoints responden 503 con un mensaje claro en vez
de romper el arranque de la API.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_client_with_device
from backend.app.auth.models import User
from backend.app.client_portal.entitlements import can_access_tool, is_operator
from backend.app.db.session import get_db

router = APIRouter(prefix="/client/niif18", tags=["client-niif18"])

TOOL_CODE = "NIIF_18_STUDIO"

#: Subdirectorios restringidos: NUNCA se sirven por /biblioteca/.
GRUPOS_RESTRINGIDOS = ("modelos-niif18", "modelos-2026")

#: Tipos que la biblioteca puede servir. Todo lo demás se rechaza.
_MIMES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


#: Ruta por defecto: la que deja el Dockerfile de producción al traer la
#: biblioteca desde su repositorio privado durante el build. Así el despliegue
#: no necesita configurar nada, y `NIIF18_BIBLIOTECA_DIR` queda solo para
#: entornos donde la biblioteca viva en otro sitio (p. ej. un volumen).
RAIZ_PROYECTO = Path(__file__).resolve().parents[3]
BIBLIOTECA_POR_DEFECTO = RAIZ_PROYECTO / "base-normativa" / "libro"


def _raiz() -> Path:
    """Directorio de la biblioteca. 503 si no está disponible."""
    crudo = os.getenv("NIIF18_BIBLIOTECA_DIR", "").strip()
    base = Path(crudo).resolve() if crudo else BIBLIOTECA_POR_DEFECTO
    if not base.is_dir():
        raise HTTPException(
            status_code=503,
            detail=(
                "La Biblioteca Normativa no está disponible en este entorno. "
                "La imagen la trae durante el build desde su repositorio privado; "
                "si falta, revise el secreto de build o defina NIIF18_BIBLIOTECA_DIR."
            ),
        )
    return base


def _exige_herramienta(db: Session, user: User) -> None:
    """Operadores pasan; un cliente necesita la herramienta concedida."""
    if is_operator(user):
        return
    if not can_access_tool(db, user.id, TOOL_CODE):
        raise HTTPException(
            status_code=403,
            detail="Su cuenta no tiene habilitada la herramienta NIIF 18 Studio.",
        )


def _exige_operador(user: User) -> None:
    """Los modelos de las firmas son material interno: solo admin/user."""
    if not is_operator(user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Los modelos de estados financieros de las firmas están "
                "restringidos a operadores de Auditconsulting."
            ),
        )


def _resolver_dentro(base: Path, relativo: str) -> Path:
    """Resuelve ``relativo`` dentro de ``base`` o lanza 400/404.

    Defensa contra path traversal: se resuelve y se comprueba que el resultado
    siga colgando de ``base``. Rechaza además los directorios restringidos.
    """
    if not relativo or relativo.startswith("/") or "\x00" in relativo:
        raise HTTPException(status_code=400, detail="Ruta no válida.")
    destino = (base / relativo).resolve()
    if destino != base and base not in destino.parents:
        raise HTTPException(status_code=400, detail="Ruta fuera de la biblioteca.")
    try:
        partes = destino.relative_to(base).parts
    except ValueError:  # pragma: no cover - cubierto por la comprobación previa
        raise HTTPException(status_code=400, detail="Ruta fuera de la biblioteca.")
    if partes and partes[0] in GRUPOS_RESTRINGIDOS:
        raise HTTPException(
            status_code=403,
            detail="Use /client/niif18/modelos/… ; estos archivos exigen rol operador.",
        )
    if not destino.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en la biblioteca.")
    return destino


# ---------------------------------------------------------------------------
# Sesión y catálogo
# ---------------------------------------------------------------------------
@router.get("/me")
def me(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> dict:
    """Identidad y rol para que la interfaz sepa qué mostrar.

    No es un control de acceso: el bloqueo real está en cada endpoint.
    """
    _exige_herramienta(db, user)
    return {
        "usuario": {
            "usuario": user.email,
            "nombre": user.email,
            "rol": user.role.value,
            "operador": is_operator(user),
        }
    }


@router.get("/normas")
def normas(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> dict:
    """Catálogo de la biblioteca.

    A un cliente se le entrega SIN la lista de modelos de las firmas: no debe
    conocer siquiera los nombres de esos archivos.
    """
    _exige_herramienta(db, user)
    manifiesto = _raiz().parent / "manifiesto.json"
    if not manifiesto.is_file():
        manifiesto = _raiz() / "manifiesto.json"
    if not manifiesto.is_file():
        raise HTTPException(
            status_code=503,
            detail="El manifiesto de la biblioteca no está disponible en el servidor.",
        )
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=503, detail=f"Manifiesto ilegible: {e.__class__.__name__}")
    if not is_operator(user):
        datos = dict(datos)
        datos["modelos"] = []
    return datos


@router.get("/modelos")
def modelos(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> dict:
    """Lista de modelos de las firmas. Solo operadores."""
    _exige_herramienta(db, user)
    _exige_operador(user)
    manifiesto = _raiz().parent / "manifiesto.json"
    if not manifiesto.is_file():
        manifiesto = _raiz() / "manifiesto.json"
    if not manifiesto.is_file():
        raise HTTPException(status_code=503, detail="Manifiesto no disponible.")
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    return {"modelos": datos.get("modelos", [])}


# ---------------------------------------------------------------------------
# Contenido
# ---------------------------------------------------------------------------
@router.get("/biblioteca/{ruta:path}")
def biblioteca(
    ruta: str,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> Response:
    """Índice y normas navegables. Cualquier usuario con la herramienta."""
    _exige_herramienta(db, user)
    base = _raiz()
    destino = _resolver_dentro(base, ruta)
    tipo = _MIMES.get(destino.suffix.lower())
    if tipo is None:
        raise HTTPException(status_code=415, detail="Tipo de archivo no servible.")
    return FileResponse(destino, media_type=tipo)


@router.get("/modelos/{grupo}/{archivo}")
def modelo(
    grupo: str,
    archivo: str,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> Response:
    """Entrega un modelo de estados financieros. SOLO operadores."""
    _exige_herramienta(db, user)
    _exige_operador(user)
    if grupo not in GRUPOS_RESTRINGIDOS:
        raise HTTPException(status_code=404, detail="Grupo de modelos no encontrado.")
    base = _raiz() / grupo
    nombre = os.path.basename(archivo)
    if not nombre.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Solo se entregan PDF.")
    destino = (base / nombre).resolve()
    if base.resolve() not in destino.parents:
        raise HTTPException(status_code=400, detail="Ruta no válida.")
    if not destino.is_file():
        raise HTTPException(status_code=404, detail="Modelo no encontrado.")
    return FileResponse(
        destino,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )
