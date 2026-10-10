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
