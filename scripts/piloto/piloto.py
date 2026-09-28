"""CLI del agente guía «NIIF Piloto» (skill .claude/skills/niif-piloto).

Envoltorio de línea de comandos sobre el servicio ``backend.app.aud.niif.piloto``,
que es la ÚNICA fuente de verdad (el mismo servicio que consume el router HTTP de la
plataforma, ``piloto_router``). La CLU solo lee/escribe archivos; el catálogo, los
requisitos, el cálculo, el armado del papel y la verificación del Excel viven en el
servicio, que a su vez reutiliza el contrato oficial de ``backend/app/aud/niif``.

Un solo motor para TODAS las pruebas NIIF (las 20 del catálogo + la planificación NIA):
no hay un agente por prueba. El cálculo NUNCA usa LLM.

Subcomandos:
  listar                          Todas las pruebas disponibles.
  requisitos <id>                 Qué datos necesita una prueba.
  plantilla  <id> <carpeta>       Escribe el ejemplo como CSV+JSON para llenar.
  ejemplo    <id> <carpeta>       Ejecuta con el ejemplo del manifiesto (demo/verificación).
  ejecutar   <id> <salida> (--datos datos.json | --carpeta carpeta_plantilla)
                                  Ejecuta con los datos reales y arma los papeles verificando el Excel.

Uso desde la raíz del repo:
  python scripts/piloto/piloto.py listar
  python scripts/piloto/piloto.py plantilla arrendamientos /tmp/arr
  python scripts/piloto/piloto.py ejecutar arrendamientos /tmp/salida --carpeta /tmp/arr
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

# La raíz del repo, para importar backend.* sin instalar el paquete.
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from backend.app.aud.niif import piloto  # noqa: E402


def _salir(mensaje: str, codigo: int = 2):
    print(json.dumps({"ok": False, "error": mensaje}, ensure_ascii=False, indent=2))
    sys.exit(codigo)


def _columnas(pid: str) -> dict:
    """{dataset: [claves de columna en orden]} desde los requisitos de la prueba."""
    return {ds["dataset"]: [c["key"] for c in ds["campos"]] for ds in piloto.requisitos(pid)["datasets"]}


# --------------------------------------------------------------------------- listar
def cmd_listar(args):
    filas = piloto.listar()
    if args.json:
        print(json.dumps({"ok": True, "pruebas": filas}, ensure_ascii=False, indent=2))
        return
    print(f"\n{len(filas)} pruebas NIIF disponibles (el orden es la matriz del socio):\n")
    for f in filas:
        rubro = f["rubro"] or "(sin rubro de catálogo)"
        marca = "✓ ejemplo" if f["tiene_ejemplo"] else "sin ejemplo"
        print(f"  • {f['id']:<26} [{rubro:<20}] {f['nombre']}  — {marca}")
    print("\nUsá:  requisitos <id>   para ver qué datos pide cada prueba.\n")


# ----------------------------------------------------------------------- requisitos
def cmd_requisitos(args):
    try:
        r = piloto.requisitos(args.id)
    except piloto.PruebaDesconocida as e:
        _salir(str(e))
    if args.json:
        print(json.dumps({"ok": True, **r}, ensure_ascii=False, indent=2))
        return
    print(f"\n=== {r['nombre']} ({args.id}) ===")
    print(f"Marcos: {', '.join(r['marcos'])}\n")
    print(r["resumen"], "\n")
    for ds in r["datasets"]:
        estrella = " (PRINCIPAL: población a recalcular)" if ds["es_principal"] else ""
        print(f"— Anexo «{ds['dataset']}»{estrella}: una fila por registro, columnas:")
        for c in ds["campos"]:
            req = "obligatorio" if c["requerido"] else "opcional"
            ej = f"  ej: {c['ejemplo']}" if c["ejemplo"] is not None else ""
            print(f"     · {c['key']:<20} {c['label']}  [{c['tipo']}, {req}]{ej}")
    if r["parametros_por_defecto"]:
        print("\n— Parámetros del auditor (con valor por defecto; ajustá solo lo que aplique):")
        for k, v in r["parametros_por_defecto"].items():
            print(f"     · {k} = {v!r}")
    print("\n— Requerimientos formales al cliente (NIA 500):")
    for req in r["requerimientos_al_cliente"]:
        marca = "obligatorio" if req["requerido"] else "opcional"
        print(f"     · {req['id']} [{marca}] {req['documento']}")
    print("\nGenerá el molde con:  plantilla", args.id, "<carpeta>\n")


# ------------------------------------------------------------------------ plantilla
def cmd_plantilla(args):
    try:
        molde = piloto.plantilla(args.id)
    except piloto.PruebaDesconocida as e:
        _salir(str(e))
    if molde is None:
        _salir(f"La prueba «{args.id}» no trae ejemplo; cargá los datos a mano según 'requisitos'.")
    columnas = _columnas(args.id)
    os.makedirs(args.carpeta, exist_ok=True)
    escritos = []
    for ds, filas in molde["datasets"].items():
        cols = columnas.get(ds) or (list(filas[0].keys()) if filas else [])
        ruta = os.path.join(args.carpeta, f"{ds}.csv")
        with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for fila in filas:
                w.writerow({c: fila.get(c, "") for c in cols})
        escritos.append({"archivo": os.path.basename(ruta), "dataset": ds, "filas": len(filas), "columnas": cols})
    with open(os.path.join(args.carpeta, "parametros.json"), "w", encoding="utf-8") as fh:
        json.dump(molde["parametros"], fh, ensure_ascii=False, indent=2)
    with open(os.path.join(args.carpeta, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": args.id, "corte": molde["corte"]}, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "id": args.id, "carpeta": args.carpeta, "corte": molde["corte"], "csv": escritos,
                      "aviso": ("Son los datos del EJEMPLO ficticio. Reemplazalos por los del cliente conservando "
                                f"columnas y nombres de archivo. Luego: ejecutar {args.id} <salida> --carpeta {args.carpeta}")},
                     ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- lectura de datos
def _leer_carpeta(carpeta: str, pid: str) -> tuple[dict, dict, str]:
    meta_p = os.path.join(carpeta, "meta.json")
    if not os.path.exists(meta_p):
        _salir(f"Falta {meta_p}. Generá la carpeta con 'plantilla' primero.")
    meta = json.load(open(meta_p, encoding="utf-8"))
    param = {}
    param_p = os.path.join(carpeta, "parametros.json")
    if os.path.exists(param_p):
        param = json.load(open(param_p, encoding="utf-8"))
    datasets = {}
    for ds in _columnas(pid):
        ruta = os.path.join(carpeta, f"{ds}.csv")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8-sig", newline="") as fh:
                datasets[ds] = [dict(r) for r in csv.DictReader(fh)]
    return datasets, param, meta.get("corte")


def _leer_json(ruta: str) -> tuple[dict, dict, str]:
    obj = json.load(open(ruta, encoding="utf-8"))
    return obj.get("datasets", {}), obj.get("parametros", {}), obj.get("corte")


# ------------------------------------------------------------------- armar papeles
def _armar(pid: str, d, reg, salida: str, base: str) -> dict:
    os.makedirs(salida, exist_ok=True)
    hechos, errores, xlsx_bytes = [], [], None
    pdf_no_disp = getattr(piloto.libro, "PDFNoDisponible", None)
    for ext, _fn, etq, _mime in piloto.FORMATOS:
        try:
            contenido = piloto.papel(d, reg, ext)
        except Exception as exc:  # noqa: BLE001 — se reporta, no se oculta
            if pdf_no_disp is not None and isinstance(exc, pdf_no_disp):
                errores.append({"formato": ext, "motivo": "PDF no disponible en este entorno (falta WeasyPrint); "
                                                          "se obtiene con «Guardar como PDF» del navegador desde el HTML"})
            else:
                errores.append({"formato": ext, "motivo": f"{type(exc).__name__}: {exc}"})
            continue
        with open(os.path.join(salida, f"{base}.{ext}"), "wb") as fh:
            fh.write(contenido)
        if ext == "xlsx":
            xlsx_bytes = contenido
        hechos.append({"formato": ext, "etiqueta": etq, "archivo": f"{base}.{ext}", "bytes": len(contenido)})
    verificacion = piloto.verificar_excel(xlsx_bytes) if xlsx_bytes else {"reabre": False}
    return {"papeles": hechos, "errores": errores, "verificacion_excel": verificacion,
            "resultado": piloto.resumen_run(reg)}


def cmd_ejemplo(args):
    from backend.app.aud.niif import ejercicio_modelo, procesadores
    try:
        mod = procesadores.PROCESADORES[args.id]
    except KeyError:
        _salir(f"Prueba desconocida: «{args.id}».")
    esc = ejercicio_modelo.escenario(mod)
    if esc is None:
        _salir(f"La prueba «{args.id}» no trae ejemplo de manifiesto.")
    datasets, param, corte = esc
    d, reg = piloto.preparar(args.id, datasets, param, corte)
    out = _armar(args.id, d, reg, args.carpeta, f"{args.id}__ejemplo")
    print(json.dumps({"ok": bool(out["papeles"]) and out["verificacion_excel"].get("reabre"),
                      "id": args.id, "corte": corte, "modo": "ejemplo ficticio del manifiesto", **out},
                     ensure_ascii=False, indent=2))


def cmd_ejecutar(args):
    if bool(args.datos) == bool(args.carpeta):
        _salir("Indicá exactamente uno: --datos <datos.json>  o  --carpeta <carpeta_plantilla>.")
    try:
        datasets, param, corte = _leer_json(args.datos) if args.datos else _leer_carpeta(args.carpeta, args.id)
    except piloto.PruebaDesconocida as e:
        _salir(str(e))
    if not corte:
        _salir("Falta la fecha de corte (meta.json 'corte' o clave 'corte' del JSON).")
    try:
        d, reg = piloto.preparar(args.id, datasets, param, corte)
    except piloto.PruebaDesconocida as e:
        _salir(str(e))
    except Exception as exc:  # noqa: BLE001
        _salir(f"El procesador no pudo calcular: {type(exc).__name__}: {exc}", codigo=1)
    out = _armar(args.id, d, reg, args.carpeta_salida, f"{args.id}__cliente")
    print(json.dumps({"ok": bool(out["papeles"]) and out["verificacion_excel"].get("reabre"),
                      "id": args.id, "corte": corte, "modo": "datos del cliente", **out},
                     ensure_ascii=False, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description="CLI del agente guía NIIF Piloto (sobre el servicio backend.app.aud.niif.piloto).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("listar", help="Todas las pruebas disponibles.")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_listar)

    s = sub.add_parser("requisitos", help="Qué datos necesita una prueba.")
    s.add_argument("id")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_requisitos)

    s = sub.add_parser("plantilla", help="Escribe el ejemplo como CSV+JSON para llenar.")
    s.add_argument("id")
    s.add_argument("carpeta")
    s.set_defaults(func=cmd_plantilla)

    s = sub.add_parser("ejemplo", help="Ejecuta con el ejemplo del manifiesto (demo/verificación).")
    s.add_argument("id")
    s.add_argument("carpeta")
    s.set_defaults(func=cmd_ejemplo)

    s = sub.add_parser("ejecutar", help="Ejecuta con datos reales y arma los papeles.")
    s.add_argument("id")
    s.add_argument("carpeta_salida")
    s.add_argument("--datos", help="Ruta a datos.json {corte, parametros, datasets}.")
    s.add_argument("--carpeta", help="Carpeta con <dataset>.csv + parametros.json + meta.json (de 'plantilla').")
    s.set_defaults(func=cmd_ejecutar)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
