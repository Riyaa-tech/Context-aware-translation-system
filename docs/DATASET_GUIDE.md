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
| `source_language`, `target_language` | NLLB code | Active: `eng_Latn`, `hin_Deva`, `deu_Latn`. `spa_Latn` is **rejected** (Spanish removed 2026-11-02) |
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

### Coverage the final challenge set must include (active scope: en↔hi, en↔de)

| Need | Example of what to write (by a fluent human) |
|---|---|
| English idioms (→ Hindi and → German) | figurative uses, incl. idioms **not** in the lexicon |
| Hindi idioms (→ English) | written or checked by a fluent Hindi speaker |
| German idioms (→ English) | written or checked by a fluent German speaker; vary word order (main clause, question, subordinate clause, perfect, zu-infinitive) |
| Literal controls | the same idioms used literally (e.g. "Die Mutter nimmt das Kind auf den Arm") |
| Sarcasm + sincere controls | in all four directions where possible |
| Context-dependent items | each with relevant, irrelevant and missing context versions |
| Idioms absent from the lexicon | so that recall is not overestimated |
| Ordinary sentences | to detect unnecessary changes |

The evaluator speaks Hindi, English and German, so every item can be rated by the same person.

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
| `idiom_dev_v2.jsonl` | dev | 67 | Manually authored by Claude (AI assistant); EN/HI rows from v1; 22 new German rows (figurative, literal controls, expected misses, no-idiom) |
| `context_dev_v2.jsonl` | dev | 50 | Same as v1 but English→Spanish targets changed to English→German (`label_revisions`) |
| `sarcasm_dev_v2.jsonl` | dev | 11 | v1 without the Spanish-source row; Spanish targets → German; 2 new German rows |
| `legacy_v1_spanish/*.jsonl` | dev | 113 | **Unchanged v1 files (Spanish scope)**, kept as the record of the 2026-11-01 pilot run; rejected by the current validator |
| `challenge_test.jsonl` | test | — | **Does not exist yet. To be written by the research team.** |

None of these is an established benchmark.

## 4. Resources

| File | Content | Status |
|---|---|---|
| `backend/resources/idioms/lexicon.json` | 35 idioms (21 EN, 6 HI, 8 DE), version 0.2.0 | all `draft` (not human-reviewed); German meanings checked against Duden online, forms/paraphrases AI-written |
| `backend/resources/idioms/legacy/lexicon_v0.1_spanish_entries.json` | 6 removed Spanish idioms | record only |
| `backend/resources/senses/sense_inventory.json` | 10 ambiguous English words | `draft` |

## 5. FLORES-200 (general quality)
Original release archive (sha256 `b8b0b767…`). `scripts/fetch_flores.py` converts the 10 study directions
(including en↔de and hi↔de); FLORES dev → our `dev`, devtest → our `test`.
