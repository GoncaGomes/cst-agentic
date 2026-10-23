"""New controlled peer for #17; never runs CST, provider requests or old probes."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> None:
    mode = os.environ.get("RECOVERY_PEER_MODE", "received")
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == "initialize":
            if mode == "startup_timeout":
                time.sleep(30)
            if mode == "startup_refusal":
                print(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "error": {"code": -32603, "message": "refused"},
                        }
                    ),
                    flush=True,
                )
                continue
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "recovery-peer", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": "inspect", "inputSchema": {"type": "object"}}]}
        elif method == "tools/call":
            data = json.loads(Path(os.environ["RECOVERY_LEDGER"]).read_text(encoding="utf-8"))
            assert data["incidents"][-1]["state"] == "in_flight"
            Path(os.environ["RECOVERY_SEEN"]).write_text(str(os.getpid()), encoding="utf-8")
            if mode == "in_flight":
                time.sleep(30)
            result = {"content": [{"type": "text", "text": "received"}], "isError": False}
        else:
            result = {}
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
    if mode == "eof_refusal":
        time.sleep(30)


if __name__ == "__main__":
    main()
