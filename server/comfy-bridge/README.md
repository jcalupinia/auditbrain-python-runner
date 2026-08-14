# comfy-bridge — generación de imágenes local desde el Command Center

Estos scripts viven en el **servidor de IA local** (no en Render). Permiten que
la pestaña **"Imagen"** del Command Center genere imágenes con ComfyUI (Flux/SDXL)
haciendo *time-sharing* de la única GPU con el modelo de chat (gpt-oss-20b/vLLM).

## Por qué time-sharing
La RTX 5060 Ti (16 GB) está casi llena con el modelo de chat. No caben chat y
ComfyUI a la vez. Al generar una imagen se apaga vLLM y arranca ComfyUI; mientras
tanto el chat del Command Center **cae solo a Gemini/Groq** (failover gratuito de
`backend/app/chat/providers.py`). Al terminar, un "janitor" restaura vLLM.

## Componentes
- **`comfy-mode.sh`** → `comfy-mode {on|off|status}`: alterna vLLM ↔ ComfyUI.
  Symlink en `/usr/local/bin/comfy-mode`.
- **`comfy_bridge.py`**: servicio aiohttp (systemd) en `127.0.0.1:8189`.
  `POST /generate {model, prompt, width, height}` → hace el swap, genera vía la
  API de ComfyUI (`:8188`), devuelve el PNG en base64. Restaura el chat tras
  `WARM_SECONDS` de inactividad. Exige cabecera `X-Comfy-Key`. CORS restringido
  a los orígenes del Command Center.

## Despliegue (resumen)
1. ComfyUI en `/opt/auditia/comfyui` (venv con PyTorch cu128) + modelos en
   `models/` (Flux `flux1-schnell-fp8`, SDXL `sd_xl_base_1.0`).
2. `comfy-mode.sh` → `/usr/local/bin/comfy-mode` (`chmod +x`).
3. Clave: `echo "COMFY_BRIDGE_KEY=$(openssl rand -hex 24)" > bridge.env`.
4. Servicio systemd `comfy-bridge` corriendo `comfy_bridge.py` (User=auditia,
   `EnvironmentFile=bridge.env`, `PATH` con `/usr/local/bin`).
5. Exponer por Tailscale (solo tailnet, HTTPS):
   `sudo tailscale serve --bg --https=8443 http://127.0.0.1:8189`
   → `https://<nodo>.<tailnet>.ts.net:8443`.

## Variables en Render (static site `auditbrain-frontend`)
- `VITE_COMFY_BRIDGE_URL` = la URL de Tailscale (p. ej. `https://auditia.tail70d973.ts.net:8443`)
- `VITE_COMFY_BRIDGE_KEY` = el valor de `COMFY_BRIDGE_KEY`

Si no se configuran, la pestaña "Imagen" **no aparece** (degradación limpia).

## Seguridad
El puente solo es accesible dentro del **tailnet** (no expuesto a internet).
`X-Comfy-Key` es defensa en profundidad. Los usuarios del Command Center deben
estar en el tailnet (Tailscale activo) para usar la pestaña Imagen.
