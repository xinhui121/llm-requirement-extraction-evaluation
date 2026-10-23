"""Original pilot metrics and error analysis, detached from private tracker imports."""
from __future__ import annotations
import hashlib
import json
import re
from collections import Counter, defaultdict

LABELS = ["priority", "apply", "stretch", "ask_hr", "hold", "skip"]


ACTIONABLE = {"priority", "apply", "stretch"}


RTW_FIELDS = (
    "work_authorization_wording",
    "sponsorship_wording",
    "sponsorship_status",
    "permanent_or_indefinite_rtw_requirement",
    "citizenship",
    "residency",
    "clearance",
)


RTW_WORDING_FIELDS = {"work_authorization_wording", "sponsorship_wording"}


ERROR_TAXONOMY = {
    "negation", "essential_vs_desirable", "experience_years", "domain_specific",
    "seniority", "RTW", "clearance/residency", "missing_requirement",
    "unsupported_inference", "other",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else None


def score(numerator, denominator):
    """Keep the small-sample numerator/denominator alongside its rate."""
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": safe_div(numerator, denominator),
    }


def _range(extraction):
    experience = extraction["experience"]
    return experience["min_years"], experience["max_years"]


def ranges_compatible(left, right):
    if left == right:
        return True
    left_min, left_max = left
    right_min, right_max = right
    if left_min is None and left_max is None:
        return right_min is None and right_max is None
    if right_min is None and right_max is None:
        return False
    left_low = float("-inf") if left_min is None else left_min
    right_low = float("-inf") if right_min is None else right_min
    left_high = float("inf") if left_max is None else left_max
    right_high = float("inf") if right_max is None else right_max
    return max(left_low, right_low) <= min(left_high, right_high)


def _normalized_wording(value):
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def _rtw_field_equal(key, left, right):
    if key in RTW_WORDING_FIELDS:
        return _normalized_wording(left) == _normalized_wording(right)
    return left == right


def _requirement_is_stated(value):
    normalized = _normalized_wording(value)
    if normalized in {"", "not stated", "unknown", "none", "not required"}:
        return False
    if re.search(r"\bno (?:specific )?(?:citizenship|nationality|residency|clearance) requirement\b", normalized):
        return False
    return True


_REQUIREMENT_LEVEL_RANK = {"unknown": -1, "none": 0, "desirable": 1, "essential": 2}


_SENIORITY_RANK = {"unknown": -1, "graduate": 0, "entry": 1, "junior": 2, "mid": 3, "senior": 4}


_UNSTATED_VALUES = {"", "not stated", "unknown", "none", "not required", None}


def critical_field_omissions(gold, model):
    """Return gold-supported critical fields made weaker or absent by the model.

    This deliberately excludes free-text skill-list wording.  It is used for
    prompt evaluation only, where a field must map to an explicit structured
    contract rather than a synonym-sensitive skill phrase.
    """
    fields = []
    gold_experience = gold["experience"]
    model_experience = model["experience"]
    if _REQUIREMENT_LEVEL_RANK[model_experience["requirement_level"]] < _REQUIREMENT_LEVEL_RANK[gold_experience["requirement_level"]]:
        fields.append("experience.requirement_level")
    if gold_experience["domain_specific"] and not model_experience["domain_specific"]:
        fields.append("experience.domain_specific")
    if gold["seniority"] != "unknown" and model["seniority"] == "unknown":
        fields.append("seniority")
    for key in RTW_FIELDS:
        if gold["rtw"][key] not in _UNSTATED_VALUES and model["rtw"][key] in _UNSTATED_VALUES:
            fields.append(f"rtw.{key}")
    return fields


