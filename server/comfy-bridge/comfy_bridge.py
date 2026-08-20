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
# Modelos añadidos (Civitai/HF) integrados en Estudio:
UPSCALER = "4x-UltraSharp.pth"                 # alta resolución para imprimir
FLUX_REALISM_LORA = "flux_realism_xlabs.safetensors"  # estilo fotorrealista (Flux)


def _upscale_tail(image_ref, out_w, out_h, upscale):
    """Cola opcional de super-resolución: 4x-UltraSharp y reescalado a 2x del
    tamaño original (nítido, listo para imprimir). Devuelve (nodos, img_final)."""
    if not upscale:
        return {}, image_ref
    nodes = {
        "_upm": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "_up": {"class_type": "ImageUpscaleWithModel",
                "inputs": {"upscale_model": ["_upm", 0], "image": image_ref}},
        "_sc": {"class_type": "ImageScale",
                "inputs": {"image": ["_up", 0], "upscale_method": "lanczos",
                           "width": out_w * 2, "height": out_h * 2, "crop": "disabled"}},
    }
    return nodes, ["_sc", 0]


def _wf_sdxl(prompt, neg, width, height, steps, seed, upscale=True, realism=True):
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": 7.0,
              "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
              "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    }
    extra, img = _upscale_tail(["8", 0], width, height, upscale)
    wf.update(extra)
    wf["9"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "cc_img", "images": img}}
    return wf


def _wf_flux(prompt, neg, width, height, steps, seed, upscale=True, realism=True):
    wf = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux1-schnell-fp8.safetensors"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["ckpt", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["ckpt", 1]}},
        "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
    }
    model_ref = ["ckpt", 0]
    if realism:  # LoRA de realismo (estilo fotorrealista) sobre el modelo Flux
        wf["lora"] = {"class_type": "LoraLoaderModelOnly",
                      "inputs": {"model": ["ckpt", 0], "lora_name": FLUX_REALISM_LORA, "strength_model": 0.8}}
        model_ref = ["lora", 0]
    wf["samp"] = {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": 1.0,
                  "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                  "model": model_ref, "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0]}}
    wf["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["samp", 0], "vae": ["ckpt", 2]}}
    extra, img = _upscale_tail(["dec", 0], width, height, upscale)
    wf.update(extra)
    wf["save"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "cc_img", "images": img}}
    return wf


def _wf_ltxv(prompt, neg, width, height, length, fps, steps, seed):
    """Workflow texto→video LTX-Video 2B (distilled). Sale un .webp animado."""
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltxv-2b-0.9.6-distilled.safetensors"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "ltxv"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["clip", 0]}},
        "lat": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": width, "height": height, "length": length, "batch_size": 1}},
        "cond": {"class_type": "LTXVConditioning", "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "frame_rate": float(fps)}},
        "msamp": {"class_type": "ModelSamplingLTXV", "inputs": {"model": ["ckpt", 0], "max_shift": 2.05, "base_shift": 0.95, "latent": ["lat", 0]}},
        "sched": {"class_type": "LTXVScheduler", "inputs": {"steps": steps, "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": ["lat", 0]}},
        "ssel": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "samp": {"class_type": "SamplerCustom", "inputs": {"model": ["msamp", 0], "add_noise": True, "noise_seed": seed, "cfg": 1.0,
                 "positive": ["cond", 0], "negative": ["cond", 1], "sampler": ["ssel", 0], "sigmas": ["sched", 0], "latent_image": ["lat", 0]}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["samp", 0], "vae": ["ckpt", 2]}},
        # Guardamos FRAMES PNG (no webp animado): ffmpeg los ensambla en un MP4
        # fiable. Prefijo único por seed para no mezclar con otras corridas.
        "save": {"class_type": "SaveImage", "inputs": {"images": ["dec", 0],
                 "filename_prefix": f"cc_vid_{seed}"}},
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
    upscale = bool(body.get("upscale", True))   # alta resolución por defecto
    realism = bool(body.get("realism", True))   # LoRA de realismo por defecto (Flux)
    if model == "sdxl":
        steps = int(body.get("steps", 25))
        wf = _wf_sdxl(prompt, neg, width, height, steps, seed, upscale=upscale, realism=realism)
    else:
        model = "flux"; steps = int(body.get("steps", 4))
        wf = _wf_flux(prompt, neg, width, height, steps, seed, upscale=upscale, realism=realism)

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


async def generate_video(req):
    if not _auth(req):
        return web.json_response({"error": "no autorizado"}, status=401)
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"error": "JSON inválido"}, status=400)

    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return web.json_response({"error": "falta 'prompt'"}, status=400)
    neg = body.get("negative") or "low quality, worst quality, blurry, distorted, jittery, watermark, text"
    width = int(body.get("width", 704)); height = int(body.get("height", 480))
    fps = int(body.get("fps", 25)); steps = int(body.get("steps", 10))
    length = int(body.get("length", 65))
    if (length - 1) % 8 != 0:  # LTXV exige múltiplos de 8 + 1
        length = ((length - 1) // 8) * 8 + 1
    seed = int(body.get("seed", int(time.time()) % 2_000_000))
    wf = _wf_ltxv(prompt, neg, width, height, length, fps, steps, seed)

    async with _lock:
        _state["busy"] = True
        t0 = time.time()
        try:
            await _ensure_comfy_on()
            loop = asyncio.get_event_loop()
            pid = (await loop.run_in_executor(None, _comfy_post, "/prompt", {"prompt": wf}))["prompt_id"]
            done = False
            for _ in range(400):
                h = await loop.run_in_executor(None, _comfy_get, f"/history/{pid}")
                if pid in h:
                    st = h[pid].get("status", {})
                    if h[pid].get("outputs"):
                        done = True
                        break
                    if st.get("status_str") == "error":
                        return web.json_response({"error": "fallo la generación", "detail": st}, status=500)
                await asyncio.sleep(1)
            if not done:
                return web.json_response({"error": "timeout de generación"}, status=504)

            # Ensamblar los frames PNG (cc_vid_<seed>_NNNNN_.png) en un MP4.
            out_dir = "/opt/auditia/comfyui/output"
            import glob as _glob
            frames = sorted(_glob.glob(os.path.join(out_dir, f"cc_vid_{seed}_*.png")))
            if not frames:
                return web.json_response({"error": "no se generaron frames"}, status=500)
            mp4 = os.path.join(out_dir, f"cc_vid_{seed}.mp4")
            rc, ffout = await _run([
                "ffmpeg", "-y", "-framerate", str(fps),
                "-pattern_type", "glob", "-i", os.path.join(out_dir, f"cc_vid_{seed}_*.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4,
            ])
            if rc == 0 and os.path.exists(mp4):
                with open(mp4, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                mime, outname = "video/mp4", os.path.basename(mp4)
            else:
                return web.json_response({"error": f"ffmpeg falló: {ffout[-300:]}"}, status=500)
            # limpiar los frames PNG (dejar solo el mp4)
            for fr in frames:
                try: os.remove(fr)
                except OSError: pass
            _state["warm_until"] = time.time() + WARM_SECONDS
            return web.json_response({
                "model": "ltxv", "filename": outname, "seconds": round(time.time() - t0, 1),
                "video_base64": b64, "mime": mime,
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
    app.router.add_post("/generate_video", generate_video)
    app.router.add_route("OPTIONS", "/{tail:.*}", preflight)
    app.on_startup.append(on_start)
    web.run_app(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
