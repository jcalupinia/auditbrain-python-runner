#!/usr/bin/env bash
# Validación visual LOCAL (sin Render, sin red externa salvo el browser).
# Levanta: stub documental + backend + frontend (vite preview) y corre Playwright.
#
# Prerrequisitos:
#   - Chromium de Playwright instalado (npm run install-browser en e2e/)
#   - venv con requirements-prod.txt instalado, exportado como PYBIN
#       export PYBIN=/ruta/al/python   (por defecto: python3)
#
# Uso:   cd e2e && bash run-local.sh
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
PYBIN="${PYBIN:-python3}"
BACKEND_PORT=8096
STUB_PORT=8099
WEB_PORT=4173
ORIGIN="http://127.0.0.1:${WEB_PORT}"

mkdir -p screenshots
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -f "$ROOT/e2e_local.db"; }
trap cleanup EXIT

echo "==> 1/5 stub documental :$STUB_PORT"
"$PYBIN" doc_stub.py "$STUB_PORT" & PIDS+=($!)

echo "==> 2/5 backend :$BACKEND_PORT"
cd "$ROOT"
DATABASE_URL="sqlite:///$ROOT/e2e_local.db" \
AUDITBRAIN_API_KEY="e2e-gpt-key" \
AUDITBRAIN_JWT_SECRET="e2e-secret" \
AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL="admin@example.com" \
AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD="Sup3rSecret!" \
DOCUMENT_SERVICE="http://127.0.0.1:${STUB_PORT}" \
CORS_ALLOW_ORIGINS="$ORIGIN" \
"$PYBIN" -m uvicorn app:app --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning & PIDS+=($!)
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$BACKEND_PORT/" >/dev/null 2>&1 && break; sleep 0.5; done

echo "==> 3/5 alta de usuario normal de prueba"
ATOK=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/auth/login" \
  -d "username=admin@example.com&password=Sup3rSecret!" \
  | "$PYBIN" -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/auth/users" \
  -H "Authorization: Bearer $ATOK" -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"abcdefgh","role":"user"}' || true

echo "==> 4/5 build + preview del frontend :$WEB_PORT"
cd "$ROOT/frontend"
VITE_API_BASE="http://127.0.0.1:${BACKEND_PORT}" npm run build >/dev/null 2>&1
npx vite preview --port "$WEB_PORT" --strictPort >/dev/null 2>&1 & PIDS+=($!)
for i in $(seq 1 40); do curl -sf "$ORIGIN" >/dev/null 2>&1 && break; sleep 0.5; done

echo "==> 5/5 Playwright"
cd "$ROOT/e2e"
BASE_URL="$ORIGIN" \
ADMIN_EMAIL="admin@example.com" ADMIN_PASSWORD="Sup3rSecret!" \
USER_EMAIL="user@example.com" USER_PASSWORD="abcdefgh" \
npx playwright test
echo
echo "Screenshots en: $ROOT/e2e/screenshots/"