def unsupported_categorical_inferences(gold, model):
    """Return model assertions that are stricter than the structured gold field."""
    fields = []
    gold_experience = gold["experience"]
    model_experience = model["experience"]
    if _REQUIREMENT_LEVEL_RANK[model_experience["requirement_level"]] > _REQUIREMENT_LEVEL_RANK[gold_experience["requirement_level"]]:
        fields.append("experience.requirement_level")
    if model_experience["domain_specific"] and not gold_experience["domain_specific"]:
        fields.append("experience.domain_specific")
    if _SENIORITY_RANK[model["seniority"]] > _SENIORITY_RANK[gold["seniority"]]:
        fields.append("seniority")
    for key in RTW_FIELDS:
        if gold["rtw"][key] in _UNSTATED_VALUES and model["rtw"][key] not in _UNSTATED_VALUES:
            fields.append(f"rtw.{key}")
    return fields


def _work_authorization_hard_blocker(wording):
    return bool(re.search(
        r"(?:right to work|permission to work|work authori[sz]ation).{0,100}(?:full duration|duration of (?:the )?(?:role|contract)|time[- ]limited.{0,30}(?:not accepted|ineligible))"
        r"|(?:graduate visa|graduate route|time[- ]limited (?:visa|permission)).{0,80}(?:not accepted|not eligible|cannot be accepted)",
        str(wording),
        re.I,
    ))


def extraction_rtw_blocker(extraction):
    rtw = extraction["rtw"]
    return any([
        rtw["permanent_or_indefinite_rtw_requirement"] == "required",
        _work_authorization_hard_blocker(rtw["work_authorization_wording"]),
        _requirement_is_stated(rtw["citizenship"]),
        _requirement_is_stated(rtw["residency"]),
        _requirement_is_stated(rtw["clearance"]),
    ])


def gold_hard(record):
    return bool(record["gold"]["hard_blockers"]) or record["gold"]["final_recommendation"] == "skip"


def _skill_item_differences(gold_items, model_items):
    """Return explicit, field-local skill-list evidence.

    Skill strings are not currently backed by a controlled ontology.  This
    intentionally performs only normalized literal comparison; consumers must
    not interpret an unmatched phrase as a semantic model error without
    review.  Keeping the actual items makes that limitation auditable.
    """
    gold_by_key = {_normalized_wording(item): item for item in gold_items}
    model_by_key = {_normalized_wording(item): item for item in model_items}
    return {
        "omitted": [gold_by_key[key] for key in sorted(gold_by_key.keys() - model_by_key.keys())],
        "added": [model_by_key[key] for key in sorted(model_by_key.keys() - gold_by_key.keys())],
    }


def structured_field_differences(gold, model):
    """Compare structured fields and retain concrete evidence for every diff."""
    differing = []
    evidence = {}
    if _range(gold) != _range(model):
        differing.append("experience.years")
        evidence["experience.years"] = {"gold": _range(gold), "model": _range(model)}
    if gold["experience"]["requirement_level"] != model["experience"]["requirement_level"]:
        differing.append("experience.requirement_level")
        evidence["experience.requirement_level"] = {
            "gold": gold["experience"]["requirement_level"],
            "model": model["experience"]["requirement_level"],
        }
    if gold["experience"]["domain_specific"] != model["experience"]["domain_specific"]:
        differing.append("experience.domain_specific")
        evidence["experience.domain_specific"] = {
            "gold": gold["experience"]["domain_specific"],
            "model": model["experience"]["domain_specific"],
        }
    if gold["seniority"] != model["seniority"]:
        differing.append("seniority")
        evidence["seniority"] = {"gold": gold["seniority"], "model": model["seniority"]}
    for key in RTW_FIELDS:
        if not _rtw_field_equal(key, gold["rtw"][key], model["rtw"][key]):
            differing.append(f"rtw.{key}")
            evidence[f"rtw.{key}"] = {"gold": gold["rtw"][key], "model": model["rtw"][key]}
    for field in ("skills_required", "skills_preferred"):
        skill_difference = _skill_item_differences(gold[field], model[field])
        if skill_difference["omitted"]:
            differing.append(f"{field}.omitted")
            evidence[f"{field}.omitted"] = skill_difference["omitted"]
        if skill_difference["added"]:
            differing.append(f"{field}.added")
            evidence[f"{field}.added"] = skill_difference["added"]
    return {"differing_fields": differing, "field_evidence": evidence}


