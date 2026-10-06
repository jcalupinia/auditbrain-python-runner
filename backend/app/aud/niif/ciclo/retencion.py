"""Retención de pruebas del ciclo AUD — el Command Center es un lugar de paso.

Decisión del dueño (2026-10-04): las pruebas no se quedan grabadas en el servidor.
El auditor descarga el papel y lo archiva en su propia base (donde viven todas las
pruebas de la auditoría del cliente). El servidor las borra automáticamente:

- **Al descargar + breve gracia (solo pruebas TERMINADAS):** cuando el auditor baja
  el papel de una prueba APROBADA (`servicio.marcar_descargada`), se registra
  ``registro["descargada_en"]`` y se borra ``AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES``
  después (30 min por defecto), suficiente para bajar varios formatos (Excel, HTML,
  Word, PDF) sin perderla a mitad.
- **Tope duro de 8 h (solo pruebas TERMINADAS):** una prueba APROBADA nunca pasa de
  ``AUD_CICLO_PRUEBA_TTL_HORAS`` (8 h) desde que se creó, se haya descargado o no.

Esto aplica a las pruebas TERMINADAS (APROBADO): el borrado automático levanta la
regla ``APROBADA_NO_SE_TOCA`` (que sigue protegiendo el borrado MANUAL del usuario).
El borrado es definitivo: fila, evidencia, bitácora y archivos del disco.

**Previsualizar ≠ archivar — el trabajo EN CURSO no se autopurga (2026-10-06).**
Una prueba que sigue ABIERTA (estado ≠ ``APROBADO``) NUNCA se borra por previsualizar
ni descargar su papel: en estas herramientas el auditor previsualiza el borrador
(Excel/HTML/Word/PDF, incluida la landing por sección) decenas de veces mientras lo
arma, y cada preview pasa por ``marcar_descargada``. Antes, descargar un borrador
abierto le ponía ``descargada_en`` y lo autodestruía a los 30 min aunque se siguiera
trabajando: dos auditores, cada uno en su propio encargo, previsualizaban su
planificación y a los ~30 min el purgador —que es GLOBAL— borraba el trabajo de
ambos (se percibía como "una persona borró a la otra"). Ahora el trabajo abierto solo
se limpia tras una **inactividad larga** (``AUD_CICLO_ABIERTA_INACTIVA_HORAS``, 72 h
por defecto), medida desde la **última actividad** (editar o previsualizar refrescan
``actualizada_en``): un borrador realmente abandonado se barre, uno activo jamás. El
"lugar de paso" limpia lo TERMINADO/descargado, no lo activo (ver ``_vencida``).

Corre en un loop de fondo arrancado en ``app.py`` (igual que el cleanup AUD/OF).
"""
from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select

from backend.app.aud.niif.ciclo import almacen
from backend.app.aud.niif.ciclo.models import Prueba, PruebaArchivo, PruebaEvento
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _parse(iso: str | None) -> datetime.datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(iso))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _vencida(p: Prueba, ahora: datetime.datetime) -> bool:
    """¿Esta prueba ya debe borrarse?

    Reglas (actualización 2026-10-06, "previsualizar ≠ archivar"):
    - **Trabajo EN CURSO (estado ≠ ``APROBADO``): intocable por previsualizar/descargar.**
      No importa si tiene ``descargada_en``: previsualizar un borrador no es archivarlo.
      Solo se limpia tras una inactividad larga (``AUD_CICLO_ABIERTA_INACTIVA_HORAS``,
      72 h), medida desde la ÚLTIMA actividad (``actualizada_en``, que se refresca al
      editar y al previsualizar). Así un borrador abandonado se barre y uno activo no.
    - **Trabajo TERMINADO (``APROBADO``): lugar de paso.** Se borra pasada la gracia
      post-descarga y, en todo caso, a las 8 h de creado. El borrado automático levanta
      aquí ``APROBADA_NO_SE_TOCA`` (que sigue protegiendo el borrado MANUAL).
    """
    en_curso = (p.estado or "").upper() != "APROBADO"
    if en_curso:
        # Activo: ni previsualizar ni descargar lo borra. Solo cae por inactividad larga.
        inactiva = settings.AUD_CICLO_ABIERTA_INACTIVA_HORAS
        ref = p.actualizada_en or p.creada_en
        return ref is not None and (ahora - ref) >= datetime.timedelta(hours=inactiva)
    # APROBADO (terminado): purgar tras la gracia de descarga…
    descargada = _parse((p.registro or {}).get("descargada_en"))
    if descargada is not None:
        gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
        if (ahora - descargada) >= datetime.timedelta(minutes=gracia):
            return True
    # …y, en todo caso, tope duro de 8 h desde la creación.
    tope_horas = settings.AUD_CICLO_PRUEBA_TTL_HORAS
    if p.creada_en is not None and (ahora - p.creada_en) >= datetime.timedelta(hours=tope_horas):
        return True
    return False


def purgar_prueba(db, p: Prueba) -> None:
    """Borra definitivamente la prueba: evidencia, bitácora, fila y archivos del
    disco. SIN la guardia ``APROBADA_NO_SE_TOCA`` (es el borrado automático del
    lugar de paso, no el manual del usuario)."""
    pid = p.id
    for a in db.execute(select(PruebaArchivo).where(PruebaArchivo.prueba_id == pid)).scalars().all():
        db.delete(a)
    for e in db.execute(select(PruebaEvento).where(PruebaEvento.prueba_id == pid)).scalars().all():
        db.delete(e)
    # Desenganchar hijas (parent_id) para no violar la FK antes de borrar la madre.
    for h in db.execute(select(Prueba).where(Prueba.parent_id == pid)).scalars().all():
        h.parent_id = None
        db.add(h)
    db.delete(p)
    db.commit()
    # Los archivos se borran del disco DESPUÉS de confirmar la base: si fallara,
    # queda una carpeta huérfana (la barre el cleanup), nunca una fila sin archivo.
    almacen.borrar_prueba(pid)


def purgar_once() -> dict:
    """Una pasada: borra las pruebas vencidas. Devuelve un resumen."""
    resumen = {"purgadas": 0}
    if not settings.AUD_CICLO_RETENCION_ENABLED:
        return resumen
    ahora = _ahora()
    # Pre-filtro barato: nada puede vencer antes de (creación + gracia), y la
    # descarga nunca es anterior a la creación. Así no recorremos las recién creadas.
    gracia = datetime.timedelta(minutes=settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES)
    db = SessionLocal()
    try:
        candidatas = db.execute(
            select(Prueba).where(Prueba.creada_en <= ahora - gracia)
        ).scalars().all()
        for p in candidatas:
            if _vencida(p, ahora):
                purgar_prueba(db, p)
                resumen["purgadas"] += 1
    finally:
        db.close()
    return resumen


async def purgar_loop() -> None:
    """Loop infinito que purga cada ``AUD_CICLO_CLEANUP_INTERVAL_SECONDS``.

    ``purgar_once`` es SÍNCRONO (abre sesión, SELECT + DELETE, borra del disco):
    se despacha a un hilo para no congelar el event loop ni el health check."""
    interval = settings.AUD_CICLO_CLEANUP_INTERVAL_SECONDS
    while True:
        try:
            s = await asyncio.to_thread(purgar_once)
            if s.get("purgadas"):
                log.info("aud_ciclo retención: %s", s)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("aud_ciclo retención falló")
        await asyncio.sleep(interval)
