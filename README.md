# Context-Aware Neural Machine Translation — Research MVP

Research implementation for the paper *"Context-Aware Neural Machine Translation: Improving Semantic
Preservation of Idiomatic, Sarcastic, and Context-Dependent Expressions"* (Fauzdar & Sonawane, VIT Vellore).

> **Status: Milestone 2 of 7 (idiom module done).** No experimental results exist yet.
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
| `POST /api/translate/enhanced` | Idiom module + controller → NLLB (`idiom_mode`: `hint` or `paraphrase`); returns decision record and pipeline events |
| `POST /api/translate/compare` | Baseline and enhanced side by side |
| `GET /api/idioms` | Idiom lexicon (all entries currently `draft`, not human-reviewed) |

Enabled directions: en→hi, hi→en, en→es, es→en. The other six directions from the paper are configured but
blocked until tested (`ALLOW_PLANNED_DIRECTIONS=1` overrides this). Settings: see `.env.example`.

## Tests

```bash
cd backend
pytest                                   # unit tests; model is MOCKED
RUN_MODEL_TESTS=1 pytest -m model -s     # REAL NLLB-200 model smoke tests
```

## Idiom module tools

```bash
python scripts/eval_idiom_detector.py      # detector P/R/F1 on the dev set (no model needed)
python scripts/run_idiom_dev_demo.py       # REAL model: baseline vs hint vs paraphrase on dev items
```

Outputs go to `experiments/metrics/` and `experiments/predictions/` with timestamps (never overwritten).

## Licences

NLLB-200 checkpoints: CC-BY-NC 4.0 (non-commercial research use). FLORES-200: CC-BY-SA 4.0.

## Docs

- `docs/REPOSITORY_AUDIT.md` — Milestone 0 audit
- `docs/IMPLEMENTATION_PLAN.md` — plan and paper alignment
- `docs/DECISIONS.md` — technical decisions
- `docs/LIMITATIONS.md` — known limitations
