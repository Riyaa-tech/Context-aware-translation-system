"""Fetch FLORES-200 (original NLLB release, CC-BY-SA 4.0) and convert directions to dataset JSONL.

  python scripts/fetch_flores.py                      # the 10 study directions, dev + devtest
  python scripts/fetch_flores.py --directions eng_Latn-hin_Deva

FLORES 'dev'     -> our split 'dev'   (smoke tests / pilots)
FLORES 'devtest' -> our split 'test'  (benchmark; runs need the frozen decision rule)
Output: experiments/datasets/flores/flores_<flores_split>_<src>-<tgt>.jsonl  (git-ignored; reproducible)
"""
import argparse
import hashlib
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.languages import DIRECTIONS  # noqa: E402

URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
SHA256 = "b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6"  # recorded 2026-11-01
RAW = ROOT / "experiments" / "datasets" / "flores" / "raw"
OUT = ROOT / "experiments" / "datasets" / "flores"
PROVENANCE = ("FLORES-200 (NLLB Team, 2022), original release archive flores200_dataset.tar.gz from "
              "dl.fbaipublicfiles.com; licence CC-BY-SA 4.0; established benchmark")


def fetch() -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    tgz = RAW / "flores200_dataset.tar.gz"
    if not tgz.exists():
        print("downloading", URL)
        urllib.request.urlretrieve(URL, tgz)
    digest = hashlib.sha256(tgz.read_bytes()).hexdigest()
    if digest != SHA256:
        sys.exit(f"checksum mismatch: {digest} != {SHA256} (archive changed; record the new release before use)")
    return tgz


_CACHE: dict[str, list[str]] = {}


def read_split(tgz: Path, lang: str, split: str) -> list[str]:
    """Read one language file straight from the archive (nothing is extracted to disk)."""
    if not _CACHE:
        with tarfile.open(tgz, "r:gz") as t:
            for m in t.getmembers():
                if m.isfile() and m.name.lstrip("./").startswith("flores200_dataset/dev"):
                    _CACHE[m.name.lstrip("./")] = t.extractfile(m).read().decode("utf-8").splitlines()
    name = f"flores200_dataset/{split}/{lang}.{split}"
    if name not in _CACHE:
        sys.exit(f"{name} not in archive")
    return _CACHE[name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--directions", default=",".join(d.key for d in DIRECTIONS))
    a = ap.parse_args()
    tgz = fetch()
    for key in a.directions.split(","):
        src, tgt = key.split("-")
        for fsplit, our in (("dev", "dev"), ("devtest", "test")):
            s, t = read_split(tgz, src, fsplit), read_split(tgz, tgt, fsplit)
            if len(s) != len(t):
                sys.exit(f"{key} {fsplit}: line counts differ ({len(s)} vs {len(t)})")
            out = OUT / f"flores_{fsplit}_{key}.jsonl"
            with open(out, "w", encoding="utf-8") as f:
                for i, (x, y) in enumerate(zip(s, t)):
                    f.write(json.dumps({"example_id": f"FLORES_{fsplit}_{key}_{i:04d}", "source_language": src,
                                        "target_language": tgt, "category": "general_benchmark", "source_text": x,
                                        "context": [], "intended_meaning": None, "reference_translation": y,
                                        "provenance": PROVENANCE, "split": our, "flores_split": fsplit,
                                        "flores_line": i}, ensure_ascii=False) + "\n")
            print(f"{out.relative_to(ROOT)}: {len(s)} sentences (our split '{our}')")
    print(f"archive sha256 {SHA256}")


if __name__ == "__main__":
    main()
