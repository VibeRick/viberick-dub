"""Cold-open takes: fresh, unstretched clone takes of the one sentence, checked by ear, over the original bed.

The earlier shots reused dub tracks whose lines were time-stretched to fit; stretched clone speech sounded
broken. Here each language gets its own natural-length take (up to 3 tries until the check passes)."""
import json
import subprocess
from pathlib import Path

from dub import check, config, voice

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "remotion" / "public" / "film"
BED = HERE.parent.parent / "runs" / "Fty2sz3dBwU.180s" / "bed.wav"
SRC = "제 부모님만 하더라도 이제 다 ChatGPT한테 물어보시는 것 같아요."
LINES = {"en": "Even my parents seem to ask ChatGPT about everything these days.",
         "hi": "लगता है मेरे माता-पिता भी अब सब ChatGPT से ही पूछते हैं।",
         "zh-Hans": "拿我父母来说，现在好像全都会去问ChatGPT了。"}
BED_AT, PAD = 8.53, 0.35

meta = {}
for lang, text in LINES.items():
    take = HERE / "narration" / f"open.{lang}.wav"
    for attempt in range(3):
        sec = voice.synth(text, take, voice_id=config.VOICE_ID, lang=lang)
        v = check.check(take, text, lang, SRC, "ko")
        ok = all(v.get(k) is True for k in ("language_ok", "content_ok", "meaning_ok"))
        print(lang, attempt, round(sec, 2), ok, v.get("heard", "")[:60])
        if ok:
            break
    total = sec + PAD * 2
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(BED_AT - PAD), "-t", str(total), "-i", str(BED),
                    "-i", str(take), "-filter_complex",
                    f"[1:a]aresample=48000,highpass=f=70:poles=2,highpass=f=70:poles=2,adelay={int(PAD*1000)}|{int(PAD*1000)},"
                    f"pan=stereo|c0=c0|c1=c0[v];[0:a]aresample=48000[b];[v][b]amix=inputs=2:normalize=0:duration=longest,"
                    "loudnorm=I=-16:TP=-1.5", "-ar", "48000", str(OUT / f"open.{lang}.wav")], check=True)
    meta[lang] = round(sec, 2)
(OUT.parent.parent / "src" / "film" / "open.json").write_text(json.dumps(meta, indent=1))
print(meta)
