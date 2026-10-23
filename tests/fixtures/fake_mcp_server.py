"""Disposable JSON-RPC peer for actual-wrapper tests; no CST or network access."""

from __future__ import annotations

import json
import sys


def main() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == "initialize":
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "offline-wrapper-peer", "version": "1"},
            }
        elif method == "tools/list":
            if request.get("params", {}).get("cursor") == "second":
                result = {"tools": [{"name": "other", "inputSchema": {"type": "object"}}]}
            else:
                result = {
                    "tools": [
                        {
                            "name": "inspect",
                            "description": "Fake inspection only",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "value": {"anyOf": [{"type": "number"}, {"type": "string"}]},
                                    "note": {"type": ["string", "null"], "default": None},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "required": ["rebuilt"],
                                "properties": {"rebuilt": {"type": "boolean"}},
                            },
                        }
                    ],
                    "nextCursor": "second",
                }
        elif method == "tools/call":
            arguments = request.get("params", {}).get("arguments", {})
            result = {
                "content": [
                    {"type": "text", "text": '{"status":"received"}'},
                    {"type": "text", "text": "Additional evidence"},
                    {"type": "image", "data": "AA==", "mimeType": "image/png"},
                ],
                "structuredContent": {} if arguments.get("invalid") else {"rebuilt": False},
                "isError": arguments.get("error", False),
            }
        else:
            result = {}
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


if __name__ == "__main__":
    main()
