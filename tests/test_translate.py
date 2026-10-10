from dub import translate


def test_budget_scales_with_language_rate():
    assert translate.budget("en", 2.0) > translate.budget("ja", 2.0) > 0
    assert translate.budget("zh-Hans", 0.1) == 4          # floor
    assert all(translate.budget(l, 2.0) > 4 for l in ("ko", "en", "ja", "zh-Hans"))


def test_missing_ids_are_retried_one_by_one(monkeypatch):
    calls = []

    def fake_batch(batch, src, lang, brief, prev):
        calls.append([u["id"] for u in batch])
        return ["" if (u["id"] == 1 and len(batch) > 1) else f"t{u['id']}" for u in batch]

    monkeypatch.setattr(translate, "_batch", fake_batch)
    units = [{"id": i, "text": f"s{i}", "slot": 2.0} for i in range(3)]
    out = translate.translate(units, "ko", "en", {"summary": "", "terms": []})
    assert out == ["t0", "t1", "t2"] and calls[-1] == [1]


def test_budget_uses_measured_cloned_voice_rate():
    assert translate.budget("en", 2.0) == int(translate.CPS["en"] * 2.0)
    assert translate.CPS["en"] > 18 and translate.CPS["ja"] > 6.5


def test_expand_rewrites_only_underfilled_lines(monkeypatch):
    sent = []

    def fake_json(prompt, schema, **k):
        sent.append(prompt)
        return {"lines": [{"id": 1, "text": "a much fuller rendering of line one here"}, {"id": 9, "text": "x"}]}

    monkeypatch.setattr(translate.gem, "json_call", fake_json)
    units = [{"id": 0, "text": "s0", "slot": 1.0}, {"id": 1, "text": "s1", "slot": 3.0}]
    texts = ["fifteen chars..", "short"]          # 15/18 ok, 5/56 underfilled
    out = translate.expand(units, texts, "ko", "en", {"summary": "", "terms": []})
    assert out == ["fifteen chars..", "a much fuller rendering of line one here"]
    assert '"id":1' in sent[0] and '"id":0' not in sent[0]


def test_expand_ignores_rewrite_that_is_longer_than_budget(monkeypatch):
    monkeypatch.setattr(translate.gem, "json_call", lambda p, s, **k: {"lines": [{"id": 0, "text": "y" * 500}]})
    out = translate.expand([{"id": 0, "text": "s", "slot": 1.0}], ["hi"], "ko", "en", {})
    assert out == ["hi"]
