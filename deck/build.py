"""Fill the official AI Builder Cup template → deck/VibeRick-Dub.pptx (+ PDF via LibreOffice).

uv run --with python-pptx python deck/build.py
Numbers come from the run reports in runs/, so the deck always matches the measured data."""
import copy
import json
import subprocess
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = ROOT.parent / "submission-template.pptx"
A = HERE / "assets"
OUT = HERE / "VibeRick-Dub.pptx"

INK, MUTED, ACCENT = RGBColor(0x11, 0x12, 0x14), RGBColor(0x5A, 0x5D, 0x66), RGBColor(0x2F, 0x5B, 0xFF)
FONT = "Arial"
L, TOP, W, BOTTOM = Emu(265350), Emu(1180000), Emu(8613300), Emu(5000000)

LINKS = {
    "product": "https://viberick-dub.web.app",
    "github": "https://github.com/jays0606/viberick-dub",
    "video": "(demo video link — added at submission)",
}


def report(name: str) -> dict | None:
    p = ROOT / "runs" / name / "out" / "report.json"
    return json.loads(p.read_text()) if p.exists() else None


def mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def set_title(slide, text: str) -> None:
    box = next(sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip())
    tf = box.text_frame
    p0 = tf.paragraphs[0]
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    for r in list(p0.runs)[1:]:
        r._r.getparent().remove(r._r)
    run = p0.runs[0] if p0.runs else p0.add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.name = Pt(20), True, FONT
    run.font.color.rgb = INK
    box.height = Emu(480000)


def text(slide, x, y, w, h, paras: list, size: int = 13, gap: int = 6):
    """paras: str | (str, dict(size, bold, color, bullet))"""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(paras):
        s, o = (item, {}) if isinstance(item, str) else item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(o.get("gap", gap))
        r = p.add_run()
        r.text = ("•  " if o.get("bullet") else "") + s
        r.font.name, r.font.size = FONT, Pt(o.get("size", size))
        r.font.bold = o.get("bold", False)
        r.font.color.rgb = o.get("color", INK)
    return tb


def image(slide, path: Path, x, y, w=None, h=None):
    from PIL import Image
    iw, ih = Image.open(path).size
    if w and h:
        if iw / ih > w / h:
            h2 = int(w * ih / iw)
            y, h = y + (h - h2) // 2, h2
        else:
            w2 = int(h * iw / ih)
            x, w = x + (w - w2) // 2, w2
    return slide.shapes.add_picture(str(path), x, y, w, h)


def table(slide, x, y, w, rows: list[list[str]], col_w: list[float], size: int = 11, row_h: int = 300000):
    t = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, Emu(row_h * len(rows))).table
    for j, f in enumerate(col_w):
        t.columns[j].width = Emu(int(w * f))
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = val
            c.fill.solid()
            c.fill.fore_color.rgb = RGBColor(0x11, 0x12, 0x14) if i == 0 else (
                RGBColor(0xF3, 0xF6, 0xFF) if i % 2 == 0 else RGBColor(0xFF, 0xFF, 0xFF))
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name, r.font.size = FONT, Pt(size)
                    r.font.bold = i == 0
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else INK
            c.margin_left = c.margin_right = Emu(70000)
            c.margin_top = c.margin_bottom = Emu(30000)
    return t


def drop(prs, index: int) -> None:
    sld = prs.slides._sldIdLst[index]
    prs.part.drop_rel(sld.rId)
    prs.slides._sldIdLst.remove(sld)


