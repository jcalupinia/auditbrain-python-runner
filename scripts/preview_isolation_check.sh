#!/usr/bin/env sh
# Verificación de AISLAMIENTO de un preview respecto a producción (se ejecuta DENTRO del contenedor
# del backend del preview; solo intenta abrir conexiones TCP y espera que fallen). No modifica nada.
#
# Uso (en el servidor, durante el piloto P-07/P-08):
#   docker exec <backend-preview> sh /app/scripts/preview_isolation_check.sh
# Objetivos configurables con PREVIEW_ISOLATION_TARGETS="host:puerto,host:puerto" (sin credenciales).
# Veredicto: AISLADO si NINGÚN objetivo acepta conexión; EXPUESTO si alguno la acepta.
set -u
TARGETS="${PREVIEW_ISOLATION_TARGETS:-z4wy8ngriiesg6z20n7ftcnj:5432,api.audit-ia.ec:443,consola.audit-ia.ec:443,clientes.audit-ia.ec:443}"
echo "== preview_isolation_check $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
echo "APP_ENV=${APP_ENV:-?}  PREVIEW_PUBLIC_HOST=${PREVIEW_PUBLIC_HOST:-?}"
echo "DATABASE_URL host: $(python - <<'EOF'
import os; from urllib.parse import urlsplit
print(urlsplit(os.environ.get("DATABASE_URL","")).hostname)
EOF
)"
python - "$TARGETS" <<'EOF'
import socket, sys
expuestos = []
for t in sys.argv[1].split(","):
    t = t.strip()
    if not t: continue
    host, _, port = t.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            print(f"  {t:45s} CONEXIÓN ACEPTADA  <-- EXPUESTO")
            expuestos.append(t)
    except OSError as e:
        print(f"  {t:45s} rechazada/sin ruta ({e.__class__.__name__})")
print("VEREDICTO:", "AISLADO" if not expuestos else f"EXPUESTO hacia {expuestos}")
sys.exit(0 if not expuestos else 1)
EOF
