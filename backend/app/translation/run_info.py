"""Collect reproducibility information: packages, hardware, model, decoding settings."""
from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata

PACKAGES = ["torch", "transformers", "tokenizers", "sentencepiece", "sacrebleu", "fastapi", "pydantic"]


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = None
    return out


def hardware_info() -> dict:
    info: dict = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "processor": platform.processor() or platform.machine(),
    }
    try:
        import psutil

        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        info["process_rss_mb"] = round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        pass
    try:
        import torch

        info["torch_threads"] = torch.get_num_threads()
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            info["gpu_peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1e6, 1)
    except Exception:
        pass
    return info


def collect_run_info(engine_info: dict | None = None) -> dict:
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "packages": package_versions(),
        "hardware": hardware_info(),
        "model": engine_info or {},
    }
