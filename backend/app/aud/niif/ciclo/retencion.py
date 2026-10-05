"""Retención de pruebas del ciclo AUD — el Command Center es un lugar de paso.

Decisión del dueño (2026-10-04): las pruebas no se quedan grabadas en el servidor.
El auditor descarga el papel y lo archiva en su propia base (donde viven todas las
pruebas de la auditoría del cliente). El servidor las borra automáticamente:

- **Al descargar + breve gracia:** cuando el usuario baja el papel
  (`servicio.marcar_descargada`), se registra ``registro["descargada_en"]``. La
  prueba se borra ``AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES`` después (30 min por
  defecto), suficiente para bajar varios formatos (Excel, HTML, Word, PDF) sin
  perderla a mitad.
- **Tope duro de 8 h:** en todo caso, nunca pasa de ``AUD_CICLO_PRUEBA_TTL_HORAS``
  (8 h) desde que se creó, se haya descargado o no.

Aplica a las pruebas TERMINADAS o ya DESCARGADAS, **aprobadas incluidas**: el
borrado automático levanta la regla ``APROBADA_NO_SE_TOCA`` (que sigue protegiendo
el borrado MANUAL del usuario). El borrado es definitivo: fila, evidencia, bitácora
y archivos del disco.

**Excepción (2026-10-05): el trabajo EN CURSO no se autopurga.** Una prueba que
sigue ABIERTA (estado ≠ ``APROBADO``) y que nunca se descargó queda intocable por
el borrado automático, aunque pase de las 8 h. El tope duro destruía una
planificación (NIA 300) a medio armar mientras el auditor la trabajaba. El "lugar
de paso" limpia lo terminado/descargado, no lo activo (ver ``_vencida``).

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

    Reglas (actualización 2026-10-05):
    - **Trabajo en curso protegido:** una prueba que sigue ABIERTA (estado distinto
      de ``APROBADO``) y que NUNCA se descargó NO se autopurga, aunque pase de las
      8 h. Antes se borraba a las 8 h "se haya descargado o no", lo que destruía una
      planificación (NIA 300) a medio armar mientras el auditor aún la trabajaba
      (síntoma: "Prueba no encontrada" al extraer/confirmar). El "lugar de paso"
      limpia papeles TERMINADOS o ya DESCARGADOS, no trabajo activo.
    - **Descargada:** una vez que el auditor bajó el papel (lo archivó en su base),
      se borra pasada la gracia post-descarga. Aplica a cualquier estado.
    - **Tope duro de 8 h:** sigue vigente para pruebas APROBADAS (terminadas) o ya
      descargadas, como backstop para que el servidor no acumule papeles cerrados.
    """
    descargada = _parse((p.registro or {}).get("descargada_en"))
    en_curso = (p.estado or "").upper() != "APROBADO"
    # Trabajo en curso y sin descargar: intocable por el borrado automático.
    if en_curso and descargada is None:
        return False
    # Descargada: ya archivada → purgar pasada la gracia.
    if descargada is not None:
        gracia = settings.AUD_CICLO_POST_DOWNLOAD_TTL_MINUTES
        if (ahora - descargada) >= datetime.timedelta(minutes=gracia):
            return True
    # Tope duro desde la creación (ya solo alcanza aprobadas o descargadas).
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
