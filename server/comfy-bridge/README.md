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

## Arquitectura: proxy por el backend (sin Tailscale en el cliente)
El navegador **no** llama al puente directamente. Llama al **backend**
(`auditbrain-python-runner`, con sesión JWT), y el backend reenvía al puente por
un **túnel público** (Cloudflare). Así el Command Center funciona **sin Tailscale**
en cada máquina, y la clave del puente **nunca sale al frontend**.

```
navegador → (JWT) backend Render → (X-Comfy-Key, túnel) puente :8189 → ComfyUI :8188
```

Endpoints del backend: `GET /chat/media/status`, `POST /chat/media/image`,
`POST /chat/media/video` (ver `backend/app/chat/media.py`).

### Túnel del puente
Servicio systemd `comfy-tunnel` corre
`cloudflared tunnel --url http://127.0.0.1:8189` y da una URL
`https://xxx.trycloudflare.com`. ⚠️ Es un **quick tunnel efímero**: la URL cambia
si el servicio reinicia → hay que refrescar `COMFY_BRIDGE_URL` en Render (mismo
pendiente que el túnel del LLM; conviene un túnel de nombre fijo).

## Variables en Render (web service `auditbrain-python-runner`, NO el frontend)
- `COMFY_BRIDGE_URL` = URL del túnel del puente (p. ej. `https://xxx.trycloudflare.com`, sin barra final)
- `COMFY_BRIDGE_KEY` = el valor de `COMFY_BRIDGE_KEY` de `bridge.env`

Si no se configuran, `GET /chat/media/status` devuelve `{enabled:false}` y la
pestaña **"Estudio"** del Command Center **no aparece** (degradación limpia).

## Herramientas de marketing (CPU · no usan la GPU · no pausan el chat)
El puente también expone motores para producción de contenido, instalados en un
venv aparte (`/opt/auditia/mediatools/venv`):

| Endpoint | Motor | Qué hace |
|---|---|---|
| `POST /removebg` | rembg (u2net) | Quita el fondo → PNG transparente. `{image_base64}` → `{image_base64}` |
| `POST /tts` | Piper (voz `es_MX-ald-medium`) | Texto → voz en off. `{text}` → `{audio_base64, mime:audio/mpeg}` |
| `POST /subtitle` | faster-whisper (small, es) | Audio/video → subtítulos. `{audio_base64}` → `{srt}` |

Instalación (una vez):
```bash
sudo mkdir -p /opt/auditia/mediatools && sudo chown auditia: /opt/auditia/mediatools
cd /opt/auditia/mediatools && python3 -m venv venv
./venv/bin/pip install "rembg[cli]" onnxruntime pillow piper-tts faster-whisper
# voz Piper:
mkdir voices && curl -L -o voices/es_MX-ald-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx
curl -L -o voices/es_MX-ald-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json
# subtitle.py (transcribe a .srt) — ver subtitle.py junto a este README
```
Estos endpoints son CPU: **no** hacen `comfy-mode on`, así que **conviven con el chat**.

## Seguridad
El puente exige `X-Comfy-Key` (48 hex). Solo el backend conoce la clave; solo
usuarios con sesión JWT pueden disparar generación. La `tailscale serve` en :8443
(tailnet) se mantiene como acceso alterno/manual, pero el Command Center ya no
depende de ella.
