"""Per-line repair loop: measure → shorten → stretch → listen → resynthesize / retranslate → accept.

Every action is logged to events.jsonl; the web UI replays it as the agent's live work log."""
from pathlib import Path

from . import check, events, fit, translate, voice

MAX_STEPS = 4


def repair_line(u: dict, text: str, src: str, lang: str, brief: dict, d: Path, run_dir: Path,
                pre: bool) -> dict:
    raw, out = d / f"{u['id']:04d}.tts.wav", d / f"{u['id']:04d}.wav"
    acts: list[dict] = []

    def act(do: str, **kw):
        acts.append({"do": do, **kw})
        events.log(run_dir, "line", lang=lang, id=u["id"], do=do, **kw)

    dur = voice.duration(raw) if pre else voice.synth(text, raw)
    act("synth", dur=round(dur, 2), slot=u["slot"], pre=pre)
    for _ in range(2):
        if not fit.needs_shorter(dur, u["slot"]):
            break
        text = translate.shorten(u["text"], text, lang, u["slot"], dur / u["slot"])
        act("shorten", text=text)
        dur = voice.synth(text, raw)
        act("synth", dur=round(dur, 2), slot=u["slot"])
    v = {"heard": "", "issue": ""}
    for attempt in range(MAX_STEPS):
        tempo = fit.decide_tempo(dur, u["slot"], allow_slow=not pre)
        final = fit.stretch(raw, out, tempo)
        v = (check.check(out, text, lang) if check.audible(out) else
             {"heard": "", "language_ok": False, "content_ok": False, "issue": "silent or truncated clip"})
        act("check", ok=v["language_ok"] and v["content_ok"], issue=v["issue"])
        if v["language_ok"] and v["content_ok"]:
            return {"id": u["id"], "text": text, "dur": round(final, 3), "slot": u["slot"],
                    "tempo": round(tempo, 3), "actions": acts, "ok": True, "issue": "", "heard": v["heard"]}
        if attempt == 0:
            act("resynth")
        elif attempt == 1:
            text = translate._batch([u], src, lang, brief, [])[0] or text
            act("retranslate", text=text)
        else:
            break
        dur = voice.synth(text, raw)
    return {"id": u["id"], "text": text, "dur": round(voice.duration(out), 3), "slot": u["slot"],
            "tempo": round(fit.decide_tempo(dur, u["slot"], allow_slow=not pre), 3), "actions": acts, "ok": False,
            "issue": v["issue"], "heard": v["heard"]}
