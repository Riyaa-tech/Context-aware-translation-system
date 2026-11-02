"""API tests for /enhanced and /compare (engine MOCKED)."""


def post(client, path, **body):
    payload = {"text": "She spilled the beans about the party.", "source_lang": "en", "target_lang": "hi", **body}
    return client.post(path, json=payload)


def test_enhanced_paraphrase(client, fake_engine):
    r = post(client, "/api/translate/enhanced", idiom_mode="paraphrase")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["controller_decision"] == "INTERVENE"
    assert b["nllb_input"] == "She revealed the secret about the party."
    assert b["events"][-1]["stage"] == "output"


def test_enhanced_rejects_unknown_module_and_mode(client):
    assert post(client, "/api/translate/enhanced", modules=["sarcasm"]).status_code == 422
    assert post(client, "/api/translate/enhanced", idiom_mode="magic").status_code == 422


def test_compare(client, fake_engine):
    r = post(client, "/api/translate/compare", idiom_mode="paraphrase")
    b = r.json()
    assert r.status_code == 200
    assert b["baseline"]["condition"] == "A_baseline"
    assert b["baseline"]["translation"] != b["enhanced"]["translation"]
    assert b["outputs_differ"] is True and b["enhanced_input_unchanged"] is False


def test_compare_ordinary_sentence(client):
    b = post(client, "/api/translate/compare", text="Good morning.").json()
    assert b["enhanced"]["controller_decision"] == "PASS_THROUGH"
    assert b["enhanced_input_unchanged"] is True and b["outputs_differ"] is False


def test_idioms_endpoint(client):
    b = client.get("/api/idioms?source_language=deu_Latn").json()
    assert b["entries"] and all(e["source_language"] == "deu_Latn" for e in b["entries"])
    assert b["counts_by_language"] == {"eng_Latn": 21, "hin_Deva": 6, "deu_Latn": 8}
    e = b["entries"][0]
    assert e["review_status"] == "draft" and e["supported_directions"] == ["deu_Latn-eng_Latn"]
    assert e["source_reference"]["source"] == "Duden online" and e["english_equivalent"]
    assert client.get("/api/idioms?source_language=spa_Latn").json()["entries"] == []


def test_enhanced_with_context(client, fake_engine):
    r = client.post("/api/translate/enhanced", json={
        "text": "He went to the bank.", "source_lang": "en", "target_lang": "hi",
        "context": ["The fisherman sat beside the river."], "modules": ["context"]})
    b = r.json()
    assert r.status_code == 200, r.text
    assert b["condition"] == "C_context_selected" and b["nllb_input"] == "He went to the riverbank."
    assert [e["stage"] for e in b["events"]][2] == "context_analysis"


def test_enhanced_concat_mode(client):
    b = client.post("/api/translate/enhanced", json={
        "text": "He went to the bank.", "source_lang": "en", "target_lang": "hi",
        "context": ["The fisherman sat beside the river."], "modules": ["context"], "context_mode": "concat"}).json()
    assert b["condition"] == "C_context_concat"


def test_too_much_context_rejected(client):
    r = client.post("/api/translate/enhanced", json={"text": "x", "source_lang": "en", "target_lang": "hi",
                                                     "context": ["a."] * 11, "modules": ["context"]})
    assert r.status_code == 422


def test_experiment_endpoints(client):
    assert any(c["name"] == "E" and not c["available"] for c in client.get("/api/experiments/conditions").json()["conditions"])
    assert client.post("/api/experiments/run", json={"config_file": "../etc/passwd"}).status_code == 400
    assert client.post("/api/experiments/run", json={}).status_code == 422
    assert client.get("/api/experiments/does_not_exist").status_code == 404
    assert "experiments" in client.get("/api/experiments").json()



def test_enhanced_german_paraphrase_and_hint(client, fake_engine):
    text = "Das glaube ich dir nicht, du nimmst mich auf den Arm!"
    p = client.post("/api/translate/enhanced", json={"text": text, "source_lang": "de", "target_lang": "en", "idiom_mode": "paraphrase"}).json()
    assert p["controller_decision"] == "INTERVENE" and p["nllb_input"] == "Das glaube ich dir nicht, du hältst mich zum Narren!"
    h = client.post("/api/translate/enhanced", json={"text": text, "source_lang": "de", "target_lang": "en", "idiom_mode": "hint"}).json()
    assert h["nllb_input"] == "Das glaube ich dir nicht, du nimmst mich auf den Arm (hältst mich zum Narren)!"
    assert fake_engine.calls[-1][1:] == ("deu_Latn", "eng_Latn")


def test_compare_german_literal_control_unchanged(client):
    b = client.post("/api/translate/compare", json={"text": "Die Mutter nimmt das weinende Kind auf den Arm.",
                                                    "source_lang": "de", "target_lang": "en"}).json()
    assert b["enhanced"]["controller_decision"] == "PASS_THROUGH" and b["enhanced_input_unchanged"] is True
