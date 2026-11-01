# Run summary: `pilot_dev_20261101T104108Z_89efe420c3f8`

- Status: **complete**; split: **dev**; reportable: **False**
- NOTE: DEV RUN - development data, not reportable as results
- Examples: 113; directions: eng_Latn-hin_Deva, eng_Latn-spa_Latn, hin_Deva-eng_Latn, spa_Latn-eng_Latn
- Model: facebook/nllb-200-distilled-600M @ f8d333a098d19b4fd9a8b18f94170487ad3f821d
- Same example IDs in every condition: True

> Descriptive only. "Output changed" means the final translation differs from condition A; it says nothing
> about whether meaning was preserved. That requires human ratings (strict SPR).

## Per condition

| Condition | Intervene | Abstain | Pass | Output changed vs A | Errors | Median module ms | Median translation ms/item |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0 | 0 | 113 | 0/113 | 0 | 0.0 | 641.4 |
| B_hint | 29 | 0 | 84 | 25/113 | 0 | 0.05 | 637.0 |
| B_paraphrase | 29 | 0 | 84 | 29/113 | 0 | 0.06 | 664.9 |
| C_selected | 13 | 25 | 75 | 8/113 | 0 | 0.03 | 666.7 |
| C_concat | 0 | 0 | 113 | 27/113 | 0 | 0.0 | 772.1 |
| D_paraphrase | 42 | 25 | 46 | 37/113 | 0 | 0.11 | 640.0 |
| D_hint | 42 | 25 | 46 | 33/113 | 0 | 0.1 | 621.8 |

## Output changed vs A, by category

| Category | n | B_hint | B_paraphrase | C_selected | C_concat | D_paraphrase | D_hint |
|---|---:|---:|---:|---:|---:|---:|---:|
| context | 17 | 0 | 0 | 8 | 13 | 8 | 8 |
| context_ambiguous_control | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| context_independent_control | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| context_irrelevant_control | 12 | 0 | 0 | 0 | 10 | 0 | 0 |
| context_missing_control | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| idiom | 34 | 25 | 29 | 0 | 0 | 29 | 25 |
| idiom_literal_control | 13 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_ambiguity_control | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_idiom_control | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| pronoun_reference | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| sarcasm | 6 | 0 | 0 | 0 | 2 | 0 | 0 |
| sincere_control | 4 | 0 | 0 | 0 | 1 | 0 | 0 |

## Interventions on control items (possible over-intervention)

- None.

## Concat control

- Items with a sentence-alignment warning: 13/39 (items with context)
