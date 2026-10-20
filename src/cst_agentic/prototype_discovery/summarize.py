"""THROWAWAY: summarize retained safe evidence; never invokes model or CST."""

import json
from pathlib import Path

HERE = Path(__file__).parent
rows = []
for filename, label in (
    ("transcripts.json", "initial"),
    ("continued_transcripts.json", "continued"),
    ("retry_2026_10_20_transcripts.json", "2026-10-20 retry"),
    ("revised_30turns_transcripts.json", "revised 30-turn"),
    ("revised_30turns_remaining_transcripts.json", "revised 30-turn remaining"),
    ("revised_30turns_final_transcripts.json", "revised 30-turn final"),
):
    path = HERE / filename
    if not path.exists():
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload["records"]:
        events = record["events"]
        requests = [e for e in events if e["kind"] == "request"]
        assistant = [e for e in events if e["kind"] == "assistant"]
        tools = [e for e in events if e["kind"] == "tool"]
        prompt = sum(e.get("usage", {}).get("prompt_tokens", 0) for e in assistant)
        completion = sum(e.get("usage", {}).get("completion_tokens", 0) for e in assistant)
        rows.append(
            {
                "run": label,
                "variant": record["variant"],
                "scenario": record["scenario"],
                "status": record.get("status", "not_recorded"),
                "max_turns": record["max_turns"],
                "run_budget": payload["budget"],
                "requests": len(requests),
                "successful_responses": len(assistant),
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "max_visible": max((len(e["visible"]) for e in requests), default=0),
                "latency_s": round(sum(e.get("latency_s", 0) for e in requests), 3),
                "discovery": [e["result"] for e in tools if e["name"] == "discover_tools"],
                "tools": [
                    {"name": e["name"], "arguments": e["arguments"], "result": e["result"]}
                    for e in tools
                    if e["name"] != "discover_tools"
                ],
                "final_output": record.get("final_output"),
                "error_type": record.get("error_type"),
            }
        )
(HERE / "measurements.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows, indent=2))
