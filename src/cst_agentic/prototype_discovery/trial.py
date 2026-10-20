"""THROWAWAY Qwen discovery trial. No CST imports, subprocesses or native operations.

Run from the original project's uv environment. Requires explicit --live and a
new approved budget; this artifact does NOT authorize future reruns.
"""

import argparse
import asyncio
import copy
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SCHEMAS = json.loads((HERE / "schemas.json").read_text(encoding="utf-8"))
LIMIT = 18
BUDGET = 48

INSTRUCTIONS = """You are a CST-aware conversational engineering assistant in a THROWAWAY
trial. ALL CST tools are MOCKS; say 'mock' in outcome summaries. Never claim native
execution or physics validation. Interpret engineering requests, offer useful
choices as questions, and execute complete authorized instructions without
approval of every call. Ask together for missing engineering choices; do not
invent dimensions, units, material properties, selected project or dependencies.
An incidental nonconflicting name may be generated. Load requested materials from
the native library first; if unavailable ask for specifications, do not substitute.
Never run a simulation unless explicitly requested. Do not add setup to standalone
geometry requests. Existing parameterized edits should reuse actual parameters;
creation is NOT arbitrary solid editing. Do not use VBA or rebuild as a workaround
without agreement. Result deletion and scope expansion require explicit consent.
Do not save unless requested. Parameter get/list schemas overpromise: actual
responses contain evaluated values, NOT stored expressions. Numeric-only port
inputs do not preserve parameter dependencies. Project paths in MCP are cached;
unit and target evidence here comes ONLY from explicitly identified mock fixture
facts, not from invented native unit/identity APIs. Bundled material queries do
not inspect project properties. Solver/mesh annotations have stale history
rationale; do not use hints as authorization or execution evidence.
Use discover_tools to REPLACE the complete group selection for the next model
request; discovery itself performs no CST operations. Empty groups reset to
startup. Rejected selections preserve the previous set. Only tools visible in the
request that produced a call may execute in that batch. Calls requiring newly
discovered schemas must wait for the next request; avoid discovery mixed with
mutations. Use meaningful small selections, not everything. Explain concrete
blockers without repetitive discovery. Brief intent is sufficient before action.
After transport uncertainty ALL CST dispatch is blocked, including status and
stop. Do not retry or reconnect; explain unknown outcome and pause. Reconnection
does not reconcile. Acknowledged server errors are distinct from lost responses.
Never equate idle with successful completion. 'Stop task' means no further task
steps, not implicit solver stop. Be concise; separate proposals from observations.
"""

CONTEXT = """Mock fixture facts (synthetic, not native readbacks): intended project
C:/mock/discovery.cst is already explicitly selected and held in an owned mock
instance. A fixture-owned independent identity/unit check established this target
and mm/GHz/ns; these are supplied test facts, not implemented MCP capabilities.
Project is unsolved and empty except when the scenario states otherwise.
"""

BUILD = """Create a NEW mock MWS project at C:/mock/patch.cst in the already owned
connected mock instance; do not replace the selected project's file. Fixture setup
establishes mm/GHz/ns for the new project independently (no unit-tool capability
is being claimed). Build the model only, do not save or run. Set named parameters:
board_w=60, board_l=60, substrate_h=1.6, patch_w=38, patch_l=29, metal_t=0.035,
feed_x=0, feed_y=-8. Use exact library PEC and Rogers RT-duroid 5870 (loss free).
Substrate: X +/-board_w/2, Y +/-board_l/2, Z 0 to substrate_h. Ground: same X/Y,
Z -metal_t to 0. Patch: X +/-patch_w/2, Y +/-patch_l/2, Z substrate_h to
substrate_h+metal_t. Centered in X/Y. One ideal 50-ohm discrete port at
(feed_x, feed_y), Z 0 to substrate_h; no connector. Preserve supported named
expressions. If the port cannot retain parameter dependencies, ask for a revision
before silently freezing coordinates. No simulation or solver configuration.
"""

