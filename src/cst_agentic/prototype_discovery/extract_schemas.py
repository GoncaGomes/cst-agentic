"""THROWAWAY: evaluate reviewed schema declarations only; never import CST code."""

import ast
import hashlib
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from mcp.types import Tool, ToolAnnotations

source, proposal = map(Path, sys.argv[1:])
here = Path(__file__).parent
namespace = {"Tool": Tool, "ToolAnnotations": ToolAnnotations, "Enum": Enum, "Any": Any}
types = ast.parse((source / "types.py").read_text(encoding="utf-8"))
enums = [
    n
    for n in types.body
    if isinstance(n, ast.ClassDef)
    and any(isinstance(b, ast.Name) and b.id == "Enum" for b in n.bases)
]
exec(compile(ast.Module(body=enums, type_ignores=[]), "types-enums", "exec"), namespace)
annotations = ast.parse((source / "tools/annotations.py").read_text(encoding="utf-8"))
nodes = [n for n in annotations.body if isinstance(n, (ast.Assign, ast.AnnAssign, ast.FunctionDef))]
exec(compile(ast.Module(body=nodes, type_ignores=[]), "annotations", "exec"), namespace)

groups = {}
for match in re.finditer(
    r"### 5\.\d+ (\w+) .*?\n(.*?)(?=\n###|\n##)", proposal.read_text(encoding="utf-8"), re.S
):
    body = match[2]
    groups[match[1]] = {
        "purpose": body.strip().split("\n")[0],
        "names": re.findall(r"^\| `(cst_\w+)`", body, re.M),
    }
assert len(groups) == 19
wanted = {"cst_connection_status"} | {n for g in groups.values() for n in g["names"]}
catalogue = {}
files = {
    name: hashlib.sha256((source / name).read_bytes()).hexdigest()
    for name in ("types.py", "tools/annotations.py")
}
modules = (
    "official connection project geometry boolean transforms materials ports boundaries "
    "mesh solvers simulation results import_export parameters diagnostics pcb workflows"
).split()
for module in modules:
    path = source / "tools" / f"{module}.py"
    text = path.read_text(encoding="utf-8")
    nodes = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "_expression_field",
            "tool",
            "_boolean_input_schema",
        }:
            nodes.append(node)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if names and not set(names) & {"logger", "DATA_DIR", "_clock", "_sleep"}:
                nodes.append(node)
            if "TOOLS" in names:
                break
    local = dict(namespace)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), local)
    files[f"tools/{module}.py"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for tool in local["TOOLS"]:
        if tool.name in wanted:
            if tool.annotations is None:
                tool = tool.model_copy(
                    update={"annotations": namespace["annotations_for"](tool.name)}
                )
            catalogue[tool.name] = tool.model_dump(by_alias=True, exclude_none=True)
assert set(catalogue) == wanted and len(catalogue) == 73
payload = {
    "basis": (
        "Source-evaluated canonical Tool declarations plus registry annotations; "
        "NOT a running tools/list snapshot."
    ),
    "upstream_commit": "a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2",
    "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
    "source_sha256": files,
    "groups": groups,
    "tools": catalogue,
}
(here / "schemas.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
)
print(json.dumps({"tools": len(catalogue), "groups": len(groups), "CST_imported": False}))
