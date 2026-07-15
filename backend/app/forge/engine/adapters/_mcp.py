"""Render compartido del archivo de servidores MCP (idéntico entre adaptadores).

Un conector `type: mcp` del cerebro se mapea a una entrada `mcpServers`. Sin
secretos. JSON determinista: indent=2, claves ordenadas, newline final.
"""

from __future__ import annotations

import json

from ..model import Brain


def mcp_servers_json(brain: Brain) -> str:
    servers = {
        c.slug: {"command": c.command, "args": c.args}
        for c in brain.connectors
        if c.type == "mcp"
    }
    obj = {"mcpServers": servers}
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
