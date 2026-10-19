"""Disposable, credential-safe SDK contract probe. Offline unless --live is explicit.

Run with the original project's installed environment, without syncing dependencies.
Live use requires --config-root pointing to the existing configured project. No MCP imports.
"""

import argparse
import asyncio
import importlib.metadata
import json
import logging
import os
import sys
from pathlib import Path


class Incompatibility(Exception):
    """A safe fixed-category probe assertion failed."""


def require(condition):
    if not condition:
        raise Incompatibility()


async def main():
    logging.disable(logging.CRITICAL)
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"
    os.environ["OPENAI_AGENTS_DONT_LOG_MODEL_DATA"] = "1"
    os.environ["OPENAI_AGENTS_DONT_LOG_TOOL_DATA"] = "1"

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
    from openai import AsyncOpenAI

    set_tracing_disabled(True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--config-root", type=Path)
    args = parser.parse_args()
    state = {"requests": 0, "phase": "setup", "responses": [], "wire": []}
    safe_names = {"probe_alpha", "probe_beta", "probe_gamma"}
    tokens = {"probe_alpha": 17, "probe_beta": 29, "probe_gamma": 41}
    invoked = []

    def emit(**data):
        print(json.dumps(data, sort_keys=True), flush=True)

    if args.live:
        require(args.config_root is not None)
        # Match config.py precedence. Do not invoke its loader, which creates a work directory.
        values = dotenv_values(args.config_root / ".env")

        def resolve(name):
            value = values.get(name)
            if value is not None and value.strip():
                return value.strip()
            return os.environ.get(name, "").strip()

        configured = {n: resolve(n) for n in ("SKYNET_BASE_URL", "SKYNET_API_KEY", "AGENT")}
        emit(configuration_presence={n: bool(v) for n, v in configured.items()})
        require(all(configured.values()))
        base_url = configured["SKYNET_BASE_URL"]
        api_key = configured["SKYNET_API_KEY"]
        model_name = configured["AGENT"]
        underlying = httpx2.AsyncHTTPTransport(retries=0)
    else:
        base_url, api_key, model_name = "https://offline.invalid/v1", "offline", "offline"

        async def mock(request):
            body = json.loads(request.content)
            messages = body["messages"]
            if messages[-1]["role"] == "tool" or state["phase"] == "none":
                text = {"alpha": "17", "beta": "29"}.get(state["phase"], "DONE")
                message = {"role": "assistant", "content": text}
                finish = "stop"
            else:
                names = {
                    "alpha": ["probe_alpha"],
                    "beta": ["probe_beta"],
                    "named": ["probe_beta"],
                    "multiple": ["probe_beta", "probe_gamma"],
                }[state["phase"]]
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"synthetic_{state['requests']}_{i}",
                            "type": "function",
                            "function": {"name": n, "arguments": '{"value":7}'},
                        }
                        for i, n in enumerate(names)
                    ],
                }
                finish = "tool_calls"
            return httpx2.Response(
                200,
                json={
                    "id": "synthetic_completion",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "offline",
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                },
            )

        underlying = httpx2.MockTransport(mock)

    origin = httpx2.URL(base_url)

    class BudgetTransport(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request):
            # Count at the actual transport boundary, including any unexpected SDK loop.
            require(state["requests"] < 8)
            require(request.method == "POST" and request.url.path.endswith("/chat/completions"))
            require(
                (request.url.scheme, request.url.host, request.url.port)
                == (origin.scheme, origin.host, origin.port)
            )
            body = json.loads(request.content)
            tools = body.get("tools", [])
            names = [t["function"]["name"] for t in tools]
            require(set(names) <= safe_names)
            strict = all(
                t["function"]["strict"] is True
                and t["function"]["parameters"]["additionalProperties"] is False
                and t["function"]["parameters"]["required"] == ["value"]
                for t in tools
            )
            require(strict)
            calls = {}
            results = {}
            for message in body["messages"]:
                for call in message.get("tool_calls", []):
                    calls[call["id"]] = call["function"]["name"]
                if message["role"] == "tool":
                    results[message["tool_call_id"]] = message["content"]
            require(set(calls) == set(results))
            preserved = all(
                record["id"] in calls and calls[record["id"]] == record["name"]
                for record in state["responses"]
                if state["phase"] in {"alpha", "beta"}
            )
            require(preserved)
            omitted_old = "probe_alpha" not in names and "probe_alpha" in calls.values()
            if state["phase"] == "beta":
                require(names == ["probe_beta"] and omitted_old)
            for call_id, name in calls.items():
                require(name in safe_names)
                require(json.loads(results[call_id]) == {"mock_token": tokens[name]})
            state["requests"] += 1
            state["wire"].append({"phase": state["phase"], "names": names})
            emit(
                request=state["requests"],
                phase=state["phase"],
                visible=names,
                strict_schema=strict,
                matched_history_pairs=len(calls),
                response_ids_preserved=preserved,
                old_tool_omitted_with_history=omitted_old,
                tool_choice_named=isinstance(body.get("tool_choice"), dict),
                tool_choice=body.get("tool_choice")
                if isinstance(body.get("tool_choice"), str)
                else None,
                parallel_tool_calls=body.get("parallel_tool_calls"),
            )
            return await underlying.handle_async_request(request)

        async def aclose(self):
            await underlying.aclose()

    async def response_hook(response):
        emit(status=response.status_code, phase=state["phase"])
        if response.status_code >= 300:
            return
        await response.aread()
        payload = response.json()
        choices = payload.get("choices", [])
        require(bool(choices))
        message = choices[0]["message"]
        calls = message.get("tool_calls") or []
        names = [c.get("function", {}).get("name") for c in calls]
        require(set(names) <= safe_names)
        for call in calls:
            require(bool(call.get("id")))
            require(json.loads(call["function"]["arguments"]) == {"value": 7})
            state["responses"].append({"id": call["id"], "name": call["function"]["name"]})
        finish = choices[0].get("finish_reason")
        emit(
            native_calls=len(calls),
            names=names,
            phase=state["phase"],
            finish_reason=finish if finish in {"stop", "tool_calls", "length"} else "other",
        )

    http = httpx2.AsyncClient(
        transport=BudgetTransport(),
        timeout=httpx2.Timeout(90.0, connect=15.0),
        follow_redirects=False,
        event_hooks={"response": [response_hook]},
    )
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        max_retries=0,
        timeout=90.0,
        http_client=http,
    )
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
    config = RunConfig(tracing_disabled=True, tool_not_found_behavior="return_error_to_model")

    def tool(name):
        async def invoke(_context, raw):
            require(json.loads(raw) == {"value": 7})
            invoked.append(name)
            return json.dumps({"mock_token": tokens[name]})

        return FunctionTool(
            name=name,
            description="Harmless synthetic lookup. Use value 7.",
            params_json_schema={
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            strict_json_schema=True,
            on_invoke_tool=invoke,
        )

    def agent(names, choice, parallel=False, stop=False):
        return Agent(
            name="synthetic-contract-probe",
            model=model,
            instructions="Use only the requested synthetic tools. Never invent their results.",
            tools=[tool(n) for n in names],
            model_settings=ModelSettings(
                tool_choice=choice,
                parallel_tool_calls=parallel,
                max_tokens=1024,
                timeout=100.0,
            ),
            tool_use_behavior="stop_on_first_tool" if stop else "run_llm_again",
        )

    async def run(a, text):
        return await asyncio.wait_for(Runner.run(a, text, max_turns=2, run_config=config), 190.0)

    emit(
        mode="live" if args.live else "offline",
        budget=8,
        versions={p: importlib.metadata.version(p) for p in ["openai-agents", "openai", "httpx2"]},
    )
    try:
        state["phase"] = "alpha"
        first = await run(
            agent(["probe_alpha"], "required"),
            "Call probe_alpha exactly once with value 7, then reply with its mock_token only.",
        )
        require(invoked == ["probe_alpha"] and "17" in str(first.final_output))
        history = first.to_input_list()
        state["phase"] = "beta"
        second = await run(
            agent(["probe_beta"], "required"),
            history
            + [
                {
                    "role": "user",
                    "content": "Call probe_beta exactly once with value 7, "
                    "then reply with its mock_token only.",
                }
            ],
        )
        require(invoked == ["probe_alpha", "probe_beta"] and "29" in str(second.final_output))
        emit(core_changed_schema_round_trip_passed=True)

        state["phase"] = "none"
        before = len(invoked)
        await run(agent(["probe_beta"], "none"), "Do not call a tool. Reply DONE.")
        require(len(invoked) == before)
        emit(none_passed=True)

        state["phase"] = "named"
        before = len(invoked)
        await run(
            agent(["probe_beta"], "probe_beta", stop=True),
            "Call probe_beta exactly once with value 7.",
        )
        require(invoked[before:] == ["probe_beta"])
        emit(named_passed=True)

        state["phase"] = "multiple"
        before = len(invoked)
        await run(
            agent(["probe_beta", "probe_gamma"], "auto", parallel=True),
            "In one assistant response call BOTH probe_beta and probe_gamma exactly once each, "
            "both with value 7. After both results reply DONE without further calls.",
        )
        require(sorted(invoked[before:]) == ["probe_beta", "probe_gamma"])
        emit(multiple_calls_round_trip_passed=True)
        if not args.live:
            try:
                await http.post(base_url.rstrip("/") + "/chat/completions", json={})
            except Incompatibility:
                emit(ninth_request_blocked=True)
            else:
                raise Incompatibility()
            require(state["requests"] == 8)
    except BaseException as exc:
        status = getattr(exc, "status_code", None)
        emit(
            stopped=True,
            phase=state["phase"],
            error_type=type(exc).__name__,
            status=status if isinstance(status, int) else None,
            requests=state["requests"],
        )
        return 1
    finally:
        await client.close()
        emit(total_requests=state["requests"], budget=8)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        print(json.dumps({"stopped": True, "error_type": type(exc).__name__}), flush=True)
        sys.exit(1)
