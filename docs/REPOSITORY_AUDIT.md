# Repository Audit (Milestone 0)

**Date:** 2026-11-01
**Repository:** https://github.com/Riyaa-tech/Context-aware-translation-system
**Auditor:** Claude Code (cloud session)

## 1. What exists

| Item | Finding |
|---|---|
| Branches / commits | **None.** `git ls-remote` returns no refs. The repository is genuinely empty. |
| README / docs | None |
| Frontend | None |
| Backend | None |
| Models / configs | None |
| Tests | None |
| Env files / credentials | None (nothing to protect or overwrite) |
| TODOs / mocks / placeholders | None (no code) |

**Conclusion:** there is no existing code to reuse or preserve. The architecture will be built from scratch.

## 2. Current architecture / technologies

None yet. Recommended stack is in `docs/IMPLEMENTATION_PLAN.md`.

## 3. Completed functionality

None.

## 4. Missing functionality

Everything listed in the master prompt (sections 4–13): translation engine, M1 idiom module, M2 context module,
semantic controller, challenge dataset, FLORES integration, evaluation (BLEU, chrF++, SPR, statistics),
annotation workflow, experiment runner, API and frontend.

## 5. Technical debt

None (empty repository).

## 6. Environment findings (this cloud session)

| Resource | Status |
|---|---|
| CPU | 4 cores |
| RAM | 15 GB (enough for NLLB-600M in fp32, ~2.5 GB) |
| GPU | **None.** All inference will be CPU-only here. |
| Disk | ~31 GB free |
| Python | 3.13 |
| Node.js | 22 |
| huggingface.co (model `facebook/nllb-200-distilled-600M`) | Reachable |
| PyPI, PyTorch CPU wheels, npm | Reachable |
| FLORES-200 tarball (`dl.fbaipublicfiles.com`) | Reachable |
| Push access to the GitHub repo | **Not available yet** (re-checked after the user asked for it; still refused). The user must connect GitHub / install the Claude GitHub App on the repo at https://claude.ai/connect-github. Until then, work is committed locally. |

### Compute implications

- Rough expectation for CPU: about 1–3 seconds per sentence with NLLB-600M (to be measured, not assumed).
- Full FLORES devtest = 1,012 sentences × 10 directions ≈ 10,000 translations → several CPU hours per condition.
  Plan: a one-direction smoke test, then transparent pilot subsets, with checkpoint/resume so a full run can be
  done later on a GPU (e.g. Colab).
- The challenge set pilot (~100–150 examples × 4 conditions) is very feasible on CPU.

## 7. Gaps in inputs (need user action)

1. ~~Research paper not found.~~ **Resolved:** paper received (24 pages, draft, states no experiments run).
   Alignment notes are in `docs/IMPLEMENTATION_PLAN.md` § "Paper alignment".
2. **Human annotators.** SPR needs real human ratings. The software will collect them; it will not create them.
   Please confirm how many raters are available (1 or 2+).
3. **Push access** (see table above).

## 8. Recommended implementation changes

Since the repository is empty, the recommendation is a clean, small architecture:
Python/FastAPI backend + React (Vite) TypeScript frontend + SQLite + JSONL experiment artifacts.
See `docs/IMPLEMENTATION_PLAN.md`.
