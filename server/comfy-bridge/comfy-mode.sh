#!/bin/bash
# ============================================================================
# comfy-mode — Time-sharing de la GPU entre el chat (vLLM) y ComfyUI.
#
# La RTX 5060 Ti (16 GB) está casi llena con gpt-oss-20b. ComfyUI necesita la
# GPU libre. Este script alterna:
#   comfy-mode on     -> apaga el chat, libera la GPU, arranca ComfyUI
#   comfy-mode off    -> apaga ComfyUI, reinicia el chat del equipo
#   comfy-mode status -> muestra qué está activo y la VRAM
#
# ⚠️  En modo ON el chat del Command Center / Open WebUI queda CAÍDO (failover
#     a la nube si aplica). Usar fuera de horario o avisando al equipo.
# ============================================================================
set -euo pipefail

COMFY_DIR="/opt/auditia/comfyui"
COMFY_PORT=8188
COMFY_LOG="$COMFY_DIR/comfy.log"
PIDFILE="$COMFY_DIR/comfy.pid"

vram_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1; }

wait_vram_free() {
  # Espera hasta que la VRAM usada baje del umbral (GPU liberada).
  local max=${1:-2000} i
  for i in $(seq 1 30); do
    [ "$(vram_used)" -lt "$max" ] && return 0
    sleep 2
  done
  echo "  ⚠️  la VRAM no bajó de ${max} MiB a tiempo"; return 1
}

comfy_running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start_comfy() {
  echo "→ Liberando la GPU (apagando vLLM)…"
  sudo docker stop vllm >/dev/null 2>&1 || true
  wait_vram_free 2000
  echo "  VRAM usada ahora: $(vram_used) MiB"

  echo "→ Arrancando ComfyUI…"
  cd "$COMFY_DIR"
  nohup ./venv/bin/python main.py --listen 0.0.0.0 --port "$COMFY_PORT" \
      > "$COMFY_LOG" 2>&1 &
  echo $! > "$PIDFILE"

  # Esperar a que sirva HTTP (o que el log delate un error de CUDA/sm_120).
  local i
  for i in $(seq 1 40); do
    if curl -sf "http://127.0.0.1:${COMFY_PORT}/" >/dev/null 2>&1; then
      echo "  ✅ ComfyUI arriba en http://100.96.235.59:${COMFY_PORT}"
      echo "     (dentro del tailnet). VRAM usada: $(vram_used) MiB"
      return 0
    fi
    if grep -qiE "no kernel image|CUDA error|not compiled|sm_120|out of memory" "$COMFY_LOG" 2>/dev/null; then
      echo "  ❌ Error de arranque. Últimas líneas:"; tail -15 "$COMFY_LOG"; return 1
    fi
    sleep 3
  done
  echo "  ⚠️  ComfyUI no respondió a tiempo. Log:"; tail -20 "$COMFY_LOG"; return 1
}

stop_comfy() {
  echo "→ Apagando ComfyUI…"
  if comfy_running; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; fi
  pkill -f "main.py --listen 0.0.0.0 --port ${COMFY_PORT}" 2>/dev/null || true
  rm -f "$PIDFILE"
  sleep 2
  wait_vram_free 2000 || true

  echo "→ Reiniciando el chat (vLLM)…"
  sudo docker start vllm >/dev/null 2>&1 || true
  local i
  for i in $(seq 1 60); do
    if sudo docker inspect -f '{{.State.Health.Status}}' vllm 2>/dev/null | grep -q healthy; then
      echo "  ✅ Chat de vuelta (vLLM healthy). VRAM usada: $(vram_used) MiB"
      return 0
    fi
    sleep 3
  done
  echo "  ⚠️  vLLM aún no reporta healthy; revisar: sudo docker logs vllm --tail 30"
}

case "${1:-}" in
  on)
    if comfy_running; then echo "ComfyUI ya está activo."; exit 0; fi
    start_comfy ;;
  off)
    stop_comfy ;;
  status)
    echo "VRAM usada: $(vram_used) MiB"
    if comfy_running; then echo "Modo: 🎨 ComfyUI (chat CAÍDO)"; else echo "Modo: 💬 Chat (vLLM)"; fi
    echo "Contenedores:"; sudo docker ps --format '  {{.Names}}\t{{.Status}}' | grep -E 'vllm|litellm|openwebui' || true ;;
  *)
    echo "Uso: comfy-mode {on|off|status}"; exit 1 ;;
esac
