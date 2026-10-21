"""Static Python argument-binding check only. Does not import CST or start a peer."""

import importlib.util
import inspect
import json
from pathlib import Path

path = Path(
    r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline"
    r"\src\cst_agentic\windows_lifetime_native_peer.py"
)
spec = importlib.util.spec_from_file_location("native_peer_static_inspection", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    inspect.signature(module.NativeFixture.event).bind(None, "operation_entered", name="native_connect")
except TypeError:
    print(json.dumps({"event_argument_binding_valid": False, "native_api_calls": 0}))
    raise SystemExit(1) from None
print(json.dumps({"event_argument_binding_valid": True, "native_api_calls": 0}))
