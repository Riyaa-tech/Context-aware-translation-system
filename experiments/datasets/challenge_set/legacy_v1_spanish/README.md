# Legacy v1 development data (Spanish scope)

These three files are the **unchanged** v1 development sets used before the scope change of 2026-11-02, when
Spanish was removed from the study and replaced by German (no Spanish-speaking evaluator; see `docs/DECISIONS.md` D31).

| File | sha256 | Used by |
|---|---|---|
| `idiom_dev.jsonl` | `3fb2d30498eb748219692c3b1b693497c064c711685eb6150969f17e019531dd` | run `pilot_dev_20261101T104108Z_89efe420c3f8`, dev explorations of 2026-11-01 |
| `context_dev.jsonl` | `5f9dfb87e15b91b41b398c576da6516e1728f97e93c006b6e314e5bf37021fb6` | same |
| `sarcasm_dev.jsonl` | `cddb49503087ae9bbd9a243ea504322d4af38b08f5dbbd5179b37a3024d55d5c` | same |

- The run manifests record these files at their old path (`experiments/datasets/challenge_set/<file>`); the hashes
  above match the manifests, so the files can be verified.
- They contain Spanish rows (`spa_Latn`), which the current validator rejects. They are kept only as a record and
  are **not** part of the active project. Active dev data: `../*_v2.jsonl`.
- All rows were manually authored by Claude (AI assistant) for development; not an established benchmark.
