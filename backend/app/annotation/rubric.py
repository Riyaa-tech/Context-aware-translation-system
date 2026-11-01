"""Annotation rubric and error taxonomy (paper Sections IV-J and VIII-A)."""

RATINGS = {
    "preserved": "Meaning preserved: a reader of the translation understands what the speaker meant.",
    "partial": "Partially preserved: some of the intended meaning is there, but something important is lost or distorted.",
    "not_preserved": "Meaning not preserved: the intended meaning is wrong or missing.",
}
SUB_SCALE = ("yes", "partial", "no", "na")  # na = not applicable (e.g. no figurative meaning in the source)
SUB_DIMENSIONS = {
    "core_proposition": "Is the core proposition (who did what) correct?",
    "figurative_meaning": "Is the figurative meaning (idiom) conveyed? 'na' if none.",
    "pragmatic_intent": "Is the pragmatic/emotional intent (e.g. sarcasm, criticism) conveyed? 'na' if none.",
}
ERROR_CATEGORIES = {
    "none": "No error",
    # idiom
    "idiom_literal_translation": "Figurative phrase translated literally",
    "idiom_misread_usage": "Literal use read as figurative, or the reverse",
    "idiom_wrong_expression": "Unrelated target-language expression swapped in",
    "idiom_content_dropped": "The idiom's content was dropped",
    "idiom_register_shift": "Paraphrase shifted degree or register",
    # sarcasm
    "sarcasm_stance_lost": "Sarcastic stance lost",
    "sarcasm_as_sincere": "Criticism turned into sincere praise",
    "sarcasm_overstated": "Speaker's hostility overstated",
    "sarcasm_bite_lost": "Claim kept but the bite is lost",
    # context
    "context_wrong_sense": "Wrong word sense",
    "context_unresolved_pronoun": "Unresolved or wrong pronoun reference",
    "context_unsupported_reading": "Reading not supported by the surrounding text",
    "context_contradiction": "Contradicts earlier information",
    "context_needless_repetition": "Needless repetition of context",
    # selective design
    "over_intervention": "A change was made that the sentence did not need",
    "module_conflict": "Incompatible readings combined",
    # ordinary
    "omission": "Omission",
    "addition": "Unsupported addition",
    "named_entity": "Wrong named entity",
    "number_date": "Changed number or date",
    "fluency": "Poor fluency",
    "grammar_meaning": "Grammar error that changes meaning",
    "wrong_script_language": "Output in the wrong script or language",
    "other": "Other (explain in comment)",
}
GUIDELINES = [
    "Judge MEANING, not word overlap with the reference. A different wording can still be 'preserved'.",
    "Use the intended meaning and the context shown; the reference translation (if any) is only a guide.",
    "Only 'preserved' counts as success in strict SPR. When unsure between preserved and partial, choose partial.",
    "You do not know which system produced a translation. Do not try to guess.",
    "Rate each item independently. Do not discuss items with the other rater until both have finished.",
]


def rubric() -> dict:
    return {"ratings": RATINGS, "sub_scale": list(SUB_SCALE), "sub_dimensions": SUB_DIMENSIONS,
            "error_categories": ERROR_CATEGORIES, "guidelines": GUIDELINES}
