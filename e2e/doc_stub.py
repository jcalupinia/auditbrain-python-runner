"""Stub local del servicio documental (sin dependencias).

Responde 200 + {"url": ...} a cualquier POST /generate_<fmt>, para que
el panel de Documentos muestre un link de descarga real en la validación
visual local. NO se usa en producción.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(ln)
        fmt = self.path.rsplit("/generate_", 1)[-1] or "doc"
        body = json.dumps(
            {"url": f"https://example.invalid/auditbrain-sample.{fmt}"}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
