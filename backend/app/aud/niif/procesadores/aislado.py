"""O2 · Aislamiento de la generación pesada de papeles en un SUBPROCESO.

El armado del libro (``libro.xlsx`` + ``libro.html``) es el paso que más memoria consume
(para una cartera grande de la prueba PCE se midió ~1,3 GB de pico). Si corre dentro del
proceso de ``uvicorn``, un pico puede disparar el OOM del contenedor y matar el backend
para todos (incidente real: ``uvicorn`` muerto por el kernel a 2,44 GB).

Este módulo ejecuta ese armado en un **proceso hijo** con ``multiprocessing`` en modo
**``spawn``** (NO ``fork``): ``uvicorn`` tiene muchos hilos y el panel usa matplotlib; un
``fork`` heredaría locks tomados por esos hilos y el hijo se COLGARÍA (deadlock clásico,
verificado en staging). ``spawn`` arranca un intérprete nuevo que reimporta limpio.
Al terminar el hijo, el sistema operativo **recupera el 100 %** de su memoria.

El resultado (xlsx/html, varios MB) se devuelve por **archivos temporales**, no por la
cola: un objeto grande en ``multiprocessing.Queue`` bloquea el hilo «feeder» del hijo
hasta que el padre drene el pipe → deadlock (verificado en staging). Por la cola solo
viaja el estado + las rutas (pequeños).

Capacidades (encargo O2):
  * Límite de memoria POR TRABAJO: watchdog de RSS real desde el padre (lee
    ``/proc/<pid>/statm``). No se usa ``RLIMIT_AS``: ``render.yaml`` lo deja ilimitado
    porque pandas/numpy reservan memoria virtual enorme al importar y los mataría.
  * Tiempo máximo por trabajo (``timeout_s``): se termina el hijo y se informa.
  * Recuperación ante errores: la excepción del hijo se re-lanza como ``GeneracionAislada``.
  * Limpieza: el hijo se ``terminate()``/``kill()``/``join()`` siempre; los temporales se borran.
  * Concurrencia: el llamador envuelve esto en ``concurrencia.limite_proceso_pesado``.

Feature flag: ``AUD_O2_SUBPROCESO`` (ver ``servicio.papel_procesador``). Apagado =
comportamiento anterior (armado en proceso), para reversión segura.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue as _queue
import shutil
import tempfile
import time
import traceback

MEM_MB = int(os.getenv("AUD_O2_MEM_MB", "0") or "0")        # tope de RSS por trabajo (0 = sin watchdog)
TIMEOUT_S = float(os.getenv("AUD_O2_TIMEOUT_S", "300") or "300")
_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


class GeneracionAislada(RuntimeError):
    """El armado del papel en el subproceso falló (error, OOM del trabajo o timeout)."""


def _rss_mb(pid: int) -> float:
    try:
        with open(f"/proc/{pid}/statm", "r") as f:
            return int(f.read().split()[1]) * _PAGE / 1048576.0
    except Exception:
        return 0.0


def computar_run_sin_db(definicion: dict, reg: dict):
    """Cálculo db-free del run del procesador: replica el subconjunto SIN base de datos de
    ``servicio._run_procesador`` (param + marco/edición + ejecutar + con_datos). Se usa cuando
    el procesador NO depende de la base (``USA_REGISTROS_ENCARGO`` falso: todas las pruebas
    NIIF salvo planificación), para poder correr TODO el pesado —cálculo incluido— en el hijo,
    recibiendo solo los datasets crudos del cliente (no las copias ya materializadas).

    IMPORTANTE: debe seguir reflejando la rama db-free de ``_run_procesador``. Si esa cambia,
    actualizar aquí (lo cubre ``AUD_O2_SUBPROCESO`` apagado como reversión)."""
    from backend.app.aud.niif import procesadores
    from backend.app.aud.niif.procesadores import datos_cliente
    proc = procesadores.de(definicion)
    param = {k: v for k, v in (reg.get("parameters") or {}).items() if k in proc.PARAMETROS}
    eng = reg.get("engagement") or {}
    param["_marco"] = eng.get("framework") or ""
    param["_edicion"] = str(eng.get("edition") or "")
    ds = reg.get("datasets") or {}
    run = proc.ejecutar(ds, param, eng.get("cutoff"))
    if "PYMES" in param["_marco"] and param["_edicion"] == "2025" and str(eng.get("cutoff")) < "2027-01-01":
        run["exceptions"] = [{"code": "PYMES_2025_ANTICIPADA", "amount": "0.00", "message":
            "La NIIF para las PYMES 2025 (3.ª edición) rige para períodos desde el 1-1-2027: con corte "
            f"{eng.get('cutoff')} solo procede si la entidad la adoptó anticipadamente y lo revela; "
            "de lo contrario use la edición 2015."}] + list(run.get("exceptions") or [])
    run["hojas"] = datos_cliente.con_datos(proc, run, ds)
    run["detalle"] = {k: v for k, v in run.get("detalle", {}).items() if k in ("tasas", "fiscal", "cortes")}
    return run


def _trabajo(spec, con_html, dir_salida, cola):
    """Corre en el HIJO: (opcional) calcula el run desde los datasets crudos y arma el libro,
    lo escribe a archivos y manda las rutas por la cola.

    ``spec`` es ``("args", args)`` (solo armado, el run ya viene en reg) o
    ``("completo", definicion, reg, eventos, version, estado)`` (cálculo + armado en el hijo)."""
    try:
        # Backend headless de matplotlib ANTES de importar libro. Bajo ``spawn`` el intérprete es
        # nuevo: el HTML incrusta Word/PowerPoint que renderizan gráficos con matplotlib, y sin un
        # backend no interactivo matplotlib intenta detectar un display y se CUELGA (verificado:
        # el hijo se colgaba en ``libro.html`` a escala). Forzar Agg lo evita.
        os.environ["MPLBACKEND"] = "Agg"
        try:
            import matplotlib
            matplotlib.use("Agg", force=True)
        except Exception:
            pass
        from backend.app.aud.niif.procesadores import libro
        if spec[0] == "completo":
            _m, definicion, reg, eventos, version, estado = spec
            try:
                run = computar_run_sin_db(definicion, reg)
            except Exception:  # noqa: BLE001 — la descarga no debe romperse por un re-cálculo
                run = reg.get("run")  # cae al resultado guardado (mismo criterio que _run_fresco)
                if not run:
                    raise
            reg = {**reg, "run": run}
            args = (definicion, reg, eventos, version, estado)
        else:
            args = spec[1]
        px = os.path.join(dir_salida, "papel.xlsx")
        with open(px, "wb") as f:
            f.write(libro.xlsx(*args))
        ph = ""
        if con_html:
            ph = os.path.join(dir_salida, "papel.html")
            h = libro.html(*args)
            with open(ph, "wb") as f:
                f.write(h if isinstance(h, (bytes, bytearray)) else str(h).encode("utf-8"))
        cola.put(("ok", px, ph))
    except MemoryError:
        cola.put(("mem", "", ""))
    except BaseException as e:  # noqa: BLE001
        cola.put(("err", f"{type(e).__name__}: {e}", traceback.format_exc()[-2000:]))


def generar_aislado(args, con_html: bool = True, mem_mb: int | None = None,
                    timeout_s: float | None = None) -> tuple[bytes, bytes]:
    """Arma ``libro.xlsx`` (+ ``libro.html``) en un subproceso aislado, con el ``run`` ya
    calculado dentro de ``args`` (el padre materializó los datos). Devuelve ``(xlsx, html)``."""
    return _ejecutar_hijo(("args", args), con_html, mem_mb, timeout_s)


def generar_aislado_completo(definicion: dict, reg: dict, eventos: list, version: int, estado: str,
                             con_html: bool = True, mem_mb: int | None = None,
                             timeout_s: float | None = None) -> tuple[bytes, bytes]:
    """Isolación COMPLETA: el hijo CALCULA el run desde los datasets crudos del cliente y arma
    el libro. El padre solo pasa ``reg`` crudo (entrada del cliente), así queda PLANO: todo el
    pico —cálculo, materialización y armado— vive y muere en el hijo. Solo para procesadores
    db-free (ver ``computar_run_sin_db``)."""
    return _ejecutar_hijo(("completo", definicion, reg, eventos, version, estado), con_html, mem_mb, timeout_s)


def _ejecutar_hijo(spec, con_html: bool, mem_mb: int | None, timeout_s: float | None) -> tuple[bytes, bytes]:
    mem_mb = MEM_MB if mem_mb is None else mem_mb
    timeout_s = TIMEOUT_S if timeout_s is None else timeout_s
    ctx = mp.get_context("spawn")
    cola = ctx.Queue()
    dir_salida = tempfile.mkdtemp(prefix="o2_papel_")
    hijo = ctx.Process(target=_trabajo, args=(spec, con_html, dir_salida, cola), daemon=True)
    hijo.start()
    limite = time.monotonic() + timeout_s
    pico = 0.0
    estado = None
    try:
        while True:
            try:
                estado = cola.get(timeout=0.2)   # drena activamente (desbloquea al hijo)
                break
            except _queue.Empty:
                pass
            if mem_mb:
                r = _rss_mb(hijo.pid)
                pico = max(pico, r)
                if r > mem_mb:
                    raise GeneracionAislada(f"El trabajo superó el tope de memoria ({r:.0f} MB > {mem_mb} MB).")
            if time.monotonic() > limite:
                raise GeneracionAislada(f"El armado del papel superó el tiempo máximo ({timeout_s:.0f}s).")
            if not hijo.is_alive():
                try:
                    estado = cola.get(timeout=2)
                    break
                except _queue.Empty:
                    raise GeneracionAislada(
                        f"El subproceso de armado terminó sin resultado (posible OOM del sistema; pico ~{pico:.0f} MB).")
        tipo, a, b = estado
        if tipo == "ok":
            with open(a, "rb") as f:
                xlsx = f.read()
            html = b""
            if b:
                with open(b, "rb") as f:
                    html = f.read()
            return xlsx, html
        if tipo == "mem":
            raise GeneracionAislada("El trabajo agotó la memoria asignada (MemoryError en el subproceso).")
        raise GeneracionAislada(a)
    finally:
        if hijo.is_alive():
            hijo.terminate()
        hijo.join(5)
        if hijo.is_alive():
            try:
                hijo.kill()
            except Exception:
                pass
            hijo.join(2)
        shutil.rmtree(dir_salida, ignore_errors=True)
