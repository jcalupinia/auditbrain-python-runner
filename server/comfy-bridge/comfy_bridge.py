#!/usr/bin/env python3
"""comfy-bridge — servicio HTTP que orquesta el time-sharing GPU para generar
imágenes desde el Command Center.

Flujo de una petición /generate:
  1. (si hace falta) `comfy-mode on` → apaga vLLM, arranca ComfyUI.
     Mientras tanto el chat del Command Center cae solo a Gemini/Groq (failover).
  2. Genera la imagen con Flux o SDXL vía la API de ComfyUI (:8188).
  3. Devuelve el PNG en base64.
  4. Tras una ventana de inactividad (WARM_SECONDS) restaura el chat (`comfy-mode off`).
     Así varias imágenes seguidas no reinician vLLM cada vez.

Seguridad: se expone SOLO por Tailscale (tailnet). Igual exige cabecera
X-Comfy-Key. Corre como servicio systemd del usuario auditia (sudo NOPASSWD).
"""
import asyncio, base64, json, os, time, urllib.request
from aiohttp import web

COMFY = "http://127.0.0.1:8188"
PORT = 8189
WARM_SECONDS = 180
KEY = os.environ.get("COMFY_BRIDGE_KEY", "")

_lock = asyncio.Lock()
_state = {"comfy_on": False, "warm_until": 0.0, "busy": False}

# Orígenes del Command Center autorizados a llamar al puente (CORS).
ALLOWED_ORIGINS = {
    "https://consola.audit-ia.ec",
    "https://auditbrain-frontend.onrender.com",
    "http://localhost:5173",
}


def _cors(req, resp):
    origin = req.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "X-Comfy-Key, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return resp


async def preflight(req):
    return _cors(req, web.Response(status=204))


# ---------- workflows ----------
def _wf_sdxl(prompt, neg, width, height, steps, seed):
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": 7.0,
              "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
              "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "cc_img", "images": ["8", 0]}},
    }


def _wf_flux(prompt, neg, width, height, steps, seed):
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["ckpt", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["ckpt", 1]}},
        "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "samp": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": 1.0,
                 "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                 "model": ["ckpt", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0]}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["samp", 0], "vae": ["ckpt", 2]}},
        "save": {"class_type": "SaveImage", "inputs": {"filename_prefix": "cc_img", "images": ["dec", 0]}},
    }


# ---------- helpers ----------
async def _run(cmd):
    p = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await p.communicate()
    return p.returncode, (out or b"").decode(errors="replace")


def _comfy_post(path, data):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def _comfy_get(path):
    return json.load(urllib.request.urlopen(COMFY + path, timeout=60))


async def _ensure_comfy_on():
    if _state["comfy_on"]:
        return
    rc, out = await _run(["comfy-mode", "on"])
    if rc != 0 or "arriba" not in out:
        raise RuntimeError(f"comfy-mode on falló: {out[-400:]}")
    _state["comfy_on"] = True


async def _restore_chat():
    rc, out = await _run(["comfy-mode", "off"])
    _state["comfy_on"] = False


async def _janitor():
    """Restaura el chat cuando pasa la ventana de calor sin actividad."""
    while True:
        await asyncio.sleep(15)
        if _state["comfy_on"] and not _state["busy"] and time.time() > _state["warm_until"]:
            async with _lock:
                if _state["comfy_on"] and not _state["busy"] and time.time() > _state["warm_until"]:
                    await _restore_chat()


# ---------- endpoints ----------
def _auth(req):
    return bool(KEY) and req.headers.get("X-Comfy-Key", "") == KEY


async def status(req):
    if not _auth(req):
        return _cors(req, web.json_response({"error": "no autorizado"}, status=401))
    return _cors(req, web.json_response({
        "mode": "comfy" if _state["comfy_on"] else "chat",
        "busy": _state["busy"],
        "warm_seconds_left": max(0, int(_state["warm_until"] - time.time())) if _state["comfy_on"] else 0,
    }))


async def generate(req):
    if not _auth(req):
        return web.json_response({"error": "no autorizado"}, status=401)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"error": "JSON inválido"}, status=400)

    model = (body.get("model") or "flux").lower()
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return web.json_response({"error": "falta 'prompt'"}, status=400)
    neg = body.get("negative") or "low quality, blurry, watermark, text artifacts"
    width = int(body.get("width", 1024)); height = int(body.get("height", 1024))
    seed = int(body.get("seed", int(time.time()) % 2_000_000))
    if model == "sdxl":
        steps = int(body.get("steps", 25)); wf = _wf_sdxl(prompt, neg, width, height, steps, seed)
    else:
        model = "flux"; steps = int(body.get("steps", 4)); wf = _wf_flux(prompt, neg, width, height, steps, seed)

    async with _lock:
        _state["busy"] = True
        t0 = time.time()
        try:
            await _ensure_comfy_on()
            loop = asyncio.get_event_loop()
            pid = (await loop.run_in_executor(None, _comfy_post, "/prompt", {"prompt": wf}))["prompt_id"]
            fname = None
            for _ in range(200):
                h = await loop.run_in_executor(None, _comfy_get, f"/history/{pid}")
                if pid in h:
                    st = h[pid].get("status", {})
                    if h[pid].get("outputs"):
                        for node in h[pid]["outputs"].values():
                            for img in node.get("images", []):
                                fname = img["filename"]
                        break
                    if st.get("status_str") == "error":
                        return web.json_response({"error": "fallo la generación", "detail": st}, status=500)
                await asyncio.sleep(1)
            if not fname:
                return web.json_response({"error": "timeout de generación"}, status=504)
            path = os.path.join("/opt/auditia/comfyui/output", fname)
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            _state["warm_until"] = time.time() + WARM_SECONDS
            return web.json_response({
                "model": model, "filename": fname, "seconds": round(time.time() - t0, 1),
                "image_base64": b64, "mime": "image/png",
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        finally:
            _state["busy"] = False


async def on_start(app):
    app["janitor"] = asyncio.create_task(_janitor())


@web.middleware
async def cors_mw(req, handler):
    if req.method == "OPTIONS":
        return _cors(req, web.Response(status=204))
    resp = await handler(req)
    return _cors(req, resp)


def main():
    if not KEY:
        raise SystemExit("Falta COMFY_BRIDGE_KEY en el entorno")
    app = web.Application(client_max_size=2 * 1024 * 1024, middlewares=[cors_mw])
    app.router.add_get("/status", status)
    app.router.add_post("/generate", generate)
    app.router.add_route("OPTIONS", "/{tail:.*}", preflight)
    app.on_startup.append(on_start)
    web.run_app(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
