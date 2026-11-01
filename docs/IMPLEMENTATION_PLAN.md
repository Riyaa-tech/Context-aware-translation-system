# Implementation Plan

## Stack (chosen because the repo is empty and the project is a student MVP)

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3, FastAPI, PyTorch (CPU wheel), Transformers, SentencePiece | Standard for NLLB |
| Metrics | SacreBLEU (BLEU + chrF++), NumPy/SciPy for bootstrap, McNemar, Cohen's kappa | Well-known, versioned |
| Storage | SQLite (annotations) + JSONL files (datasets, predictions, logs) + JSON manifests | No servers to run |
| Frontend | React + Vite + TypeScript + Tailwind + Recharts | No server-side rendering is needed, so Vite is simpler than Next.js |
| Tests | pytest (unit tests mock the model; marked `@pytest.mark.model` tests run the real model) | Clear split of mocked vs real |

No Postgres, Redis, Celery, Docker or microservices.

## Directory layout

```
backend/
  app/
    api/             # FastAPI routers
    config/          # settings, language codes, thresholds (YAML)
    translation/     # nllb_engine.py (cached model, batching, forced BOS token)
    modules/         # idiom_detector.py, idiom_resolver.py, context_selector.py, context_resolver.py
    controller/      # semantic_controller.py (PASS_THROUGH / INTERVENE / ABSTAIN)
    evaluation/      # bleu.py, chrf.py, spr.py, detector_metrics.py, statistical_tests.py
    annotation/      # SQLite store, blinding, export
    experiments/     # runner, conditions, checkpointing, manifests
    schemas/         # Pydantic models
  resources/         # idiom lexicon, ambiguous-word sense inventory (JSON)
  tests/
experiments/
  configs/ datasets/{challenge_set,flores}/ predictions/ annotations/ metrics/ reports/
frontend/
docs/
```

## Milestones

| # | Work | Acceptance check |
|---|---|---|
| 1 | NLLB engine + `/health`, `/api/translate/baseline`; language config for 4 directions (en↔hi, en↔es); run-info recording; real-model smoke test | A real sentence translated through the API, test output shown |
| 2 | M1: reviewed idiom lexicon (small, EN first, a few HI/ES), exact + normalized (lemma/inflection) matching, literal-vs-figurative rules using context cues, two intervention styles (gloss hint, controlled paraphrase), abstention | Unit tests incl. literal controls; idiom examples run end-to-end |
| 3 | M2: sliding window, relevance scoring (sense-cue overlap + optional embedding similarity), small sense inventory (bank, bat, pitch, …), simple pronoun handling, no-context and irrelevant-context controls; controller integration | Unit tests for the 4 context states; context examples end-to-end |
| 4 | Experiment runner: conditions A–D plus diagnostic variants (hint vs paraphrase, selected vs unfiltered context), same IDs/config, checkpoint + resume, manifest, never-overwrite | Pilot run on the dev split, then the test split, all conditions |
| 5 | BLEU, chrF++, SPR, ΔSPR, detector/controller metrics, bootstrap CIs, McNemar, kappa; blinded annotation API + store + export; FLORES smoke test | Metric unit tests vs hand-computed values |
| 6 | Frontend: Translate, Pipeline, Experiments, Annotate, Dashboard pages using real API data; missing metrics shown as "unavailable" | App runs against the backend; screenshots |
| 7 | Full test run, pilot experiments, reports, README, the other docs, LIMITATIONS | Documented end-to-end run |

## Key method decisions (to confirm)

1. **How interventions reach NLLB.** NLLB cannot take a separate "hint" input. Two options are implemented and compared:
   - *Controlled paraphrase:* replace the idiom/ambiguous word in the source with its reviewed literal meaning
     (e.g. "She spilled the beans." → "She revealed the secret.").
   - *Inline gloss hint:* keep the original phrase and add the meaning in brackets. This may leak into output, so it is
     measured, not assumed to work.
2. **M3 sarcasm:** challenge-set evaluation category only in the MVP (no validated multilingual detector is available).
   Condition E will be shown as "not implemented".
