# Prompt v2 change plan — frozen Pilot25

## Scope

Prompt v2 changes extraction instructions only. It does not change the output schema, frozen data, 20/5 split, candidate snapshot, deterministic quality gate, adapter policy, human gold, or production tracker.

The Prompt v1 oracle audit showed that correct extraction alone reaches 10/25 final-recommendation accuracy. This is a deterministic system limitation, not a target for Prompt v2.

## Development-only v1 evidence used

| Observed development extraction issue | Count | Prompt v2 response |
|---|---:|---|
| `experience.domain_specific` mismatch | 12 cases | Require explicit prior-domain experience/knowledge; exclude employer industry, title and responsibilities as evidence. |
| Unsupported categorical inferences | 13 cases / 20 field assertions | Default to safe schema values when direct evidence is absent; require evidence spans for restrictive claims. |
| `seniority` mismatch | 6 cases | Use years, early-career wording, ownership, management and specialist evidence jointly; do not decide from title alone. |
| Experience requirement-level mismatch | 3 cases | Add literal negation and essential-versus-preferred rules. |
| RTW field mismatches | 6 cases | Separate work authorisation, sponsorship, permanent RTW, citizenship, residency and clearance; forbid cross-field inference. |

Skill-list exact-string differences are deliberately not a Prompt v2 target because the current metric treats semantically equivalent wording as unequal.

## Frozen v1 → v2 changes

1. Add an evidence discipline for all eligibility-critical structured fields.
2. Tighten `domain_specific` to prior-domain requirements only, with explicit anti-industry/title/responsibility counterexamples.
3. Make seniority a multi-signal decision rather than a title-driven decision.
4. Expand literal handling of negation and essential/preferred wording.
5. Split every RTW-related field and state default-safe behaviour when the JD is silent.
6. Explicitly prohibit skill wording optimisation against any unseen reference.

No final-recommendation instruction, candidate-profile information, gold label, historical decision, or deterministic-gate policy has been added to Prompt v2.
