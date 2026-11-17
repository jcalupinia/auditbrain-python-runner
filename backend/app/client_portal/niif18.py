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

import datetime
import hashlib
import hmac

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.auth import service as auth_service
from backend.app.auth.deps import _session_check_enabled, require_client_with_device
from backend.app.auth.jwt_tokens import _secret
from backend.app.auth.models import Role, User
from backend.app.client_portal.entitlements import can_access_tool, is_operator
from backend.app.core.config import settings
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
# Pase de biblioteca (cookie) — por qué existe
# ---------------------------------------------------------------------------
# Las normas se abren como páginas: el usuario hace clic en un enlace y el
# navegador NAVEGA a .../biblioteca/normas/ifrs9.html. Una navegación no puede
# llevar la cabecera ``Authorization``, así que con Bearer a secas toda norma
# respondía 401 "Falta token Bearer".
#
# Tampoco sirve traer el HTML por fetch y abrirlo como ``blob:``: los archivos
# de la biblioteca se citan entre ellos (``cf.html#CF2018_2.4``,
# ``../index.html``) — casi 9.000 referencias — y bajo ``blob:`` no hay
# directorio contra el que resolverlas. Se perdería la navegación cruzada, que
# es justamente el valor de la biblioteca.
#
# Solución: un PASE propio, de vida corta, en una cookie HttpOnly que el
# navegador sí manda en una navegación. El pase:
#   * lo emite ``POST /client/niif18/pase``, que exige Bearer y la herramienta;
#   * NO es un token de sesión: no lleva ``role`` ni ``sid``, así que no abre
#     ningún otro endpoint del portal (``require_client_with_device`` lo
#     rechaza con 403 por falta de rol);
#   * va restringido por ``Path`` a este router, así que no viaja al resto de
#     la API;
#   * solo se acepta en los dos endpoints de CONTENIDO. El catálogo, ``/me`` y
#     la lista de modelos siguen exigiendo Bearer.
# El control de rol de los modelos de las firmas NO cambia: se vuelve a
# comprobar en cada petición, venga por Bearer o por pase.

#: Nombre de la cookie del pase.
PASE_COOKIE = "niif18_pase"

#: Claim que distingue al pase de un token de sesión del portal.
PASE_SCOPE = "niif18-biblioteca"

#: Ruta de la cookie: solo este router la recibe.
PASE_PATH = f"{settings.PLATFORM_API_PREFIX}/client/niif18"


def _pase_ttl_min() -> int:
    """Minutos de vida del pase (``NIIF18_PASE_TTL_MINUTES``, def. 30).

    30 min y no más: el pase no se refresca al leer una norma (no pasa por
    ``touch_session``), así que es la única ventana en la que puede sobrevivir
    a la caducidad por inactividad de la sesión del portal. El Studio lo
    renueva cada 20 min, con margen de sobra mientras su pestaña siga abierta.
    El logout y el relevo de cuenta lo invalidan al instante por el ``sid``.
    """
    try:
        valor = int(os.getenv("NIIF18_PASE_TTL_MINUTES", "30"))
    except ValueError:
        return 30
    return valor if 1 <= valor <= 720 else 30


def _cookie_segura() -> bool:
    """``Secure`` en la cookie. Por defecto SÍ; solo se apaga a propósito.

    ``NIIF18_PASE_COOKIE_SECURE=false`` sirve para desarrollo y pruebas sobre
    http. En producción no se toca: la cookie viaja solo por HTTPS.
    """
    return os.getenv("NIIF18_PASE_COOKIE_SECURE", "true").strip().lower() not in {
        "false", "0", "no",
    }


def _pase_secret() -> str:
    """Clave de firma PROPIA del pase, derivada del secreto de la plataforma.

    No se firma con ``_secret()`` a secas. Si se hiciera, el pase sería un JWT
    válido para ``decode_token`` y, como ``auth.deps._user_from_token`` mira el
    rol del usuario en la base y NO el claim ``role``, el pase de un OPERADOR
    autenticaría peticiones a los endpoints de staff del Command Center. Está
    comprobado: con el pase firmado con el secreto común,
    ``GET /api/v1/staff/tools`` respondía 200.

    Con una clave derivada el pase NO verifica contra el secreto de la
    plataforma, así que no sirve como token en ningún otro endpoint, presente o
    futuro, sin depender de que cada dependencia recuerde revisar un claim.
    """
    return hmac.new(
        _secret().encode("utf-8"), b"niif18-pase-biblioteca-v1", hashlib.sha256
    ).hexdigest()


def _emitir_pase(user: User) -> str:
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    return jwt.encode(
        {
            "sub": user.email,
            "scope": PASE_SCOPE,
            # Sesión del portal vigente al emitirlo: si el cliente cierra
            # sesión (queda en None) o alguien más toma la cuenta, el pase deja
            # de valer sin esperar a que expire.
            "sid": getattr(user, "current_session_id", None),
            "iat": ahora,
            "exp": ahora + datetime.timedelta(minutes=_pase_ttl_min()),
        },
        _pase_secret(),
        algorithm="HS256",
    )


def _usuario_del_pase(pase: str, db: Session) -> User:
    try:
        payload = jwt.decode(pase, _pase_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="El pase de la biblioteca expiró. Vuelva a abrir el NIIF 18 Studio.",
        )
    if payload.get("scope") != PASE_SCOPE:
        raise HTTPException(status_code=403, detail="Este token no abre la biblioteca.")
    user = auth_service.get_user_by_email(db, payload.get("sub") or "")
    if not user or not user.is_active or user.role not in (Role.client, Role.admin, Role.user):
        raise HTTPException(status_code=401, detail="Credenciales inválidas o token expirado.")
    # Sesión única del portal: el pase no sobrevive al logout ni a un relevo de
    # cuenta. Los operadores están exentos, igual que en el resto del portal.
    if user.role == Role.client and _session_check_enabled():
        if not payload.get("sid") or payload.get("sid") != user.current_session_id:
            raise HTTPException(
                status_code=401,
                detail="La sesión del portal se cerró. Vuelva a ingresar a AUDIT-IA.",
            )
    return user


def _acceso_contenido(
    request: Request,
    device_id: str | None = Cookie(default=None, alias="device_id"),
    pase: str | None = Cookie(default=None, alias=PASE_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Bearer (fetch del Studio) o pase (navegación a una norma)."""
    if request.headers.get("Authorization", "").lower().startswith("bearer "):
        return require_client_with_device(request=request, device_id=device_id, db=db)
    if not pase:
        raise HTTPException(
            status_code=401,
            detail="Falta token Bearer o pase de biblioteca.",
        )
    return _usuario_del_pase(pase, db)


@router.post("/pase")
def abrir_pase(
    respuesta: Response,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> dict:
    """Deja la cookie del pase para que los enlaces de las normas abran."""
    _exige_herramienta(db, user)
    minutos = _pase_ttl_min()
    respuesta.set_cookie(
        PASE_COOKIE,
        _emitir_pase(user),
        max_age=minutos * 60,
        httponly=True,
        secure=_cookie_segura(),
        samesite="lax",
        path=PASE_PATH,
    )
    return {"vence_en_minutos": minutos}


@router.delete("/pase")
def cerrar_pase(respuesta: Response) -> dict:
    """Retira la cookie. El portal lo llama al cerrar sesión."""
    respuesta.delete_cookie(PASE_COOKIE, path=PASE_PATH)
    return {"cerrado": True}


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
    user: User = Depends(_acceso_contenido),
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
    user: User = Depends(_acceso_contenido),
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
