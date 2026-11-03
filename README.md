# Context-Aware Neural Machine Translation — Research MVP

Research implementation for the paper *"Context-Aware Neural Machine Translation: Improving Semantic
Preservation of Idiomatic, Sarcastic, and Context-Dependent Expressions"* (Fauzdar & Sonawane, VIT Vellore).

> **Status: all 7 milestones of the software are complete. The research question is not answered yet.**
> What exists: a working system, an experiment pipeline, an evaluation and annotation framework, and dev-data pilots.
> What is missing: a team-written held-out test set, a frozen decision rule, human ratings, and the FLORES devtest run.
> The paper's SPR values (55.0% → 77.7%) are simulated planning numbers, not measurements.

## Scope at a glance

| | |
|---|---|
| Translation model | `facebook/nllb-200-distilled-600M`, **unchanged** (no fine-tuning), pinned revision `f8d333a…` |
| Active languages | **English, Hindi, German.** Spanish was removed on 2026-11-02 (no Spanish-speaking evaluator) |
| Active directions (4) | English → Hindi · Hindi → English · English → German · German → English |
| Planned, **not tested** (6) | Hindi → German · German → Hindi · French → Arabic · Arabic → Hindi · Chinese → French · Swahili → Hindi |
| Idiom processing | Rule-based (lexicon + cue words); 21 English, 6 Hindi, 8 German entries, **all AI-written drafts awaiting human review** |
| Context processing | Rule-based selection over 10 ambiguous English words; **no pronoun-resolution module** |
| Sarcasm | **No sarcasm detector**; sarcasm is an evaluation category only |
| Human evaluation | **One evaluator** (fluent in Hindi, English and German) rates all four directions; no inter-rater agreement (kappa) can be reported |

## What it does (in one example)

Previous sentence: *"The fisherman sat beside the river."* Current sentence: *"He went to the bank."*

| System | Text sent to NLLB-200 | Hindi output |
|---|---|---|
| Baseline (condition A) | He went to the bank. | वह बैंक में गया। ("into the bank") |
| Proposed (selected context) | He went to the **riverbank**. | वह नदी के तट पर गया। ("on the riverbank") |

The translation model `facebook/nllb-200-distilled-600M` is **never modified** (revision `f8d333a…`, no fine-tuning).
Small rule-based modules sit in front of it; a controller decides, for each sentence, to **pass it through**,
**intervene** (controlled paraphrase / hint / explicit word sense) or **abstain**, and logs why.

- **M1 Idiom module**: "She spilled the beans" → "She revealed the secret" (but not "spilled the beans on the floor");
  German: "Du nimmst mich auf den Arm" → "Du hältst mich zum Narren" (but not "Die Mutter nimmt das Kind auf den Arm").
- **M2 Selective context**: uses only *relevant* earlier sentences, to pick the meaning of an ambiguous word.
- **M3 Sarcasm**: not implemented; sarcasm is an evaluation category only.

## Quick start (demo, one server)

Requirements: Python 3.11+ (tested on 3.13), Node 20+ (tested on 22), ~4 GB free RAM, ~3 GB disk for the model.

```bash
git clone https://github.com/Riyaa-tech/Context-aware-translation-system
cd Context-aware-translation-system
python3 -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # skip on a CUDA machine
pip install -r backend/requirements.txt                              # or requirements-lock.txt for exact versions
```

```bash
cd frontend
npm ci
npm run build
cd ..
```

```bash
cd backend
NLLB_PRELOAD=1 uvicorn app.main:app --port 8000
```

Open **http://localhost:8000**. The first start downloads the model (~2.4 GB).

## The research app

| Page | What it shows |
|---|---|
| **Translate** | Minimal translator: optional preceding context, sentence, input/output language (English, Hindi, German), translation with Copy. Uses the proposed system (idiom + selected-context modules) through `/api/translate/enhanced` — one model call |
| **Pipeline** | The real logged backend events for the last translation (idiom candidates, context scores, controller decision, NLLB input, output), plus a *Compare with baseline* button (condition A) |
| **Experiments** | All conditions of a stored run; BLEU/chrF++ and SPR shown as **"unavailable"** until measured, never as 0 |
| **Annotate** | Blinded human rating (system and category hidden), batch creation, CSV/JSONL export |
| **Dashboard** | Run history, datasets, model configuration, per-direction results, confidence intervals, error analysis, report downloads |

**Demo script (presentation).** On the Translate page, type these examples:
1. English → Hindi: "She finally spilled the beans about the surprise party." then the literal "He spilled the beans all over
   the kitchen floor." — the idiom is paraphrased; the literal sentence is left alone.
2. German → English: "Das glaube ich dir nicht, du nimmst mich auf den Arm!" → "…you're making a fool of me!";
   "Die Mutter nimmt das weinende Kind auf den Arm." is left unchanged.
3. English → Hindi, sentence "He went to the bank.": with context "The fisherman sat beside the river." it becomes
   "riverbank"; with context "My cousin called me yesterday." it does not.
4. Open **Research ▾ → Pipeline** to show why the controller decided, and press *Compare with baseline*.
Start the server with `NLLB_PRELOAD=1` beforehand so the model is loaded before the first translation.

Development mode with hot reload: `cd frontend && npm run dev` (proxies `/api` to port 8000).

## Running the research workflow

