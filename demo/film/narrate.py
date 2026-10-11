"""Narration for the v2 film in the creator's consented clone; each take must pass the product's own listening check."""
import json, re, sys
from pathlib import Path
from dub import check, config, voice

script = Path("demo/film/SCRIPT.md").read_text()
lines = dict(re.findall(r"^(N\d) — (.+)$", script, re.M))
out = Path("demo/film/narration"); out.mkdir(parents=True, exist_ok=True)
man = json.loads((out / "manifest.json").read_text()) if (out / "manifest.json").exists() else {}
for key, text in lines.items():
    if man.get(key, {}).get("text") == text:
        continue
    for attempt in range(3):
        p = out / f"{key}.wav"
        voice.synth(text, p, voice_id=config.VOICE_ID, lang="en")
        v = check.check(p, text, "en", text, "en")
        ok = all(v.get(k) is True for k in ("language_ok", "content_ok", "meaning_ok"))
        print(key, attempt, round(voice.duration(p), 2), ok, v.get("issue", ""), flush=True)
        if ok:
            break
    man[key] = {"text": text, "seconds": voice.duration(p), "ok": ok, "verdict": v}
    (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2))
print("total", round(sum(m["seconds"] for m in man.values()), 1))
