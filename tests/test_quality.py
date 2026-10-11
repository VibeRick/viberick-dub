import array
import json
import math
import shutil
import sys
import wave

import pytest

from dub import quality


def wav(path, segments, rate=16000, channels=1):
    samples = array.array("h")
    for seconds, amplitude in segments:
        samples.extend(int(amplitude * math.sin(2 * math.pi * 220 * i / rate))
                       for i in range(round(seconds * rate)) for _ in range(channels))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())
    return path


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required for PCM audit")
def test_pcm_audit_normalizes_sample_rates_and_counts_real_gap(tmp_path):
    src = wav(tmp_path / "source.wav", [(2, 8000)], rate=48000, channels=2)
    dub = wav(tmp_path / "dub.wav", [(0.5, 8000), (1, 0), (.5, 8000)], rate=24000)
    result = quality.compare_activity(quality.audio_activity(src), quality.audio_activity(dub), 2)
    assert result["source_detected_silence_seconds"] == 0
    assert result["source_active_dub_silent_seconds"] == 1
    assert result["gaps_over_0_5_seconds_during_source_activity"] == 1
    assert result["source_active_coverage_fraction"] == .5


def test_silent_source_has_no_coverage_claim_or_gap_false_positive():
    result = quality.compare_activity(quality.Activity([False] * 100, 2), quality.Activity([False] * 100, 2), 2)
    assert result["source_active_coverage_fraction"] is None
    assert result["source_active_dub_silent_seconds"] == 0
    assert result["gaps_over_0_5_seconds_during_source_activity"] == 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required for PCM audit")
def test_shifting_speech_beyond_end_cannot_look_like_improvement(tmp_path):
    src = quality.audio_activity(wav(tmp_path / "src.wav", [(2, 8000)]))
    good = quality.audio_activity(wav(tmp_path / "good.wav", [(2, 8000)]))
    shifted = quality.audio_activity(wav(tmp_path / "shifted.wav", [(2, 0), (2, 8000)]))
    baseline = quality.compare_activity(src, good, 2)
    regression = quality.compare_activity(src, shifted, 2)
    assert baseline["source_active_dub_silent_seconds"] == 0
    assert regression["source_active_dub_silent_seconds"] == 2
    assert regression["dub_active_beyond_source_seconds"] == 2
    assert regression["dub_detected_silence_seconds"] == 2


def test_truncated_audio_is_not_credited_as_speech():
    result = quality.compare_activity(quality.Activity([True] * 100, 2), quality.Activity([True] * 50, 1), 2)
    assert result["dub_audio_missing_seconds"] == 1
    assert result["source_active_dub_silent_seconds"] == 1


def test_timing_uses_actual_placement_and_flags_script_leakage():
    rows = [{"id": 1, "text": "Hello 한국어", "ok": True}, {"id": 2, "text": "Done", "ok": True}]
    units = [{"id": 1, "start": 1, "end": 2}, {"id": 2, "start": 3, "end": 4}]
    timeline = [{"id": 1, "start": .5, "end": 2}, {"id": 2, "start": 4, "end": 6}]
    result = quality.audit_lines(rows, units, timeline, "en", dubbed_duration=5, source_duration=4)
    assert result["timing"]["early"]["max_seconds"] == .5
    assert result["timing"]["late"]["max_seconds"] == 1
    assert result["tail"]["missing_audio_seconds"] == 1
    assert result["tail"]["overflow_past_source_seconds"] == 2
    assert not result["tail"]["placed_audio_complete"]
    assert "Korean" in result["flagged_lines"][0]["issues"][0]


def test_missing_old_placement_is_unknown_not_zero():
    result = quality.audit_lines([{"id": 0, "text": "hello", "dur": 2}],
                                 [{"id": 0, "start": 0, "end": 2}], [], "en", 2, 2)
    assert result["timing"]["absolute"] is None
    assert result["timing_missing_line_ids"] == [0]
    assert result["tail"]["missing_audio_seconds"] is None
    assert not result["tail"]["placed_audio_complete"]


def test_missing_entire_source_line_prevents_completeness_claim():
    result = quality.audit_lines([{"id": 0, "text": "hello", "start": 0, "end": 1}],
                                 [{"id": 0, "start": 0}, {"id": 1, "start": 1}], [], "en", 2, 2)
    assert result["unrepresented_source_line_ids"] == [1]
    assert not result["tail"]["placed_audio_complete"]


def test_cli_refuses_to_overwrite_report(tmp_path, monkeypatch):
    from tools import assess_quality
    report = tmp_path / "existing.json"
    report.write_text('{"preserved": true}')
    monkeypatch.setattr(sys, "argv", ["assess_quality", "run", "--output", str(report)])
    with pytest.raises(SystemExit):
        assess_quality.main()
    assert json.loads(report.read_text()) == {"preserved": True}
