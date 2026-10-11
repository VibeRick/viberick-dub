from dub import mix, voice


def test_overlong_clip_pushes_next_and_catches_up(tmp_path):
    clips = []
    for i, sec in enumerate([1.5, 0.5, 0.5]):
        p = tmp_path / f"{i}.wav"
        p.write_bytes(voice._silence_wav(sec))
        clips.append(p)
    units = [{"start": 0.0}, {"start": 1.0}, {"start": 3.0}]
    st = mix.place(units, clips, total=4.0, out=tmp_path / "t.wav")
    assert abs(st["late_max"] - 0.58) < 0.01 and st["late_lines"] == 1
    assert abs(voice.duration(tmp_path / "t.wav") - 4.0) < 0.01   # no artificial tail


def test_paragraph_lines_flow_back_to_back(tmp_path):
    clips = []
    for i in range(3):
        p = tmp_path / f"{i}.wav"
        p.write_bytes(voice._silence_wav(0.5))
        clips.append(p)
    units = [{"start": 0.0}, {"start": 1.0}, {"start": 3.0}]
    st = mix.place(units, clips, total=4.0, out=tmp_path / "t.wav", flow=[None, 0.0, None])
    assert st["starts"] == [0.0, max(0.5, 1.0 - mix.MAX_EARLY), 3.0]


def test_flowing_line_starts_at_most_max_early(tmp_path):
    clips = []
    for i in range(2):
        p = tmp_path / f"{i}.wav"
        p.write_bytes(voice._silence_wav(0.5))
        clips.append(p)
    st = mix.place([{"start": 0.0}, {"start": 3.0}], clips, total=4.0, out=tmp_path / "t.wav", flow=[None, 0.12])
    assert st["starts"] == [0.0, 3.0 - mix.MAX_EARLY]


def _db(p, start, dur):
    import re
    import subprocess
    r = subprocess.run(["ffmpeg", "-ss", str(start), "-t", str(dur), "-i", str(p), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    return float(re.search(r"mean_volume: ([-\d.]+)", r.stderr).group(1))


def test_mix_keeps_the_voice_level_and_fills_gaps_with_room_tone(tmp_path):
    import subprocess
    src = tmp_path / "v.wav"   # 2 s of tone, then 2 s of digital silence
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "aevalsrc=0.1*sin(2*PI*300*t)*lt(t\\,2):s=24000:d=4", str(src)], check=True)
    out = tmp_path / "m.m4a"
    mix.mix(src, None, out)
    assert abs(_db(out, 0.2, 1.5) - _db(src, 0.2, 1.5)) < 0.5   # not normalized
    gap = _db(out, 2.3, 1.5)
    assert -95 < gap < -70   # room tone, not digital zero and not audible hiss
