"""Annotation store (blinding, persistence, export) and run evaluation report.
Engine is MOCKED; all ratings are SYNTHETIC fixtures, never presented as human judgments."""
import json

import pytest
from fastapi.testclient import TestClient

from app.annotation.store import AnnotationError, AnnotationStore
from app.api.deps import get_store
from app.evaluation.report import aggregate_rating, evaluate_run
from app.experiments.runner import ROOT, ExperimentRunner, read_predictions
from app.main import app
from tests.conftest import FakeEngine

DEV = ["experiments/datasets/challenge_set/idiom_dev.jsonl"]


@pytest.fixture
def run(tmp_path):
    r = ExperimentRunner(FakeEngine(), runs_dir=tmp_path / "runs")
    exp = r.create({"name": "t", "split": "dev", "seed": 1, "datasets": DEV, "conditions": ["A", "B_paraphrase"],
                    "limit": 12, "_config_file": "test"})
    r.run(exp)
    preds = {c: read_predictions(exp, c, r.runs_dir) for c in ("A", "B_paraphrase")}
    return exp, r.runs_dir, preds


@pytest.fixture
def store(tmp_path):
    return AnnotationStore(tmp_path / "ann.sqlite3")


def test_batch_merges_identical_outputs_and_hides_conditions(run, store):
    exp, _, preds = run
    b = store.create_batch(exp, preds)
    changed = sum(a["final_translation"] != p["final_translation"] for a, p in zip(preds["A"], preds["B_paraphrase"]))
    assert b["n_items"] == 12 + changed and b["n_condition_outputs"] == 24
    view = store.rater_items(b["batch_id"], "rater_1")
    item = view["items"][0]
    assert "condition" not in json.dumps(item) and "category" not in item
    assert set(item) >= {"source_text", "context", "intended_meaning", "translation", "item_id"}


def test_rater_orders_differ_but_are_stable(run, store):
    exp, _, preds = run
    bid = store.create_batch(exp, preds)["batch_id"]
    o1 = [i["item_id"] for i in store.rater_items(bid, "r1")["items"]]
    assert o1 == [i["item_id"] for i in store.rater_items(bid, "r1")["items"]]
    assert o1 != [i["item_id"] for i in store.rater_items(bid, "r2")["items"]]


def test_save_validate_update_and_export(run, store):
    exp, _, preds = run
    bid = store.create_batch(exp, preds)["batch_id"]
    iid = store.rater_items(bid, "r1")["items"][0]["item_id"]
    with pytest.raises(AnnotationError):
        store.save_annotation({"item_id": iid, "rater_id": "r1", "rating": "great"})
    with pytest.raises(AnnotationError):
        store.save_annotation({"item_id": iid, "rater_id": "r1", "rating": "partial", "primary_error": "bogus"})
    with pytest.raises(AnnotationError):
        store.save_annotation({"item_id": iid, "rater_id": "bad id!", "rating": "partial"})
    store.save_annotation({"item_id": iid, "rater_id": "r1", "rating": "partial", "primary_error": "idiom_literal_translation"})
    store.save_annotation({"item_id": iid, "rater_id": "r1", "rating": "preserved"})  # update, not duplicate
    rows = store.export(bid)
    assert len(rows) == 1 and rows[0]["rating"] == "preserved" and rows[0]["conditions"]
    assert store.rater_items(bid, "r1", only_pending=True)["done"] == 1
    assert "rating" in store.export_csv(bid).splitlines()[0]
    # persistence: a new store object on the same file sees the data
    assert AnnotationStore(store.path).export(bid)[0]["rating"] == "preserved"


def test_aggregation_rule():
    assert aggregate_rating({}) == (None, "unrated")
    assert aggregate_rating({"a": "partial"}) == ("partial", "single_rater")
    assert aggregate_rating({"a": "preserved", "b": "preserved"}) == ("preserved", "agreement")
    assert aggregate_rating({"a": "preserved", "b": "not_preserved"}) == ("not_preserved", "conservative_minimum")
    assert aggregate_rating({"a": "preserved", "b": "partial", "adjudicator": "preserved"}) == ("preserved", "adjudicated")


def test_report_without_ratings_marks_spr_unavailable(run):
    exp, runs_dir, _ = run
    rep = evaluate_run(exp, runs_dir=runs_dir)
    assert rep["semantic"]["available"] is False and "human" in rep["semantic"]["reason"]
    assert rep["general_quality"]["A"]["available"] is False  # no references in this dev set
    assert rep["controller"]["B_paraphrase"]["intervention_coverage"] > 0
    assert rep["detectors"]["B_paraphrase"]["idiom"]["n_items"] == 12