SCENARIOS = [
    (
        "proposal",
        "cylinder",
        6,
        "Create one solid cylinder of radius 5 mm, height 10 mm, base center (0,0,0), "
        "along +Z using exact library PEC. Do nothing else.",
        {},
    ),
    (
        "focused",
        "cylinder",
        5,
        "Create one solid cylinder of radius 5 mm, height 10 mm, base center (0,0,0), "
        "along +Z using exact library PEC. Do nothing else.",
        {},
    ),
    (
        "proposal",
        "existing_edit",
        6,
        "In the selected parameterized patch project, change existing patch_l from 29 "
        "to 30 mm, keep all other design inputs and verified solver setup, and rerun "
        "asynchronously and monitor with bounded waits. This fixture's external readback "
        "established the patch references patch_l, but stored expressions are not "
        "available from MCP. I explicitly consent to deleting existing simulation "
        "results for this edit. Do not reconstruct any solids.",
        {"solved": True},
    ),
    (
        "proposal",
        "unsupported_edit",
        2,
        "Change the height of existing nonparametric Body:Rod from 10 to 12 mm, "
        "preserving its identity. Fixture inspection confirms no dimension parameter "
        "exists. Do not replace or scale the solid, and do not run.",
        {},
    ),
    (
        "proposal",
        "over_budget",
        3,
        "Discovery-mechanism trial only: first request the complete union of "
        "project_context, parameters, materials_basic and geometry_basic. If rejected, "
        "switch to project_context plus parameters and report the rejection and active "
        "selection. Do not execute any CST operation.",
        {},
    ),
    (
        "proposal",
        "missing_tool",
        2,
        "Activate geometry_basic, then report availability. This synthetic server "
        "catalogue lacks cst_create_cylinder. If activation fails, do not substitute "
        "another geometry family or retry discovery. Do not create anything.",
        {"missing": ["cst_create_cylinder"]},
    ),
    (
        "proposal",
        "uncertain_mutation",
        4,
        "Create one solid cylinder of radius 5 mm, height 10 mm, base center (0,0,0), "
        "along +Z using PEC already loaded by this fixture. Do nothing else. "
        "A synthetic transport failure may occur: do not infer whether a mutation happened.",
        {"loaded": ["PEC"], "uncertain_on": "cst_create_cylinder"},
    ),
]

# Exercise safety/discovery edge cases before the longest construction cases.
SCENARIOS.sort(
    key=lambda case: {
        "over_budget": 0,
        "missing_tool": 1,
        "uncertain_mutation": 2,
        "unsupported_edit": 3,
        "cylinder": 4,
        "existing_edit": 5,
    }[case[1]]
)
SCENARIOS.extend(
    [
        ("proposal", "construction", 6, BUILD, {}),
        ("focused", "construction", 6, BUILD, {}),
    ]
)


def groups_for(variant):
    groups = copy.deepcopy(SCHEMAS["groups"])
    if variant == "focused":
        groups["project_context"] = {
            "purpose": "Inspect current project tree (read context only).",
            "names": ["cst_project_tree"],
        }
        groups["materials_basic"] = {
            "purpose": (
                "Load exact native material library entries; search bundled names "
                "(not project properties)."
            ),
            "names": ["cst_load_material", "cst_list_materials"],
        }
    return groups


def visible(state):
    names = {"discover_tools", "cst_connection_status"}
    if state["variant"] == "focused":
        names.add("cst_project_info")
    for group in state["active"]:
        names.update(state["groups"][group]["names"])
    return sorted(names)


def discovery(state, selected):
    old = list(state["active"])
    if any(g not in state["groups"] for g in selected):
        return {"status": "rejected", "reason": "unknown_group", "active_groups": old}
    candidate = dict(state, active=list(dict.fromkeys(selected)))
    names = visible(candidate)
    missing = sorted(set(names) & set(state.get("missing", [])))
    if missing or len(names) > LIMIT:
        return {
            "status": "rejected",
            "reason": "missing_tool" if missing else "over_budget",
            "missing": missing,
            "proposed_count": len(names),
            "limit": LIMIT,
            "active_groups": old,
            "active_names": visible(state),
        }
    state["active"] = candidate["active"]
    return {
        "status": "activated_next_request",
        "active_groups": state["active"],
        "active_names": names,
        "visible_count": len(names),
    }


