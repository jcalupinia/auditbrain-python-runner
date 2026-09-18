"""Mide cuánto tarda y cuánta memoria usa la lectura de un análisis de antigüedad real.

Uso:
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD>
    .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> \\
        --hoja MPE --fila-encabezado 5 \\
        --mapeo documento=0,cliente=1,emision=2,vencimiento=3,saldo=8

``--hoja``, ``--fila-encabezado`` y ``--mapeo`` son opcionales: sin ellos el script
usa la primera hoja y la detección automática de encabezado (el caso simple). Se
necesitan cuando el archivo real no trae un anexo limpio con encabezado en la
primera fila, que es el caso más pesado que hemos visto en producción.
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


def _parsear_mapeo(texto: str) -> dict[str, int]:
    """Convierte 'documento=0,cliente=1,...' en el dict de índices que espera leer_cartera."""
    return {campo: int(idx) for campo, idx in
            (par.split("=") for par in texto.split(",") if par)}


def _parsear_args(argv: list[str]) -> dict:
    if len(argv) < 3:
        raise SystemExit("Uso: bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD> "
                          "[--hoja NOMBRE] [--fila-encabezado N] [--mapeo campo=idx,...]")
    opts = {"ruta": argv[1], "corte": date.fromisoformat(argv[2]),
            "hoja": None, "fila_encabezado": None, "mapeo": None}
    resto = argv[3:]
    i = 0
    while i < len(resto):
        bandera = resto[i]
        valor = resto[i + 1]
        if bandera == "--hoja":
            opts["hoja"] = valor
        elif bandera == "--fila-encabezado":
            opts["fila_encabezado"] = int(valor)
        elif bandera == "--mapeo":
            opts["mapeo"] = _parsear_mapeo(valor)
        else:
            raise SystemExit(f"Argumento no reconocido: {bandera}")
        i += 2
    return opts


def _pico_memoria_mb() -> float:
    """Memoria maxima que ha ocupado el proceso, en MB.

    Se mide el pico del PROCESO y no con `tracemalloc`: seguir cada asignacion
    multiplica por diez el tiempo de la lectura y falsearia la medicion que es
    el objeto de este script. Ademas, lo que hace caer el servicio por falta de
    memoria es la huella real del proceso, no la suma de los objetos de Python.
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


opts = _parsear_args(sys.argv)
contenido = open(opts["ruta"], "rb").read()
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
