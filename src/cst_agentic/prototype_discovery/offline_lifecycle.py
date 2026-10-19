"""THROWAWAY deterministic SDK batch-timing demonstration. Zero network/CST access."""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx2
from trial import SCHEMAS, discovery, groups_for, mock_call, visible


async def main():
    logging.disable(logging.CRITICAL)
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"
    from agents import (
        Agent,
        FunctionTool,
        ModelSettings,
        OpenAIChatCompletionsModel,
        RunConfig,
        Runner,
        set_tracing_disabled,
    )
    from openai import AsyncOpenAI

    set_tracing_disabled(True)
    records = []
    for mode in ("remove_old_then_call_old", "add_new_and_call_too_early"):
        state = dict(
            variant="proposal",
            groups=groups_for("proposal"),
            active=["geometry_basic"] if mode.startswith("remove") else ["parameters"],
            missing=[],
            poisoned=False,
            project="C:/mock/discovery.cst",
            loaded=["PEC"],
            params={},
            objects=[],
            running=False,
            solved=False,
        )
        events = []

        async def respond(request, state=state, events=events, mode=mode):
            body = json.loads(request.content)
            state["dispatch"] = {t["function"]["name"] for t in body["tools"]}
            events.append(
                {
                    "request_visible": sorted(state["dispatch"]),
                    "history_tool_results": sum(m["role"] == "tool" for m in body["messages"]),
                }
            )
            if len([e for e in events if "request_visible" in e]) == 1:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "select",
                            "type": "function",
                            "function": {
                                "name": "discover_tools",
                                "arguments": json.dumps(
                                    {
                                        "groups": [
                                            "parameters"
                                            if mode.startswith("remove")
                                            else "geometry_basic"
                                        ]
                                    }
                                ),
                            },
                        },
                        {
                            "id": "cylinder",
                            "type": "function",
                            "function": {
                                "name": "cst_create_cylinder",
                                "arguments": json.dumps(
                                    {
                                        "component": "Body",
                                        "name": "Rod",
                                        "axis": "z",
                                        "outer_radius": 5,
                                        "range_min": 0,
                                        "range_max": 10,
                                        "material": "PEC",
                                    }
                                ),
                            },
                        },
                    ],
                }
                finish = "tool_calls"
            else:
                message, finish = {"role": "assistant", "content": "DONE"}, "stop"
            return httpx2.Response(
                200,
                json={
                    "id": "offline",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "offline",
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                },
            )

        http = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
        client = AsyncOpenAI(
            base_url="https://offline.invalid/v1",
            api_key="offline",
            max_retries=0,
            http_client=http,
        )

        def make(name, schema, state=state, events=events):
            async def invoke(_ctx, raw):
                args = json.loads(raw)
                if name not in state["dispatch"]:
                    result = {"status": "blocked", "reason": "not_active_in_originating_request"}
                elif name == "discover_tools":
                    result = discovery(state, args["groups"])
                else:
                    result = mock_call(state, name, args)
                events.append({"invoked": name, "result": result})
                return json.dumps(result)

            return FunctionTool(
                name=name,
                description="Offline timing demonstration.",
                params_json_schema=schema,
                strict_json_schema=False,
                on_invoke_tool=invoke,
                is_enabled=lambda _ctx, _agent: name in visible(state),
            )

        tools = [
            make(
                "discover_tools",
                {
                    "type": "object",
                    "properties": {"groups": {"type": "array", "items": {"type": "string"}}},
                    "required": ["groups"],
                },
            )
        ]
        for name, definition in SCHEMAS["tools"].items():
            tools.append(make(name, definition["inputSchema"]))
        try:
            agent = Agent(
                name="offline-batch-demo",
                tools=tools,
                model=OpenAIChatCompletionsModel(model="offline", openai_client=client),
                model_settings=ModelSettings(parallel_tool_calls=True),
            )
            result = await Runner.run(
                agent,
                "Synthetic timing demonstration",
                max_turns=2,
                run_config=RunConfig(
                    tracing_disabled=True, tool_not_found_behavior="return_error_to_model"
                ),
            )
            records.append(
                {
                    "mode": mode,
                    "events": events,
                    "final": result.final_output,
                    "objects": state["objects"],
                    "network_requests": 0,
                }
            )
        finally:
            await client.close()
    path = Path(__file__).with_name("offline_lifecycle.json")
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