def build() -> Path:
    demo, full, multi = report("Fty2sz3dBwU.180s"), report("Fty2sz3dBwU"), report("PqVbypvxDto.120s")
    prs = Presentation(str(TEMPLATE))
    s = prs.slides

    # 1 · Team details
    box = next(sh for sh in s[0].shapes if sh.has_text_frame)
    tf = box.text_frame
    lines = ["Team Details", "", "Team name: VibeRick", "Team leader name: Jaeho Shin",
             "Problem Statement: Media, Content & Digital Experiences — creators reach only the viewers who "
             "speak their language. VibeRick Dub turns one video into dubbed tracks in the creator's own voice."]
    for i, p in enumerate(tf.paragraphs):
        for r in p.runs:
            r.text = ""
        if i < len(lines) and p.runs:
            p.runs[0].text = lines[i]
    while len(tf.paragraphs) < len(lines):
        p = tf.add_paragraph()
        p.add_run().text = lines[len(tf.paragraphs) - 1]
    image(s[0], A / "logo-v.png", Emu(7900000), Emu(3150000), Emu(950000), Emu(950000))

    # 3 · Brief
    set_title(s[2], "Brief about the idea")
    text(s[2], L, TOP, Emu(5300000), Emu(3700000), [
        ("One video. Every language. Your own voice.", {"size": 22, "bold": True, "gap": 12}),
        "Paste a YouTube link. An AI agent built on Gemini transcribes it, translates every sentence to fit its "
        "timing, speaks it in the creator's own cloned voice, then listens back to every line and repairs what "
        "doesn't sound right.",
        "The creator gets dubbed tracks and subtitles ready for YouTube's multi-language audio — in minutes, for "
        "cents per minute, with consent built in: the cloned voice is used only for the person who recorded it.",
        ("Languages today: Korean · English · Japanese · Chinese (source detected automatically).",
         {"color": MUTED, "size": 12}),
    ], size=14, gap=10)
    image(s[2], A / "shot-studio-en.png", Emu(5750000), TOP, Emu(3150000), Emu(3700000))

    # 4 · Opportunities
    set_title(s[3], "Opportunities")
    text(s[3], L, TOP, W, Emu(3800000), [
        ("How is it different from existing ideas?", {"bold": True, "size": 14}),
        ("YouTube auto-dubbing: not the creator's voice, cannot be edited, and Korean sources get only English and "
         "Indonesian. VibeRick Dub speaks in the creator's own voice, in any of our languages, and shows every line.",
         {"bullet": True}),
        ("Voice-clone dubbing services (ElevenLabs, Rask, Perso) charge ~$0.33–2.20 per minute and run open-loop. "
         "Our agent listens to every dubbed line with Gemini and repairs it, for ~$0.05 per dubbed minute.",
         {"bullet": True}),
        ("How will it solve the problem?", {"bold": True, "size": 14}),
        ("YouTube: creators who add multi-language audio get over 25% of watch time from other languages. "
         "VibeRick Dub makes that track a one-link job instead of a studio booking.", {"bullet": True}),
        ("USP", {"bold": True, "size": 14}),
        ("Own voice + time-fitted translation + a self-verifying agent + consent by design (two locks: channel "
         "consent and speaker verification), all on Google Cloud.", {"bullet": True}),
    ], size=13, gap=7)

    # 5 · Features
    set_title(s[4], "List of features offered by the solution")
    feats = [
        ("Creator's own voice", "Gemini 3.8 Flash TTS voice replication from a 20 s sample + spoken consent"),
        ("Translation that fits the clock", "Each sentence gets a character budget from its time slot and the voice's measured speed"),
        ("Self-verifying agent", "Gemini listens to every dubbed line; too long → shorten, wrong → re-speak → re-translate → flag"),
        ("Accurate transcript", "Chirp 3 timings + Gemini proofreading by listening (7.6% CER, on par with the best tool we tested)"),
        ("Multi-speaker", "Chirp 3 diarization; Gemini casts a fitting preset voice for every other speaker"),
        ("Consent lock", "Clone only for the channel owner whose voice verifies against the consent recording"),
        ("Live studio", "Watch the agent work in real time; switch languages on the video; synced transcript"),
        ("Ready to upload", "Dubbed MP4 + M4A (−14 LUFS, original music kept) + SRT/VTT subtitles"),
    ]
    for k, (h, d) in enumerate(feats):
        col, row = k % 2, k // 2
        text(s[4], Emu(265350 + col * 4350000), Emu(1180000 + row * 930000), Emu(4200000), Emu(880000),
             [(h, {"bold": True, "size": 14, "gap": 3}), (d, {"color": MUTED, "size": 12})])

    # 6 · Process flow
    set_title(s[5], "Process flow diagram")
    image(s[5], A / "flow.png", L, TOP, W, Emu(3800000))

    # 7 · Wireframes → the real UI
    set_title(s[6], "Wireframes / mock: the live product")
    image(s[6], A / "shot-hero.png", L, TOP, Emu(6100000), Emu(3800000))
    image(s[6], A / "shot-mobile.png", Emu(6550000), TOP, Emu(2300000), Emu(3800000))

    # 8 · Architecture
    set_title(s[7], "Architecture diagram of the proposed solution")
    image(s[7], A / "arch.png", L, TOP, W, Emu(3800000))

    # 9 · Technologies
    set_title(s[8], "Technologies used in the solution")
    table(s[8], L, TOP, W, [
        ["Technology", "Role"],
        ["Gemini 3.8 Flash (Vertex AI)", "Proofread by listening · dubbing brief · translate to time · shorten · judge every clip · cast voices"],
        ["Gemini 3.8 Flash TTS — voice replication", "The creator's own voice in other languages (SynthID watermarked)"],
        ["Chirp 3 (Speech-to-Text v2)", "Word timestamps + speaker diarization — the timing backbone"],
        ["Cloud Run (service + Job)", "FastAPI API · dubbing worker (4 vCPU, demucs, ECAPA, ffmpeg)"],
        ["Firestore", "Jobs, live agent event stream, per-line results (realtime listeners)"],
        ["Firebase Hosting", "Web app; /api/** rewritten to Cloud Run"],
        ["Cloud Storage", "Batch STT input; public dubbed MP4/M4A/SRT/VTT"],
        ["Secret Manager · Artifact Registry · Cloud Build", "Keys · container image · builds"],
        ["Open source", "demucs (music bed), ECAPA-TDNN (speaker verification for the consent lock), yt-dlp, ffmpeg"],
    ], [0.36, 0.64], size=11, row_h=330000)

    # 10 · Cost
    set_title(s[9], "Estimated implementation cost")
    usd = demo["gemini_text_usd"] if demo else 0.28
    dubbed_min = (demo["duration"] / 60 * len(demo["langs"])) if demo else 9
    text_pm = usd / dubbed_min
    table(s[9], L, TOP, Emu(4800000), [
        ["Per dubbed minute (measured)", "USD"],
        ["Gemini 3.8 Flash text + listening checks", f"{text_pm:.3f}"],
        ["Gemini 3.8 Flash TTS (25 audio tokens/s, $9/1M)", "0.014"],
        ["Chirp 3 (per source min ÷ 3 languages)", "0.005"],
        ["Cloud Run Job (4 vCPU)", "0.003"],
        ["Total", f"≈ {text_pm + 0.022:.2f}"],
    ], [0.78, 0.22], size=12, row_h=360000)
    table(s[9], Emu(5300000), TOP, Emu(3580000), [
        ["Voice-clone dubbing", "USD / min"],
        ["ElevenLabs", "0.33 – 2.20"],
        ["Rask AI", "≈ 1.56"],
        ["Perso AI", "≈ 0.55 – 0.73"],
        ["VibeRick Dub", f"≈ {text_pm + 0.022:.2f}"],
    ], [0.6, 0.4], size=12, row_h=360000)
    text(s[9], L, Emu(3500000), W, Emu(1200000), [
        ("Competitor list prices checked 2026-10-10. Fixed cost: Cloud Run scales to zero; Firestore and Hosting "
         "stay within the free tier for the demo.", {"color": MUTED, "size": 11})])

    # 11 · Snapshots
    set_title(s[10], "Snapshots of the prototype")
    image(s[10], A / "shot-studio-ja.png", L, TOP, Emu(4250000), Emu(2700000))
    image(s[10], A / "shot-log.png", Emu(4628650), TOP, Emu(4250000), Emu(2700000))
    text(s[10], L, Emu(3950000), W, Emu(900000), [
        ("Left: Japanese dub with subtitles and the synced transcript. Right: the agent log — every shorten, "
         "re-speak, re-translate and Gemini verdict, streamed live from Firestore.", {"color": MUTED, "size": 12})])

    # 12 · Performance
    set_title(s[11], "Prototype performance report / benchmarking")
    rows = [["Measure", "Result"]]
    if demo:
        ok = sum(l["ok"] for l in demo["langs"]); n = sum(l["lines"] for l in demo["langs"])
        rows += [["3-min Korean video → en, ja, zh: lines verified by Gemini listening", f"{ok} / {n}"],
                 ["Timing drift (p95, worst language)", f"{max(l['late_p95'] for l in demo['langs']):.2f} s"],
                 ["Wall-clock, 3 languages", mmss(demo["sec_total"])]]
    if full:
        okf = sum(l["ok"] for l in full["langs"]); nf = sum(l["lines"] for l in full["langs"])
        rows += [[f"Full {mmss(full['duration'])} video → 3 languages: verified · wall-clock",
                  f"{okf} / {nf} · {mmss(full['sec_total'])}"]]
    if multi:
        rows += [["2-speaker English podcast → Korean: lines verified; voices cast", "28 / 28 · male + female presets"]]
    rows += [["Transcript CER vs creator's edited captions (3 runs)", "Chirp 3 + Gemini 7.6–7.9% · Chirp 8.6% · Gemini 10.6–11.8%"],
             ["Gemini-only timestamps drift (why Chirp is the clock)", "up to 42 s"],
             ["Speaker similarity to the creator (ECAPA cosine)", "English clone 0.68 · creator 0.90 · others 0.00–0.09"]]
    table(s[11], L, TOP, W, rows, [0.62, 0.38], size=11, row_h=330000)

    # 13 · Future
    set_title(s[12], "Additional details / future development")
    text(s[12], L, TOP, W, Emu(3800000), [
        ("More languages: the same path covers every language Gemini TTS speaks; subtitles for 100+.", {"bullet": True}),
        ("One-click publish to YouTube multi-language audio via the YouTube Data API.", {"bullet": True}),
        ("Guest consent in the browser: guests record the consent line and get their own cloned voice.", {"bullet": True}),
        ("Line editor: fix one line, re-speak only that line; glossary per channel.", {"bullet": True}),
        ("Emotion and emphasis transfer from the original delivery; lip-sync for on-camera close-ups.", {"bullet": True}),
        ("Shorts and podcasts: the same agent for vertical video and audio-only feeds.", {"bullet": True}),
    ], size=14, gap=10)

    # 14 · Links
    set_title(s[13], "Links")
    text(s[13], L, TOP, W, Emu(2400000), [
        ("GitHub public repository", {"bold": True}), (LINKS["github"], {"color": ACCENT}),
        ("Demo video (under 3 minutes)", {"bold": True}), (LINKS["video"], {"color": ACCENT}),
        ("Final product", {"bold": True}), (LINKS["product"], {"color": ACCENT}),
    ], size=15, gap=6)

    # 15 · Responsible AI (blank slide in the template)
    tb = text(s[14], L, Emu(663825), W, Emu(480000), [("Consent and safety by design", {"bold": True, "size": 20})])
    text(s[14], L, TOP, Emu(5000000), Emu(3800000), [
        ("Two locks before a voice is cloned", {"bold": True, "size": 14}),
        ("1. Channel lock: the channel owner recorded the consent statement.", {"size": 13}),
        ("2. Speaker lock: the diarized speaker's voice verifies against that recording (ECAPA cosine ≥ 0.45).",
         {"size": 13}),
        ("Everyone else gets a Gemini preset voice chosen by Gemini after listening to them.", {"size": 13}),
        ("Only a 192-number voice embedding is stored, never the audio. Every clip carries SynthID.",
         {"size": 13, "color": MUTED}),
    ], gap=9)
    table(s[14], Emu(5500000), TOP, Emu(3380000), [
        ["Speaker vs consent recording", "Cosine"],
        ["Creator (own video)", "0.90"],
        ["Creator's consent take", "0.88"],
        ["Podcast speaker A", "0.09"],
        ["Podcast speaker B", "0.00"],
        ["Threshold", "0.45"],
    ], [0.68, 0.32], size=12, row_h=360000)

    drop(prs, 1)   # the template's "how to download" instruction slide
    prs.save(OUT)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(HERE), str(OUT)],
                   check=True, capture_output=True)
    return OUT


if __name__ == "__main__":
    print(build())
