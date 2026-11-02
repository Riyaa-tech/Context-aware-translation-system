# Pilot Findings (development data — NOT results)

> Everything here comes from **development data** written by the same AI assistant that wrote the rules, or
> from a **100-sentence FLORES dev subset**. No human has rated any output. These observations guide the next
> steps; none of them may be reported as evidence for or against the method.

> **Scope note (2026-11-02):** the 2026-11-01 runs below used the earlier **Spanish** scope (en↔es instead of en↔de).
> They are kept unchanged as history. Spanish-specific observations (e.g. "engañando") no longer apply to the active
> project. German observations are in the section at the end.

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

## German scope — development observations (2026-11-02; dev data, NOT results)
- German idiom detector on 22 German dev rows (AI-written): precision 1.00, recall 0.67, no false positives on the
  4 literal controls and 3 no-idiom sentences (optimistic). The 5 misses are by design: idioms not in the lexicon,
  unlisted variants, more than 2 words between the parts of an idiom. Before adding zu-infinitive / subordinate-past
  forms and the `{gap2}` slot, recall was 0.47 (D33).
- Single real-model examples (not ratings): baseline "Du nimmst mich auf den Arm!" → "you're taking me by the arm";
  with the paraphrase → "you're making a fool of me". English → German: "She finally revealed the secret …" →
  "Sie enthüllte endlich das Geheimnis …".
- NLLB-600M turned several German "tease" verbs into vulgar or wrong English (*veralbern* → "fucking with me",
  "bribe me"; *necken*/*foppen* → "fuck me"); DE_001 therefore uses *zum Narren halten* (D34).
- **German pilot runs (2026-11-02, CPU):**
  - `flores_smoke_dev_de_20261102T…` — FLORES dev, en→de, first 100 sentences (pilot subset): A = BLEU(13a) 33.56 ·
    spBLEU 39.80 · chrF++ 58.73; D_paraphrase identical outputs (0 interventions, the same 8 abstentions as en→hi).
  - `pilot_dev_v2_20261102T085537Z_f1663c668552` — 128 v2 dev items × 7 conditions, 0 errors, same IDs everywhere;
    0 interventions on control items; C_concat changed 11/12 irrelevant-context outputs, C_selected 0/12.
- Reading the German → English outputs (author impressions, not ratings): paraphrase often conveyed the meaning
  ("shake my arm" → "make a fool of me"; "press my thumbs" → "wish me luck"; "understood only the station" →
  "didn't understand anything at all"); **one paraphrase backfired: "einen Fauxpas begangen" → "committed a false
  passport"** (DE_003 wording must be revised in the evaluator review); for *Holzweg* and *Kinderspiel* the baseline was
  already idiomatic ("on the wrong track", "child's play"); hint mode was mostly ignored; NLLB dropped the second
  sentence of "Siehst du den Bus nicht? Hast du Tomaten auf den Augen?" in both A and the paraphrase.
