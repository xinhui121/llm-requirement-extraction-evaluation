#!/usr/bin/env python3
"""Demonstrate the original request builder on one input; dry run by default."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from responses_client import (
    OpenAIResponsesAPIError, _contains_tool_output, _extract_output_text,
    _post_openai_response, build_request_payload, non_sensitive_request_configuration,
)
from schema_validation import validate
from structured_output_schema_compat import assert_openai_strict_schema_compatible


def prepare_request(record, config, version):
    if config["api_endpoint"] != "https://api.openai.com/v1/responses":
        raise ValueError("Only the official OpenAI Responses endpoint is accepted")
    schema = json.loads((ROOT / config["llm_output_schema_path"]).read_text())
    assert_openai_strict_schema_compatible(schema)
    context = {
        "config": config, "schema": schema,
        "prompt": (ROOT / f"prompts/{version}.txt").read_text(),
        # A minimal object keeps labels and any private profile out of the request.
        "record": {"full_jd_text": record["full_jd_text"]},
    }
    return build_request_payload(context), schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=ROOT / "samples/inputs.jsonl")
    parser.add_argument("--eval-id", default="synthetic-001")
    parser.add_argument("--prompt-version", choices=["v1", "v2"], default="v2")
    parser.add_argument("--model", help="Responses model available to your account; required with --live")
    parser.add_argument("--live", action="store_true", help="Make one billable API request")
    parser.add_argument("--output", type=Path, help="New JSONL file for live output; existing files are never overwritten")
    args = parser.parse_args()
    if args.live and (not args.model or not args.output):
        parser.error("--live requires --model and --output")
    if args.output and args.output.exists():
        parser.error("Output already exists; choose a new path")
    records = [json.loads(line) for line in args.records.read_text().splitlines() if line.strip()]
    matches = [row for row in records if row["eval_id"] == args.eval_id]
    if len(matches) != 1:
        parser.error("eval-id must match exactly one input record")
    config = json.loads((ROOT / "config/demo.json").read_text())
    config["model_id"] = args.model or "MODEL_ID_REQUIRED_FOR_LIVE_RUN"
    payload, schema = prepare_request(matches[0], config, args.prompt_version)
    if not args.live:
        print(json.dumps({"mode": "dry_run_no_api_call", "eval_id": args.eval_id, "request_configuration": non_sensitive_request_configuration(payload)}, indent=2))
        return
    api_key = os.environ.get(config["api_key_env"])
    if not api_key:
        parser.error("OPENAI_API_KEY is not set")
    # Reserve the file before making a request, using exclusive creation.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        response = _post_openai_response(config["api_endpoint"], api_key, payload)
        if response.get("status") not in {None, "completed"} or _contains_tool_output(response):
            raise ValueError("Response was incomplete or contained unexpected tool output")
        output = json.loads(_extract_output_text(response))
        validate(output, schema)
        row = {"eval_id": args.eval_id, "raw_output": output, "prompt_version": args.prompt_version, "requested_model": args.model, "actual_model": response.get("model")}
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("One extraction saved. Evaluate only against corresponding labelled records.")


if __name__ == "__main__":
    try:
        main()
    except OpenAIResponsesAPIError as exc:
        # Provider messages can contain identifiers; display only status here.
        raise SystemExit(f"OpenAI request failed (HTTP {exc.diagnostic.get('status_code')}).") from None
    except (ValueError, KeyError, OSError, RuntimeError):
        raise SystemExit("Extraction failed. Check input/configuration and use a new output path before retrying.") from None
