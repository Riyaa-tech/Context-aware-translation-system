"""Experiment runner: config validation, checkpoint/resume, consistency (engine MOCKED)."""
import json

import pytest
import yaml

from app.experiments.conditions import ConditionError, get_condition, list_conditions
from app.experiments.datasets import assign_split, load_challenge_files
from app.experiments.runner import ROOT, ExperimentError, ExperimentRunner, list_runs, read_predictions
from tests.conftest import FakeEngine

DEV = ["experiments/datasets/challenge_set/idiom_dev_v2.jsonl", "experiments/datasets/challenge_set/context_dev_v2.jsonl"]


def cfg(**kw):
    base = {"name": "t", "split": "dev", "seed": 1, "datasets": DEV, "conditions": ["A", "B_paraphrase", "C_selected"],
            "batch_size": 7, "_config_file": "test"}
    base.update(kw)
    return base


@pytest.fixture
def runner(tmp_path):
    return ExperimentRunner(FakeEngine(), runs_dir=tmp_path)


def preds(runner, exp_id, cond):
    return read_predictions(exp_id, cond, runner.runs_dir)


def test_conditions_registry():
    names = {c["name"] for c in list_conditions()}
    assert {"A", "B_hint", "B_paraphrase", "C_selected", "C_concat", "D_paraphrase", "D_hint", "E"} <= names
    with pytest.raises(ConditionError, match="not implemented"):
        get_condition("E")
    with pytest.raises(ConditionError):
        get_condition("Z")


def test_config_rules(runner):
    with pytest.raises(ExperimentError, match="baseline"):
        runner.create(cfg(conditions=["B_paraphrase"]))
    with pytest.raises(ConditionError):
        runner.create(cfg(conditions=["A", "E"]))
    with pytest.raises(ExperimentError, match="decision_rule_file"):
        runner.create(cfg(split="test"))
    # the committed template is not frozen yet -> refused
    with pytest.raises(ExperimentError, match="not frozen"):
        runner.create(cfg(split="test", decision_rule_file="experiments/configs/decision_rule.yaml"))


def test_frozen_decision_rule_allows_test_run(runner, tmp_path):
    rule = ROOT / "experiments" / "configs" / "_tmp_frozen_rule_for_tests.yaml"
    rule.write_text(yaml.safe_dump({"frozen": True, "written_by": "test"}))
    try:
        with pytest.raises(ExperimentError, match="no rows with split 'test'"):  # passes the rule check, then no test rows
            runner.create(cfg(split="test", decision_rule_file=str(rule.relative_to(ROOT))))
    finally:
        rule.unlink()


def test_full_run_same_ids_and_records(runner):
    exp = runner.create(cfg())
    m = runner.run(exp)
    assert m["status"] == "complete" and m["consistency"]["ok"]
    assert m["reportable"] is False and "DEV RUN" in m["notes"][0]
    ids = {c: [r["example_id"] for r in preds(runner, exp, c)] for c in m["conditions"]}
    assert set(ids["A"]) == set(ids["B_paraphrase"]) == set(ids["C_selected"]) == set(m["example_ids"])
    r = next(x for x in preds(runner, exp, "C_selected") if x["example_id"] == "CTX_DEV_001")
    assert r["nllb_input"] == "He went to the riverbank." and r["condition"] == "C_context_selected"
    for key in ("experiment_id", "intended_meaning", "controller_decision", "final_translation", "latency_ms"):
        assert key in r
    assert m["run_info"]["packages"]["transformers"]


def test_interrupt_and_resume_gives_identical_results(tmp_path):
    r1 = ExperimentRunner(FakeEngine(), runs_dir=tmp_path / "a")
    full = r1.create(cfg())
    r1.run(full)
    r2 = ExperimentRunner(FakeEngine(), runs_dir=tmp_path / "b")
    exp = r2.create(cfg())
    m = r2.run(exp, stop_after_batches=3)
    assert m["status"] == "interrupted"
    partial = len(preds(r2, exp, "A"))
    assert 0 < partial < m["n_examples"]
    m = ExperimentRunner(FakeEngine(), runs_dir=tmp_path / "b").run(exp)  # fresh process-like resume
    assert m["status"] == "complete" and m["consistency"]["ok"] and m.get("resumed_at")
    for c in m["conditions"]:
        a = {x["example_id"]: x["final_translation"] for x in preds(r1, full, c)}
        b = {x["example_id"]: x["final_translation"] for x in preds(r2, exp, c)}
        assert a == b


def test_torn_last_line_is_redone(runner):
    exp = runner.create(cfg(conditions=["A"]))
    runner.run(exp, stop_after_batches=1)
    p = runner.runs_dir / exp / "predictions" / "A.jsonl"
    p.write_text(p.read_text() + '{"example_id": "IDIOM_DEV_0')  # simulate crash mid-write
    m = runner.run(exp)
    assert m["consistency"]["ok"] and m["conditions"]["A"]["repaired_lines"] == 1
    assert (runner.runs_dir / exp / "predictions" / "A.torn.log").exists()


def test_dataset_change_blocks_resume(runner, tmp_path):
    ds = tmp_path / "ds.jsonl"
    rows = [json.loads(l) for l in open(ROOT / DEV[0], encoding="utf-8")][:5]
    ds.write_text("\n".join(json.dumps(r) for r in rows))
    exp = runner.create(cfg(datasets=[str(ds)], conditions=["A"]))
    rows[0]["source_text"] = "changed"
    ds.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ExperimentError, match="changed"):
        runner.run(exp)


def test_failed_items_are_kept(tmp_path):
    eng = FakeEngine(fail_texts=("The train leaves at seven tomorrow morning.",))
    r = ExperimentRunner(eng, runs_dir=tmp_path)
    exp = r.create(cfg(conditions=["A"]))
    m = r.run(exp)
    recs = preds(r, exp, "A")
    bad = [x for x in recs if x["translation_status"] == "error"]
    assert len(recs) == m["n_examples"] and len(bad) == 1 and m["conditions"]["A"]["errors"] == 1


def test_never_overwrites_and_lists(runner):
    exp = runner.create(cfg(conditions=["A"], limit=3))
    runner.run(exp)
    assert list_runs(runner.runs_dir)[0]["experiment_id"] == exp
    assert len(preds(runner, exp, "A")) == 3


def test_dataset_validation_catches_errors(tmp_path):
    bad = tmp_path / "bad.jsonl"
    row = json.loads(open(ROOT / DEV[0], encoding="utf-8").readline())
    bad.write_text("\n".join([json.dumps(row), json.dumps(row), json.dumps({**row, "example_id": "X", "category": "weird"}), "{oops"]))
    errs = load_challenge_files([bad]).errors
    assert any("duplicate example_id" in e for e in errs)
    assert any("unknown category" in e for e in errs)
    assert any("invalid JSON" in e for e in errs)


def test_split_is_deterministic_and_roughly_proportional():
    ids = [f"X_{i}" for i in range(2000)]
    a = [assign_split(i, 7, 0.8) for i in ids]
    assert a == [assign_split(i, 7, 0.8) for i in ids]
    assert 0.76 < a.count("test") / len(a) < 0.84
    assert a != [assign_split(i, 8, 0.8) for i in ids]
