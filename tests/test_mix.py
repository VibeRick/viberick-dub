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
    assert abs(voice.duration(tmp_path / "t.wav") - 5.0) < 0.01   # total + 1 s tail
