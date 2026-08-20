#!/usr/bin/env python3
"""Genera subtítulos .srt en español desde un audio/video, con faster-whisper.

Uso: python subtitle.py <entrada_audio_o_video> <salida.srt>
Vive en /opt/auditia/mediatools/subtitle.py (venv con faster-whisper).
Lo invoca el endpoint /subtitle del comfy-bridge.
"""
import sys

from faster_whisper import WhisperModel


def fmt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(sys.argv[1], language="es")
    out = []
    for i, s in enumerate(segs, 1):
        out.append(f"{i}\n{fmt(s.start)} --> {fmt(s.end)}\n{s.text.strip()}\n")
    open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out))
    print("segmentos:", len(out))


if __name__ == "__main__":
    main()
