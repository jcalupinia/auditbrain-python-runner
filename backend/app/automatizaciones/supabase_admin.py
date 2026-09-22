"""Cliente HTTP del Supabase self-hosted de la app de presupuestos.

ÚNICA pieza del portal que conoce ``PRESUPUESTOS_SERVICE_ROLE_KEY``. Son
funciones de transporte puro: no hay reglas de negocio aquí (esas viven en
``service.py``). La llave nunca se registra en logs ni viaja en los mensajes
de error.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

_TIMEOUT = 20
_INTENTOS = 3  # intento inicial + 2 reintentos
_ESPERA_INICIAL = 1.0
_MAX_CUERPO = 200


class SupabaseAdminError(RuntimeError):
    """Cualquier fallo hablando con el Supabase de la app de presupuestos.

    ``status`` es el código HTTP del 4xx que devolvió Supabase/GoTrue, o
    ``None`` cuando el fallo fue de red o un 5xx agotado (infraestructura,
    no un rechazo del cliente). El router lo usa para distinguir "correo ya
    registrado" (409) de "no se pudo contactar" (502)."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def _credenciales() -> tuple[str, str]:
    url = os.getenv("PRESUPUESTOS_SUPABASE_URL", "").strip().rstrip("/")
    llave = os.getenv("PRESUPUESTOS_SERVICE_ROLE_KEY", "").strip()
    faltan = [
        nombre
        for nombre, valor in (
            ("PRESUPUESTOS_SUPABASE_URL", url),
            ("PRESUPUESTOS_SERVICE_ROLE_KEY", llave),
        )
        if not valor
    ]
    if faltan:
        raise SupabaseAdminError(
            "Falta configurar "
            + " y ".join(faltan)
            + " para conectarse al Supabase de la app de presupuestos."
        )
    return url, llave


def _pedir(
    metodo: str,
    ruta: str,
    *,
    json: Any = None,
    params: dict | None = None,
    bearer: str | None = None,
    extra_headers: dict | None = None,
):
    """Hace la llamada con reintentos y traduce cualquier fallo a un error tipado.

    Reintenta SOLO en errores de red y 5xx; un 4xx es definitivo (reintentarlo
    solo duplicaría altas o borrados).
    """
    if bearer == "":
        # Un token de sesión vacío NUNCA debe colarse silenciosamente como la
        # llave de servicio (``bearer or llave``); eso sería escalar
        # privilegios por un bug del llamador. ``bearer=None`` (el default)
        # sigue siendo el uso intencional de la llave de servicio.
        raise SupabaseAdminError("Token vacío: no se puede autenticar la llamada.")
    base, llave = _credenciales()
    headers = {
        "apikey": llave,
        "Authorization": f"Bearer {bearer or llave}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    url = f"{base}{ruta}"
    espera = _ESPERA_INICIAL

    for intento in range(1, _INTENTOS + 1):
        try:
            resp = requests.request(
                metodo,
                url,
                headers=headers,
                json=json,
                params=params,
                timeout=_TIMEOUT,
            )
        except requests.RequestException as e:
            # Nunca se registra str(e): puede arrastrar la URL con credenciales.
            ultimo = f"sin respuesta ({type(e).__name__})"
        else:
            if resp.status_code < 400:
                return resp
            cuerpo = (resp.text or "")[:_MAX_CUERPO]
            if resp.status_code < 500:
                raise SupabaseAdminError(
                    f"Supabase {resp.status_code} en {metodo} {ruta}: {cuerpo}",
                    status=resp.status_code,
                )
            ultimo = f"{resp.status_code}: {cuerpo}"

        if intento < _INTENTOS:
            log.warning(
                "Supabase presupuestos %s %s falló (%d/%d), reintentando",
                metodo,
                ruta,
                intento,
                _INTENTOS,
            )
            time.sleep(espera)
            espera *= 2

    raise SupabaseAdminError(f"Supabase {ultimo} en {metodo} {ruta} tras {_INTENTOS} intentos")


def _json(resp, metodo: str, ruta: str) -> Any:
    try:
        return resp.json()
    except ValueError:
        raise SupabaseAdminError(
            f"Supabase devolvió una respuesta no-JSON en {metodo} {ruta}"
        ) from None


# --- Usuarios (GoTrue admin API) -------------------------------------------


def crear_usuario(email: str, nombre: str) -> dict:
    """Crea el usuario ya confirmado y sin contraseña (la define él con el enlace)."""
    resp = _pedir(
        "POST",
        "/auth/v1/admin/users",
        json={
            "email": email,
            "email_confirm": True,
            "user_metadata": {"nombre": nombre},
        },
    )
    return _json(resp, "POST", "/auth/v1/admin/users")


def enlace_acceso(email: str, redirect_to: str) -> str:
    """Enlace de un solo uso para que el usuario fije su clave."""
    ruta = "/auth/v1/admin/generate_link"
    resp = _pedir(
        "POST",
        ruta,
        json={"type": "recovery", "email": email, "redirect_to": redirect_to},
    )
    datos = _json(resp, "POST", ruta)
    enlace = (datos or {}).get("action_link")
    if not enlace:
        raise SupabaseAdminError("Supabase no devolvió 'action_link' al generar el enlace de acceso")
    return enlace


def bloquear_usuario(user_id: str, bloquear: bool) -> None:
    _pedir(
        "PUT",
        f"/auth/v1/admin/users/{user_id}",
        json={"ban_duration": "876000h" if bloquear else "none"},
    )


def borrar_usuario(user_id: str) -> None:
    _pedir("DELETE", f"/auth/v1/admin/users/{user_id}")


def usuario_de_token(access_token: str) -> dict:
    """Valida el token de sesión de un usuario de la app y devuelve su perfil."""
    resp = _pedir("GET", "/auth/v1/user", bearer=access_token)
    return _json(resp, "GET", "/auth/v1/user")


# --- Datos (PostgREST) ------------------------------------------------------


def rpc(nombre: str, payload: dict, *, token_usuario: str | None = None) -> Any:
    """``token_usuario`` (Tarea 9): ejecuta la función PostgreSQL con el JWT del
    propio usuario en vez de la llave de servicio, para que reglas como
    ``es_admin_empresa`` (que leen ``auth.uid()``) se apliquen igual que
    cuando llama la app. El gateway de Supabase igual exige una ``apikey``
    válida del proyecto, así que esa sigue siendo la de servicio (la maneja
    ``_pedir``); solo el ``Authorization`` cambia."""
    ruta = f"/rest/v1/rpc/{nombre}"
    resp = _pedir("POST", ruta, json=payload, bearer=token_usuario)
    return _json(resp, "POST", ruta) if (resp.text or "").strip() else None


def consultar(tabla: str, params: dict, *, token_usuario: str | None = None) -> list:
    ruta = f"/rest/v1/{tabla}"
    resp = _pedir("GET", ruta, params=params, bearer=token_usuario)
    return _json(resp, "GET", ruta)


def insertar(tabla: str, filas: list[dict]) -> list:
    ruta = f"/rest/v1/{tabla}"
    resp = _pedir(
        "POST", ruta, json=filas, extra_headers={"Prefer": "return=representation"}
    )
    return _json(resp, "POST", ruta)
