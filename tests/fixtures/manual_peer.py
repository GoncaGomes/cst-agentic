"""Controlled manual-mode MCP peer; no CST imports or provider requests."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> None:
    mode, observation = sys.argv[1:]
    # Only report explicitly synthetic sentinels/presence, never environment values.
    Path(observation).write_text(
        json.dumps(
            {
                "manual": os.environ.get("CST_CONNECT_MODE") == "manual",
                "toolsets": os.environ.get("CST_TOOLSETS") == "connection",
                "work": bool(os.environ.get("CST_WORK_DIR")),
                "forbidden": [
                    key
                    for key in (
                        "SKYNET_API_KEY",
                        "PYTHONPATH",
                        "PYTHONHOME",
                        "ARBITRARY_CONFIG",
                        "ACCESS_TOKEN",
                    )
                    if key in os.environ
                ],
                "calls": [],
            }
        ),
        encoding="utf-8",
    )
    print("synthetic-private-server-stderr", file=sys.stderr, flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == "initialize":
            if mode == "timeout":
                time.sleep(30)
            if mode == "refusal":
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "error": {"code": -32603, "message": "synthetic-private-refusal"},
                        }
                    ),
                    flush=True,
                )
                continue
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "manual-peer", "version": "1"},
            }
        elif method == "tools/list":
            if mode == "catalogue_timeout":
                time.sleep(30)
            names = (
                []
                if mode == "bad_catalogue"
                else ["cst_connect", "cst_disconnect", "cst_connection_status"]
            )
            result = {
                "tools": [{"name": name, "inputSchema": {"type": "object"}} for name in names]
            }
        else:
            data = json.loads(Path(observation).read_text(encoding="utf-8"))
            data["calls"].append(method)
            Path(observation).write_text(json.dumps(data), encoding="utf-8")
            result = (
                {
                    "content": [{"type": "text", "text": '{"mode":"offline"}'}],
                    "structuredContent": {"mode": "offline"},
                    "isError": False,
                }
                if mode == "conversation" and method == "tools/call"
                else {}
            )
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
    if mode == "eof_refusal":
        time.sleep(30)


if __name__ == "__main__":
    main()
