"""URL → dubbed tracks + subtitles. Each step caches its artifact in the run dir; delete it to redo.

uv run python -m dub.pipeline https://youtu.be/<id> --to en,ja,zh-Hans --max-sec 180"""
import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import (agent, brief as briefmod, config, events, fetch, gem, mix, para, proofread, review,
               separate, stt, subs, translate, units as unitsmod, voice)


def _cached(p: Path, make):
    if p.exists():
        return json.loads(p.read_text())
    v = make()
    p.write_text(json.dumps(v, ensure_ascii=False, indent=1))
    return v


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def run_dir_for(vid: str, max_sec: float | None) -> Path:
    return config.RUNS / (f"{vid}.{int(max_sec)}s" if max_sec else vid)


def prepare(url: str, max_sec: float | None) -> tuple[Path, dict, float]:
    """Download once into runs/<id>/, then cut (dev/demo mode) into runs/<id>.<N>s/."""
    vid = fetch.video_id(url)
    base = config.RUNS / vid
    info = fetch.fetch(url, base, max_sec)
    events.log(base, "fetched", title=info.get("title"))
    run_dir = run_dir_for(vid, max_sec)
    run_dir.mkdir(parents=True, exist_ok=True)
    total = min(max_sec, info["duration"]) if max_sec else info["duration"]
    if run_dir != base:
        for name in ("source.wav", "source.stt.flac", "source.mp4"):
            if not (run_dir / name).exists():
                extra = ["-c", "copy"] if name.endswith(".mp4") else []
                _ff("-i", str(base / name), "-t", str(total), *extra, str(run_dir / name))
        (run_dir / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return run_dir, info, total


def dub_language(run_dir: Path, us: list[dict], src: str, lang: str, brf: dict, total: float,
                 bed: Path | None) -> dict:
    t0 = time.time()
    d = run_dir / "dub" / lang
    d.mkdir(parents=True, exist_ok=True)
    done = d.parent / f"{lang}.json"
    remix = done.exists()   # agent already ran: only re-place and re-mix, log nothing new
    texts = _cached(d / "texts.json", lambda: translate.expand(us, translate.translate(us, src, lang, brf),
                                                                src, lang, brf))
    if remix:
        prev = json.loads(done.read_text())
        rows, t0 = prev["rows"], time.time() - prev["report"]["sec"]
        pre = [bool(r["actions"][0].get("pre")) for r in rows]
        for i, r in enumerate(rows):   # give flagged lines another pass (e.g. after a guard change)
            if not r["ok"]:
                rows[i] = agent.repair_line(us[i], r["text"], src, lang, brf, d, run_dir, False)
    else:
        events.log(run_dir, "translated", lang=lang, lines=len(texts))
        pre = [False] * len(us)
        with ThreadPoolExecutor(8) as ex:
            for g, ok in ex.map(lambda g: (g, _safe_group(g, us, texts, lang, d)), para.groups(us)):
                for i in g:
                    pre[i] = ok
        events.log(run_dir, "voiced", lang=lang, para_lines=sum(pre), lines=len(us))
        with ThreadPoolExecutor(8) as ex:
            rows = list(ex.map(lambda i: agent.repair_line(us[i], texts[i], src, lang, brf, d, run_dir, pre[i]),
                               range(len(us))))
    take = [False] * len(us)
    for g in para.groups(us):
        for k, i in enumerate(g):
            take[i] = pre[i] and k > 0
    repaired = [any(a["do"] in ("shorten", "resynth", "retranslate") for a in r["actions"]) for r in rows]
    flow = unitsmod.flow_gaps(us, take, repaired, [r["text"] for r in rows])
    timeline = run_dir / "dub" / f"{lang}.voice.wav"
    drift = mix.place(us, [d / f"{r['id']:04d}.wav" for r in rows], total, timeline, flow)
    drift.pop("starts")
    out = run_dir / "out"
    out.mkdir(exist_ok=True)
    mix.mix(timeline, bed, out / f"dub.{lang}.m4a")
    srt = subs.srt(us, [r["text"] for r in rows], lang)
    (out / f"subs.{lang}.srt").write_text(srt)
    (out / f"subs.{lang}.vtt").write_text(subs.vtt(srt))
    if (run_dir / "source.mp4").exists():
        _ff("-i", str(run_dir / "source.mp4"), "-i", str(out / f"dub.{lang}.m4a"), "-map", "0:v", "-map", "1:a",
            "-c", "copy", "-shortest", "-movflags", "+faststart", str(out / f"video.{lang}.mp4"))
    rep = {"lang": lang, "lines": len(rows), "ok": sum(r["ok"] for r in rows),
           "first_pass_ok": sum(1 for r in rows if [a["do"] for a in r["actions"]].count("check") == 1 and r["ok"]),
           "shortened": sum(1 for r in rows if any(a["do"] == "shorten" for a in r["actions"])),
           "para_lines": sum(pre), "sec": round(time.time() - t0, 1), **drift}
    (d.parent / f"{lang}.json").write_text(json.dumps({"report": rep, "rows": rows}, ensure_ascii=False, indent=1))
    if not remix:
        events.log(run_dir, "language_done", **rep)
    return rep


def _safe_group(g, us, texts, lang, d) -> bool:
    if all((d / f"{us[i]['id']:04d}.tts.wav").exists() for i in g):
        return True
    try:
        return para.synth_group([texts[i] for i in g], lang, d, [us[i]["id"] for i in g])
    except Exception:  # noqa: BLE001  per-line synthesis in the agent is the fallback
        return False


def main(url: str, to: list[str] | None = None, max_sec: float | None = None, separate_bed: bool = True) -> Path:
    t0 = time.time()
    run_dir, info, total = prepare(url, max_sec)
    if "channel_id" not in info:   # info.json written before channel_id was kept
        raw = json.loads((config.RUNS / fetch.video_id(url) / "source.info.json").read_text())
        info["channel_id"] = raw.get("channel_id")
    config.ACTIVE["voice"] = config.voice_for(info)
    events.log(run_dir, "voice", voice="cloned" if config.ACTIVE["voice"] == config.VOICE_ID else "preset",
               consent=config.ACTIVE["voice"] == config.VOICE_ID)
    events.log(run_dir, "start", url=url, title=info.get("title"), duration=total)
    bed = None
    if separate_bed:
        _, bed = separate.separate(run_dir)
        events.log(run_dir, "separated")
    audio, wav = run_dir / "source.stt.flac", run_dir / "source.wav"
    src_guess = unitsmod.detect_language(f"{info.get('title', '')} {info.get('description', '')}")
    words = _cached(run_dir / "words.json", lambda: stt.chirp_words(audio, src_guess, run_dir))
    events.log(run_dir, "transcribed", words=len(words), engine="chirp_3")
    cues = _cached(run_dir / "cues.json", lambda: proofread.proofread(audio, words, info, src_guess))
    src = unitsmod.detect_language(" ".join(c["text"] for c in cues))
    us = unitsmod.make_units(cues, total)
    (run_dir / "units.json").write_text(json.dumps(us, ensure_ascii=False, indent=1))
    events.log(run_dir, "proofread", cues=len(cues), src=src)
    (run_dir / "out").mkdir(exist_ok=True)
    srt = subs.srt(us, [u["text"] for u in us], src)
    (run_dir / "out" / f"subs.{src}.srt").write_text(srt)
    (run_dir / "out" / f"subs.{src}.vtt").write_text(subs.vtt(srt))
    if (run_dir / "source.mp4").exists() and not (run_dir / "out" / "video.orig.mp4").exists():
        _ff("-i", str(run_dir / "source.mp4"), "-c", "copy", "-movflags", "+faststart",
            str(run_dir / "out" / "video.orig.mp4"))
    brf = _cached(run_dir / "brief.json", lambda: briefmod.make_brief(us, info, src))
    events.log(run_dir, "brief", summary=brf["summary"], terms=len(brf["terms"]))
    langs = to or unitsmod.targets_for(src)
    with ThreadPoolExecutor(len(langs)) as ex:
        reports = list(ex.map(lambda l: dub_language(run_dir, us, src, l, brf, total, bed), langs))
    summary = {"video": info.get("id"), "title": info.get("title"), "src": src, "duration": total,
               "units": len(us), "langs": reports, "gemini_text_usd": gem.cost(), "tts_calls": voice.CALLS["n"],
               "sec_total": round(time.time() - t0, 1)}
    (run_dir / "out" / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    review.write(run_dir, wav, us, langs)
    events.log(run_dir, "done", units=len(us), sec_total=summary["sec_total"])
    return run_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--to", default="")
    ap.add_argument("--max-sec", type=float, default=0)
    ap.add_argument("--no-bed", action="store_true", help="skip demucs; dub track has no background")
    a = ap.parse_args()
    print(main(a.url, [x for x in a.to.split(",") if x] or None, a.max_sec or None, not a.no_bed))
