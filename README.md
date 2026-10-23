# LLM Requirement Extraction for Recruitment Decision Support

## Project Overview

A Python evaluation project exploring how reliably an LLM can extract structured recruitment requirements from job descriptions. It compares two frozen prompts against human labels and separates extraction quality from downstream decision logic.

## Problem

Valid JSON can still contain incorrect requirements. A useful evaluation must test field accuracy, unsupported assertions and the effect of downstream rules independently of output structure.

## Approach

- **25 human-labelled job descriptions**, with a fixed **20 development / 5 holdout** split.
- **OpenAI Responses API** with strict JSON Schema structured outputs.
- **Two frozen prompt versions**; v2 designed using development errors only.
- Field-level evaluation of experience, essential/desirable requirements, domain-specific experience, seniority and work-authorisation wording.
- Error analysis and a separate **gold-extraction audit**: feed human-labelled extraction into the unchanged downstream gate to isolate policy/adapter errors.
- Reproducible experiment records: frozen hashes, split membership, configuration and aggregate results.

## Key Findings

Both prompts produced schema-valid output on **25/25 cases (100%)**. Factual accuracy remained mixed:

| Metric | Development: v1 → v2 | Holdout: v1 → v2 |
|---|---:|---:|
| Domain-specific accuracy | 8/20 → 10/20 | 4/5 → 5/5 |
| Seniority accuracy | 14/20 → 16/20 | 5/5 → 4/5 |
| Essential/desirable accuracy | 17/20 → 16/20 | 3/5 → 4/5 |
| Experience-year exact match | 20/20 → 20/20 | 5/5 → 4/5 |
| Permanent/indefinite work-authorisation accuracy | 20/20 → 20/20 | 4/5 → 5/5 |
| Unsupported categorical assertions | 20 → 16 | 2 → 1 |

**v2 improved some fields and regressed on others.** Unsupported-assertion cases fell from 13/20 to 12/20 in development and 2/5 to 1/5 in holdout. These assertions are defined by structured-label comparisons, rather than a comprehensive hallucination audit.

Final recommendation accuracy remained **7/25 (28%)** for both prompts. Even human-gold extraction achieved only **10/25 (40%)** through the existing downstream gate, exposing a separate policy/adapter limitation. This is an observed audit result, not a theoretical performance ceiling.

See [results summary](results/SUMMARY.md) and [metric definitions](docs/methodology.md).

## What I Learned

- Schema-valid output does not guarantee factual accuracy.
- AI systems need systematic testing against explicit references.
- Compare alternatives across a fixed dataset rather than relying on individual examples.
- Separate extraction errors from downstream decision logic.
- Reproducibility and error analysis make mixed results useful.

## Repository Structure

```text
src/          Original extraction client, metrics and schema validators
scripts/      Small public demo and offline evaluation entry points
prompts/      Frozen v1 and v2 prompts
schemas/      Output and annotation contracts
config/       Demo settings, historical configurations and fixed split
results/      Original aggregate metrics and comparison summaries
samples/      Synthetic inputs, expected outputs and illustrative errors
docs/         Methodology, prompt changes and source provenance
tests/        Offline checks for scoring, data handling and API requests
```

**Data policy:** Full third-party job descriptions, contact details, reviewer identifiers, candidate profiles and raw case-level results are excluded. All public examples are synthetic and were created for this release; they are separate from the 25-case experiment. See [samples](samples/README.md).

## How to Run

Use **Python 3.9+**. The public code uses only the standard library; `requirements.txt` documents this.

```bash
# Offline: score synthetic predictions, including deliberate factual errors.
python3 scripts/evaluate.py

# Inspect a request configuration without credentials or an API call.
python3 scripts/extract.py

# Run offline checks.
python3 -m unittest discover -s tests -v
```

For an optional billable extraction, set `OPENAI_API_KEY` in your shell using your normal secret-management method, then specify a Responses model available to your account:

```bash
python3 scripts/extract.py --live --model YOUR_MODEL_ID \
  --prompt-version v2 --eval-id synthetic-001 --output runs/sample-output.jsonl
```

The demo reads credentials only from the environment. Generated files under `runs/` are ignored, and existing output files are never overwritten. Historical model/configuration identifiers are retained as recorded; their current availability is not assumed.

## Limitations

This is a small research prototype: **25 cases and only 5 holdout cases** cannot support broad statistical generalisation. Labels came from one reviewer, with one recorded run per prompt and no repeated-run variance study. Literal field/skill comparisons have ontology and wording limitations.

The public package runs synthetic examples and evaluates supplied predictions. Re-running the original benchmark requires the withheld corpus and private tracker context; the historical downstream gate is outside this package. Published aggregate metrics are unchanged. [Reproducibility details](docs/methodology.md).
