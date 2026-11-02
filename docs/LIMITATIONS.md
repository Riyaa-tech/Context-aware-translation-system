# Limitations

## What has NOT been done (the research question is still open)
- **No held-out test set exists.** The challenge test items must be written by the research team (DATASET_GUIDE §2).
- **No human ratings exist**, so no strict SPR, ΔSPR, McNemar test or harmful-intervention rate has been measured.
- **No German performance has been measured** beyond dev-data detector checks and single example translations.
- **FLORES-200 devtest has not been run.** Only a 100-sentence FLORES *dev* subset (en→hi) was scored.
- **Only 4 directions are in the active experiment** (en↔hi, en↔de). The other six directions (hi↔de, fr→ar, ar→hi, zh→fr,
  sw→hi) are configured, not tested. Spanish was removed on 2026-11-02 because no Spanish-speaking evaluator is available.
- **The decision rule is not frozen** (`experiments/configs/decision_rule.yaml` has TO_BE_SET values).
- The paper's simulated SPR values (55.0% → 77.7%) remain simulated; nothing here replaces them yet.

## Compute
- Development used CPU only (4 cores, no GPU). Measured ≈ 0.65 s per short sentence and ≈ 2.5 s per FLORES
  sentence; full FLORES devtest ≈ 7 CPU-hours per condition. Latency numbers are CPU numbers.
- The model download (2.4 GB) was verified once (Milestone 1); later runs used the cached copy.

## Idiom module (M1)
- Small lexicon (35 entries: 21 EN, 6 HI, 8 DE), all **draft** (AI-written, not human-reviewed). German meanings were checked
  against Duden online; German forms, paraphrases and cue words are AI-written and await the evaluator's review.
- Surface-form matching only: misses passives, inserted words, unlisted forms and any idiom not in the lexicon.
- Literal/figurative decision = cue-word rules (rule scores, not probabilities); no trained classifier; no embedding similarity.
- Span replacement can break grammar (Hindi postpositions); paraphrase wording can shift tone: NLLB rendered the German
  paraphrases *veralbern*/*necken*/*foppen* as vulgar English, so DE_001 uses *zum Narren halten*, which leans to
  "fool" rather than "tease" (DECISIONS D34).
- German word order is covered by listed forms plus slots ({akk}, {dat}, {gap}, {gap2}); more than 2 words between the
  parts of an idiom, unlisted variants ("nie ein Blatt", "die Daumen halten") and unlisted idioms are missed.
- DE_003 paraphrase *einen Fauxpas begehen* was translated by NLLB as "committed a false passport" on the dev pilot;
  the wording must be revised before the freeze.
- German hint mode repeats slot words inside the brackets ("auf den Arm nimmt (mich ständig zum Narren hält)").
- Some paraphrases assume past tense where English forms are ambiguous (`let`, `hit`).
- Hint mode leaks brackets into outputs.

## Context module (M2)
- 10 English ambiguous words only; no Hindi or German source words.
- Relevance = listed cue words; implied context without those words is missed (also within the sentence itself).
- No pronoun/reference resolution.
- Replacement wording is target-independent and can backfire; rewrites for match (fire) and date (fruit) are disabled.
- The concat control's last-sentence extraction is fragile (sentence-count mismatch in 13/39 dev items with context).

## Sarcasm (M3)
- Not implemented; evaluation category only. Condition E unavailable.

## Data and evaluation
- All challenge data so far is dev data written by the AI assistant that also wrote the rules: detector numbers are optimistic.
- Several dev labels were corrected after first scoring (recorded per item and in DECISIONS D13).
- COMET not included.
- The annotation tool has no login; rater IDs are self-reported. Use on a trusted machine/network.
- **One human evaluator** (fluent in Hindi, English, German) rates all four directions. Results must state that only one
  evaluator participated; **Cohen's kappa is not calculated and no inter-rater reliability can be claimed**.

## Scope of claims
- NLLB-200 is used unchanged; this is not a fine-tuned or document-level model.
- Any future claim must stay within the directions, phenomena and data actually evaluated.
- NLLB-200 is CC-BY-NC 4.0: research/non-commercial use only. FLORES-200 is CC-BY-SA 4.0.
