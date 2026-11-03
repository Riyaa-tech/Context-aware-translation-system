"""NLLB-200 translation engine.

The backbone is used exactly as released: no fine-tuning, no weight changes.
All experimental conditions call `translate_batch` with the same GenerationConfig.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

from app.config.settings import GenerationConfig, Settings

log = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    source_text: str
    translation: str
    source_lang: str
    target_lang: str
    # ok | empty_output | input_truncated | error   (failures are reported, never dropped)
    status: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class TranslationBackend(Protocol):
    """Anything that can translate a batch. Unit tests use a fake implementation."""

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[TranslationResult]: ...

    @property
    def is_loaded(self) -> bool: ...

    def info(self) -> dict: ...


class NLLBEngine:
    """Lazily loads and caches the model once per process; thread-safe generation."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gen: GenerationConfig = settings.generation
        self._model = None
        self._tokenizer = None
        self._device = None
        self._resolved_revision: str | None = None
        self._loading = False
        self._load_error: str | None = None
        self._load_seconds: float | None = None
        self._load_lock = threading.Lock()
        self._gen_lock = threading.Lock()

    # ---------- loading ----------
    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def state(self) -> str:
        """not_loaded | loading | ready | error (shown on /health so the UI can tell users what is happening)."""
        if self._model is not None:
            return "ready"
        if self._loading:
            return "loading"
        return "error" if self._load_error else "not_loaded"

    def load(self) -> None:
        """Load once (same model, revision and settings as always); records failures for /health."""
        with self._load_lock:
            if self._model is not None:
                return
            self._loading, self._load_error = True, None
            try:
                self._load_model()
            except Exception as e:
                self._load_error = f"{type(e).__name__}: {e}"
                log.exception("Model loading failed")
                raise
            finally:
                self._loading = False

    def _load_model(self) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        t0 = time.perf_counter()
        dev = self.settings.device
        if dev == "auto":
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        torch.manual_seed(self.settings.seed)
        log.info("Loading %s @ %s on %s", self.settings.model_id, self.settings.model_revision, dev)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.settings.model_id, revision=self.settings.model_revision
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.settings.model_id, revision=self.settings.model_revision
        )
        model.eval()
        model.to(dev)
        self._device = dev
        self._resolved_revision = getattr(model.config, "_commit_hash", None) or self.settings.model_revision
        self._model = model
        self._load_seconds = time.perf_counter() - t0
        log.info("Model loaded in %.1fs (revision %s)", self._load_seconds, self._resolved_revision)

    # ---------- inference ----------
    def _lang_token_id(self, lang: str) -> int:
        tok_id = self._tokenizer.convert_tokens_to_ids(lang)
        if tok_id is None or tok_id == self._tokenizer.unk_token_id:
            raise ValueError(f"Tokenizer has no language token for '{lang}'")
        return tok_id

    def _generate(self, texts: list[str], source_lang: str, target_lang: str) -> list[TranslationResult]:
        import torch

        tok = self._tokenizer
        tok.src_lang = source_lang
        forced_bos = self._lang_token_id(target_lang)

        # Count tokens without truncation first, so truncation is detected and reported.
        full_lens = [len(ids) for ids in tok(texts, add_special_tokens=True)["input_ids"]]
        enc = tok(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.gen.max_input_tokens,
        ).to(self._device)

        t0 = time.perf_counter()
        with self._gen_lock, torch.inference_mode():
            out = self._model.generate(
                **enc,
                forced_bos_token_id=forced_bos,
                num_beams=self.gen.num_beams,
                max_new_tokens=self.gen.max_new_tokens,
                do_sample=self.gen.do_sample,
                length_penalty=self.gen.length_penalty,
                early_stopping=self.gen.early_stopping,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        decoded = tok.batch_decode(out, skip_special_tokens=True)

        results = []
        per_item_ms = elapsed_ms / max(len(texts), 1)
        for i, (src, hyp) in enumerate(zip(texts, decoded)):
            hyp = hyp.strip()
            out_len = int((out[i] != tok.pad_token_id).sum().item())
            warnings: list[str] = []
            status = "ok"
            if full_lens[i] > self.gen.max_input_tokens:
                status = "input_truncated"
                warnings.append(f"Input had {full_lens[i]} tokens; truncated to {self.gen.max_input_tokens}.")
            if out_len >= self.gen.max_new_tokens:
                warnings.append("Output reached max_new_tokens and may be cut off.")
            if not hyp:
                status = "empty_output"
            results.append(
                TranslationResult(
                    source_text=src,
                    translation=hyp,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    status=status,
                    latency_ms=round(per_item_ms, 1),
                    input_tokens=min(full_lens[i], self.gen.max_input_tokens),
                    output_tokens=out_len,
                    warnings=warnings,
                )
            )
        return results

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[TranslationResult]:
        """Translate texts in mini-batches. A failing batch is retried item by item,
        and items that still fail are returned with status="error" (never dropped)."""
        if not texts:
            return []
        self.load()
        results: list[TranslationResult] = []
        bs = max(1, self.settings.batch_size)
        for start in range(0, len(texts), bs):
            chunk = texts[start : start + bs]
            try:
                results.extend(self._generate(chunk, source_lang, target_lang))
            except Exception as exc:  # includes torch.OutOfMemoryError
                log.warning("Batch failed (%s); retrying items one at a time", exc)
                self._free_memory()
                for text in chunk:
                    try:
                        results.extend(self._generate([text], source_lang, target_lang))
                    except Exception as exc2:
                        self._free_memory()
                        results.append(
                            TranslationResult(
                                source_text=text,
                                translation="",
                                source_lang=source_lang,
                                target_lang=target_lang,
                                status="error",
                                latency_ms=0.0,
                                error=f"{type(exc2).__name__}: {exc2}",
                            )
                        )
        return results

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        return self.translate_batch([text], source_lang, target_lang)[0]

    def _free_memory(self) -> None:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def info(self) -> dict:
        return {
            "model_id": self.settings.model_id,
            "requested_revision": self.settings.model_revision,
            "resolved_revision": self._resolved_revision,
            "loaded": self.is_loaded,
            "state": self.state,
            "load_error": self._load_error,
            "device": self._device,
            "load_seconds": round(self._load_seconds, 2) if self._load_seconds else None,
            "batch_size": self.settings.batch_size,
            "generation_config": self.gen.as_dict(),
        }
