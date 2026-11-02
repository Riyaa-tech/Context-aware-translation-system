# Implemented Methodology

This describes what the code actually does. Paper = "Context-Aware Neural Machine Translation: Improving Semantic
Preservation of Idiomatic, Sarcastic, and Context-Dependent Expressions" (draft). Where the implementation is
narrower than the paper, it says so.

## 1. Backbone (paper IV-C)
- `facebook/nllb-200-distilled-600M`, revision `f8d333a098d19b4fd9a8b18f94170487ad3f821d`, **unchanged** (no fine-tuning).
- Source language set on the tokenizer; generation forced to start with the target-language token.
- Decoding (all conditions): beam 4, no sampling, max 256 new tokens; inputs over 512 tokens are truncated and flagged.
- Active directions: en→hi, hi→en, **en→de, de→en** (`deu_Latn`). Spanish was removed on 2026-11-02 (no Spanish-speaking
  evaluator); the paper's planned hi↔es directions became hi↔de. The six planned directions are configured but blocked
  until tested. FLORES files exist for all ten.

## 2. M1 — Idiom-aware processing (paper IV-E)
1. **Candidates**: surface-form matching against a JSON lexicon (35 entries: 21 EN, 6 HI, 8 DE), case-insensitive,
   whitespace-tolerant, Devanagari-aware word boundaries. Slots: English possessive (`pull {poss} leg`); German
   accusative/dative objects (`{akk}`, `{dat}`) and up to two extra words (`{gap}`, `{gap2}`), so German verb-second,
   verb-final, perfect and zu-infinitive forms can be listed explicitly. Words captured by object slots count as cue evidence.
2. **Usage (figurative / literal / uncertain)**: rule score = entry prior + 0.10 × figurative cues (max +0.20)
   − 0.40 × literal cues − 0.50 if a literal "follower" word comes right after the match. Cues are searched in the
   sentence (outside the idiom) and in the provided context. Figurative if ≥ 0.60, literal if ≤ 0.40, else uncertain.
   *The paper proposes an XLM-R classifier; per paper IX-A it is deferred until labelled data exists.*
3. **Resolution**: each lexicon form has a same-form paraphrase. Two interventions:
   `hint` = "spilled the beans (revealed the secret)"; `paraphrase` = "revealed the secret".
4. All entries are `draft` (written by an AI assistant, not human-reviewed); every record logs the status. German
   meanings were checked against Duden online (cited per entry); German forms, paraphrases and cues await review.
5. Replacements are capitalised only at a sentence start (German nouns are always capitalised, so the old
   "copy the span's first-letter case" rule was wrong for German).

## 3. M2 — Selective discourse context (paper IV-F)
1. Ambiguous words from a 10-word English sense inventory (bank, bat, pitch, glasses, spring, match, date, seal, court, light).
2. If the sentence's own cue words settle the sense (lead ≥ 1 cue) → **NO_CONTEXT_REQUIRED**.
3. Otherwise, sliding window of the last 3 sentences; each sentence's relevance = cue hits × 0.8^(distance−1);
   selected if ≥ 0.5. None given → **CONTEXT_INSUFFICIENT**; none selected → **CONTEXT_IRRELEVANT**;
   winning sense support ≥ 0.75 and lead ≥ 0.5 → **RELEVANT_CONTEXT_SELECTED**; else **CONTEXT_AMBIGUOUS**.
4. The resolved sense becomes an explicit word in the **current sentence** ("bank" → "riverbank"); NLLB still
   receives one sentence. Dominant senses (e.g. financial bank) need no rewrite.
5. Not implemented: pronoun/reference resolution.

## 4. M3 — Sarcasm (paper IV-G)
Not implemented. Sarcasm and sincere-control items are an **evaluation category only**; condition E is unavailable.

## 5. Controller (paper IV-H)
Per span: idiom accepted only if figurative, score ≥ 0.60, entry confidence ≥ 0.50 and review status allowed;
literal → no change; uncertain → abstain. Context accepted only in RELEVANT_CONTEXT_SELECTED with a rewrite;
irrelevant/insufficient/ambiguous → abstain. Overlapping lexicon entries, or idiom and context rewriting the same
text → abstain on both and log a conflict. Sentence decision: INTERVENE if any span accepted; else ABSTAIN if
any abstention; else PASS_THROUGH. Deterministic; every threshold is logged in the record.

## 6. Conditions (paper IV-I)
A (baseline), B_hint, B_paraphrase, C_selected, C_concat (control: unfiltered context prepended, last output
sentence kept), D_paraphrase, D_hint. E not implemented. Same examples, checkpoint, decoding and scorer for all.

## 7. Evaluation (paper III-B, IV-J)
See `EVALUATION.md`: BLEU(13a) and spBLEU(flores200) under separate names, chrF++, paired bootstrap; strict SPR
from blinded human ratings, pooled; ΔSPR with paired bootstrap CI and exact McNemar; one evaluator (no kappa);
harmful-intervention rate over activations; detector and controller metrics from gold labels.

## 8. Data discipline (paper IV-D, V-B, VII-B)
Dev and test kept apart; splits by hash(seed, id); test runs need a frozen, committed decision rule; dataset hashes
are checked on resume; dev-set label corrections are recorded per item.
