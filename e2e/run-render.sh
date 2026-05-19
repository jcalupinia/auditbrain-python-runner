#!/usr/bin/env bash
# Validación visual contra el sitio REAL desplegado en Render.
# Requiere: red permitida a *.onrender.com + Chromium de Playwright +
# credenciales reales de prueba (NO uses cuentas sensibles).
#
# Uso:
#   export FRONTEND_URL="https://auditbrain-frontend.onrender.com"
#   export ADMIN_EMAIL=...  ADMIN_PASSWORD=...
#   export USER_EMAIL=...   USER_PASSWORD=...
#   cd e2e && bash run-render.sh
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p screenshots
: "${FRONTEND_URL:?define FRONTEND_URL}"
BASE_URL="$FRONTEND_URL" npx playwright test
echo "Screenshots en: $(pwd)/screenshots/"
