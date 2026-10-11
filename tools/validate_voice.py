"""Plan or run isolated, explicitly budgeted validation of saved source lines.

Default is offline dry-run. Execution requires --execute, --budget-usd, and
explicit per-request estimated allowances. Those allowances are operator inputs,
NOT verified Google prices or guaranteed request maxima. No automatic refunds
are inferred from audio duration or token usage. Provider-side billing can differ.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from dub.budget import Budget


def fingerprint(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "sha256": digest, "bytes": path.stat().st_size}


@contextmanager
def guarded_requests(budget: Budget, voice_allowance: float, text_allowance: float):
    """Wrap actual network attempts so inner retries also consume admission slots."""
    from dub import gem, voice
    original_client, original_open = gem.client, voice.urllib.request.urlopen
    evidence = {"text_usage": [], "final_audio": []}

    class Models:
        def generate_content(self, **kwargs):
            with budget.reserve("text", text_allowance):
                result = original_client().models.generate_content(**kwargs)
                usage = getattr(result, "usage_metadata", None)
                if usage:
                    evidence["text_usage"].append({k: getattr(usage, k, None) for k in
                        ("prompt_token_count", "candidates_token_count", "thoughts_token_count")})
                return result

    def open_voice(request, *args, **kwargs):
        if getattr(request, "full_url", None) != voice.URL:
            raise RuntimeError("Validation allows only the configured TTS endpoint through this transport")
        with budget.reserve("tts", voice_allowance):
            return original_open(request, *args, **kwargs)

    gem.client = lambda: SimpleNamespace(models=Models())
    voice.urllib.request.urlopen = open_voice
    try:
        yield evidence
    finally:
        gem.client = original_client
        voice.urllib.request.urlopen = original_open


def build_plan(run: Path, langs: list[str], ids: list[int] | None) -> tuple[dict, list[dict], dict]:
    required = [run / name for name in ("units.json", "brief.json", "cast.json", "out/report.json")]
    units = json.loads(required[0].read_text())
    summary = json.loads(required[-1].read_text())
    if summary["duration"] > 180:
        raise ValueError("This validation tool is restricted to cached runs of at most 180 seconds")
    if len(langs) != len(set(langs)) or not langs or any(l not in {"en", "ja", "zh-Hans", "ko"} for l in langs):
        raise ValueError("Select unique supported target languages")
    chosen = units if ids is None else [u for u in units if u["id"] in ids]
    if not chosen or (ids is not None and {u["id"] for u in chosen} != set(ids)):
        raise ValueError("Select existing source line IDs")
    if len(chosen) * len(langs) > 69:
        raise ValueError("Validation is limited to 69 line-language pairs")
    return ({"run": str(run.resolve()), "source_language": summary["src"], "languages": langs,
             "line_ids": [u["id"] for u in chosen], "line_language_pairs": len(chosen) * len(langs),
             "inputs": [fingerprint(p) for p in required],
             "scope": "Fresh translation, speech, and audio checks only; no source fetch, cloud upload, or STT",
             "notice": "Dry run reads cached inputs only. Execution requires prior approval and explicit allowances."},
            chosen, json.loads(required[1].read_text()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--langs", nargs="+", default=["en", "ja", "zh-Hans"])
    parser.add_argument("--line-ids", type=int, nargs="+")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--run-budget-usd", type=float)
    parser.add_argument("--ledger-path", type=Path)
    parser.add_argument("--selection-kind", choices=["stress-set", "heldout"], default="stress-set")
    parser.add_argument("--tts-allowance-usd", type=float)
    parser.add_argument("--text-allowance-usd", type=float)
    parser.add_argument("--max-tts-calls", type=int, default=120)
    parser.add_argument("--max-text-calls", type=int, default=200)
    args = parser.parse_args()
    plan, units, brief = build_plan(args.run, args.langs, args.line_ids)
    plan["implementation"] = [fingerprint(Path(__file__).resolve().parents[1] / "dub" / f"{name}.py")
                              for name in ("agent", "check", "translate", "voice", "fit", "gem", "budget")]
    if args.output.exists() or args.output.resolve().is_relative_to(args.run.resolve()):
        parser.error("Choose a new isolated output directory outside the source run")
    plan["output"] = str(args.output.resolve())
    plan["selection_kind"] = args.selection_kind
    plan["spending_guard"] = {"global_estimated_budget_usd": args.budget_usd,
        "run_estimated_budget_usd": args.run_budget_usd, "tts_allowance_usd": args.tts_allowance_usd,
        "text_allowance_usd": args.text_allowance_usd,
        "ledger": str(args.ledger_path.resolve()) if args.ledger_path else None,
        "max_calls": {"tts": args.max_tts_calls, "text": args.max_text_calls}}
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if any(v is None or v <= 0 for v in (args.budget_usd, args.tts_allowance_usd, args.text_allowance_usd)):
        parser.error("Execution requires positive budget-usd, tts-allowance-usd, and text-allowance-usd")
    if args.ledger_path is None:
        parser.error("Execution requires --ledger-path to preserve reservations across trials")
    budget = Budget(args.budget_usd, {"tts": args.max_tts_calls, "text": args.max_text_calls},
                    ledger_path=args.ledger_path, run_cap_usd=args.run_budget_usd)
    # Imports do not read keys; credential access begins only inside admitted calls.
    import os
    from dub import agent, config, translate, voice
    # Execute only with explicitly provisioned current-project environment keys.
    # Never silently fall back to a generic keychain credential or another account.
    text_key, tts_key = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_TTS_API_KEY")
    if not text_key or not tts_key:
        parser.error("Execution requires both explicit VibeRick GEMINI_API_KEY and GEMINI_TTS_API_KEY environment values; keychain fallback is disabled")
    if __import__("dub.gem", fromlist=["_client"])._client is not None:
        parser.error("Run validation in a fresh process with no previously initialized Gemini client")
    original_keys = config.gemini_key, config.tts_key
    args.output.mkdir(parents=True)
    for name in ("units.json", "brief.json", "cast.json"):
        shutil.copy2(args.run / name, args.output / name)
    (args.output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    rows, evidence = {}, {}
    try:
        config.gemini_key, config.tts_key = lambda: text_key, lambda: tts_key
        with guarded_requests(budget, args.tts_allowance_usd, args.text_allowance_usd) as evidence:
            for lang in args.langs:
                destination = args.output / "dub" / lang
                destination.mkdir(parents=True)
                rows[lang] = []
                texts = translate.expand(units, translate.translate(units, plan["source_language"], lang, brief),
                                         plan["source_language"], lang, brief)
                for index, unit in enumerate(units):
                    text = texts[index]
                    row = agent.repair_line(unit, text, plan["source_language"], lang, brief,
                                            destination, args.output, False, [r["text"] for r in rows[lang][-3:]])
                    rows[lang].append(row)
                    audio = destination / f"{unit['id']:04d}.wav"
                    evidence["final_audio"].append({"language": lang, "id": unit["id"],
                        "final_wav_bytes": audio.stat().st_size, "seconds": voice.duration(audio)})
                    (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    finally:
        config.gemini_key, config.tts_key = original_keys
        (args.output / "budget.json").write_text(json.dumps({**budget.snapshot(), "usage_evidence": evidence}, indent=2))


if __name__ == "__main__":
    main()