3. **Challenge set:** a manually authored pilot (target ~150 examples: idiom, context, sarcasm, plus literal,
   sincere and context-free controls), clearly labelled `manually authored`, with a seeded dev/test split. Lexicon and
   rules are built only from dev examples.
4. **Reference translations:** left `null` unless a human provides them. BLEU/chrF++ on the challenge set are only
   computed where references exist; FLORES gives general-quality BLEU/chrF++.
5. **FLORES:** the original FLORES-200 release (CC BY-SA 4.0), devtest split; spBLEU (flores200 tokenizer) and 13a BLEU
   reported under separate, clearly named labels.

## Paper alignment (from the 24-page draft)

Points from the paper that the implementation follows exactly:

| Paper section | Requirement | How it is implemented |
|---|---|---|
| III-A | Report which FLORES release was used; original repo archived Nov 2023, later releases by OLDI | Manifest records release name, URL and checksum |
| III-B | 13a SacreBLEU must not be labelled spBLEU; tables never mix tokenizers | Metric keys carry the tokenizer name (`bleu_13a`, `spbleu_flores200`) |
| III-B | Per-direction scores always shown next to any average | Reports list directions first, average last with method stated |
| IV-C | Failures, truncations, empty outputs logged, never dropped; completion rate reported | Every prediction row has a `status` field |
| IV-D | Controls: literal idioms, sincere positives, clear-context items; dedup; train/dev/test split | Dataset schema + validation script |
| IV-E | Compare three inputs: original, lexicon hint, paraphrase. Classifier (XLM-R) only once labelled data exists (IX-A) | MVP uses transparent rules; classifier slot left open and documented |
| IV-F | Irrelevant context as negative control; unfiltered context "if time allows" | Both implemented as diagnostic conditions |
| IV-G | Sarcasm: label kept separate from intervention | M3 = evaluation category only unless validated |
| IV-H | Modules disagree → abstain and log conflict | Controller rule |
| IV-J | Overall SPR pooled from counts, not averaged; partial-preservation rate reported separately; relative change labelled | `spr.py` |
| IV-J | Harmful-intervention rate = share of **activations** that turn a "preserved" baseline into "not preserved" | Denominator = intervened items |
| IV-J | Raters judge core proposition, figurative meaning, pragmatic intent, additions/omissions separately; blinded | Annotation form fields |
| VII-B | Decision rule (acceptable general-quality loss) fixed **before** final scoring | `experiments/configs/decision_rule.yaml` written and committed before the test run |
| VIII-A | Error taxonomy (idiom, sarcasm, context, over-intervention, module conflict, ordinary errors); primary + secondary | Annotation error-category list |
| V-D | NLLB is CC-BY-NC 4.0 (non-commercial); FLORES CC-BY-SA 4.0 | Stated in README and LIMITATIONS |

## Final status (2026-11-01)

| Milestone | Status | Evidence |
|---|---|---|
| 0 Repository audit | Done | `REPOSITORY_AUDIT.md` |
| 1 Baseline engine + API | Done | Real-model tests; `/api/translate/baseline` |
| 2 Idiom module (M1) + controller | Done | Dev P/R/F1 1.00/0.85/0.92 (optimistic) |
| 3 Context module (M2) | Done | Dev state/sense accuracy 0.98/1.00 (optimistic) |
| 4 Experiment runner | Done | `pilot_dev` run, 7 conditions × 113 items, 0 errors |
| 5 Evaluation + annotation + FLORES | Done | FLORES dev smoke test; metric tests vs hand values |
| 6 Research app | Done | 5 pages on the real API; browser-checked |
| 7 Final validation + docs | Done | Fresh-clone reproduction; all suites pass |
| **Research answer** | **Open** | Needs test items, frozen decision rule, human ratings, FLORES devtest |

Not implemented by design or scope: M3 sarcasm module (condition E), pronoun resolution, XLM-R usage classifier,
embedding similarity, COMET.
