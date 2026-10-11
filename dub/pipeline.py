"""URL → dubbed tracks + subtitles. Each step caches its artifact in the run dir; delete it to redo.

uv run python -m dub.pipeline https://youtu.be/<id> --to en,ja,zh-Hans --max-sec 180"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import (agent, brief as briefmod, config, events, fetch, gem, mix, para, proofread, review,
               separate, speakers, stt, subs, translate, units as unitsmod, voice)


PARAGRAPH = os.environ.get("DUB_PARAGRAPH") == "1"


def _cached(p: Path, make):
    if p.exists():
        return json.loads(p.read_text())
    v = make()
    p.write_text(json.dumps(v, ensure_ascii=False, indent=1))
    return v


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


CACHE_POLICY = "2026-10-10-scene-timeline-best-match-v2"


def _fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def cache_identity(run_dir: Path) -> dict:
    """Bound source bytes and voice/casting policy to cached IDs; contains no credentials."""
    audio = run_dir / "source.wav"
    digest = hashlib.sha256()
    with audio.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"policy": CACHE_POLICY, "source_audio_sha256": digest.hexdigest(),
            "casting_code_sha256": hashlib.sha256(Path(speakers.__file__).read_bytes()).hexdigest(),
            "verification_threshold": os.environ.get("DUB_VERIFY_THRESHOLD", "0.45"),
            "voice_policy": _fingerprint({"voice": config.VOICE_ID, "model": config.TTS_MODEL,
                    "channels": sorted(config.CONSENTED_CHANNELS), "fallback": config.FALLBACK_VOICE})}


def guard_cache(run_dir: Path, units: list[dict] | None = None) -> None:
    """Refuse stale normal-run caches. Explicit offline_remix deliberately bypasses
    this guard because it reuses fixed cached clips without casting or paid calls.
    Never delete legacy work or silently regenerate it against reassigned unit IDs.
    """
    path = run_dir / "cache-identity.json"
    identity = cache_identity(run_dir)
    prior = json.loads(path.read_text()) if path.exists() else None
    legacy = any((run_dir / name).exists() for name in ("units.json", "cast.json", "dub"))
    message = ("Incompatible cached run. Preserve this directory and use a new isolated run directory "
               "for synthesis, or --offline-remix for a strictly cache-only remix.")
    if prior is None and legacy:
        raise ValueError(message)
    if prior and any(prior.get(k) != v for k, v in identity.items()):
        raise ValueError(message)
    if units is not None:
        digest = _fingerprint(units)
        if prior and prior.get("units_sha256") not in (None, digest):
            raise ValueError(message)
        identity["units_sha256"] = digest
    elif prior and "units_sha256" in prior:
        identity["units_sha256"] = prior["units_sha256"]
    path.write_text(json.dumps(identity, indent=2))


def scene_cuts(run_dir: Path, duration: float) -> dict:
    """Offline hard-cut heuristic, not lip sync: sample 4 fps, scale to width 320,
    select FFmpeg scene score >0.35. Resolution is 250 ms; fades/motion may be missed
    or misclassified. Decode at most 3600 s with one thread and a 90 s wall timeout.
    Cache both success and unavailable status so a missing detector never bills an API.
    """
    cache = run_dir / "scene-cuts.json"
    if cache.exists():
        return json.loads(cache.read_text())
    result = {"algorithm": "ffmpeg-scene", "threshold": .35, "sample_fps": 4,
              "analyzed_seconds": min(duration, 3600), "cuts": [], "status": "no_video"}
    video = run_dir / "source.mp4"
    if video.exists():
        try:
            proc = subprocess.run(["ffmpeg", "-hide_banner", "-threads", "1", "-i", str(video),
                                   "-t", str(result["analyzed_seconds"]), "-an", "-filter_threads", "1",
                                   "-vf", "fps=4,scale=320:-2,select='gt(scene,0.35)',showinfo",
                                   "-f", "null", "-"], capture_output=True, text=True, timeout=90, check=True)
            result["cuts"] = sorted(set(round(float(t), 3) for t in
                                          re.findall(r"pts_time:([0-9.]+)", proc.stderr)))
            result["status"] = "complete" if duration <= 3600 else "partial"
        except (subprocess.SubprocessError, OSError):
            result["status"] = "unavailable"
    cache.write_text(json.dumps(result, indent=2))
    return result


def anchor_scenes(cues: list[dict], cuts: list[float]) -> list[dict]:
    """Never split speech at a visual cut. Protect an existing boundary only when
    the cut falls in its source pause; report in-sentence cuts for review instead.
    """
    result = []
    for i, original in enumerate(cues):
        cue = dict(original)
        before = [t for t in cuts if (cues[i-1]["end"] if i else 0) <= t <= cue["start"]]
        inside = [t for t in cuts if cue["start"] < t < cue["end"]]
        if before:
            cue.update(hard_anchor=True, scene_cut=True, scene_cuts_before=before)
        if inside:
            cue["scene_cuts_inside"] = inside
        result.append(cue)
    return result


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
                 bed: Path | None, offline: bool = False) -> dict:
    t0 = time.time()
    d = run_dir / "dub" / lang
    d.mkdir(parents=True, exist_ok=True)
    done = d.parent / f"{lang}.json"
    remix = done.exists()   # agent already ran: only re-place and re-mix, log nothing new
    if offline and not done.exists():
        raise ValueError(f"Offline remix requires cached rows: {done}")
    texts = ([r["text"] for r in json.loads(done.read_text())["rows"]] if offline else
             _cached(d / "texts.json", lambda: translate.expand(us, translate.translate(us, src, lang, brf),
                                                                src, lang, brf)))
    if remix:
        prev = json.loads(done.read_text())
        rows = prev["rows"]
        pre = [bool((r.get("actions") or [{}])[0].get("pre")) for r in rows]
        for i, r in enumerate(rows):   # give flagged lines another pass (e.g. after a guard change)
            if not r["ok"] and not offline:
                rows[i] = agent.repair_line(us[i], r["text"], src, lang, brf, d, run_dir, False, texts[max(0, i - 3):i])
    else:
        events.log(run_dir, "translated", lang=lang, lines=len(texts))
        pre = [False] * len(us)
        if PARAGRAPH:   # off by default: units are whole sentences, and cutting takes failed for Japanese
            with ThreadPoolExecutor(8) as ex:
                for g, ok in ex.map(lambda g: (g, _safe_group(g, us, texts, lang, d)), para.groups(us)):
                    for i in g:
                        pre[i] = ok
        events.log(run_dir, "voiced", lang=lang, para_lines=sum(pre), lines=len(us))
        with ThreadPoolExecutor(8) as ex:
            rows = list(ex.map(lambda i: agent.repair_line(us[i], texts[i], src, lang, brf, d, run_dir, pre[i],
                                                           texts[max(0, i - 3):i]),
                               range(len(us))))
    take = [False] * len(us)
    for g in para.groups(us):
        for k, i in enumerate(g):
            take[i] = pre[i] and k > 0
    repaired = [any(a["do"] in ("shorten", "resynth", "retranslate") for a in r["actions"]) for r in rows]
    flow = unitsmod.flow_gaps(us, take, repaired, [r["text"] for r in rows])
    timeline = run_dir / "dub" / f"{lang}.voice.wav"
    drift = mix.place(us, [d / f"{r['id']:04d}.wav" for r in rows], total, timeline, flow)
    starts, ends = drift.pop("starts"), drift.pop("ends")
    for u, r, start, end in zip(us, rows, starts, ends):
        r.update(source_start=u["start"], source_end=u["end"],
                 start=start, end=end, dub_start=start, dub_end=end)
    out = run_dir / "out"
    out.mkdir(exist_ok=True)
    mix.mix(timeline, bed, out / f"dub.{lang}.m4a")
    for row in rows:
        for n, action in enumerate(row.get("actions", [])):
            if action.get("audio_file") and action.get("ok") is False:
                source = (d / action["audio_file"]).resolve()
                if source.is_relative_to(d.resolve()) and source.is_file():
                    key = f"line.{lang}.{row['id']}.attempt{n}.wav"
                    shutil.copy2(source, out / key)
                    action["audio_key"] = key
    timeline_rows = [{"id": r["id"], "source_start": u["start"], "source_end": u["end"],
                      "start": r["dub_start"], "end": r["dub_end"], "spk": u.get("spk"),
                      "tempo": r["tempo"], "hard_anchor": bool(u.get("hard_anchor")),
                      "scene_cuts_before": u.get("scene_cuts_before", []),
                      "scene_cuts_inside": u.get("scene_cuts_inside", [])} for u, r in zip(us, rows)]
    (out / f"timeline.{lang}.json").write_text(json.dumps(timeline_rows, indent=2))
    srt = subs.srt(timeline_rows, [r["text"] for r in rows], lang)
    (out / f"subs.{lang}.srt").write_text(srt)
    (out / f"subs.{lang}.vtt").write_text(subs.vtt(srt))
    if (run_dir / "source.mp4").exists():
        _ff("-i", str(run_dir / "source.mp4"), "-i", str(out / f"dub.{lang}.m4a"), "-map", "0:v", "-map", "1:a",
            "-c", "copy", "-movflags", "+faststart", str(out / f"video.{lang}.mp4"))
    rep = {"lang": lang, "src": src, "lines": len(rows), "ok": sum(r["ok"] for r in rows),
           "first_pass_ok": sum(1 for r in rows if [a["do"] for a in r["actions"]].count("check") == 1 and r["ok"]),
           "shortened": sum(1 for r in rows if any(a["do"] == "shorten" for a in r["actions"])),
           "para_lines": sum(pre),
           "sec": prev["report"].get("sec") if remix else round(time.time() - t0, 1),
           "scene_anchor_crossings": sum(1 for i, u in enumerate(us) if i and
                u.get("scene_cuts_before") and ends[i-1] > min(u["scene_cuts_before"])), **drift}
    if remix:
        rep["remix_sec"] = round(time.time() - t0, 3)
        if "timing_provenance" in prev["report"]:
            rep["timing_provenance"] = prev["report"]["timing_provenance"]
    else:
        rep["timing_provenance"] = "measured_language_generation_wall_clock"
    (d.parent / f"{lang}.json").write_text(json.dumps({"report": rep, "rows": rows}, ensure_ascii=False, indent=1))
    if not offline:
        events.log(run_dir, "language_done", **rep)
    return rep


def _safe_group(g, us, texts, lang, d) -> bool:
    if all((d / f"{us[i]['id']:04d}.tts.wav").exists() for i in g):
        return True
    try:
        return para.synth_group([texts[i] for i in g], lang, d, [us[i]["id"] for i in g], us[g[0]].get("voice"))
    except Exception:  # noqa: BLE001  per-line synthesis in the agent is the fallback
        return False


def main(url: str, to: list[str] | None = None, max_sec: float | None = None, separate_bed: bool = True,
         on_language_done=None) -> Path:
    t0 = time.time()
    run_dir, info, total = prepare(url, max_sec)
    guard_cache(run_dir)
    if "channel_id" not in info:   # info.json written before channel_id was kept
        raw = json.loads((config.RUNS / fetch.video_id(url) / "source.info.json").read_text())
        info["channel_id"] = raw.get("channel_id")
    config.ACTIVE["voice"] = config.voice_for(info)
    events.log(run_dir, "voice", voice="pending" if config.ACTIVE["voice"] == config.VOICE_ID else "preset",
               consent=False, verification_pending=config.ACTIVE["voice"] == config.VOICE_ID)
    events.log(run_dir, "start", url=url, title=info.get("title"), duration=total)
    bed = vocals = None
    if separate_bed:
        vocals, bed = separate.separate(run_dir)
        events.log(run_dir, "separated")
    audio, wav = run_dir / "source.stt.flac", run_dir / "source.wav"
    src_guess = unitsmod.guess_source(info)
    words = _cached(run_dir / "words.json", lambda: stt.chirp_words(audio, src_guess, run_dir))
    events.log(run_dir, "transcribed", words=len(words), engine="chirp_3")
    cues = _cached(run_dir / "cues.json", lambda: proofread.proofread(audio, words, info, src_guess))
    src = unitsmod.detect_language(" ".join(c["text"] for c in cues))
    scenes = scene_cuts(run_dir, total)
    us = unitsmod.make_units(anchor_scenes(speakers.label_cues(cues, words), scenes["cuts"]), total)
    guard_cache(run_dir, us)
    consent = config.ACTIVE["voice"] == config.VOICE_ID
    cast = _cached(run_dir / "cast.json", lambda: speakers.cast(us, vocals, config.VOICE_ID, consent, run_dir))
    for u in us:
        u["voice"] = cast[u.get("spk") or "1"]["voice"]
    events.log(run_dir, "cast", speakers=[{"spk": s, **c} for s, c in cast.items()])
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
    langs = unitsmod.pick_targets(to, src)
    reports, failures = _languages(run_dir, us, src, langs, brf, total, bed, on_language_done)
    summary = {"video": info.get("id"), "title": info.get("title"), "src": src, "duration": total,
               "units": len(us), "langs": reports, "failures": failures, "gemini_text_usd": gem.cost(), "tts_calls": voice.CALLS["n"],
               "sec_total": round(time.time() - t0, 1), "scene_detection": scenes,
               "publication_warnings": [{"lang": r["lang"], "error": r["publication_warning"]}
                                        for r in reports if r.get("publication_warning")]}
    (run_dir / "out" / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    review.write(run_dir, wav, us, [r["lang"] for r in reports])
    events.log(run_dir, "done", units=len(us), sec_total=summary["sec_total"])
    return run_dir


def _languages(run_dir, us, src, langs, brf, total, bed, callback=None, offline=False):
    reports, failures = {}, []
    with ThreadPoolExecutor(max(1, min(3, len(langs)))) as ex:
        pending = {ex.submit(dub_language, run_dir, us, src, lang, brf, total, bed, offline): lang
                   for lang in langs}
        for future in as_completed(pending):
            lang = pending[future]
            try:
                report = future.result()
                reports[lang] = report
            except Exception as exc:
                failures.append({"lang": lang, "error": type(exc).__name__})
                continue
            if callback:
                try:
                    callback(run_dir, lang, report)
                except Exception as exc:
                    report["publication_warning"] = type(exc).__name__
    return [reports[l] for l in langs if l in reports], failures


def regenerate_line(run_dir: Path, lang: str, line_id: int, text: str) -> dict:
    """Regenerate one row inside a caller-provided isolated revision workspace.

    Caller owns preview/acceptance and must not supply the accepted original workspace.
    Other rows, including flagged rows, are remixed without paid retries.
    """
    run_dir = Path(run_dir)
    if not text.strip():
        raise ValueError("Replacement text must not be empty")
    us = json.loads((run_dir / "units.json").read_text())
    summary = json.loads((run_dir / "out" / "report.json").read_text())
    brf = json.loads((run_dir / "brief.json").read_text())
    cached = run_dir / "dub" / f"{lang}.json"
    data = json.loads(cached.read_text())
    idx = next((i for i, u in enumerate(us) if u["id"] == line_id), None)
    if idx is None:
        raise ValueError("Unknown line id")
    before = {k: v for k, v in data["rows"][idx].items() if k != "revision_before"}
    row = agent.repair_line(us[idx], text.strip(), summary["src"], lang, brf,
                            run_dir / "dub" / lang, run_dir, False,
                            [r["text"] for r in data["rows"][max(0, idx - 3):idx]],
                            preserve_user_text=True)
    row["revision_before"] = before
    data["rows"][idx] = row
    cached.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    bed = resolve_bed(run_dir)
    report = dub_language(run_dir, us, summary["src"], lang, brf, summary["duration"],
                          bed, offline=True)
    summary["langs"] = [report if r["lang"] == lang else r for r in summary["langs"]]
    (run_dir / "out" / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return report


def resolve_bed(run_dir: Path) -> Path | None:
    return next((p for p in (run_dir / "bed.wav", run_dir / "no_vocals.wav") if p.exists()), None)


def offline_remix(run_dir: Path, to: list[str] | None = None) -> Path:
    """Explicit cache-only entrypoint. Never downloads, repairs, transcribes or synthesizes.

    Existing clips/recordings stay untouched. Only derived timeline, captions, mixes and review
    artifacts are regenerated; the original generation cost/time remains in the report.
    """
    run_dir = Path(run_dir)
    old = json.loads((run_dir / "out" / "report.json").read_text())
    us = json.loads((run_dir / "units.json").read_text())
    scenes = scene_cuts(run_dir, old["duration"])
    us = anchor_scenes(us, scenes["cuts"])
    old["scene_detection"] = scenes
    (run_dir / "units.json").write_text(json.dumps(us, ensure_ascii=False, indent=1))
    langs = to or [r["lang"] for r in old["langs"]]
    bed = resolve_bed(run_dir)
    reports, failures = _languages(run_dir, us, old["src"], langs, {}, old["duration"], bed, offline=True)
    if failures:
        raise RuntimeError(f"Offline remix failed: {failures}")
    updated = {r["lang"]: r for r in reports}
    old["langs"] = [updated.get(r["lang"], r) for r in old["langs"]]
    old["offline_remixed"] = True
    (run_dir / "out" / "report.json").write_text(json.dumps(old, ensure_ascii=False, indent=1))
    review.write(run_dir, run_dir / "source.wav", us, [r["lang"] for r in old["langs"]])
    return run_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--offline-remix", type=Path, help="Remix an existing run from cached clips; no API calls")
    ap.add_argument("--to", default="")
    ap.add_argument("--max-sec", type=float, default=0)
    ap.add_argument("--no-bed", action="store_true", help="skip demucs; dub track has no background")
    a = ap.parse_args()
    targets = [x for x in a.to.split(",") if x] or None
    if a.offline_remix:
        print(offline_remix(a.offline_remix, targets))
    elif a.url:
        print(main(a.url, targets, a.max_sec or None, not a.no_bed))
    else:
        ap.error("url or --offline-remix is required")
