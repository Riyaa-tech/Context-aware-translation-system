# Pilot Findings (development data — NOT results)

> Everything here comes from **development data** written by the same AI assistant that wrote the rules, or
> from a **100-sentence FLORES dev subset**. No human has rated any output. These observations guide the next
> steps; none of them may be reported as evidence for or against the method.

## Runs
| Run | Data | Conditions |
|---|---|---|
| `pilot_dev_20261101T104108Z_89efe420c3f8` | 113 dev items (53 idiom, 50 context, 10 sarcasm) | A, B_hint, B_paraphrase, C_selected, C_concat, D_paraphrase, D_hint |
| `flores_smoke_dev_20261101T110037Z_619907905455` | FLORES-200 **dev**, en→hi, first 100 sentences | A, D_paraphrase |

## Measured (descriptive, no ratings)
| What | Value |
|---|---|
| Errors / missing items | 0 in every condition; same IDs across conditions |
| Idiom detector on dev (P / R / F1) | 1.00 / 0.85 / 0.92 (n=53; optimistic) |
| Context module on dev (state / sense accuracy) | 0.98 / 1.00 (n=50 / 22; optimistic) |
| Interventions on control items (literal idioms, sincere, irrelevant/missing context) | 0 in every condition |
| Outputs changed vs A on irrelevant-context controls | C_selected 0/12 · C_concat 10/12 |
| Intervention coverage on dev | B 25.7% · C_selected 11.5% · D 37.2% |
| Module time per sentence | ≈ 0.1 ms (median) vs ≈ 650 ms NLLB on CPU |
| FLORES dev subset, en→hi (A) | BLEU(13a) 32.03 · spBLEU 37.85 · chrF++ 55.74 (n=100) |
| FLORES dev subset, D_paraphrase vs A | identical outputs (0 interventions, 8 abstentions); Δ = 0 |

## Observed by reading outputs (author impressions, not ratings)
- Paraphrase mode often turned a literal idiom translation into the intended meaning
  ("a piece of cake" → "बहुत आसान" instead of "केक का टुकड़ा").
- Hint mode leaked the bracketed hint into 17/29 outputs.
- Some interventions plausibly hurt: "engañando" → "cheating on me"; Hindi replacements broke agreement
  ("दादा की बहुत प्यारा"); one unrelated phrase changed ("missing the deadline" → "remembering").
- Some context rewrites backfired before dev tuning ("flying bat" → "flying stick"; "matchstick" → "torch").
- Selected context fixed clear sense errors ("bank" → riverbank; "pitch" → sales presentation; "glasses" → drinking glasses).
- On FLORES, the context module abstained on sentences whose sense was obvious from non-cue words ("Nadal … match").
- Final output check: 0 errors/empty outputs; all 13 warnings are C_concat alignment warnings; one FLORES sentence
  kept Latin-script species names in the Hindi output (baseline behaviour; the reference transliterates them).

## What this suggests testing (decision rule to be fixed first)
1. Paraphrase vs hint on held-out idioms (human SPR + harmful-intervention rate).
2. Selected vs unfiltered (concat) context on context items **and** on irrelevant-context controls.
3. Whether D's gains (if any) exceed B and C separately.
4. Whether general quality (FLORES devtest, all directions) is unchanged — the selective design predicts few
   interventions on general text.
