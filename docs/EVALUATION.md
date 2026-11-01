# Evaluation

General translation quality and semantic preservation are measured **separately** and never mixed in one number.

## 1. General quality (reference-based)

Computed only on items that have a human reference translation (FLORES-200; challenge items with references).

| Key | Metric | Configuration |
|---|---|---|
| `bleu_13a` | SacreBLEU BLEU | tokenizer `13a` (not comparable with FLORES spBLEU) |
| `spbleu_flores200` | SacreBLEU BLEU | tokenizer `flores200` (SentencePiece; the FLORES-200 setup) |
| `chrfpp` | chrF++ | char order 6, word order 2, beta 2 |

- Every score is stored with its SacreBLEU signature (version, tokenizer, smoothing).
- Scores are reported **per direction**. No average is computed by default (paper III-B).
- Variant vs A: **paired bootstrap resampling** (Koehn 2004), 1,000 samples, fixed seed → Δ, 95% CI, share of samples
  where the variant is not better.

## 2. Strict Semantic Preservation Rate (primary metric)

Raters label each translation: `preserved` / `partial` / `not_preserved`.

```
SPR (%) = preserved / evaluated × 100        (partial is NOT a success)
ΔSPR (pp) = SPR(variant) − SPR(A)            (absolute percentage points)
Δrel (%) = ΔSPR / SPR(A) × 100               (always labelled "relative")
```

- Overall SPR is **pooled from counts**, not averaged across categories.
  Example: 70/100 idioms + 10/50 context items → 80/150 = 53.3%, not (70% + 20%)/2 = 45%.
- Reported overall, per category, per direction, per condition; partial-preservation rate reported separately.
- 95% CI for each SPR: percentile bootstrap (2,000 samples, fixed seed).
- ΔSPR: paired bootstrap CI + **exact McNemar test** on the paired preserved/not-preserved outcomes
  (n01 = fixed by the variant, n10 = broken by the variant).
- Paired comparisons use only items rated in both conditions.

### Multiple raters
- Agreement: Cohen's kappa on the 3-class rating and on the strict binary (preserved vs not).
- Aggregated rating per item: adjudicated (rater id `adjudicator`) > single rater > agreement > **conservative minimum**
  (the lower of the ratings). The counts for each rule are reported.
- With one rater, reports carry a "single rater; no agreement statistic" limitation.

### Annotation workflow
1. `python scripts/create_annotation_batch.py <experiment_id>` builds a blinded batch. Each distinct output per example
   is one item (identical outputs from several conditions are rated once); condition and category are hidden;
   each rater gets their own shuffled order.
2. Raters use `http://localhost:8000/annotate` (or the frontend Annotation page): source, context, intended meaning,
   reference (if any), translation; overall rating; core proposition / figurative meaning / pragmatic intent
   (yes/partial/no/na); unsupported addition; omission; primary error category (paper VIII-A taxonomy); comment.
3. Export: `GET /api/annotations/export?batch_id=...&format=jsonl|csv`.

**Ratings are only entered by people. No LLM or automatic rating is ever stored as a human judgment.**

## 3. Detector and controller metrics (no ratings needed)

| Metric | Definition |
|---|---|
| Idiom precision / recall / F1 | Positive = figurative idiom the controller acted on, vs gold labels |
| Context state / sense accuracy | vs gold state and gold sense |
| Intervention coverage | share of items with decision INTERVENE |
| Abstention rate | share with ABSTAIN |
| Control false-intervention rate | INTERVENE on control items (literal idioms, sincere, irrelevant/missing context, …) |
| Harmful-intervention rate | among activations: baseline rated `preserved` → variant not `preserved` (needs ratings) |

Detector scores describe when a module fires; they say nothing directly about SPR.

## 4. Running it

```bash
python scripts/evaluate_run.py <experiment_id>                    # everything that needs no ratings
python scripts/evaluate_run.py <experiment_id> --batch <batch_id>  # + strict SPR from human ratings
```
Outputs: `experiments/metrics/<id>__eval_<time>.json` and `experiments/reports/<id>__eval_<time>.md`.
Also available as `GET /api/research/metrics` and `GET /api/research/ablation`.

## 5. Interpretation rules
- A numerically higher score is not "significant" unless the test above says so; always give n, CI and p.
- A rise in BLEU/chrF++ alone never counts as success for a module (paper XI-B).
- Dev-set numbers (including detector scores) are optimistic and not reportable.
- Claims stay within the directions, phenomena and data actually evaluated.
