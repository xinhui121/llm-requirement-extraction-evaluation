import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from evaluate import evaluate, read_rows
from extract import prepare_request
from responses_client import OpenAIResponsesAPIError, _post_openai_response
from structured_output_schema_compat import find_openai_strict_compatibility_issues


class PublicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.records = read_rows(ROOT / "samples/inputs.jsonl")
        self.predictions = read_rows(ROOT / "samples/illustrative_predictions.jsonl")

    def test_schema_validity_does_not_hide_factual_errors(self):
        metrics, errors = evaluate(self.records, self.predictions)
        self.assertEqual(1.0, metrics["structured_output"]["schema_validity_rate"])
        self.assertEqual(0.5, metrics["requirement_extraction"]["domain_specific_accuracy"])
        self.assertEqual(0.5, metrics["requirement_extraction"]["seniority_accuracy"])
        self.assertEqual(1, metrics["unsupported_categorical_assertions"]["field_occurrence_count"])
        self.assertEqual(["synthetic-002"], [row["eval_id"] for row in errors])
        self.assertNotIn("final_system_output", metrics)
        self.assertNotIn("final_recommendation", errors[0]["gold_extraction"])

    def test_invalid_schema_preserves_total_case_denominator(self):
        self.predictions[1]["raw_output"]["unexpected"] = True
        metrics, _ = evaluate(self.records, self.predictions)
        self.assertEqual(2, metrics["case_count"])
        self.assertEqual(0.5, metrics["structured_output"]["schema_validity_rate"])
        self.assertEqual(1, metrics["numerator_denominator"]["domain_specific_accuracy"]["denominator"])

    def test_missing_extra_or_duplicate_predictions_fail(self):
        for predictions in [self.predictions[:1], self.predictions + [self.predictions[0]], [{**self.predictions[0], "eval_id": "unknown"}, self.predictions[1]]]:
            with self.subTest(count=len(predictions)):
                with self.assertRaises(ValueError):
                    evaluate(self.records, predictions)

    def test_downstream_scoring_requires_real_supplied_decisions(self):
        with self.assertRaises(ValueError):
            evaluate(self.records, self.predictions, include_downstream=True)

    def test_request_excludes_labels_and_candidate_context(self):
        config = json.loads((ROOT / "config/demo.json").read_text())
        config["model_id"] = "test-model"
        record = deepcopy(self.records[0])
        record["gold"] = {"sentinel": "DO_NOT_SEND_REFERENCE_6721"}
        record["candidate"] = {"sentinel": "DO_NOT_SEND_PROFILE_9283"}
        payload, schema = prepare_request(record, config, "v2")
        serialised = json.dumps(payload)
        self.assertNotIn("DO_NOT_SEND_REFERENCE_6721", serialised)
        self.assertNotIn("DO_NOT_SEND_PROFILE_9283", serialised)
        self.assertIn(record["full_jd_text"], payload["input"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertNotIn("tools", payload)
        self.assertNotIn("temperature", payload)
        self.assertEqual([], find_openai_strict_compatibility_issues(schema))

    def test_request_rejects_non_openai_endpoint(self):
        config = json.loads((ROOT / "config/demo.json").read_text())
        config.update(model_id="test-model", api_endpoint="https://example.invalid/responses")
        with self.assertRaises(ValueError):
            prepare_request(self.records[0], config, "v1")

    def test_api_error_message_redacts_credential(self):
        import io
        import urllib.error
        from unittest.mock import patch
        credential = "test-only-credential-keep-private"
        error = urllib.error.HTTPError("https://api.openai.com/v1/responses", 401, "unauthorized", {}, io.BytesIO(json.dumps({"error": {"message": f"Invalid credential {credential}"}}).encode()))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(OpenAIResponsesAPIError) as caught:
                _post_openai_response("https://api.openai.com/v1/responses", credential, {})
        self.assertNotIn(credential, str(caught.exception))

    def test_existing_output_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / "metrics.json"
            sentinel.write_text("preserve existing results")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate.py"), "--output-dir", folder], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("preserve existing results", sentinel.read_text())

    def test_archived_copies_match_recorded_provenance(self):
        provenance = json.loads((ROOT / "docs/source_provenance.json").read_text())
        for artifact in provenance["artifacts"]:
            with self.subTest(path=artifact["public_path"]):
                actual = hashlib.sha256((ROOT / artifact["public_path"]).read_bytes()).hexdigest()
                self.assertEqual(artifact["public_sha256"], actual)

if __name__ == "__main__":
    unittest.main()
