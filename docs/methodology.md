# Evaluation and reproducibility

## Frozen experiment

The experiment evaluated 25 independently human-labelled, source-verified job descriptions. Five additional unlabelled candidates in the private preparation set were excluded from pilot metrics. The fixed split contains 20 development and 5 holdout cases. Prompt v2 was designed from development extraction errors and the gold-extraction audit; holdout case-level comparisons were excluded from prompt design.

Each model request contained one JD and one frozen prompt. Human labels, historical decisions and candidate information were excluded from model input. The original workflow validated and normalised the extraction, mapped it into the existing deterministic gate, then scored both extraction and final recommendations.

Historical settings are recorded in `config/experiment_protocol.json` and `config/recorded/`. They retain the original model identifier, `gpt-5.6-terra`, low reasoning effort, 1,800 output-token cap, `store=false`, strict `text.format` JSON Schema and no tools. These are records of the experiment, not an assertion that this model is currently available. The recorded JSON configurations reference private files and the original `LLM_JOB_EVAL_API_KEY` environment-variable name; they are archival, not public CLI configurations. The public demo uses `config/demo.json`, `OPENAI_API_KEY` and an explicitly supplied model.

## Metrics

- **Schema validity:** valid structured outputs / all cases.
- **Field accuracy:** exact matches against gold among schema-valid outputs. Report schema validity alongside field accuracy: invalid outputs are excluded from field denominators.
- **Experience years:** exact `(min_years, max_years)` match, plus a separate compatible-range metric. Matching null ranges are compatible; unknown versus known ranges are not.
- **Essential/desirable, domain-specific, seniority:** exact match to the frozen categorical labels.
- **Work-authorisation fields:** exact comparisons, with case/whitespace normalisation for the two wording fields. General UK work eligibility does not automatically imply no sponsorship or permanent permission.
- **Unsupported categorical assertions:** fields stronger than gold under the original requirement/seniority ordering, a positive domain-specific flag absent in gold, or an assertion where the corresponding gold work-authorisation field is unstated. This is a defined proxy, not a universal factuality measure.
- **Critical omissions:** weaker/absent critical structured fields under the original scoring rules.
- **Skills:** normalised literal list differences support error review; equivalent phrases can differ, so these are not treated as a semantic skill-accuracy score.
- **Downstream metrics:** exact six-class recommendation accuracy, hard-blocker precision/recall and false-skip/false-actionable rates. These require supplied gate decisions and candidate-specific gold; the public evaluator can score those with `--include-downstream` but does not generate them.

The public evaluator defaults to extraction-only scoring. It supplies neutral compatibility metadata internally to the unchanged combined pilot scorer and removes all downstream-decision metrics from its report. No candidate fit or recommendation is inferred. Prediction IDs must match labelled IDs exactly; missing/duplicate cases fail rather than silently changing the denominator.

## What can be reproduced publicly

- Run synthetic inputs and score supplied predictions offline.
- Inspect both frozen prompts, all three schemas and the fixed split.
- Inspect the request configuration offline or make an optional one-case API call.
- Review unchanged aggregate results and their source hashes.
- Inspect the prompt change plan and prompt diff.

Full third-party JDs, case-level model evidence, reviewer identifiers, source archives and private candidate/tracker context remain outside this repository. Their redistribution rights have not been established. Consequently the public package alone cannot independently rerun the original 25-case benchmark or downstream gate. Hashes support artifact integrity; they do not substitute for access to the data or establish external validation.

`docs/source_provenance.json` maps public files to relative original paths and hashes. Prompt/schema/config/result copies are byte-for-byte copies. `src/metrics.py` and `src/responses_client.py` retain selected original function bodies verbatim, with imports and module documentation adjusted to remove private tracker dependencies. The two CLI wrappers and synthetic samples were added for public use. Original experiment files were left unchanged.

## Error analysis and downstream audit

Development comparison recorded 9 fixed field errors and 5 regressed field errors; 2 previously correct cases became incorrect. Error categories overlap. Prompt v2 targeted domain-specific experience, seniority, literal negation, essential/desirable distinctions and separate work-authorisation fields.

The gold-extraction audit observed 10/25 correct downstream recommendations. It diagnoses policy/adapter mismatch relative to the frozen annotation policy; it does not prove a mathematical upper bound on other systems. Its 12 development mismatches were attributed to 9 gate-policy mismatches, 2 adapter mappings and 1 annotation-policy mismatch in the original audit. These attribution counts are reported from the private audit, whose case-level evidence is withheld.

One reviewer, one model configuration and one run per prompt limit interpretation. With five holdout cases, a single changed result moves accuracy by 20 percentage points. The held-out findings describe this pilot and do not establish population-level reliability or hiring suitability.
