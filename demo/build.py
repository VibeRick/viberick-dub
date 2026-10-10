"""Assemble the < 3 min demo video → demo/VibeRick-Dub-demo.mp4.

Narration is spoken by the creator's own cloned voice through dub.voice (the product itself). The hook uses
the real dubbed MP4s with their audio; the screen recordings are captures of the live site.
uv run python demo/build.py"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dub import voice  # noqa: E402

D = ROOT / "demo"
RAW, CARDS, TMP = D / "raw", D / "cards", D / "build"
RUN = ROOT / "runs" / "Fty2sz3dBwU.180s" / "out"
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
W, H, FPS = 1920, 1080, 30
BG = "0x0e0f11"

NARRATION = {
    "n1": "That was me. In the original, I only speak Korean. The English, the Japanese and the Chinese are me "
          "too: my own voice, dubbed by an AI agent built on Gemini. This is VibeRick Dub.",
    "n2": "YouTube says creators who add multi-language audio get over a quarter of their watch time from other "
          "languages. But YouTube's auto-dubbing doesn't use your voice, can't be edited, and for Korean videos "
          "it only offers English and Indonesian. Voice-clone dubbing services charge up to two dollars a minute.",
    "n3": "Here's how it works. I paste a link, and a Cloud Run job takes over. It separates my voice from the "
          "music. Chirp 3 timestamps every word and tells the speakers apart. Gemini listens to the audio and "
          "fixes the transcript, then translates each sentence to fit the exact time I spoke it, and speaks it "
          "in my cloned voice.",
    "n4": "Then the agent listens to every line it made. If a line runs long, it rewrites it shorter. If Gemini "
          "hears a wrong word or the wrong language, it speaks the line again, then re-translates it, and only "
          "then flags it for a human. Every step streams live from Firestore.",
    "n5": "When it's done, I switch languages right on the video, with subtitles and a transcript that follows "
          "along. Every line was verified by Gemini listening, and the timing stays within a fifth of a second "
          "of the original.",
    "n6": "Voice cloning needs consent, so it's built in. My voice is only used on my channel, and only for a "
          "speaker whose voice matches my consent recording. In a two-person podcast, each guest got a fitting "
          "Gemini voice. Nobody got mine.",
    "n7": "It all runs on Google Cloud: Gemini, Chirp, Cloud Run, Firestore and Firebase, for about three cents "
          "per dubbed minute. One video. Every language. Your own voice.",
}
HOOK = [("orig", "Original · Korean"), ("en", "English · my voice, dubbed by AI"),
        ("ja", "Japanese · my voice, dubbed by AI"), ("zh-Hans", "Chinese · my voice, dubbed by AI")]
HOOK_SPAN = (8.6, 13.3)


def ff(*a: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


def dur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True, check=True).stdout)


def narration() -> dict[str, Path]:
    out = {}
    for k, text in NARRATION.items():
        p = TMP / f"{k}.wav"
        if not p.exists():
            voice.synth(text, p)
        out[k] = p
    return out


def fit_frame(extra: str = "") -> str:
    return (f"{extra}scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},"
            f"fps={FPS},format=yuv420p,setsar=1")


def still(img: Path, seconds: float, audio: Path | None, out: Path, lead: float = 0.4) -> Path:
    a = (["-i", str(audio), "-filter_complex", f"[1:a]adelay={int(lead * 1000)}:all=1,apad[a]", "-map", "0:v", "-map", "[a]"]
         if audio else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a"])
    ff("-loop", "1", "-t", f"{seconds:.2f}", "-i", str(img), *a, "-vf", fit_frame(), "-t", f"{seconds:.2f}",
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out))
    return out


def clip(src: Path, a: float, b: float, seconds: float, audio: Path | None, out: Path, crop: str = "",
         lead: float = 0.4) -> Path:
    """Video segment [a, b] of src, retimed to `seconds`, under narration audio."""
    speed = (b - a) / seconds
    vf = fit_frame(f"trim={a}:{b},setpts=(PTS-STARTPTS)/{speed:.4f},{crop}")
    aud = (["-i", str(audio), "-filter_complex", f"[0:v]{vf}[v];[1:a]adelay={int(lead * 1000)}:all=1,apad[a]",
            "-map", "[v]", "-map", "[a]"] if audio else
           ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-map", "1:a"])
    ff("-i", str(src), *aud, "-t", f"{seconds:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
       "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out))
    return out


def label_png(text: str, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(FONT, 34)
    w = int(f.getlength(text)) + 44
    im = Image.new("RGBA", (w, 66), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, 65), radius=14, fill=(0, 0, 0, 165))
    ImageDraw.Draw(im).text((22, 13), text, font=f, fill=(255, 255, 255, 255))
    im.save(out)
    return out


def hook() -> list[Path]:
    a, b = HOOK_SPAN
    outs = []
    for k, (lang, label) in enumerate(HOOK):
        o = TMP / f"hook_{k}.mp4"
        lab = label_png(label, TMP / f"label_{k}.png")
        ff("-ss", str(a), "-to", str(b), "-i", str(RUN / f"video.{lang}.mp4"), "-i", str(lab), "-filter_complex",
           f"[0:v]{fit_frame()}[v];[v][1:v]overlay=48:44[o]", "-map", "[o]", "-map", "0:a",
           "-af", "afade=t=in:d=0.08,afade=t=out:st=4.5:d=0.2", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(o))
        outs.append(o)
    return outs


def build() -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    n = narration()
    d = {k: dur(p) for k, p in n.items()}
    pad = 0.9
    live, studio = RAW / "live-job.webm", RAW / "studio.webm"
    parts = [*hook(),
             still(CARDS / "title.png", d["n1"] + pad, n["n1"], TMP / "s1.mp4"),
             still(CARDS / "problem.png", d["n2"] + pad, n["n2"], TMP / "s2.mp4"),
             # typing + submit in real time, then the whole pipeline sped up under the narration
             clip(live, 2.0, 395.0, d["n3"] + pad, n["n3"], TMP / "s3.mp4", crop="crop=1160:652:140:0,"),
             # the agent log, zoomed
             clip(live, 330.0, 392.0, d["n4"] + pad, n["n4"], TMP / "s4.mp4", crop="crop=760:428:560:150,"),
             clip(studio, 5.0, 5.0 + min(dur(studio) - 6, d["n5"] + pad), d["n5"] + pad, n["n5"], TMP / "s5.mp4",
                  crop="crop=1160:652:140:0,"),
             still(CARDS / "consent.png", d["n6"] + pad, n["n6"], TMP / "s6.mp4"),
             still(CARDS / "close.png", d["n7"] + pad + 1.5, n["n7"], TMP / "s7.mp4")]
    lst = TMP / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = D / "VibeRick-Dub-demo.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5", "-movflags", "+faststart", str(out))
    total = dur(out)
    print(json.dumps({"out": str(out), "seconds": round(total, 1), "parts": {p.stem: round(dur(p), 1) for p in parts}}))
    assert total < 179.5, f"demo is {total:.1f}s, must be under 3:00"
    return out


if __name__ == "__main__":
    build()
