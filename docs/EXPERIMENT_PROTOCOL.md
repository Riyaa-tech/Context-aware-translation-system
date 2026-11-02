# Experiment Protocol

## Conditions

| Key | Paper | Pipeline | Purpose |
|---|---|---|---|
| `A` | A | NLLB only | Baseline |
| `B_hint` | B | Idiom module, inline hint | Idiom handling (hint form) |
| `B_paraphrase` | B | Idiom module, controlled paraphrase | Idiom handling (paraphrase form) |
| `C_selected` | C | Selected context → meaning-explicit sentence | Context effect |
| `C_concat` | control | All window sentences prepended; last output sentence kept | Does *selection* matter vs unfiltered context? |
| `D_paraphrase` | D | Idiom (paraphrase) + selected context | Combined effect |
| `D_hint` | D | Idiom (hint) + selected context | Combined effect (hint form) |
| `E` | E* | — | **Not implemented** (no validated sarcasm module) |

Active directions: en→hi, hi→en, en→de, de→en (Spanish removed 2026-11-02). The seven conditions are
unchanged by the scope change and every condition runs on all four directions.

Fixed across all conditions: model `facebook/nllb-200-distilled-600M` @ `f8d333a…`, decoding (beam 4, no sampling,
max 256 new tokens), examples, directions, scorer versions. Ordinary sentences and literal/irrelevant-context
controls are included so unnecessary changes show up.

## Procedure

1. **Freeze** the lexicon, sense inventory and all thresholds (commit hash recorded in the run manifest via the config).
2. Team writes test items (en↔hi and en↔de, incl. German idioms and literal controls) → `scripts/validate_dataset.py` → `scripts/make_split.py` with a recorded seed.
3. Fill in and commit `experiments/configs/decision_rule.yaml` (`frozen: true`) **before** the test run.
   The runner refuses test runs otherwise.
4. Run: `python scripts/run_experiment.py experiments/configs/main_test.yaml`
   (resumable: `--resume <experiment_id>`).
5. Blind human annotation of all conditions' outputs by the project's single evaluator (Hindi, English, German);
   report the single-rater limitation (no kappa).
6. Compute metrics and statistics from stored predictions + annotations (no re-translation needed).

## Run outputs (`experiments/runs/<experiment_id>/`)

- `config.json` — frozen config + hash
- `manifest.json` — status, dataset file hashes, example IDs, directions, per-condition progress, decision counts,
  latency, package versions, hardware, model revision, consistency check
- `predictions/<condition>.jsonl` — one full decision record per example, written after every batch

Dev runs are marked `reportable: false` and "DEV RUN".

## Controls answered

| Question | Comparison |
|---|---|
| Does the idiom module help idioms? | `B_*` vs `A` on `idiom` |
| Hint or paraphrase? | `B_hint` vs `B_paraphrase` |
| Does selected context help? | `C_selected` vs `A` on `context` |
| Selected vs unfiltered context? | `C_selected` vs `C_concat` |
| Complementary modules? | `D_*` vs `B_*`, `C_selected` |
| Harm to ordinary sentences? | all variants vs `A` on control categories (harmful-intervention rate) |
