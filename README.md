# Context-Aware Neural Machine Translation — Research MVP

Research implementation for the paper *"Context-Aware Neural Machine Translation: Improving Semantic
Preservation of Idiomatic, Sarcastic, and Context-Dependent Expressions"* (Fauzdar & Sonawane, VIT Vellore).

> **Status: Milestone 4 of 7 (experiment runner done; dev pilot only — no test data yet).** No experimental results exist yet.
> The SPR values in the paper (55.0% → 77.7%) are simulated planning numbers, not measurements.

The backbone is `facebook/nllb-200-distilled-600M`, used **unchanged** (no fine-tuning), pinned to
revision `f8d333a098d19b4fd9a8b18f94170487ad3f821d`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only; skip for GPU
pip install -r backend/requirements.txt
```

The first translation downloads the model (~2.4 GB) into the Hugging Face cache.

## Run the API

```bash
cd backend
NLLB_PRELOAD=1 uvicorn app.main:app --port 8000
```

```bash
curl -X POST localhost:8000/api/translate/baseline -H 'content-type: application/json' \
  -d '{"text":"He went to the bank.","source_lang":"en","target_lang":"hi"}'
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Server and model status |
| `GET /api/languages` | Languages and the 10 study directions (4 enabled, 6 planned) |
| `GET /api/system/run-info` | Package versions, hardware, model revision, decoding settings |
| `POST /api/translate/baseline` | Condition A: plain NLLB-200 |
| `POST /api/translate/enhanced` | Semantic modules + controller → NLLB. `modules`: `idiom`, `context`; `idiom_mode`: `paraphrase` (default) or `hint`; `context_mode`: `selected` (default) or `concat` (diagnostic control); `context`: preceding sentences. Returns decision record and pipeline events |
| `POST /api/translate/compare` | Baseline and enhanced side by side |
| `GET /api/experiments/conditions` | Experimental conditions (E listed as not implemented) |
| `POST /api/experiments/run` | Start/resume a run in the background (`config_file` under `experiments/configs/`) |
| `GET /api/experiments` | Experiment history |
| `GET /api/experiments/{id}` | Manifest of one run |
| `GET /api/experiments/{id}/results` | Per-condition decision/intervention summaries (quality metrics come in Milestone 5) |
| `GET /api/idioms` | Idiom lexicon (all entries currently `draft`, not human-reviewed) |

Enabled directions: en→hi, hi→en, en→es, es→en. The other six directions from the paper are configured but
blocked until tested (`ALLOW_PLANNED_DIRECTIONS=1` overrides this). Settings: see `.env.example`.

## Tests

```bash
cd backend
pytest                                   # unit tests; model is MOCKED
RUN_MODEL_TESTS=1 pytest -m model -s     # REAL NLLB-200 model smoke tests
```

## Experiments

```bash
python scripts/run_experiment.py experiments/configs/pilot_dev.yaml   # DEV pilot, all conditions
python scripts/run_experiment.py --resume <experiment_id>             # continue an interrupted run
python scripts/run_experiment.py --list
python scripts/validate_dataset.py <file.jsonl>                       # check a challenge-set file
```

Each run gets its own folder in `experiments/runs/` (never overwritten). Test-split runs are refused until
`experiments/configs/decision_rule.yaml` is filled in and frozen. See `docs/EXPERIMENT_PROTOCOL.md` and
`docs/DATASET_GUIDE.md`.

## Module tools (development data only)

```bash
python scripts/eval_idiom_detector.py      # idiom detector P/R/F1 on the dev set (no model needed)
python scripts/eval_context_module.py      # context state/sense accuracy on the dev set (no model needed)
python scripts/run_dev_explore.py --dataset experiments/datasets/challenge_set/context_dev.jsonl \
    --conditions A,C_selected,C_concat     # REAL model, exploratory dev outputs
```

Outputs go to `experiments/metrics/` and `experiments/predictions/` with timestamps (never overwritten).

## Licences

NLLB-200 checkpoints: CC-BY-NC 4.0 (non-commercial research use). FLORES-200: CC-BY-SA 4.0.

## Docs

- `docs/REPOSITORY_AUDIT.md` — Milestone 0 audit
- `docs/IMPLEMENTATION_PLAN.md` — plan and paper alignment
- `docs/DATASET_GUIDE.md` — dataset schema, provenance, rules for test items
- `docs/EXPERIMENT_PROTOCOL.md` — conditions, controls, procedure
- `docs/DECISIONS.md` — technical decisions
- `docs/LIMITATIONS.md` — known limitations
