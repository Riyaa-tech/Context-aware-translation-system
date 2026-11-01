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
| D10 | 2026-11-01 | Default idiom mode = `paraphrase` (changed from `hint` at the user's request to choose). Both modes are still run as separate conditions | Dev run: hint brackets leaked into 17/29 outputs; paraphrase more often conveyed the meaning (author impression, not human ratings) |
| D11 | 2026-11-01 | Context module = rule-based sense selection over a 10-word inventory; NLLB still receives one sentence | Paper IV-F/V-D: no document-level claims; small set of common ambiguities is a realistic start |
| D12 | 2026-11-01 | "Unfiltered context" control = concat window + sentence, keep the last output sentence; alignment warnings logged | Paper IV-F "no selection at all" alternative |
| D13 | 2026-11-01 | Context dev labels corrected after first scoring: "The bag is light" was not ambiguous (in-sentence cue); the shared "irrelevant" sentence contained the cue "weather" (relevant for spring); the pronoun item's gold state changed to "needs context" | Labelling errors in DEV data; corrections recorded per item (`label_revisions`) |
| D14 | 2026-11-01 | Replacement wordings chosen on dev: bat.animal "flying bat" → "bat animal"; match.fire and date.fruit rewrites disabled | Dev outputs: "flying bat" → "flying stick", "matchstick" → "torch", "date fruits" → "frutas de dato" |
| D15 | 2026-11-01 | Pronoun/reference resolution not implemented | Needs a parser/coreference model; a weak heuristic would add noise |
| D16 | 2026-11-01 | Redundant cues removed (a cue already covered by a shorter prefix cue, e.g. "fisherman" by "fish") | Prevented double counting |
| D17 | 2026-11-01 | One folder per run (`experiments/runs/<name>_<UTC time>_<config hash>`), predictions appended per batch, atomic manifest writes, torn lines repaired on resume (logged to `.torn.log`) | Checkpoint/resume without losing or duplicating examples |
| D18 | 2026-11-01 | Resume refused if any dataset file hash changed; condition A required in every run | Paired comparisons on identical inputs |
| D19 | 2026-11-01 | Test-split runs require a frozen, committed `decision_rule.yaml` | Paper VII-B: decision rule fixed before final scoring |
| D20 | 2026-11-01 | Splits assigned by hash(seed, example_id) | Reproducible and independent of row order |
| D21 | 2026-11-01 | Metric keys name the tokenizer (`bleu_13a`, `spbleu_flores200`, `chrfpp`); signatures stored; per-direction only | Paper III-B: never present 13a BLEU as spBLEU; no hidden averaging |
| D22 | 2026-11-01 | Annotation items = distinct outputs per example (identical outputs across conditions rated once); condition and category hidden; per-rater seeded order | Blinding (paper IV-J) and ~75% less rating work on the dev pilot (201 vs 791) |
| D23 | 2026-11-01 | Multi-rater aggregation: adjudicated > single > agreement > conservative minimum | Strict metric; disagreement never inflates SPR |
| D24 | 2026-11-01 | Harmful-intervention denominator = activations (INTERVENE, or context actually prepended in concat) | Paper IV-J definition |
| D25 | 2026-11-01 | FLORES-200 original release archive (sha256 `b8b0b767…`); FLORES dev → our `dev`, devtest → our `test` | Paper III-A: state the release; devtest runs require the frozen decision rule |
| D26 | 2026-11-01 | Exact McNemar via binomial (no scipy); bootstrap with fixed seeds | Fewer dependencies; reproducible |
| D27 | 2026-11-01 | Minimal server-side annotation page (`/annotate`) in addition to the planned React page | Lets the team start rating before Milestone 6 |
| D28 | 2026-11-01 | Frontend: React 18 + Vite 5 + TypeScript + Tailwind 3 + Recharts (versions pinned); FastAPI serves `frontend/dist` | No SSR needed; one server for the demo |
| D29 | 2026-11-01 | Charts: validated reference palette slots 1–3 (light + dark steps), single-series bars in slot 1, value labels + table view on every chart | Dataviz method; light-mode slot 3 is below 3:1 contrast, so labels/table are required |
| D30 | 2026-11-01 | Backend's simple rating page moved to `/annotate-lite`; the React app owns `/annotate` | Avoid a route clash when loading `/annotate` directly |
