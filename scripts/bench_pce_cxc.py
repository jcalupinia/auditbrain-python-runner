"""Mide cuánto tarda y cuánta memoria usa la lectura de un análisis de antigüedad real.

Uso (lectura de UN archivo):
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD>
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> \\
        --hoja MPE --fila-encabezado 5 \\
        --mapeo documento=0,cliente=1,emision=2,vencimiento=3,saldo=8

``--hoja``, ``--fila-encabezado`` y ``--mapeo`` son opcionales: sin ellos el script
usa la primera hoja y la detección automática de encabezado (el caso simple). Se
necesitan cuando el archivo real no trae un anexo limpio con encabezado en la
primera fila, que es el caso más pesado que hemos visto en producción.

Uso (``--tres``, la PETICIÓN COMPLETA del endpoint):
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> --tres
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> --tres \\
        --hoja MPE --mapeo documento=0,cliente=1,emision=2,vencimiento=3,saldo=8 \\
        --fechas 2023-12-31,2024-12-31,2025-12-31

``--tres`` es el escenario que fija ``MAX_BYTES_POR_ARCHIVO`` en el router: no la
lectura de un archivo, sino los TRES cortes de una petición real, que
``backend/app/aud/pce_cxc/service.py`` mantiene los tres en memoria a la vez.
Usa el mismo archivo como los tres cortes y llama a
``backend.app.aud.pce_cxc.service.analizar`` (la misma función que invoca el
router) con parámetros mínimos, tal como llega desde ``POST /analizar``. Sin
``--fechas`` usa 2023-12-31 / 2024-12-31 / 2025-12-31; con ``--fechas`` se
reproduce cualquier otro juego de fechas recibido. ``--fila-encabezado`` no
aplica a ``--tres``: el servicio real (``service.analizar``, el mismo que llama
el router) no lo admite, solo ``hoja`` y ``mapeo`` viajan en la petición.
"""
import sys
import time
from datetime import date
from pathlib import Path

# El script se invoca como `python scripts/bench_pce_cxc.py`, asi que sys.path[0]
# es `scripts/` y no la raiz del repositorio: sin esto no se ve el paquete backend.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar  # noqa: E402
from backend.app.aud.pce_cxc.lectura import leer_cartera  # noqa: E402

USO = ("Uso: bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> "
       "[--hoja NOMBRE] [--fila-encabezado N] [--mapeo campo=idx,...] "
       "[--tres] [--fechas AAAA-MM-DD,AAAA-MM-DD,AAAA-MM-DD]")

#: Fechas por defecto de los tres cortes en modo `--tres`: las mismas con las
#: que se midió la tabla de la petición completa citada en el comentario de
#: `MAX_BYTES_POR_ARCHIVO` (backend/app/aud/pce_cxc/router.py).
FECHAS_POR_DEFECTO_TRES = (date(2023, 12, 31), date(2024, 12, 31), date(2025, 12, 31))


def _parsear_mapeo(texto: str) -> dict[str, int]:
    """Convierte 'documento=0,cliente=1,...' en el dict de índices que espera leer_cartera."""
    return {campo: int(idx) for campo, idx in
            (par.split("=") for par in texto.split(",") if par)}


def _parsear_fechas(texto: str) -> tuple[date, date, date]:
    """Convierte 'AAAA-MM-DD,AAAA-MM-DD,AAAA-MM-DD' en las tres fechas de los cortes."""
    partes = [p.strip() for p in texto.split(",") if p.strip()]
    if len(partes) != 3:
        raise SystemExit(f"--fechas necesita exactamente tres fechas separadas por coma.\n{USO}")
    fecha_a, fecha_b, fecha_c = (date.fromisoformat(p) for p in partes)
    return fecha_a, fecha_b, fecha_c


def _parsear_args(argv: list[str]) -> dict:
    if len(argv) < 3:
        raise SystemExit(USO)
    opts = {"ruta": argv[1], "corte": date.fromisoformat(argv[2]),
            "hoja": None, "fila_encabezado": None, "mapeo": None,
            "tres": False, "fechas": None}
    resto = argv[3:]
    i = 0
    while i < len(resto):
        bandera = resto[i]
        if bandera == "--tres":
            opts["tres"] = True
            i += 1
            continue
        # Toda bandera restante necesita un valor: sin este chequeo, una bandera
        # al final de la línea de comandos (p. ej. "--hoja" sin nombre) revienta
        # con un IndexError crudo en vez de explicar cómo se usa el script.
        if i + 1 >= len(resto):
            raise SystemExit(f"Falta el valor de {bandera}.\n{USO}")
        valor = resto[i + 1]
        if bandera == "--hoja":
            opts["hoja"] = valor
        elif bandera == "--fila-encabezado":
            opts["fila_encabezado"] = int(valor)
        elif bandera == "--mapeo":
            opts["mapeo"] = _parsear_mapeo(valor)
        elif bandera == "--fechas":
            opts["fechas"] = _parsear_fechas(valor)
        else:
            raise SystemExit(f"Argumento no reconocido: {bandera}\n{USO}")
        i += 2
    if opts["tres"] and opts["fila_encabezado"] is not None:
        raise SystemExit("--fila-encabezado no aplica con --tres: el servicio real "
                          "(service.analizar, el mismo que llama el router) no admite ese "
                          "parámetro; solo hoja y mapeo viajan en la petición real.")
    return opts