def test_report_with_synthetic_ratings(run, store):
    exp, runs_dir, preds = run
    bid = store.create_batch(exp, preds)["batch_id"]
    # SYNTHETIC fixture: rater says changed (B) outputs preserved, unchanged baseline outputs not preserved.
    a_out = {r["example_id"]: r["final_translation"] for r in preds["A"]}
    for rater in ("r1", "r2"):
        for it in store.rater_items(bid, rater)["items"]:
            eid = next(r["example_id"] for r in preds["A"] + preds["B_paraphrase"]
                       if r["final_translation"] == it["translation"] and r["original_sentence"] == it["source_text"])
            rating = "not_preserved" if it["translation"] == a_out[eid] else "preserved"
            store.save_annotation({"item_id": it["item_id"], "rater_id": rater, "rating": rating})
    rep = evaluate_run(exp, store=store, batch_id=bid, runs_dir=runs_dir)
    sem = rep["semantic"]
    assert sem["available"] and sem["single_rater_limitation"] is False
    assert sem["per_condition"]["A"]["overall"]["spr"] == 0.0
    d = sem["per_condition"]["B_paraphrase"]["delta_vs_A"]["overall"]
    assert d["delta_pp"] > 0 and d["mcnemar"]["n10_worsened"] == 0
    assert sem["inter_rater_agreement"]["r1|r2"]["three_class"]["kappa"] == 1.0
    assert sem["per_condition"]["B_paraphrase"]["harmful_intervention"]["harmful"] == 0


def test_report_general_quality_with_references(tmp_path):
    rows = [json.loads(l) for l in open(ROOT / DEV[0], encoding="utf-8")][:6]
    for r in rows:
        r["reference_translation"] = f"[{r['target_language']}] {r['source_text']}"  # equals FakeEngine echo
    ds = tmp_path / "ref.jsonl"
    ds.write_text("\n".join(json.dumps(r) for r in rows))
    rn = ExperimentRunner(FakeEngine(), runs_dir=tmp_path / "runs")
    exp = rn.create({"name": "g", "split": "dev", "seed": 1, "datasets": [str(ds)], "conditions": ["A", "B_paraphrase"],
                     "_config_file": "t"})
    rn.run(exp)
    rep = evaluate_run(exp, runs_dir=rn.runs_dir, bootstrap_samples=50)
    a = rep["general_quality"]["A"]["by_direction"]["eng_Latn-hin_Deva"]
    assert a["chrfpp"]["score"] == 100.0 and "tok:13a" in a["bleu_13a"]["signature"]
    assert "paired_bootstrap_vs_A" in rep["general_quality"]["B_paraphrase"]


def test_annotation_api(run, store):
    exp, runs_dir, preds = run
    bid = store.create_batch(exp, preds)["batch_id"]
    app.dependency_overrides[get_store] = lambda: store
    try:
        c = TestClient(app)
        assert "preserved" in c.get("/api/annotations/rubric").json()["ratings"]
        assert c.get("/api/annotations/batches").json()["batches"][0]["batch_id"] == bid
        items = c.get(f"/api/annotations?batch_id={bid}&rater_id=r9").json()["items"]
        ok = c.post("/api/annotations", json={"item_id": items[0]["item_id"], "rater_id": "r9", "rating": "partial"})
        assert ok.status_code == 200
        assert c.post("/api/annotations", json={"item_id": items[0]["item_id"], "rater_id": "r9", "rating": "x"}).status_code == 400
        assert c.get(f"/api/annotations/export?batch_id={bid}").text.count("\n") == 0  # one JSONL row
        assert c.get(f"/api/annotations/export?batch_id={bid}&format=csv").status_code == 200
        assert c.get("/annotate-lite").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_research_endpoints_on_fake_run(run, store, monkeypatch):
    exp, runs_dir, preds = run
    import app.api.routes_research as rr
    import app.evaluation.report as rep_mod
    import app.experiments.runner as runner_mod

    monkeypatch.setattr(runner_mod, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(rr, "list_runs", lambda: runner_mod.list_runs(runs_dir))
    real = rep_mod.evaluate_run
    monkeypatch.setattr(rr, "evaluate_run", lambda e, **kw: real(e, runs_dir=runs_dir, **kw))
    app.dependency_overrides[get_store] = lambda: store
    try:
        c = TestClient(app)
        m = c.get(f"/api/research/metrics?experiment_id={exp}").json()
        assert m["semantic"]["available"] is False
        a = c.get("/api/research/ablation").json()
        rows = {r["condition"]: r for r in a["rows"]}
        assert a["semantic_available"] is False
        assert rows["A"]["spr_overall"] is None and rows["A"]["chrfpp"] is None  # unavailable -> null, never 0
        assert rows["B_paraphrase"]["intervention_coverage"] > 0
    finally:
        app.dependency_overrides.clear()