def mock_call(state, name, args):
    if state["poisoned"]:
        return {"status": "blocked", "reason": "transport_uncertain", "mock": True}
    if name == state.get("uncertain_on"):
        state["poisoned"] = True
        return {
            "outcome": "uncertain",
            "transport_response_received": False,
            "effect": "unknown",
            "all_CST_dispatch_blocked": True,
            "note": "Injected client-side trace, NOT a received MCP error.",
            "mock": True,
        }
    if name in {"cst_connection_status", "cst_project_info"}:
        return {
            "status": "ok",
            "mode": "connected",
            "project_open": True,
            "project_path": state["project"],
            "path_evidence": "cached_session_path",
            "running": state["running"],
            "mock": True,
        }
    if name == "cst_project_tree":
        return {"status": "ok", "items": state["objects"], "truncated": False, "mock": True}
    if name == "cst_create_project":
        state["project"] = args["path"]
        return {"status": "ok", "path": args["path"], "mock": True}
    if name == "cst_load_material":
        if args["library_name"] not in {"PEC", "Rogers RT-duroid 5870 (loss free)"}:
            return {"status": "error", "code": "library_material_unavailable", "mock": True}
        state["loaded"].append(args["name"])
        return {
            "status": "ok",
            "name": args["name"],
            "library_name": args["library_name"],
            "native_properties_verified": False,
            "mock": True,
        }
    if name == "cst_assign_material":
        if args["solid"] not in state["objects"]:
            return {"status": "error", "code": "unknown_solid", "mock": True}
        if args["material"] not in state["loaded"]:
            return {"status": "error", "code": "material_not_loaded", "mock": True}
        return {
            "status": "ok",
            "solid": args["solid"],
            "material": args["material"],
            "native_properties_verified": False,
            "mock": True,
        }
    if name == "cst_list_materials":
        return {
            "status": "ok",
            "materials": ["PEC", "Rogers RT-duroid 5870 (loss free)"],
            "source": "synthetic_bundled_database",
            "mock": True,
        }
    if name == "cst_get_material_info":
        return {
            "status": "ok",
            "source": "synthetic_bundled_database",
            "project_properties_verified": False,
            "mock": True,
        }
    if name == "cst_add_discrete_port":
        return {
            "status": "ok",
            "arguments": args,
            "parametric_dependencies_preserved": False,
            "mock": True,
        }
    if name in {"cst_get_solver_info", "cst_get_mesh_info"}:
        return {
            "status": "ok",
            "fixture_setup": "Previously verified fixture setup unchanged",
            "native_readback": False,
            "mock": True,
        }
    if name == "cst_read_project_log":
        return {
            "status": "ok",
            "text": "Synthetic solver activity ended; no numerical validation.",
            "mock": True,
        }
    if name == "cst_list_parameters":
        return {
            "status": "ok",
            "result": "\n".join(f"{k} = {v}" for k, v in state["params"].items()),
            "mock": True,
        }
    if name == "cst_get_parameter":
        return {
            "status": "ok",
            "result": str(state["params"].get(args["name"], "missing")),
            "mock": True,
        }
    if name == "cst_set_parameter":
        if state["solved"] and not args.get("delete_results", False):
            return {"status": "error", "code": "results_exist", "mock": True}
        state["solved"] = False
        state["params"][args["name"]] = args["value"]
        return {
            "status": "ok",
            "name": args["name"],
            "value": args["value"],
            "parameters_changed": True,
            "mock": True,
        }
    if name in {"cst_create_cylinder", "cst_create_brick", "cst_create_sphere"}:
        if args.get("material", "PEC") not in state["loaded"]:
            return {"status": "error", "code": "material_not_loaded", "mock": True}
        reference = args["component"] + ":" + args["name"]
        if reference in state["objects"]:
            return {"status": "error", "code": "name_collision", "mock": True}
        state["objects"].append(reference)
        return {"status": "ok", "solid": reference, "native_effect_verified": False, "mock": True}
    if name == "cst_run_simulation_async":
        state["running"] = True
        return {"status": "started", "running": True, "mock": True}
    if name == "cst_get_simulation_status":
        return {"status": "ok", "running": state["running"], "mock": True}
    if name == "cst_wait_for_simulation":
        state["running"] = False
        return {
            "status": "finished",
            "confirmed": True,
            "solve_observed": True,
            "running": False,
            "elapsed_s": 0.1,
            "warning": "Synthetic activity transition only, no numerical validation.",
            "mock": True,
        }
    return {"status": "blocked", "reason": "mock_handler_not_implemented", "mock": True}


