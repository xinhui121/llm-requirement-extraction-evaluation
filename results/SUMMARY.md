# Recorded experiment results

These are the original 25-case pilot aggregates, separate from the public synthetic examples. Fractions retain the small-sample denominator.

| Metric | Development v1 | Development v2 | Holdout v1 | Holdout v2 |
|---|---:|---:|---:|---:|
| Schema validity | 20/20 (100%) | 20/20 (100%) | 5/5 (100%) | 5/5 (100%) |
| Experience years: exact | 20/20 (100%) | 20/20 (100%) | 5/5 (100%) | 4/5 (80%) |
| Experience years: compatible | 20/20 (100%) | 20/20 (100%) | 5/5 (100%) | 5/5 (100%) |
| Essential vs desirable | 17/20 (85%) | 16/20 (80%) | 3/5 (60%) | 4/5 (80%) |
| Domain-specific experience | 8/20 (40%) | 10/20 (50%) | 4/5 (80%) | 5/5 (100%) |
| Seniority | 14/20 (70%) | 16/20 (80%) | 5/5 (100%) | 4/5 (80%) |
| Final recommendation | 6/20 (30%) | 6/20 (30%) | 1/5 (20%) | 1/5 (20%) |

## Unsupported categorical assertions

| Split | Cases v1 → v2 | Field assertions v1 → v2 |
|---|---:|---:|
| Development | 13 → 12 | 20 → 16 |
| Holdout | 2 → 1 | 2 → 1 |

Development domain-specific and seniority accuracy improved, while essential/desirable accuracy regressed. Holdout domain-specific, essential/desirable and permanent-work-authorisation fields improved, while experience-year exactness and seniority regressed. Both prompts were schema-valid on 25/25 cases.

Across all 25 cases, both prompts reached 7/25 (28%) exact downstream recommendation accuracy. The separate gold-extraction audit observed 10/25 (40%): 8/20 development and 2/5 holdout. This diagnoses an additional gate/adapter limitation relative to the labels; it is not a theoretical ceiling.

Development comparison recorded 9 fixed field errors, 5 regressed field errors and 2 previously correct cases becoming incorrect. These counts are preserved in `development_case_comparison_summary.json`.

The schema/field scoring denominators and unsupported-assertion proxy are defined in [methodology](../docs/methodology.md). Source paths and hashes for the byte-for-byte result copies are in [provenance](../docs/source_provenance.json). Full case-level evidence is withheld with the raw corpus. Five holdout cases do not support broad generalisation claims.