```bash
# 1. Data
python scripts/fetch_flores.py                                   # FLORES-200, checksum-verified, 10 directions
python scripts/validate_dataset.py experiments/datasets/challenge_set/<file>.jsonl
python scripts/make_split.py pool.jsonl challenge_test.jsonl --seed 20261101

# 2. Experiments (each run gets its own folder in experiments/runs/; never overwritten)
python scripts/run_experiment.py experiments/configs/pilot_dev.yaml       # dev pilot, all conditions
python scripts/run_experiment.py experiments/configs/flores_smoke_dev.yaml      # en→hi
python scripts/run_experiment.py experiments/configs/flores_smoke_dev_de.yaml   # en→de
python scripts/run_experiment.py --resume <experiment_id>
python scripts/run_experiment.py --list

# 3. Human annotation, then evaluation
python scripts/create_annotation_batch.py <experiment_id>               # raters use the Annotate page
python scripts/evaluate_run.py <experiment_id> [--batch <batch_id>]     # writes experiments/metrics + reports
python scripts/summarize_run.py <experiment_id>

# Module checks on dev data (no model needed)
python scripts/eval_idiom_detector.py        # defaults to idiom_dev_v2.jsonl
python scripts/eval_context_module.py        # defaults to context_dev_v2.jsonl
```

**Main experiment** (`experiments/configs/main_test.yaml`) runs only after the team has (1) written and validated
`challenge_test.jsonl`, (2) frozen the lexicon/inventory/thresholds, and (3) filled in and committed
`experiments/configs/decision_rule.yaml` with `frozen: true`. The runner refuses test runs otherwise.

## Experimental conditions

| Key | System |
|---|---|
| A | Plain NLLB-200 |
| B_hint / B_paraphrase | + idiom module (inline hint / controlled paraphrase) |
| C_selected | + selected context |
| C_concat | Control: all previous sentences prepended, no selection |
| D_paraphrase / D_hint | Idiom + selected context |
| E | Not implemented (no validated sarcasm module) |

## Tests

```bash
cd backend
pytest                                   # 192 unit/API tests; translation model MOCKED
RUN_MODEL_TESTS=1 pytest -m model -s     # 15 tests with the REAL NLLB-200 model
```

```bash
cd frontend
npm test                                 # 4 tests
```

## API (main endpoints)

| Endpoint | Purpose |
|---|---|
| `GET /health` · `GET /api/languages` · `GET /api/system/run-info` | Status, directions, versions/hardware |
| `POST /api/translate/baseline` · `/enhanced` · `/compare` | Translation (enhanced returns the decision record and pipeline events) |
| `GET /api/experiments/conditions` · `POST /api/experiments/run` · `GET /api/experiments[/{id}[/results]]` | Experiments |
| `GET /api/annotations/rubric` · `POST /api/annotations/batches` · `GET/POST /api/annotations` · `GET /api/annotations/export` | Human annotation |
| `GET /api/research/metrics` · `/ablation` · `/datasets` · `/reports` · `/errors` | Metrics and dashboard data |
| `GET /api/idioms` · `GET /annotate-lite` | Lexicon; simple rating page (no frontend build needed) |

Interactive API docs: http://localhost:8000/docs. Settings: `.env.example`.

## Repository layout

```
backend/app/        api · pipeline · modules (M1, M2) · controller · translation · experiments · evaluation · annotation
backend/resources/  idiom lexicon, sense inventory (draft)
backend/tests/      192 mocked + 15 real-model tests
frontend/           React + Vite + TypeScript research app
experiments/        configs · datasets · runs · metrics · reports
scripts/            CLI tools listed above
docs/               see below
```

## Documentation

| Document | Content |
|---|---|
| `docs/ARCHITECTURE.md` | Components, request and experiment flow |
| `docs/METHODOLOGY.md` | What the implementation actually does, vs the paper |
| `docs/EXPERIMENT_PROTOCOL.md` | Conditions, controls, procedure |
| `docs/DATASET_GUIDE.md` | Schema, provenance, rules for test items |
| `docs/EVALUATION.md` | Metrics, annotation workflow, statistics |
| `docs/PILOT_FINDINGS.md` | What the dev pilots show (not results) |
| `docs/LIMITATIONS.md` | Known limitations and what has not been done |
| `docs/DECISIONS.md` | Technical decisions log |
| `docs/NEXT_STEPS_ASSISTANT_PROMPT.md` | Prompt for an AI assistant that guides the team through the remaining steps |
| `docs/REPOSITORY_AUDIT.md` · `docs/IMPLEMENTATION_PLAN.md` | Milestone 0 audit and plan |

## Next steps for the research team

1. Write ~100–150+ test items with controls (template: `experiments/datasets/challenge_set/TEMPLATE_challenge_items.jsonl`); include idioms *not* in the lexicon.
2. The evaluator reviews the Hindi and German lexicon entries (currently `draft`; German meanings were checked
   against Duden, everything else is AI-written), then the team freezes lexicon, sense inventory and thresholds.
3. Freeze the decision rule, then run `main_test.yaml`.
4. The evaluator rates the blinded batch (all four directions). With one evaluator, report the single-rater
   limitation; no kappa or inter-rater reliability can be claimed.
5. Run FLORES devtest for the enabled directions on a GPU (≈ 7 CPU-hours per condition otherwise).
6. `evaluate_run.py --batch …` → report measured SPR, ΔSPR, CIs and McNemar p-values, positive or negative.

## Licences

Code: as chosen by the repository owners. NLLB-200 checkpoints: CC-BY-NC 4.0 (non-commercial research use).
FLORES-200: CC-BY-SA 4.0. Development datasets in this repo are manually authored and labelled as such.
