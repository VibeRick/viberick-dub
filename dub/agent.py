"""Per-line repair loop: measure → shorten → stretch → listen → resynthesize / retranslate → accept.

Every action is logged to events.jsonl; the web UI replays it as the agent's live work log."""
from pathlib import Path
import re
import shutil

from . import check, events, fit, translate, voice

MAX_STEPS = 4
MIN_KEEP = 0.5   # never accept a rewrite under half the current length
UNDERFILL = 0.80  # measured underfill: test fuller source-faithful phrasing before leaving a long gap
_FILLER = re.compile(r"[\s.,!?…~음어아네예흠]+$")


def repair_line(u: dict, text: str, src: str, lang: str, brief: dict, d: Path, run_dir: Path,
                pre: bool, prev: list[str] | None = None, preserve_user_text: bool = False) -> dict:
    raw, out = d / f"{u['id']:04d}.tts.wav", d / f"{u['id']:04d}.wav"
    acts: list[dict] = []

    def act(do: str, **kw):
        acts.append({"do": do, **kw})
        events.log(run_dir, "line", lang=lang, id=u["id"], do=do, **kw)

    if not text.strip():
        out.write_bytes(voice._silence_wav(0.3))
        filler = bool(_FILLER.fullmatch(u["text"].strip())) or not u["text"].strip()
        issue = "" if filler else "Translation is empty for a meaningful source line."
        act("skip" if filler else "flag", issue=issue)
        return {"id": u["id"], "text": "", "dur": 0.3, "slot": u["slot"], "tempo": 1.0, "actions": acts,
                "ok": filler, "issue": issue, "heard": ""}

    # Fix obvious script leakage before paying for speech. Metadata helps delivery but is not a language lock.
    for _ in range(0 if preserve_user_text else 2):
        problem = translate.script_issue(text, lang)
        if not problem:
            break
        act("translation_flag", issue=problem)
        text = translate._batch([u], src, lang, brief, prev or [])[0] or text
        pre = False  # the paragraph take contains the old translation
        act("retranslate", text=text)
    if problem := translate.script_issue(text, lang):
        out.write_bytes(voice._silence_wav(0.3))
        act("flag", issue=problem)
        return {"id": u["id"], "text": text, "dur": 0.3, "slot": u["slot"], "tempo": 1.0,
                "actions": acts, "ok": False, "issue": problem, "heard": ""}

    dur = voice.duration(raw) if pre else voice.synth(text, raw, voice_id=u.get("voice"), lang=lang)
    act("synth", dur=round(dur, 2), slot=u["slot"], pre=pre)

    if not preserve_user_text and not pre and dur / u["slot"] < UNDERFILL:
        fuller = translate.fuller(u, text, lang, dur, brief)
        if (fuller != text and len(text) < len(fuller) <= translate.budget(lang, u["slot"]) * 1.1
                and not translate.script_issue(fuller, lang)):
            candidate = d / f"{u['id']:04d}.fuller.wav"
            candidate_dur = voice.synth(fuller, candidate, voice_id=u.get("voice"), lang=lang)
            # Keep the original take if fuller wording is not actually a better duration fit.
            if abs(candidate_dur - u["slot"]) < abs(dur - u["slot"]) and candidate_dur <= u["slot"] * 1.15:
                candidate.replace(raw)
                text, dur = fuller, candidate_dur
                act("lengthen", text=text, dur=round(dur, 2), slot=u["slot"])
            else:
                candidate.unlink(missing_ok=True)
    for _ in range(0 if preserve_user_text else 2):
        if not fit.needs_shorter(dur, u["slot"]):
            break
        shorter = translate.shorten(u["text"], text, lang, u["slot"], dur / u["slot"])
        if len(shorter.strip()) < MIN_KEEP * len(text.strip()) or translate.script_issue(shorter, lang):
            break   # a tiny slot would gut the line ("あ"): keep it and let the spill absorb it
        text = shorter
        act("shorten", text=text)
        dur = voice.synth(text, raw, voice_id=u.get("voice"), lang=lang)
        act("synth", dur=round(dur, 2), slot=u["slot"])
    v = {"heard": "", "issue": ""}
    for attempt in range(MAX_STEPS):
        final = fit.finish(raw, out)
        v = check.normalize_verdict(check.check(out, text, lang, u["text"], src) if check.audible(out) else
             {"heard": "", "language_ok": False, "content_ok": False, "meaning_ok": False,
              "issue": "silent or truncated clip"})
        accepted = all(v[k] is True for k in ("language_ok", "content_ok", "meaning_ok"))
        audio = {}
        if not accepted:
            saved = d / "attempts" / f"{u['id']:04d}" / f"check-{attempt}.wav"
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out, saved)
            audio = {"audio_file": saved.relative_to(d).as_posix(), "text": text}
        act("check", ok=accepted, issue=v["issue"], meaning_ok=v["meaning_ok"], **audio)
        if accepted:
            timing_issue = ""
            if preserve_user_text and (final / u["slot"] < UNDERFILL or final > u["slot"] * 1.05):
                timing_issue = "Manual text preserved; speech underfills its slot." if final < u["slot"] else "Manual text preserved; speech exceeds its slot."
                act("flag", issue=timing_issue)
            return {"id": u["id"], "text": text, "dur": round(final, 3), "slot": u["slot"],
                    "tempo": 1.0, "actions": acts, "ok": not bool(timing_issue), "issue": timing_issue, "heard": v["heard"]}
        if preserve_user_text:
            if attempt >= 2:
                break
            act("resynth", text_preserved=True)
        elif attempt == 0 and (v["meaning_ok"] or v["issue"] == "silent or truncated clip"):
            act("resynth")
        elif attempt < 2:
            repair_brief = {**brief, "repair_feedback": f"Rejected candidate: {text}. Issue: {v['issue']}"}
            proposed = translate._batch([u], src, lang, repair_brief, prev or [])[0] or text
            if translate.script_issue(proposed, lang):
                act("translation_flag", issue=translate.script_issue(proposed, lang))
                break
            text = proposed
            act("retranslate", text=text)
        else:
            break
        dur = voice.synth(text, raw, voice_id=u.get("voice"), lang=lang)
    return {"id": u["id"], "text": text, "dur": round(voice.duration(out), 3), "slot": u["slot"],
            "tempo": 1.0, "actions": acts, "ok": False,
            "issue": v["issue"], "heard": v["heard"]}
