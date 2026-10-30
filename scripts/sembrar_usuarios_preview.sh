#!/usr/bin/env bash
# =============================================================================
# sembrar_usuarios_preview.sh — Script de administración para sembrar las
# cuentas de prueba (admin real + 8 operadores) de un PREVIEW en Hetzner/Coolify.
#
# Se ejecuta EN EL HOST (usa `docker exec` contra el backend del preview). El
# código real del seeder vive dentro del contenedor; este script solo orquesta
# y aplica guardas fail-closed.
#
# NO contiene correos ni secretos. Los correos viven en identidades.json dentro
# del volumen aislado del PR; la contraseña de Postgres se lee de /run/secrets
# dentro del contenedor y NUNCA se imprime.
#
# Uso:
#   sembrar_usuarios_preview.sh <contenedor_backend> <pr> verificar
#   sembrar_usuarios_preview.sh <contenedor_backend> <pr> sembrar
#   sembrar_usuarios_preview.sh <contenedor_backend> <pr> credenciales --si-mostrar
#
#   verificar     (por defecto) Solo lectura: guarda de identidad/BD + validación
#                 de identidades.json. NO siembra, NO escribe nada.
#   sembrar       Guarda + validación + ejecuta el seeder + verifica las 9 cuentas.
#                 NO muestra contraseñas.
#   credenciales  Operación SEPARADA y EXPLÍCITA: imprime en la terminal los 9
#                 pares correo→clave (requiere el flag --si-mostrar).
#
# Garantías (fail-closed): antes de cualquier siembra exige, en el MISMO proceso,
#   APP_ENV=preview  Y  driver=postgresql  Y  host=db  Y  preview_pr_number()==<pr>.
# Si algo no cuadra, aborta sin tocar nada. Nunca conecta a producción: el host
# `db` dentro del contenedor del PR resuelve, por la red interna aislada del
# preview, al Postgres EXCLUSIVO de ese PR.
#
# NO usa `set -x` a propósito (expondría la contraseña al construir DATABASE_URL).
# =============================================================================
set -euo pipefail

if [ "${TRACE:-}" = "1" ]; then echo "ABORTA: TRACE/-x está prohibido (expondría secretos)." >&2; exit 10; fi

CONTAINER="${1:-}"
PR="${2:-}"
ACCION="${3:-verificar}"
FLAG="${4:-}"

uso() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
}
[ -n "$CONTAINER" ] && [ -n "$PR" ] || uso
case "$PR" in (*[!0-9]*|'') echo "ABORTA: <pr> debe ser numérico." >&2; exit 64;; esac

# --- 1. Contenedor existe y está corriendo ----------------------------------
estado="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || true)"
if [ "$estado" != "true" ]; then
  echo "ABORTA: el contenedor '$CONTAINER' no existe o no está corriendo." >&2
  exit 1
fi

# run_py <programa-python> [argv...] : ejecuta python DENTRO del contenedor con
# DATABASE_URL reconstruida desde /run/secrets/pg_password (nunca impresa).
run_py() {
  local prog="$1"; shift
  printf '%s' "$prog" | docker exec -i "$CONTAINER" sh -c '
    set -eu
    [ -s /run/secrets/pg_password ] || { echo "ABORTA: falta /run/secrets/pg_password en el contenedor" >&2; exit 9; }
    export DATABASE_URL="postgresql://auditbrain:$(cat /run/secrets/pg_password)@db:5432/auditbrain"
    exec python /dev/stdin "$@"
  ' sh "$@"
}

# run_py_nodb <programa-python> [argv...] : python sin DATABASE_URL (solo lee
# archivos del volumen; no toca la base).
run_py_nodb() {
  local prog="$1"; shift
  printf '%s' "$prog" | docker exec -i "$CONTAINER" python /dev/stdin "$@"
}

# --- 2. Guarda de identidad + BD (solo lectura; no conecta, no crea tablas) --
GUARDA_PY='
import sys
from backend.app.core import preview
from backend.app.db.session import engine
pr_esperado = sys.argv[1]
u = engine.url
errs = []
if not preview.is_preview():
    errs.append("APP_ENV != preview")
if not u.drivername.startswith("postgresql"):
    errs.append("driver no es postgresql (es %s)" % u.drivername)
if (u.host or "") != "db":
    errs.append("host no es el db interno (es %r)" % u.host)
pr = None
try:
    pr = preview.preview_pr_number()
except Exception as e:
    errs.append("identidad de preview invalida: %s" % type(e).__name__)
if pr != pr_esperado:
    errs.append("pr del preview %r != esperado %r" % (pr, pr_esperado))
if errs:
    print("GUARDA FALLO:")
    for e in errs:
        print("  -", e)
    sys.exit(2)
print("GUARDA OK: driver=%s host=%s pr=%s app_env=preview" % (u.drivername, u.host, pr))
'

# --- 3. Validación de identidades.json (forma, sin mostrar correos) ----------
IDENT_PY='
import json, os, sys
p = "/var/data/preview-seed/identidades.json"
n_ops_esperado = 8
try:
    st = os.stat(p)
except FileNotFoundError:
    print("identidades.json NO EXISTE:", p); sys.exit(3)
perm = st.st_mode & 0o777
try:
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
except json.JSONDecodeError as e:
    print("JSON INVALIDO: %s (linea %d, col %d)" % (e.msg, e.lineno, e.colno)); sys.exit(3)
except Exception as e:
    print("ILEGIBLE:", type(e).__name__); sys.exit(3)
errs = []
if not isinstance(d, dict):
    errs.append("no es un objeto JSON")
adm = d.get("admin") if isinstance(d, dict) else None
ops = d.get("operators") if isinstance(d, dict) else None
if not (isinstance(adm, str) and adm.strip()):
    errs.append("admin ausente o vacio")
