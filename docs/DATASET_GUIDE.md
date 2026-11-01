# Dataset Guide

## 1. Challenge set (semantic preservation)

One JSON object per line (JSONL). Validate with:

```bash
python scripts/validate_dataset.py experiments/datasets/challenge_set/<file>.jsonl
```

### Required fields

| Field | Type | Meaning |
|---|---|---|
| `example_id` | string | Unique, stable ID (e.g. `IDIOM_T_001`) |
| `source_language`, `target_language` | NLLB code | e.g. `eng_Latn`, `hin_Deva`, `spa_Latn` |
| `category` | string | See categories below |
| `source_text` | string | The sentence to translate |
| `context` | list of strings | Preceding sentences, oldest first (`[]` if none) |
| `intended_meaning` | string | What the sentence means, in plain words (used by raters) |
| `reference_translation` | string or `null` | Only if a fluent person wrote one. **Never invent references.** |
| `provenance` | string | Who wrote it / where it came from, licence, who checked it |
| `split` | `dev` / `test` / `unassigned` | Use `scripts/make_split.py` to assign |

### Optional gold labels (for detector/controller metrics)
`gold_idiom_id`, `gold_usage` (`figurative`/`literal`/`none`), `gold_context_state`, `gold_sense`.

### Categories

| Phenomenon | Target items | Controls (needed to detect harm) |
|---|---|---|
| Idioms | `idiom` | `idiom_literal_control` (same idiom used literally), `no_idiom_control` |
| Sarcasm | `sarcasm` | `sincere_control` (same positive words meant sincerely) |
| Context | `context` | `context_irrelevant_control`, `context_missing_control`, `context_independent_control`, `context_ambiguous_control`, `no_ambiguity_control`, `pronoun_reference` |

Paper targets: 400 idiom / 300 sarcasm / 300 context = 1,000 items. These are **plans**, not existing data.

## 2. Rules for the TEST split (paper IV-D, V-B)

1. **Write test items after freezing** the idiom lexicon, sense inventory and thresholds. No edits afterwards.
2. **Test items should be written or checked by project members**, not by the AI assistant that wrote the rules
   (otherwise items may unconsciously favour the rules).
3. A fluent speaker must confirm that idioms/sarcasm still work in non-English source items.
4. Remove exact duplicates (the validator checks); review near-duplicates by hand.
5. No single language, phenomenon or famous expression should dominate. Cells with < 10 items are flagged as small.
6. Include idioms that are **not** in the lexicon, too — otherwise recall is overestimated.
7. Record provenance and licence for every item. Label hand-written items "manually authored".
8. Assign splits with a recorded seed: `python scripts/make_split.py pool.jsonl challenge_test.jsonl --seed 20261101`.

A template is in `experiments/datasets/challenge_set/TEMPLATE_challenge_items.jsonl`.

## 3. Current files

| File | Split | Items | Provenance |
|---|---|---:|---|
| `idiom_dev.jsonl` | dev | 53 | Manually authored by Claude (AI assistant); development only |
| `context_dev.jsonl` | dev | 50 | Manually authored by Claude (AI assistant); development only; some labels corrected (see `label_revisions`) |
| `sarcasm_dev.jsonl` | dev | 10 | Manually authored by Claude (AI assistant); development only |
| `challenge_test.jsonl` | test | — | **Does not exist yet. To be written by the research team.** |

None of these is an established benchmark.

## 4. Resources

| File | Content | Status |
|---|---|---|
| `backend/resources/idioms/lexicon.json` | 33 idioms (21 EN, 6 HI, 6 ES) | all `draft` (not human-reviewed) |
| `backend/resources/senses/sense_inventory.json` | 10 ambiguous English words | `draft` |

## 5. FLORES-200 (general quality)
Integrated in Milestone 5 (devtest split; the release used will be recorded).