async def main():
    logging.disable(logging.CRITICAL)
    for key in (
        "OPENAI_AGENTS_DISABLE_TRACING",
        "OPENAI_AGENTS_DONT_LOG_MODEL_DATA",
        "OPENAI_AGENTS_DONT_LOG_TOOL_DATA",
    ):
        os.environ[key] = "1"
    import httpx2
    from agents import (
        Agent,
        FunctionTool,
        ModelSettings,
        OpenAIChatCompletionsModel,
        RunConfig,
        Runner,
        set_tracing_disabled,
    )
    from dotenv import dotenv_values
    from jsonschema import Draft202012Validator
    from openai import AsyncOpenAI

    set_tracing_disabled(True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--budget-ledger", type=Path, required=True)
    parser.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        print("Live execution requires --live and fresh human authorization.")
        return 1
    if args.evidence_file.exists() or not args.budget_ledger.is_file():
        print("Refusing to overwrite evidence or start without the existing cumulative ledger.")
        return 1
    values = dotenv_values(args.config_root / ".env")

    def resolve(key):
        return (values.get(key) or os.environ.get(key, "")).strip()

    configured = {key: resolve(key) for key in ("SKYNET_BASE_URL", "SKYNET_API_KEY", "AGENT")}
    print(json.dumps({"configuration_presence": {k: bool(v) for k, v in configured.items()}}))
    if not all(configured.values()):
        return 1

    def safe(value):
        text = json.dumps(value, ensure_ascii=True)
        for secret in configured.values():
            text = text.replace(json.dumps(secret)[1:-1], "[CONFIGURATION REDACTED]")
        return json.loads(text)

    ledger = args.budget_ledger
    used = json.loads(ledger.read_text()) if ledger.exists() else {"requests": 0}
    state = {}
    records = []
    underlying = httpx2.AsyncHTTPTransport(retries=0)
    origin = httpx2.URL(configured["SKYNET_BASE_URL"])

    def save():
        payload = {"budget": BUDGET, "requests_used": used["requests"], "records": records}
        args.evidence_file.write_text(
            json.dumps(safe(payload), indent=2) + "\n", encoding="utf-8"
        )

    class BudgetTransport(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if used["requests"] >= BUDGET:
                raise RuntimeError("budget_exhausted")
            if (request.url.scheme, request.url.host, request.url.port) != (
                origin.scheme,
                origin.host,
                origin.port,
            ):
                raise RuntimeError("origin_rejected")
            if request.method != "POST" or not request.url.path.endswith("/chat/completions"):
                raise RuntimeError("request_rejected")
            body = json.loads(request.content)
            names = [t["function"]["name"] for t in body.get("tools", [])]
            if sorted(names) != visible(state) or len(names) > LIMIT:
                raise RuntimeError("visibility_mismatch")
            state["dispatch"] = set(names)
            calls, results = set(), set()
            for message in body["messages"]:
                calls.update(c["id"] for c in message.get("tool_calls", []))
                if message["role"] == "tool":
                    results.add(message["tool_call_id"])
            if calls != results:
                raise RuntimeError("unpaired_history")
            used["requests"] += 1
            ledger.write_text(json.dumps(used), encoding="utf-8")
            event = {
                "kind": "request",
                "request": used["requests"],
                "visible": names,
                "active_groups": list(state["active"]),
                "matched_history_pairs": len(calls),
            }
            state["events"].append(event)
            started = time.monotonic()
            try:
                response = await underlying.handle_async_request(request)
                await response.aread()
                event["latency_s"] = round(time.monotonic() - started, 3)
                event["http_status"] = response.status_code
                if response.status_code != 200:
                    save()
                    raise RuntimeError("provider_http_failure")
                payload = response.json()
                choice = payload["choices"][0]
                message = choice["message"]
                state["events"].append(
                    {
                        "kind": "assistant",
                        "text": message.get("content"),
                        "tool_calls": [
                            {"name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                            for c in message.get("tool_calls") or []
                        ],
                        "finish_reason": choice.get("finish_reason"),
                        "usage": payload.get("usage"),
                    }
                )
                save()
                return response
            except BaseException as exc:
                event["error_type"] = type(exc).__name__
                save()
                raise

        async def aclose(self):
            await underlying.aclose()

    http = httpx2.AsyncClient(
        transport=BudgetTransport(), timeout=httpx2.Timeout(90, connect=15), follow_redirects=False
    )
    client = AsyncOpenAI(
        base_url=configured["SKYNET_BASE_URL"],
        api_key=configured["SKYNET_API_KEY"],
        max_retries=0,
        timeout=90,
        http_client=http,
    )
    model = OpenAIChatCompletionsModel(model=configured["AGENT"], openai_client=client)

    def tools():
        groups = state["groups"]
        description = (
            "Replace COMPLETE selected groups for NEXT request; "
            "atomic rejection preserves old selection. "
            "Limit 18 visible functions, including startup. Empty resets. No CST execution.\n"
            + "\n".join(f"{g} ({len(v['names'])}): {v['purpose']}" for g, v in groups.items())
        )
        discovery_schema = {
            "type": "object",
            "properties": {
                "groups": {"type": "array", "items": {"type": "string", "enum": list(groups)}}
            },
            "required": ["groups"],
            "additionalProperties": False,
        }

        def make(name, schema, description):
            async def invoke(_context, raw):
                try:
                    data = json.loads(raw)
                    errors = list(Draft202012Validator(schema).iter_errors(data))
                    if errors:
                        result = {
                            "status": "rejected",
                            "reason": "invalid_arguments",
                            "paths": [list(e.path) for e in errors],
                        }
                    elif name not in state["dispatch"]:
                        result = {
                            "status": "blocked",
                            "reason": "not_active_in_originating_request",
                        }
                    elif name == "discover_tools":
                        result = discovery(state, data["groups"])
                    else:
                        result = mock_call(state, name, data)
                except (ValueError, TypeError):
                    data, result = None, {"status": "rejected", "reason": "invalid_json"}
                state["events"].append(
                    {
                        "kind": "tool",
                        "name": name,
                        "arguments": data,
                        "result": result,
                        "state": {
                            k: state[k]
                            for k in (
                                "project",
                                "params",
                                "objects",
                                "loaded",
                                "running",
                                "poisoned",
                                "active",
                            )
                        },
                    }
                )
                # Snapshot mutable in-memory state now, rather than after later mutations.
                state["events"][-1] = copy.deepcopy(state["events"][-1])
                save()
                return json.dumps(result)

            return FunctionTool(
                name=name,
                description=description,
                params_json_schema=schema,
                strict_json_schema=False,
                on_invoke_tool=invoke,
                is_enabled=lambda _ctx, _agent: name in visible(state),
            )

        result = [make("discover_tools", discovery_schema, description)]
        for name, definition in SCHEMAS["tools"].items():
            result.append(make(name, definition["inputSchema"], definition["description"]))
        return result

    try:
        for variant, scenario, max_turns, prompt, setup in SCENARIOS:
            if used["requests"] >= BUDGET:
                break
            state.clear()
            state.update(
                variant=variant,
                scenario=scenario,
                groups=groups_for(variant),
                active=[],
                dispatch=set(),
                events=[],
                poisoned=False,
                project="C:/mock/discovery.cst",
                params={"patch_l": 29} if scenario == "existing_edit" else {},
                objects=["Antenna:Patch"] if scenario == "existing_edit" else [],
                loaded=[],
                solved=False,
                running=False,
            )
            state.update(setup)
            record = {
                "variant": variant,
                "scenario": scenario,
                "prompt": CONTEXT + prompt,
                "setup": setup,
                "max_turns": max_turns,
                "events": state["events"],
            }
            records.append(record)
            agent = Agent(
                name="throwaway-cst-discovery",
                model=model,
                instructions=INSTRUCTIONS,
                tools=tools(),
                model_settings=ModelSettings(
                    tool_choice="auto", parallel_tool_calls=True, max_tokens=3072, timeout=100
                ),
            )
            before = used["requests"]
            try:
                result = await asyncio.wait_for(
                    Runner.run(
                        agent,
                        CONTEXT + prompt,
                        max_turns=max_turns,
                        run_config=RunConfig(
                            tracing_disabled=True, tool_not_found_behavior="return_error_to_model"
                        ),
                    ),
                    timeout=600,
                )
                record["final_output"] = result.final_output
                record["status"] = "returned"
            except BaseException as exc:
                record["status"] = "bounded_stop"
                record["error_type"] = type(exc).__name__
                if type(exc).__name__ != "MaxTurnsExceeded":
                    save()
                    print(
                        json.dumps(
                            {
                                "scenario": scenario,
                                "stopped": True,
                                "error_type": type(exc).__name__,
                                "requests_used": used["requests"],
                            }
                        ),
                        flush=True,
                    )
                    return 1
            save()
            print(
                json.dumps(
                    {
                        "variant": variant,
                        "scenario": scenario,
                        "status": record["status"],
                        "requests": used["requests"] - before,
                        "total_requests": used["requests"],
                    }
                ),
                flush=True,
            )
    finally:
        await client.close()
        save()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        print(json.dumps({"stopped": True, "error_type": type(exc).__name__}), flush=True)
        sys.exit(1)