def differing_fields(gold, model):
    """Backward-compatible field-name-only view of structured differences."""
    return structured_field_differences(gold, model)["differing_fields"]


def error_categories(fields, gold, model):
    categories = set()
    if "experience.years" in fields:
        categories.add("experience_years")
        if gold["experience"]["requirement_level"] == "none" or model["experience"]["requirement_level"] == "none":
            categories.add("negation")
    if "experience.requirement_level" in fields:
        categories.add("essential_vs_desirable")
        if "none" in {gold["experience"]["requirement_level"], model["experience"]["requirement_level"]}:
            categories.add("negation")
    if "experience.domain_specific" in fields:
        categories.add("domain_specific")
    if "seniority" in fields:
        categories.add("seniority")
    if any(field.startswith("rtw.") for field in fields):
        categories.add("RTW")
    if any(field in {"rtw.residency", "rtw.clearance"} for field in fields):
        categories.add("clearance/residency")
    if any(field in {"skills_required.omitted", "skills_preferred.omitted"} for field in fields):
        categories.add("missing_requirement")
    if any(field in {"skills_required.added", "skills_preferred.added"} for field in fields):
        categories.add("unsupported_inference")
    return sorted(categories or {"other"})


def calculate_metrics(eval_records, results):
    by_id = {record["eval_id"]: record for record in eval_records}
    total = len(eval_records)
    valid = [result for result in results if result["schema_valid"]]
    counters = Counter()
    confusion = {gold: {prediction: 0 for prediction in LABELS} for gold in LABELS}
    errors = []
    for result in results:
        record = by_id[result["eval_id"]]
        if not result["schema_valid"]:
            errors.append({
                "eval_id": result["eval_id"], "gold_extraction": record["gold"], "model_extraction": None,
                "gold_recommendation": record["gold"]["final_recommendation"], "system_recommendation": None,
                "differing_fields": ["schema"], "error_category": ["other"], "schema_error": result["schema_error"],
            })
            continue
        gold = record["gold"]
        model = result["raw_llm_structured_output"]
        system = result["deterministic_final_recommendation"]
        counters["experience_exact"] += _range(gold) == _range(model)
        counters["experience_compatible"] += ranges_compatible(_range(gold), _range(model))
        counters["requirement_level"] += gold["experience"]["requirement_level"] == model["experience"]["requirement_level"]
        counters["domain_specific"] += gold["experience"]["domain_specific"] == model["experience"]["domain_specific"]
        counters["seniority"] += gold["seniority"] == model["seniority"]
        gold_rtw = extraction_rtw_blocker(gold)
        model_rtw = extraction_rtw_blocker(model)
        counters["rtw_tp"] += gold_rtw and model_rtw
        counters["rtw_fn"] += gold_rtw and not model_rtw
        rtw_matches = []
        for key in RTW_FIELDS:
            matched = _rtw_field_equal(key, gold["rtw"][key], model["rtw"][key])
            counters[f"rtw_field_{key}"] += matched
            rtw_matches.append(matched)
        counters["rtw_all_fields"] += all(rtw_matches)
        predicted_hard = result["deterministic_hard_blocker_detected"]
        actual_hard = gold_hard(record)
        counters["hard_tp"] += actual_hard and predicted_hard
        counters["hard_fn"] += actual_hard and not predicted_hard
        counters["hard_fp"] += not actual_hard and predicted_hard
        counters["recommendation_exact"] += gold["final_recommendation"] == system
        if system in LABELS:
            confusion[gold["final_recommendation"]][system] += 1
        gold_actionable = gold["final_recommendation"] in ACTIONABLE and not gold["hard_blockers"]
        counters["gold_actionable"] += gold_actionable
        counters["false_skip"] += gold_actionable and system == "skip"
        gold_non_actionable_hard = actual_hard
        counters["gold_hard"] += gold_non_actionable_hard
        counters["false_actionable"] += gold_non_actionable_hard and system in ACTIONABLE
        comparison = structured_field_differences(gold, model)
        fields = comparison["differing_fields"]
        if gold["final_recommendation"] != system:
            fields.append("final_recommendation")
            comparison["field_evidence"]["final_recommendation"] = {
                "gold": gold["final_recommendation"], "model": system,
            }
        if fields:
            categories = error_categories(fields, gold, model)
            assert set(categories) <= ERROR_TAXONOMY
            errors.append({
                "eval_id": result["eval_id"], "gold_extraction": gold, "model_extraction": model,
                "gold_recommendation": gold["final_recommendation"], "system_recommendation": system,
                "differing_fields": fields, "field_evidence": comparison["field_evidence"],
                "error_category": categories,
            })
    valid_count = len(valid)
    metrics = {
        "case_count": total,
        "structured_output": {"schema_valid_count": valid_count, "schema_validity_rate": safe_div(valid_count, total)},
        "requirement_extraction": {
            "experience_year_exact_match": safe_div(counters["experience_exact"], valid_count),
            "experience_year_compatible_match": safe_div(counters["experience_compatible"], valid_count),
            "essential_vs_desirable_accuracy": safe_div(counters["requirement_level"], valid_count),
            "domain_specific_accuracy": safe_div(counters["domain_specific"], valid_count),
            "seniority_accuracy": safe_div(counters["seniority"], valid_count),
            "rtw_field_accuracy": {
                key: safe_div(counters[f"rtw_field_{key}"], valid_count)
                for key in RTW_FIELDS
            },
            "rtw_all_fields_exact_match": safe_div(counters["rtw_all_fields"], valid_count),
            "sponsorship_status_accuracy": safe_div(counters["rtw_field_sponsorship_status"], valid_count),
        },
        "eligibility_critical": {
            "rtw_blocker_recall": safe_div(counters["rtw_tp"], counters["rtw_tp"] + counters["rtw_fn"]),
            "hard_blocker_recall": safe_div(counters["hard_tp"], counters["hard_tp"] + counters["hard_fn"]),
            "hard_blocker_precision": safe_div(counters["hard_tp"], counters["hard_tp"] + counters["hard_fp"]),
        },
        "final_system_output": {
            "exact_recommendation_accuracy": safe_div(counters["recommendation_exact"], valid_count),
            "confusion_matrix": confusion,
            "false_skip_count": counters["false_skip"],
            "false_skip_rate": safe_div(counters["false_skip"], counters["gold_actionable"]),
            "false_actionable_count": counters["false_actionable"],
            "false_actionable_rate": safe_div(counters["false_actionable"], counters["gold_hard"]),
        },
    }
    metrics["numerator_denominator"] = {
        "schema_validity": score(valid_count, total),
        "experience_year_exact_match": score(counters["experience_exact"], valid_count),
        "experience_year_compatible_match": score(counters["experience_compatible"], valid_count),
        "essential_vs_desirable_accuracy": score(counters["requirement_level"], valid_count),
        "domain_specific_accuracy": score(counters["domain_specific"], valid_count),
        "seniority_accuracy": score(counters["seniority"], valid_count),
        "rtw_blocker_recall": score(counters["rtw_tp"], counters["rtw_tp"] + counters["rtw_fn"]),
        "hard_blocker_precision": score(counters["hard_tp"], counters["hard_tp"] + counters["hard_fp"]),
        "hard_blocker_recall": score(counters["hard_tp"], counters["hard_tp"] + counters["hard_fn"]),
        "exact_final_recommendation_accuracy": score(counters["recommendation_exact"], valid_count),
        "false_actionable": score(counters["false_actionable"], counters["gold_hard"]),
        "false_skip": score(counters["false_skip"], counters["gold_actionable"]),
    }
    for key in RTW_FIELDS:
        metrics["numerator_denominator"][f"rtw_{key}_accuracy"] = score(
            counters[f"rtw_field_{key}"], valid_count
        )
    return metrics, errors


def load_predictions(path):
    predictions = {}
    for record in read_jsonl(path):
        eval_id = record.get("eval_id")
        raw = record.get("raw_output", record.get("output"))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                pass
        predictions[eval_id] = raw
    return predictions
