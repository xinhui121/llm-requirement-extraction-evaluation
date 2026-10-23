#!/usr/bin/env python3
"""Score supplied extractions using the original pilot metrics; no API calls."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from metrics import calculate_metrics, critical_field_omissions, unsupported_categorical_inferences
from schema_validation import SchemaValidationError, validate


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = [row["eval_id"] for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("Input must be nonempty and eval_id values must be unique")
    return rows


def evaluate(records, predictions, *, include_downstream=False):
    schema = json.loads((ROOT / "schemas/llm_output.schema.json").read_text())
    record_ids = [row["eval_id"] for row in records]
    prediction_ids = [row["eval_id"] for row in predictions]
    if not record_ids or len(record_ids) != len(set(record_ids)) or len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("Records and predictions must have unique IDs and records must be nonempty")
    if set(record_ids) != set(prediction_ids):
        raise ValueError("Records and predictions must contain exactly the same eval_id values")
    records_by_id = {row["eval_id"]: row for row in records}
    prepared_records, prepared_results = [], []
    unsupported, omissions = Counter(), Counter()
    unsupported_cases = omission_cases = 0
    for prediction in predictions:
        record = records_by_id[prediction["eval_id"]]
        gold = dict(record["gold"])
        gold_extraction = {key: value for key, value in gold.items() if key not in {"hard_blockers", "final_recommendation"}}
        validate(gold_extraction, schema)
        if include_downstream:
            if gold.get("final_recommendation") not in {"priority", "apply", "stretch", "ask_hr", "hold", "skip"} or not isinstance(gold.get("hard_blockers"), list):
                raise ValueError("Downstream evaluation requires gold recommendation and hard_blockers")
            decision = prediction.get("deterministic_final_recommendation")
            hard = prediction.get("deterministic_hard_blocker_detected")
            if decision not in {"priority", "apply", "stretch", "ask_hr", "hold", "skip"} or not isinstance(hard, bool):
                raise ValueError("Downstream evaluation requires an existing decision and boolean blocker result for every case")
        else:
            # Compatibility metadata for the unchanged combined pilot scorer.
            # Its downstream metrics are discarded below; no decision is inferred.
            gold.update(hard_blockers=[], final_recommendation="hold")
            decision, hard = "hold", False
        prepared_records.append({"eval_id": record["eval_id"], "gold": gold})
        raw = prediction.get("raw_output")
        error = None
        try:
            validate(raw, schema)
        except SchemaValidationError as exc:
            error = str(exc)
        prepared_results.append({
            "eval_id": record["eval_id"], "raw_llm_structured_output": raw,
            "schema_valid": error is None, "schema_error": error,
            "deterministic_final_recommendation": decision,
            "deterministic_hard_blocker_detected": hard,
        })
        if error is None:
            unsupported_fields = unsupported_categorical_inferences(gold, raw)
            omitted_fields = critical_field_omissions(gold, raw)
            unsupported.update(unsupported_fields)
            omissions.update(omitted_fields)
            unsupported_cases += bool(unsupported_fields)
            omission_cases += bool(omitted_fields)
    metrics, errors = calculate_metrics(prepared_records, prepared_results)
    if not include_downstream:
        del metrics["final_system_output"]
        metrics["eligibility_critical"] = {"rtw_blocker_recall": metrics["eligibility_critical"]["rtw_blocker_recall"]}
        for key in ["hard_blocker_precision", "hard_blocker_recall", "exact_final_recommendation_accuracy", "false_actionable", "false_skip"]:
            metrics["numerator_denominator"].pop(key)
        for row in errors:
            row.pop("gold_recommendation", None)
            row.pop("system_recommendation", None)
            row["gold_extraction"] = {key: value for key, value in row["gold_extraction"].items() if key not in {"hard_blockers", "final_recommendation"}}
    metrics["unsupported_categorical_assertions"] = {"case_count": unsupported_cases, "field_occurrence_count": sum(unsupported.values()), "by_field": dict(unsupported)}
    metrics["critical_field_omissions"] = {"case_count": omission_cases, "field_occurrence_count": sum(omissions.values()), "by_field": dict(omissions)}
    metrics["evaluation_scope"] = "extraction_and_supplied_downstream_decisions" if include_downstream else "extraction_only"
    return metrics, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=ROOT / "samples/inputs.jsonl")
    parser.add_argument("--predictions", type=Path, default=ROOT / "samples/illustrative_predictions.jsonl")
    parser.add_argument("--include-downstream", action="store_true", help="Score supplied recorded decisions; does not run a gate")
    parser.add_argument("--output-dir", type=Path, help="New directory only; existing directories are never overwritten")
    args = parser.parse_args()
    metrics, errors = evaluate(read_rows(args.records), read_rows(args.predictions), include_downstream=args.include_downstream)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (args.output_dir / "errors.jsonl").write_text("".join(json.dumps(row) + "\n" for row in errors))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f"Evaluation failed: {exc}") from None
