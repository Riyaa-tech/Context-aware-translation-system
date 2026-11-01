"""Registry of experimental conditions (paper Table II plus diagnostic controls, spec Section 8).

All conditions share the same model, decoding settings and examples; only the semantic
intervention differs.
"""
from __future__ import annotations

from app.pipeline import PipelineConfig

CONDITIONS: dict[str, dict] = {
    "A": {"config": PipelineConfig(idiom_enabled=False), "description": "Plain NLLB-200 (baseline)"},
    "B_hint": {"config": PipelineConfig(idiom_mode="hint"), "description": "NLLB + idiom module, inline meaning hint"},
    "B_paraphrase": {"config": PipelineConfig(idiom_mode="paraphrase"), "description": "NLLB + idiom module, controlled paraphrase"},
    "C_selected": {"config": PipelineConfig(idiom_enabled=False, context_mode="selected"), "description": "NLLB + selected context (M2)"},
    "C_concat": {"config": PipelineConfig(idiom_enabled=False, context_mode="concat"),
                 "description": "Diagnostic control: unfiltered context window prepended, last sentence kept"},
    "D_paraphrase": {"config": PipelineConfig(idiom_mode="paraphrase", context_mode="selected"),
                     "description": "Idiom (paraphrase) + selected context"},
    "D_hint": {"config": PipelineConfig(idiom_mode="hint", context_mode="selected"), "description": "Idiom (hint) + selected context"},
}

# Paper condition E (D + sarcasm/intent) is optional and only allowed once a validated module exists.
NOT_IMPLEMENTED = {"E": "Sarcasm/intent module (M3) is not implemented; sarcasm is an evaluation category only."}


class ConditionError(ValueError):
    pass


def get_condition(name: str) -> PipelineConfig:
    if name in NOT_IMPLEMENTED:
        raise ConditionError(f"Condition {name} unavailable: {NOT_IMPLEMENTED[name]}")
    if name not in CONDITIONS:
        raise ConditionError(f"Unknown condition '{name}'. Available: {sorted(CONDITIONS)}")
    return CONDITIONS[name]["config"]


def list_conditions() -> list[dict]:
    out = [{"name": k, "description": v["description"], "pipeline": v["config"].as_dict(),
            "condition_label": v["config"].condition_name, "available": True} for k, v in CONDITIONS.items()]
    out += [{"name": k, "description": v, "available": False} for k, v in NOT_IMPLEMENTED.items()]
    return out