def _pico_memoria_mb() -> float:
    """Memoria maxima que ha ocupado el proceso, en MB.

    Se mide el pico del PROCESO y no con `tracemalloc`: seguir cada asignacion
    multiplica por diez el tiempo de la lectura y falsearia la medicion que es
    el objeto de este script. Ademas, `tracemalloc` solo contabiliza las
    asignaciones que hace Python, no la memoria nativa que reservan openpyxl y
    sus dependencias (el parser XML de la librería estándar, la descompresión
    del .zip del .xlsx, etc.), así que además de lento habria subestimado el
    pico real. Lo que tumba el proceso en produccion es la huella real de
    memoria, no la suma de los objetos de Python.
    """
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class _Contadores(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        # Hay que declarar los tipos: sin `restype` el manejador del proceso
        # (-1) se trunca a entero de 32 bits y la llamada devuelve ceros.
        proceso = ctypes.windll.kernel32.GetCurrentProcess
        proceso.restype = wintypes.HANDLE
        consultar = ctypes.windll.psapi.GetProcessMemoryInfo
        consultar.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Contadores), wintypes.DWORD]
        consultar.restype = wintypes.BOOL
        c = _Contadores()
        c.cb = ctypes.sizeof(_Contadores)
        if not consultar(proceso(), ctypes.byref(c), c.cb):
            raise OSError("no se pudo leer la memoria del proceso")
        return c.PeakWorkingSetSize / 1024 / 1024
    import resource  # Linux (lo que corre en el servidor): ru_maxrss viene en KB
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _medir_un_archivo(opts: dict, contenido: bytes) -> None:
    bandas = desdoblar(BANDAS_POR_DEFECTO, 730)

    inicio = time.perf_counter()
    r = leer_cartera(contenido, opts["ruta"], opts["corte"], bandas, hoja=opts["hoja"],
                     mapeo=opts["mapeo"], fila_encabezado=opts["fila_encabezado"])
    segundos = time.perf_counter() - inicio
    pico = _pico_memoria_mb()

    print(f"archivo      : {opts['ruta']} ({len(contenido) / 1024 / 1024:.1f} MB)")
    print(f"hoja         : {r['hoja']} (encabezado en fila {r['fila_encabezado']})")
    print(f"documentos   : {len(r['filas']):,}")
    print(f"descartados  : {len(r['descartados']):,}")
    motivos: dict[str, int] = {}
    for d in r["descartados"]:
        motivos[d["motivo"]] = motivos.get(d["motivo"], 0) + 1
    for motivo, cuantos in sorted(motivos.items(), key=lambda kv: -kv[1]):
        print(f"  - {motivo}: {cuantos:,}")
    print(f"saldo total  : {r['total_saldo']:,.2f}")
    print(f"tiempo       : {segundos:.1f} s")
    print(f"memoria pico : {pico:.0f} MB (pico del proceso)")


def _medir_tres(opts: dict) -> None:
    # Import diferido: solo hace falta para --tres, y evita cargar toda la
    # cadena de dependencias del servicio (motor, cohortes, exporter...) cuando
    # se mide la lectura de un solo archivo.
    from backend.app.aud.pce_cxc import service  # noqa: E402

    fechas = opts["fechas"] or FECHAS_POR_DEFECTO_TRES
    # OJO: cada corte necesita su PROPIA copia de los bytes en memoria, no el
    # mismo objeto `contenido` repetido tres veces. El endpoint real hace
    # `contenido = await archivo.read(...)` DENTRO del bucle, una vez por
    # archivo: son tres lecturas independientes, cada una con su propio buffer
    # en RAM. Si aquí se reutilizara la misma variable `contenido` en las tres
    # entradas de `cortes` (o incluso `bytes(contenido)` o `contenido[:]`, que
    # para un `bytes` no copian: devuelven el mismo objeto por identidad, ya
    # que `bytes` es inmutable y CPython aprovecha eso para no duplicar), el
    # pico medido subestimaría el real en, aproximadamente, dos archivos de
    # menos. Releer el archivo del disco tres veces reproduce fielmente esa
    # memoria: tres objetos `bytes` distintos, los tres vivos a la vez mientras
    # `service.analizar` procesa la petición completa.
    cortes = [{"nombre": f"{opts['ruta']} (corte {i + 1}/3)",
               "contenido": open(opts["ruta"], "rb").read(),
               "fecha": fecha, "hoja": opts["hoja"], "mapeo": opts["mapeo"]}
              for i, fecha in enumerate(fechas)]
    assert len({id(c["contenido"]) for c in cortes}) == 3, \
        "los tres cortes deben ser objetos bytes independientes, no el mismo buffer reutilizado"

    tam_mb = len(cortes[0]["contenido"]) / 1024 / 1024
    inicio = time.perf_counter()
    r = service.analizar(cortes, {})
    segundos = time.perf_counter() - inicio
    pico = _pico_memoria_mb()

    documentos = sum(c["documentos"] for c in r["bitacora"]["cortes"])
    print(f"archivo      : {opts['ruta']} ({tam_mb:.1f} MB c/u, x3 cortes, x3 lecturas independientes)")
    print(f"fechas       : {', '.join(f.isoformat() for f in fechas)}")
    print(f"documentos   : {documentos:,} (suma de los tres cortes)")
    print(f"ecl_total    : {r['ecl_total']:,.2f}")
    print(f"tiempo       : {segundos:.1f} s")
    print(f"memoria pico : {pico:.0f} MB (pico del proceso, PETICIÓN COMPLETA con los tres cortes)")


opts = _parsear_args(sys.argv)

if opts["tres"]:
    # Cada corte hace su propia lectura del disco (ver el comentario dentro de
    # `_medir_tres`): no hay un `contenido` compartido que leer aquí primero.
    _medir_tres(opts)
else:
    contenido = open(opts["ruta"], "rb").read()
    _medir_un_archivo(opts, contenido)