if not isinstance(ops, list):
    errs.append("operators no es una lista")
elif len(ops) != n_ops_esperado:
    errs.append("operators tiene %d (se esperan %d)" % (len(ops), n_ops_esperado))
elif not all(isinstance(x, str) and x.strip() for x in ops):
    errs.append("algun operator vacio o no-string")
print("archivo: tamano=%d bytes permisos=%o admin_no_vacio=%s n_operators=%s" % (
    st.st_size, perm, bool(isinstance(adm, str) and adm.strip()),
    len(ops) if isinstance(ops, list) else "N/A"))
if perm != 0o600:
    print("AVISO: permisos no son 600 (son %o) -- usa el reemplazo atomico para corregir" % perm)
if errs:
    print("IDENTIDADES INVALIDAS:")
    for e in errs:
        print("  -", e)
    sys.exit(3)
print("IDENTIDADES OK (admin + %d operadores)" % n_ops_esperado)
'

# --- 5. Siembra + comprobación de las 9 cuentas (guarda re-aplicada) ---------
SEED_PY='
import sys
from backend.app.core import preview
from backend.app.db.session import engine, SessionLocal
pr_esperado = sys.argv[1]
u = engine.url
if not (preview.is_preview() and u.drivername.startswith("postgresql") and (u.host or "") == "db"):
    sys.exit("ABORTA: guarda de preview/Postgres fallo justo antes de sembrar")
try:
    if preview.preview_pr_number() != pr_esperado:
        sys.exit("ABORTA: pr del preview != %s" % pr_esperado)
except Exception:
    sys.exit("ABORTA: identidad de preview invalida")

from backend.app.core import preview_seed
from backend.app.auth import service as auth_service
from backend.app.auth.models import Role

resumen = preview_seed.seed_preview_users(SessionLocal())
print("RESUMEN SEEDER:", resumen)
if resumen.get("skipped", True):
    sys.exit("ABORTA: el seeder se salto (no es preview?)")
if resumen.get("admin") not in ("seeded", "exists"):
    sys.exit("ABORTA: admin no quedo configurado (%s)" % resumen.get("admin"))
if resumen.get("operadores_fallidos", 1) != 0:
    sys.exit("ABORTA: hubo operadores fallidos (%s)" % resumen.get("operadores_fallidos"))

# Comprobacion contra la BD: 1 admin + 8 operadores ACTIVOS = 9 (sin imprimir correos)
ident = preview_seed._load_identities()
correos = ([ident["admin"]] if ident["admin"] else []) + list(ident["operators"])
s = SessionLocal()
admins = users = 0
for c in correos:
    usr = auth_service.get_user_by_email(s, c)
    if usr and usr.is_active:
        if usr.role == Role.admin:
            admins += 1
        elif usr.role == Role.user:
            users += 1
s.close()
print("CUENTAS ACTIVAS: admin=%d user=%d total=%d" % (admins, users, admins + users))
if not (admins == 1 and users == 8):
    sys.exit("ABORTA: no hay 9 cuentas activas (se esperaba 1 admin + 8 user)")
print("SEEDER OK: 9 cuentas (1 admin + 8 operadores) y el resumen coincide")
'

echo ">>> [1/3] Guarda de identidad y conexion (solo lectura)…"
run_py "$GUARDA_PY" "$PR"
echo ">>> [2/3] Validacion de identidades.json (sin mostrar correos)…"
run_py_nodb "$IDENT_PY"

case "$ACCION" in
  verificar)
    echo ">>> [3/3] Modo VERIFICAR: todo OK. NO se sembro nada."
    echo "    Para sembrar:    $0 \"$CONTAINER\" \"$PR\" sembrar"
    ;;
  sembrar)
    echo ">>> [3/3] Sembrando y verificando las 9 cuentas (sin mostrar contrasenas)…"
    run_py "$SEED_PY" "$PR"
    echo ">>> Verificador read-only (debe decir 'DIFERENCIAS: 0')…"
    docker exec -i "$CONTAINER" sh -c '
      set -eu
      [ -s /run/secrets/pg_password ] || { echo "ABORTA: falta pg_password" >&2; exit 9; }
      export DATABASE_URL="postgresql://auditbrain:$(cat /run/secrets/pg_password)@db:5432/auditbrain"
      exec python scripts/verificar_usuarios_preview.py'
    echo ">>> LISTO. Cuentas sembradas y verificadas."
    echo "    Para obtener las 9 contrasenas (operacion separada y explicita):"
    echo "       $0 \"$CONTAINER\" \"$PR\" credenciales --si-mostrar"
    ;;
  credenciales)
    if [ "$FLAG" != "--si-mostrar" ]; then
      echo "ABORTA: 'credenciales' imprime datos SENSIBLES en pantalla." >&2
      echo "Reejecuta con el flag explicito:  $0 \"$CONTAINER\" \"$PR\" credenciales --si-mostrar" >&2
      exit 64
    fi
    echo "########################################################################"
    echo "#  SENSIBLE: a continuacion se imprimen 9 pares correo -> contrasena.   #"
    echo "#  No lo guardes en un archivo ni lo pegues en Git/GitHub/logs.         #"
    echo "#  Repartelas por canal privado y cierra la terminal al terminar.       #"
    echo "########################################################################"
    docker exec -i "$CONTAINER" python scripts/recuperar_clave_preview.py --listar
    echo "---- Fin. Confirma visualmente que las 9 claves son DISTINTAS. ----"
    ;;
  *)
    echo "ABORTA: accion desconocida '$ACCION' (usa: verificar | sembrar | credenciales)" >&2
    exit 64
    ;;
esac
