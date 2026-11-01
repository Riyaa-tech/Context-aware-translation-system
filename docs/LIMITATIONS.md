# Known Limitations (updated each milestone)

## General
- CPU-only development machine; latency figures are CPU numbers.
- No experimental results exist yet. No human ratings exist yet. The paper's SPR values are simulated.

## Idiom module (M1) — Milestone 2
- **Lexicon is small (33 entries: 21 EN, 6 HI, 6 ES) and unreviewed** (`draft`). Hindi and Spanish entries need a fluent speaker.
- **Surface-form matching only.** Misses passives ("the beans were spilled"), inserted words ("spilled all the beans"),
  forms not listed ("costaron un ojo de la cara") and any idiom not in the lexicon. Seen on the dev set.
- **Usage check is cue-word rules**, not a trained classifier. Scores are rule scores, not probabilities.
- **No multilingual embedding similarity** (optional in the spec); not implemented.
- **Span replacement can break grammar** when surrounding words depend on the idiom:
  Hindi "दादा **की** आँखों का तारा" → "दादा की बहुत प्यारा" (needs "को"); "मेरी नाक में दम" → "मेरी बहुत परेशान" (needs "मुझे").
- **Paraphrase word choice can introduce a wrong sense:** "tomando el pelo" → "engañando" was translated as "cheating on me".
- **Some paraphrases assume past tense** where the English form is ambiguous (`let`, `hit`); noted per entry.
- **Hint mode leaks**: on the dev run, bracketed hints appeared in 17/29 outputs.
- Dev-set detector metrics are optimistic: the same person (AI assistant) wrote the rules and the dev examples.
  Test items should be written or checked by a project member after the lexicon is frozen.

## Context module (M2) — Milestone 3
- **Only 10 English ambiguous words** (bank, bat, pitch, glasses, spring, match, date, seal, court, light); no Hindi/Spanish source words.
- **Cue-word relevance only.** Context that implies a sense without listed cue words ("willow trees", "edge") is missed.
- **Pronoun/reference resolution is not implemented** ("She put *it* on the table" after "a new lamp").
- **Replacement wording is target-independent and can backfire**: "flying bat" → Hindi "flying stick". Rewrites for
  match (fire) and date (fruit) are disabled because no tested wording worked.
- **The concat control is fragile**: on the dev run, 11/34 items had a sentence-count mismatch, and some outputs
  were the translation of the context sentence instead of the current one.
- **Some rewrites change nothing**: NLLB already picked the right word for "glasses", "court", "light", "spring" in several dev items.
