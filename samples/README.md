# Synthetic examples

All examples were written for this public release. They use fictional employers and contain no copied source JD text, personal contacts or private candidate profiles. They were never part of the 25-case benchmark.

- `inputs.jsonl`: synthetic JD text and author-written reference extractions (`gold` denotes a reference, not a claim of independent human labelling).
- `expected_outputs.jsonl`: corresponding correct example outputs, written by the release author.
- `illustrative_predictions.jsonl`: manually constructed demonstration outputs, including deliberate domain-specific and seniority errors in `synthetic-002`. These are not API responses or new experimental results.

```bash
python3 scripts/evaluate.py --predictions samples/expected_outputs.jsonl
python3 scripts/evaluate.py --predictions samples/illustrative_predictions.jsonl
```

The second command demonstrates that 2/2 schema-valid outputs can still have field-level errors. The first command checks the fixture format against its own reference; its perfect score is not evidence of model performance.

The public demo request sends only JD text plus the chosen frozen prompt. Gold annotations are not sent to the API. To evaluate a single live response, supply a labelled records file containing exactly that same ID; the evaluator rejects missing predictions.
