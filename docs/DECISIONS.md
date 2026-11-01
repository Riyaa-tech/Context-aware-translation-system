# Technical Decisions

| # | Date | Decision | Why |
|---|---|---|---|
| D1 | 2026-11-01 | Backend: FastAPI + Transformers; frontend: React (Vite); storage: SQLite + JSONL | Repo was empty; smallest stack that meets the spec |
| D2 | 2026-11-01 | Pin `facebook/nllb-200-distilled-600M` to revision `f8d333a098d19b4fd9a8b18f94170487ad3f821d` | Reproducibility |
| D3 | 2026-11-01 | Decoding: beam 4, no sampling, max 256 new tokens, inputs truncated at 512 tokens (truncation reported) | Deterministic; identical across conditions |
| D4 | 2026-11-01 | Only en↔hi and en↔es enabled; other 6 paper directions blocked until tested | Never claim untested directions |
| D5 | 2026-11-01 | M1 idiom usage check = transparent cue rules, not an XLM-R classifier | Paper IX-A: classifiers only once labelled data exists. Rules are auditable |
| D6 | 2026-11-01 | Lexicon stores each surface form with a same-form paraphrase ("spilled the beans" → "revealed the secret") | Keeps paraphrases grammatical without a morphology engine |
| D7 | 2026-11-01 | All lexicon entries `review_status: "draft"`; controller accepts draft entries in pilot mode, and every record logs the status | Entries were authored by an AI assistant; no human has reviewed them yet |
| D8 | 2026-11-01 | Literal-only evidence → PASS_THROUGH; mixed/weak evidence or overlapping entries → ABSTAIN | Paper IV-H: abstain on conflict; a confidently literal idiom needs no help |
| D9 | 2026-11-01 | Short cues (<4 chars) also match `-s`/`-es` plurals | Fixes a dev-set false positive ("eggs" vs cue "egg"). Change made on DEV data only |
| D10 | 2026-11-01 | Pipeline default idiom mode = `hint` (paper Table II wording); both modes are run as separate conditions | Which mode is better is an experimental question |
