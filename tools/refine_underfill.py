"""Narrow, budgeted underfill refinement; defaults to an offline plan.

Preserves source run. Uses final existing text, one agent pass per selected line,
then accepts only an automatically passed, script-clean, closer-duration take.
This is a fit experiment, not a human listening-quality verdict.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

from dub.budget import Budget, BudgetExceeded
from dub.translate import script_issue
from tools.validate_voice import fingerprint, guarded_requests


def select_rows(rows, units, limit=6):
    by_id = {u["id"]: u for u in units}
    candidates = [r for r in rows if r["id"] in by_id and r["slot"] > 0
                  and r["dur"] / r["slot"] < .82
                  and by_id[r["id"]]["end"] - by_id[r["id"]]["start"] > 1]
    return sorted(candidates, key=lambda r: (r["dur"] / r["slot"], r["id"]))[:limit]


def better(candidate, original, unit, lang):
    target = min(unit["slot"], unit["end"] - unit["start"])
    if not candidate.get("ok"):
        return False, "automated check failed"
    if script_issue(candidate.get("text", ""), lang) or script_issue(candidate.get("heard", ""), lang):
        return False, "script leakage"
    if candidate["dur"] > unit["slot"]:
        return False, "slot overflow"
    if abs(candidate["dur"] - target) >= abs(original["dur"] - target) - .02:
        return False, "duration not closer by at least 20ms"
    return True, "closer duration, passed automated checks, no script leakage or slot overflow"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger-path", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.run.resolve()):
        parser.error("Choose a new isolated output outside the input run")
    units = json.loads((args.run / "units.json").read_text())
    by_id = {u["id"]: u for u in units}
    summary = json.loads((args.run / "out/report.json").read_text())
    brief = json.loads((args.run / "brief.json").read_text())
    langs = [r["lang"] for r in summary["langs"]]
    originals = {lang: json.loads((args.run / "dub" / f"{lang}.json").read_text()) for lang in langs}
    selected = {lang: select_rows(data["rows"], units) for lang, data in originals.items()}
    inputs = [args.run / name for name in ("units.json", "brief.json", "cast.json", "source.wav", "out/report.json")]
    inputs += [args.run / "dub" / f"{lang}.json" for lang in langs]
    inputs += [args.run / "dub" / lang / f"{r['id']:04d}.wav" for lang in langs for r in selected[lang]]
    plan = {"selection": {lang: [r["id"] for r in rows] for lang, rows in selected.items()},
            "selection_kind": "measured-underfill stress set, not heldout",
            "inputs": [fingerprint(p) for p in inputs],
            "code": [fingerprint(Path("dub") / f"{n}.py") for n in ("agent", "translate", "voice", "check", "fit", "budget")],
            "tool": fingerprint(Path(__file__)),
            "spending": {"shared_cap_usd": 100, "trial_cap_usd": 20, "request_allowance_usd": .20,
                         "ledger": str(args.ledger_path.resolve()), "kind": "estimated allowance, not actual provider billing"}}
    if not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    from dub import agent, config, gem, pipeline
    from dub.quality import audit_run
    if agent.UNDERFILL != .80:
        parser.error("Refinement requires the reviewed UNDERFILL=0.80 agent")
    keys = [os.environ.get(k) for k in ("GEMINI_API_KEY", "GEMINI_TTS_API_KEY")]
    if not all(keys) or gem._client is not None:
        parser.error("Fresh process and explicit VibeRick environment keys required; no fallback")
    budget = Budget(100, {"tts": 500, "text": 500}, ledger_path=args.ledger_path, run_cap_usd=20)
    shutil.copytree(args.run, args.output)
    (args.output / "refinement-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    outcomes, evidence = [], {}
    old_keys = config.gemini_key, config.tts_key
    stopped = False
    try:
        config.gemini_key, config.tts_key = lambda: keys[0], lambda: keys[1]
        with guarded_requests(budget, .20, .20) as evidence:
            for lang in langs:
                data = originals[lang]
                for original in selected[lang]:
                    ident = original["id"]
                    unit = by_id[ident]
                    candidate_dir = args.output / "refinement-candidates" / lang / str(ident)
                    candidate_dir.mkdir(parents=True)
                    backup = args.output / "refinement-original" / lang / str(ident)
                    backup.mkdir(parents=True)
                    (backup / "row.json").write_text(json.dumps(original, ensure_ascii=False, indent=2))
                    main_dir = args.output / "dub" / lang
                    for suffix in ("wav", "tts.wav"):
                        existing = main_dir / f"{ident:04d}.{suffix}"
                        if existing.exists():
                            shutil.copy2(existing, backup / existing.name)
                    outcome = {"lang": lang, "id": ident, "original_duration": original["dur"],
                               "target_seconds": min(unit["slot"], unit["end"] - unit["start"])}
                    try:
                        index = next(i for i, r in enumerate(data["rows"]) if r["id"] == ident)
                        candidate = agent.repair_line(unit, original["text"], summary["src"], lang, brief,
                                                      candidate_dir, args.output, False,
                                                      [r["text"] for r in data["rows"][max(0, index-3):index]])
                        accepted, reason = better(candidate, original, unit, lang)
                        outcome.update(accepted=accepted, reason=reason, candidate_duration=candidate["dur"], candidate=candidate)
                        if accepted:
                            for suffix in ("wav", "tts.wav"):
                                shutil.copy2(candidate_dir / f"{ident:04d}.{suffix}", main_dir / f"{ident:04d}.{suffix}")
                            if (candidate_dir / "attempts").exists():
                                shutil.copytree(candidate_dir / "attempts", main_dir / "attempts", dirs_exist_ok=True)
                            data["rows"][index] = candidate
                    except Exception as error:
                        outcome.update(accepted=False, reason=f"candidate error: {type(error).__name__}")
                        stopped = isinstance(error, BudgetExceeded)
                    outcomes.append(outcome)
                    (args.output / "refinement-results.json").write_text(json.dumps(outcomes, ensure_ascii=False, indent=2))
                    (args.output / "dub" / f"{lang}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
                    print(f"{lang} line {ident}: {'accepted' if outcome['accepted'] else 'kept original'} ({outcome['reason']})", flush=True)
                    if stopped:
                        break
                if stopped:
                    break
    finally:
        config.gemini_key, config.tts_key = old_keys
        (args.output / "refinement-budget.json").write_text(json.dumps({**budget.snapshot(), "usage_evidence": evidence}, indent=2))
    pipeline.offline_remix(args.output)
    (args.output / "refinement-quality.json").write_text(json.dumps({"audits": [audit_run(args.run), audit_run(args.output)]}, indent=2))
    unchanged = all(fingerprint(Path(item["path"]))["sha256"] == item["sha256"] for item in plan["inputs"])
    if not unchanged:
        raise RuntimeError("Source input changed during refinement; investigate before presenting results")
    print(json.dumps({"accepted": sum(r["accepted"] for r in outcomes), "attempted": len(outcomes),
                      "budget_stopped": stopped, "source_unchanged": unchanged, "output": str(args.output)}))


if __name__ == "__main__":
    main()
