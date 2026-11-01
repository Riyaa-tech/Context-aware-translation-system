"""End-to-end semantic pipeline: detectors -> controller -> (rewrite) -> unchanged NLLB.

Produces a full decision record plus timed pipeline events (used by the explainability page).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

from app.controller.semantic_controller import INTERVENE, ControllerConfig, SemanticController
from app.modules.idiom_detector import IdiomConfig, IdiomDetector
from app.modules.idiom_resolver import IDIOM_MODES, apply_idioms


@dataclass(frozen=True)
class PipelineConfig:
    idiom_enabled: bool = True
    idiom_mode: str = "hint"  # hint | paraphrase
    idiom: IdiomConfig = field(default_factory=IdiomConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)

    def __post_init__(self):
        if self.idiom_mode not in IDIOM_MODES:
            raise ValueError(f"idiom_mode must be one of {IDIOM_MODES}")

    @property
    def condition_name(self) -> str:
        if not self.idiom_enabled:
            return "A_baseline"
        return f"B_idiom_{self.idiom_mode}"

    @property
    def active_modules(self) -> list[str]:
        return ["idiom"] if self.idiom_enabled else []


class _Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 2)


def _event(stage: str, status: str, duration_ms: float, details: dict | None = None) -> dict:
    return {"stage": stage, "status": status, "duration_ms": duration_ms, "details": details or {}}


@dataclass
class PipelineResult:
    record: dict
    events: list[dict]
    translation_result: object  # TranslationResult


class SemanticPipeline:
    def __init__(self, engine, config: PipelineConfig | None = None, detector: IdiomDetector | None = None):
        self.engine = engine
        self.config = config or PipelineConfig()
        self.detector = detector or IdiomDetector(config=self.config.idiom)
        self.controller = SemanticController(self.config.controller)

    def prepare(self, text: str, source_lang: str, context: list[str] | None = None) -> tuple[dict, list[dict]]:
        """Run everything up to (not including) translation. Returns (partial record, events)."""
        cfg = self.config
        context = context or []
        events = [_event("input", "done", 0.0, {"text": text, "context_sentences": len(context)})]

        candidates = []
        if cfg.idiom_enabled:
            t = _Timer()
            candidates = self.detector.detect(text, source_lang, context)
            events.append(_event("idiom_detection", "done", t.ms(), {"candidates": [c.as_dict() for c in candidates]}))
        else:
            events.append(_event("idiom_detection", "skipped", 0.0, {"reason": "module disabled in this condition"}))
        events.append(_event("context_analysis", "skipped", 0.0, {"reason": "context module not implemented yet (Milestone 3)"}))

        t = _Timer()
        ctrl = self.controller.decide(candidates)
        modified, rewrites = None, []
        if ctrl.decision == INTERVENE:
            modified, rewrites = apply_idioms(text, ctrl.accepted_idioms, cfg.idiom_mode)
        events.append(_event("controller", "done", t.ms(), {**ctrl.as_dict(), "idiom_mode": cfg.idiom_mode,
                                                           "rewrites": [asdict(r) for r in rewrites]}))
        record = {
            "active_modules": cfg.active_modules,
            "condition": cfg.condition_name,
            "module_predictions": {"idiom": [
                {"idiom_id": c.idiom_id, "matched_text": c.matched_text, "usage": c.usage,
                 "intended_meaning": c.intended_meaning, "review_status": c.review_status,
                 "figurative_cues": c.figurative_cues_found, "literal_cues": c.literal_cues_found,
                 "literal_follower": c.literal_follower_found} for c in candidates]} if cfg.idiom_enabled else {},
            "confidence_scores": {"idiom": {c.idiom_id: {"usage_score": c.usage_score, "entry_confidence": c.entry_confidence}
                                            for c in candidates}} if cfg.idiom_enabled else {},
            "thresholds": {"idiom": cfg.idiom.as_dict(), "controller": cfg.controller.as_dict()},
            "controller_decision": ctrl.decision,
            "span_decisions": ctrl.as_dict()["span_decisions"],
            "conflicts": ctrl.conflicts,
            "idiom_mode": cfg.idiom_mode if cfg.idiom_enabled else None,
            "original_sentence": text,
            "context": context,
            "modified_sentence": modified,
            "rewrites": [asdict(r) for r in rewrites],
            "abstention_reason": ctrl.abstention_reason,
        }
        return record, events

    def run(self, text: str, source_lang: str, target_lang: str, context: list[str] | None = None,
            example_id: str | None = None) -> PipelineResult:
        t_all = _Timer()
        record, events = self.prepare(text, source_lang, context)
        nllb_input = record["modified_sentence"] or text
        t = _Timer()
        result = self.engine.translate(nllb_input, source_lang, target_lang)
        events.append(_event("translation", result.status, t.ms(),
                             {"nllb_input": nllb_input, "model": self.engine.info().get("model_id")}))
        events.append(_event("output", "done", 0.0, {"final_translation": result.translation}))
        record.update({
            "example_id": example_id or f"adhoc-{uuid.uuid4().hex[:8]}",
            "source_lang": source_lang,
            "target_lang": target_lang,
            "nllb_input": nllb_input,
            "final_translation": result.translation,
            "translation_status": result.status,
            "latency_ms": {"total": t_all.ms(), "translation": result.latency_ms,
                           "modules": round(sum(e["duration_ms"] for e in events if e["stage"] in
                                                ("idiom_detection", "context_analysis", "controller")), 2)},
        })
        return PipelineResult(record=record, events=events, translation_result=result)
