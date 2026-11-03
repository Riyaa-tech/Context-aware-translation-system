# Architecture

## Overview

```
                        ┌──────────────────────── React app (frontend/) ─────────────────────────┐
                        │ Translate · Pipeline · Experiments · Annotate · Dashboard              │
                        └───────────────────────────────┬────────────────────────────────────────┘
                                                        │ JSON over HTTP (/api/...)
┌──────────────────────────────────────── FastAPI (backend/app) ─────────────────────────────────────────┐
│ api/            routes: translate, experiments, annotations, research, resources, health                │
│                                                                                                         │
│ pipeline.py     SemanticPipeline:  input ─► M1 idiom detection ─► M2 context analysis ─► controller      │
│                                    ─► (rewrite) ─► NLLB-200 (unchanged) ─► decision record + events     │
│ modules/        idiom_lexicon · idiom_detector · idiom_resolver · sense_inventory · context_selector     │
│                 rewrite · text_utils                                                                    │
│ controller/     semantic_controller  (PASS_THROUGH / INTERVENE / ABSTAIN, conflicts, thresholds)        │
│ translation/    nllb_engine (cached model, batching, forced target token) · run_info                    │
│ experiments/    conditions · datasets (validation, splits) · runner (checkpoint/resume, manifests)      │
│ evaluation/     overlap_metrics (BLEU/spBLEU/chrF++) · spr · statistics · run_metrics · report          │
│ annotation/     rubric · store (SQLite, blinded batches, export)                                        │
└──────────────┬──────────────────────────────┬──────────────────────────────┬──────────────────────────┘
               │                              │                              │
   backend/resources/               experiments/                   experiments/annotations/
   idioms/lexicon.json              datasets/ (challenge, FLORES)  annotations.sqlite3 (git-ignored;
   senses/sense_inventory.json      configs/  runs/  metrics/      export to share)
                                    reports/
```

## Request flow

The Translate page calls `POST /api/translate/enhanced` (proposed system, one NLLB call). `POST /api/translate/compare`
(baseline + proposed, two NLLB calls) and `POST /api/translate/baseline` remain available; the Pipeline page uses
`/baseline` only when the user asks for a comparison.

1. Validate the direction (only enabled directions; `config/languages.py`).
2. Baseline (`/compare`, `/baseline` only): `NLLBEngine.translate(text)` → condition A.
3. Proposed: `SemanticPipeline.run(text, context)`:
   - `IdiomDetector.detect` → candidates with usage label and rule score
   - `ContextSelector.analyze` → per ambiguous word: state, selected sentences, resolved sense
   - `SemanticController.decide` → decision + per-span reasons + conflicts
   - rewrites applied to the source (idiom hint/paraphrase, explicit sense word)
   - `NLLBEngine.translate(nllb_input)`; every step appended as a timed event
4. Response = translation(s) + full decision record + events (the Pipeline page renders these events).

## Experiment flow

`scripts/run_experiment.py <config>` → `ExperimentRunner.create` (validate config, datasets, decision-rule guard)
→ `run` (per condition, per direction, per batch: `prepare` → `translate_batch` → `finalize` → append JSONL,
update manifest atomically) → consistency check. `scripts/evaluate_run.py` reads stored predictions (+ ratings)
and never re-translates.

## Key design points

| Point | Where |
|---|---|
| Language scope: en↔hi, en↔de active; Spanish retired with an explanatory error | `config/languages.py` |
| NLLB is never modified; one shared GenerationConfig for every condition | `translation/nllb_engine.py`, `config/settings.py` |
| Deterministic controller; all thresholds in frozen dataclasses and logged per record | `controller/`, `modules/*Config` |
| NLLB always receives one sentence (except the explicit `concat` control) | `pipeline.py` |
| Failures kept with `status: error`; truncation and alignment warnings recorded | `nllb_engine.py`, `pipeline.py` |
| Runs never overwritten; resume repairs torn lines; dataset hashes checked | `experiments/runner.py` |
| Raters never see condition or category | `annotation/store.py` |
| Unmeasured metrics are `{"available": false, "reason": ...}` / `null`, never 0 | `evaluation/report.py`, frontend `lib/format.ts` |

## Tech stack

Python 3.13 · FastAPI · PyTorch (CPU) · Transformers 4.57 · SacreBLEU 2.6 · SQLite · React 18 · Vite 5 ·
TypeScript · Tailwind 3 · Recharts 2. Exact versions: `backend/requirements-lock.txt`, `frontend/package-lock.json`.

## Tests

| Suite | Count | Model |
|---|---:|---|
| `backend/tests` (default) | 192 | **mocked** (`FakeEngine`) |
| `backend/tests -m model` (`RUN_MODEL_TESTS=1`) | 15 | **real** NLLB-200 |
| `frontend` (`npm test`) | 4 | no backend |
