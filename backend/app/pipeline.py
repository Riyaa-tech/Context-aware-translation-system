"""End-to-end semantic pipeline: detectors -> controller -> (rewrite) -> unchanged NLLB.

Produces a full decision record plus timed pipeline events (used by the explainability page).

Context modes
  none      : the current sentence only.
  selected  : M2. Relevant preceding sentences are selected and used ONLY to choose a
              meaning-explicit wording of the current sentence; NLLB still sees one sentence.
  concat    : diagnostic control (paper IV-F, "no selection at all"): all window sentences are
              prepended to the input, and the last sentence of the output is kept.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict, dataclass, field

from app.controller.semantic_controller import INTERVENE, ControllerConfig, SemanticController
from app.modules.context_selector import ContextConfig, ContextSelector, context_rewrites
from app.modules.idiom_detector import IdiomConfig, IdiomDetector
from app.modules.idiom_resolver import IDIOM_MODES, idiom_rewrites
from app.modules.rewrite import apply_rewrites

CONTEXT_MODES = ("none", "selected", "concat")
_SENT_SPLIT = re.compile(r"(?<=[.!?।。؟])\s+")


@dataclass(frozen=True)
class PipelineConfig:
    idiom_enabled: bool = True
    idiom_mode: str = "paraphrase"  # hint | paraphrase   (see docs/DECISIONS.md D10)
    context_mode: str = "none"  # none | selected | concat
    idiom: IdiomConfig = field(default_factory=IdiomConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)

    def __post_init__(self):
        if self.idiom_mode not in IDIOM_MODES:
            raise ValueError(f"idiom_mode must be one of {IDIOM_MODES}")
        if self.context_mode not in CONTEXT_MODES:
            raise ValueError(f"context_mode must be one of {CONTEXT_MODES}")

    @property
    def condition_name(self) -> str:
        parts = []
        if self.idiom_enabled:
            parts.append(f"idiom_{self.idiom_mode}")
        if self.context_mode != "none":
            parts.append(f"context_{self.context_mode}")
        if not parts:
            return "A_baseline"
        letter = "D" if len(parts) == 2 else ("B" if self.idiom_enabled else "C")
        return f"{letter}_" + "+".join(parts)

    @property
    def active_modules(self) -> list[str]:
        mods = ["idiom"] if self.idiom_enabled else []
        if self.context_mode == "selected":
            mods.append("context")
        elif self.context_mode == "concat":
            mods.append("context_concat")
        return mods

    def as_dict(self) -> dict:
        return {"idiom_enabled": self.idiom_enabled, "idiom_mode": self.idiom_mode, "context_mode": self.context_mode,
                "idiom": self.idiom.as_dict(), "context": self.context.as_dict(), "controller": self.controller.as_dict()}


class _Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 2)


def _event(stage: str, status: str, duration_ms: float, details: dict | None = None) -> dict:
    return {"stage": stage, "status": status, "duration_ms": duration_ms, "details": details or {}}


def extract_last_sentence(translation: str, n_source_sentences: int) -> tuple[str, list[str]]:
    """For concat mode: keep the last sentence of the output. Warn if segment counts disagree."""
    parts = [p for p in _SENT_SPLIT.split(translation.strip()) if p.strip()]
    warnings = []
    if len(parts) != n_source_sentences:
        warnings.append(f"concat alignment uncertain: {n_source_sentences} source sentences, {len(parts)} output segments")
    return (parts[-1] if parts else ""), warnings


@dataclass
class PipelineResult:
    record: dict
    events: list[dict]
    translation_result: object  # TranslationResult


class SemanticPipeline:
    def __init__(self, engine, config: PipelineConfig | None = None, detector: IdiomDetector | None = None,
                 selector: ContextSelector | None = None):
        self.engine = engine
        self.config = config or PipelineConfig()
        self.detector = detector or IdiomDetector(config=self.config.idiom)
        self.selector = selector or ContextSelector(config=self.config.context)
        self.controller = SemanticController(self.config.controller)

    def prepare(self, text: str, source_lang: str, context: list[str] | None = None) -> tuple[dict, list[dict]]:
        """Run everything up to (not including) translation. Returns (partial record, events).
        record["nllb_input"] is exactly what must be sent to NLLB."""
        cfg = self.config
        context = [c for c in (context or []) if c and c.strip()]
        events = [_event("input", "done", 0.0, {"text": text, "context_sentences": len(context)})]

        candidates = []
        if cfg.idiom_enabled:
            t = _Timer()
            candidates = self.detector.detect(text, source_lang, context)
            events.append(_event("idiom_detection", "done", t.ms(), {"candidates": [c.as_dict() for c in candidates]}))
        else:
            events.append(_event("idiom_detection", "skipped", 0.0, {"reason": "module disabled in this condition"}))

        analysis = None
        if cfg.context_mode == "selected":
            t = _Timer()
            analysis = self.selector.analyze(text, source_lang, context)
            events.append(_event("context_analysis", "done", t.ms(), analysis.as_dict()))
        elif cfg.context_mode == "concat":
            window = context[-cfg.context.window_size:]
            events.append(_event("context_analysis", "concat_all", 0.0,
                                 {"reason": "diagnostic control: all window sentences prepended, no selection",
                                  "window": window}))
        else:
            events.append(_event("context_analysis", "skipped", 0.0, {"reason": "context disabled in this condition"}))

        t = _Timer()
        ctrl = self.controller.decide(candidates, analysis)
        rewrites = []
        if ctrl.decision == INTERVENE:
            rewrites = idiom_rewrites(text, ctrl.accepted_idioms, cfg.idiom_mode) + context_rewrites(text, ctrl.accepted_context_words)
        modified = apply_rewrites(text, rewrites) if rewrites else None
        sentence_for_nllb = modified or text

        concat_window: list[str] = []
        if cfg.context_mode == "concat" and context:
            concat_window = context[-cfg.context.window_size:]
            nllb_input = " ".join(concat_window + [sentence_for_nllb])
        else:
            nllb_input = sentence_for_nllb
        events.append(_event("controller", "done", t.ms(), {**ctrl.as_dict(), "idiom_mode": cfg.idiom_mode,
                                                           "rewrites": [asdict(r) for r in rewrites],
                                                           "nllb_input": nllb_input}))
        record = {
            "condition": cfg.condition_name,
            "active_modules": cfg.active_modules,
            "module_predictions": {},
            "confidence_scores": {},
            "thresholds": {"idiom": cfg.idiom.as_dict(), "context": cfg.context.as_dict(), "controller": cfg.controller.as_dict()},
            "controller_decision": ctrl.decision,
            "span_decisions": ctrl.as_dict()["span_decisions"],
            "conflicts": ctrl.conflicts,
            "idiom_mode": cfg.idiom_mode if cfg.idiom_enabled else None,
            "context_mode": cfg.context_mode,
            "original_sentence": text,
            "context": context,
            "selected_context": analysis.selected_context if analysis else [],
            "context_state": analysis.state if analysis else None,
            "concat_window": concat_window,
            "modified_sentence": modified,
            "rewrites": [asdict(r) for r in rewrites],
            "abstention_reason": ctrl.abstention_reason,
            "nllb_input": nllb_input,
            "_n_source_sentences": len(concat_window) + 1,
        }
        if cfg.idiom_enabled:
            record["module_predictions"]["idiom"] = [
                {"idiom_id": c.idiom_id, "matched_text": c.matched_text, "usage": c.usage,
                 "intended_meaning": c.intended_meaning, "review_status": c.review_status,
                 "figurative_cues": c.figurative_cues_found, "literal_cues": c.literal_cues_found,
                 "literal_follower": c.literal_follower_found} for c in candidates]
            record["confidence_scores"]["idiom"] = {
                c.idiom_id: {"usage_score": c.usage_score, "entry_confidence": c.entry_confidence} for c in candidates}
        if analysis:
            record["module_predictions"]["context"] = [
                {"word_id": w.word_id, "matched_text": w.matched_text, "state": w.state, "resolved_sense": w.resolved_sense,
                 "resolved_gloss": w.resolved_gloss, "replacement": w.replacement} for w in analysis.words]
            record["confidence_scores"]["context"] = {w.word_id: w.sense_support for w in analysis.words}
        return record, events

    @staticmethod
    def finalize(record: dict, events: list[dict], result) -> None:
        """Attach the NLLB result to the record (shared by run() and batch scripts)."""
        final = result.translation
        warnings = list(result.warnings)
        n = record.pop("_n_source_sentences", 1)
        if record["concat_window"] and result.status != "error":
            final, w = extract_last_sentence(result.translation, n)
            warnings += w
            record["raw_concat_translation"] = result.translation
        record.update({"final_translation": final, "translation_status": result.status,
                       "translation_warnings": warnings, "translation_error": result.error})
        events.append(_event("translation", result.status, result.latency_ms, {"nllb_input": record["nllb_input"]}))
        events.append(_event("output", "done", 0.0, {"final_translation": final, "warnings": warnings}))

    def run(self, text: str, source_lang: str, target_lang: str, context: list[str] | None = None,
            example_id: str | None = None) -> PipelineResult:
        t_all = _Timer()
        record, events = self.prepare(text, source_lang, context)
        t = _Timer()
        result = self.engine.translate(record["nllb_input"], source_lang, target_lang)
        translation_ms = t.ms()
        self.finalize(record, events, result)
        record.update({
            "example_id": example_id or f"adhoc-{uuid.uuid4().hex[:8]}",
            "source_lang": source_lang,
            "target_lang": target_lang,
            "latency_ms": {"total": t_all.ms(), "translation": translation_ms,
                           "modules": round(sum(e["duration_ms"] for e in events if e["stage"] in
                                                ("idiom_detection", "context_analysis", "controller")), 2)},
        })
        return PipelineResult(record=record, events=events, translation_result=result)
