# Dubbing studio revision in progress

The goal is an end-to-end improvement to dubbing quality, source-caption handling, the studio, reliability, and submission materials. This is not a release or completion record.

## Authorization and boundaries

The user approved up to **US$100** in response to the request for paid Gemini validation of up to three minutes in three languages and selected failed-line tests. Calls use only the named Gemini secrets in GCP project `viberick`, accessed with `jaeho.shin@viberick.com`; no generic keychain fallback is permitted in the validation tool. A shared local ledger reserves a conservative per-request allowance, including retries. These reservations are not an invoice or a provider-enforced cap.

The revised API, worker and Firebase Hosting are deployed. Public podcast-sample publication, final video publication, public repository creation and submission remain pending. Existing `.gitignore` edits predate this work and are preserved.

## Implemented locally

- Actual source/dub timings persist through subtitles, timeline exports, row inspection and cloud publication. Early/late/absolute displacement are distinct metrics.
- Complete audio tails are retained without an unconditional extra second. Same-speaker lines cannot overlap themselves at scene anchors; genuine speaker overlap uses wider accumulation and headroom adjustment.
- Offline scene detection records cuts and protects existing boundaries. It does not split words or claim lip synchronization.
- Translation script leakage is checked before speech. Speech directions use structured metadata. Severe underfill gets a measured-duration rewrite attempt; generated alternatives are retained only when duration fit improves.
- Listening checks include source meaning; missing or incorrectly typed verdict fields fail closed. Meaning failures trigger retranslation, not merely another reading of the same error.
- Failed generated takes are preserved for real audition. Empty meaningful translations are flagged rather than silently treated as success.
- Clone selection is fail-closed, highest-match and ambiguity-aware. Legacy caches cannot silently bypass changed casting/grouping policies.
- Language completion is incremental and independent of other languages. Publication failures do not erase successful synthesis reports.
- Owned jobs support isolated line preview, audition, explicit acceptance/discard, revision checks, quotas, renewable leases and expired-worker recovery. Ready does not imply a passed quality check.
- Studio includes source/target intervals, simultaneous transcript/activity/inspector, audio switching without resetting position, separate below-video captions and review-only local manifests.
- Deployment bundles exclude local media, voice recordings, secrets and review fixtures.

## Caption-free source

The original GEO tutorial has precaption rendered parts under the existing YouTube editing workspace. `runs/review-2026-10-10/clean-source.mp4` reconstructs its first 180 seconds, preserving the privacy blur and camera. Its lossless decoded audio equals the cached source WAV. Korean slide content remains; speech captions are no longer baked into the video. All five clean source/dub outputs passed full decoding.

Provenance: `docs/review-2026-10-10/clean-source-provenance.json`.

## Evidence and honest limitations

- Existing-clip remix improved timing bounds and export consistency, **not silence**. See `quality-audit-180s-v3.json`; it must not be described as a naturalness improvement.
- First paid stress set: IDs 1, 8, 13, 18 across English, Japanese and Chinese; 12/12 final automated passes. English Korean-script leakage was removed; duration fit improved in some Japanese/Chinese examples and worsened in some English examples. This is selected stress testing, not an unbiased quality benchmark.
- Fresh complete validation passed 69/69 automated checks. Final isolated output is `runs/refined-3min-2026-10-11/`: 12 of 15 targeted refinements accepted, rejected alternatives retained separately, original runs preserved.
- Same-180-second RMS silence comparison (baseline → final): English 53.26 → 48.64 s; Japanese 70.54 → 60.24 s; Chinese 66.28 → 52.00 s. Longest gaps overlapping source activity: 5.06 → 2.20 s; 7.68 → 3.40 s; 6.56 → 2.94 s. Energy threshold -40 dBFS, 20 ms frames; these are not human naturalness ratings. Chinese longest gap slightly worsened from the first fresh iteration (2.82 → 2.94 s).
- Old 15-minute output has not been regenerated and still has three flagged lines. No full-length quality claim follows from the three-minute experiment.
- Budget ledger: `runs/validation-budget-2026-10-10.json`. `budget.json` in each trial contains usage evidence and final reservations.
- Last broad test checkpoint: 172 passed, one live test excluded. Rerun after remaining edits.
- Desktop/narrow-browser validation demonstrated seeking and track switching at 143.88 seconds, caption separation, real archived records, and no console errors. Narrow viewport was 390 CSS pixels. This is not physical-phone or human-language acceptance.

## Local review and next actions

Serve with `uv run --offline uvicorn tools.review_server:app --host 127.0.0.1 --port 8878` and open `http://127.0.0.1:8878/?review=./review/manifest.json`. Range requests are required for reliable local seeking; the plain Python static server did not provide that behavior.

After complete generation, use `tools.assemble_validation` to create a new isolated combined run with the clean source, then `tools.assess_quality` for comparison and `tools.build_studio_review` to refresh the local fixture. Keep automated listening, RMS silence estimates, actual timing and human preference separate.

Current review deck: `deck/review-2026-10-10/VibeRick-Dub-review.pdf` (914,396 bytes), with editable PPTX and visual verification. Its main story uses the two-person podcast; the creator three-minute measurements and old 15-minute benchmark remain separate evidence. Original deck is preserved.

Archived creator draft: http://localhost:8891/VibeRickDubReview — 53.23 seconds. The current primary preview is http://localhost:8891/VibeRickDubPodcast — 72.63 seconds. No final film export or public upload has occurred.

Shared budget ledger reserves US$81.60 of the approved US$100; this is a conservative request allowance, not an invoice. No further paid generation is currently running.

Deployment readiness records the serving image/digest, verified cloud smoke, IAM and rollback commands. Private snapshot retention still needs a separately reviewed prefix-limited policy. Public podcast replacement is pending user approval; no publication command has been executed.

## Demo direction corrected — 2026-10-11

The user rejected the single-creator GEO demo as the submission story and requested a recognizable two-person podcast. The replacement source is Lex Fridman Podcast #475 with Demis Hassabis, YouTube `-HzgcbRXUK8`, original 56:27–57:07. `runs/podcast-demo-2026-10-11/source.mp4` contains only that exact 40-second excerpt. It is a local review source, not a claim of reuse permission.

The opening must visibly say **AI AUDIO DUBBING** from the first frame. The proof must audibly switch Original / Korean / Japanese / Chinese while fixed speaker labels and distinct preset voices preserve the two-person structure. Lex uses Charon and Demis uses Algieba; neither is a cloned celebrity voice. All 18 podcast utterances passed automated language/content/meaning checks. The first Korean line was editorially corrected to scientific terminology and rechecked. The final demo preview is 72.63 seconds at http://localhost:8891/VibeRickDubPodcast; the actual studio review is http://127.0.0.1:8878/?review=./review/podcast/manifest.json. Moving-video preview was corrected to native Remotion playback after canvas-video rendering proved blank in the browser. The old 53.23-second creator film remains preserved as an earlier draft.

The user approved app deployment and an improved sample, then corrected the desired sample to the podcast. Public creator-sample replacement was stopped. Backend release and exact-text smoke are complete; new podcast publication requires the pending final review.

### Real cloud smoke found and corrected an edit contract issue

Candidate viberick-dub-00009-hij and worker build `studio-20261011` successfully created an owned 12-second English test job. Idempotency replay, unauthorized 403, incremental media, real preview acceptance and discard passed. An explicit short edit was nevertheless automatically lengthened by the normal dubbing agent. Traffic promotion was withheld.

Manual regeneration now sets `preserve_user_text=True`: no automatic shortening, lengthening or retranslation of the supplied wording; checks and same-text retries remain. Timing underfill/overflow is flagged for review. Normal automated dubbing keeps its existing measured rewrites. Focused tests and the full suite pass (167 passed, one live test excluded). New immutable build `studio-20261011b`, Cloud Build `a68fa438-cadb-4788-92bb-d260e75ed90b`, completed with digest `sha256:8d31316651e39f038847ce9e4b0bda82654868f40f2554645bb1b5e0ffff7894`; the real exact-text preview passed and the corrected revision now serves public traffic.

### Final local preview acceptance

- Podcast composition has 2179 frames at 30 fps (72.63 seconds). First frame shows **AI AUDIO DUBBING**, actual Lex/Demis portraits, and preset disclosure. Native moving video and the actual studio screenshot render in the browser after replacing blank canvas-based preview elements.
- Complete first speaker pair appears in Original / Korean / Japanese / Chinese; the source cutoff avoids starting and clipping the next Lex sentence. A complete longer Korean answer follows.
- The final Korean opening uses “새로운 가설이나 과학적 발견이라니, 정말 멋진 기분이겠죠.” and passed a new meaning/content/language check. Both voices were distinguishable in model listening checks. This is not native-human acceptance.
- Actual studio Japanese switching retained time 5.34 seconds, duration 40 seconds, readyState 4. Below-video captions reflected the Japanese Demis turn; console error checks for product and Remotion were empty.
- Updated review PDF is 914,396 bytes, with a podcast-focused story and separate creator benchmark. Form draft is 994/1024 characters. No final film export or competition submission.

### Production release completed

API `viberick-dub-00010-rih` now serves 100% of traffic and the worker uses corrected digest `8d31316651e39f038847ce9e4b0bda82654868f40f2554645bb1b5e0ffff7894`. A real third preview preserved the exact submitted English sentence; audio/content/meaning checks passed and underfill stayed an honest warning. Discard preserved accepted revision 1. Origin and Firebase health checks pass. Unauthenticated private ownership and quota reads returned 403. Firebase Hosting released the revised five-file bundle, excluding all local review media.

The new podcast has not been published to the public sample collection. Its publication question is pending. Shared conservative reservations are US$81.60, leaving US$18.40; these are not reconciled charges.

## Completion audit — current state checked 2026-10-11

| Requirement | Authoritative evidence | State |
|---|---|---|
| Recognizable two-person source | Exact original 56:27–57:07, 40-second `source.mp4`; metadata names Lex/Demis | Prepared and shown |
| Service obvious immediately | Primary Remotion opening and inspected first-frame capture: AI AUDIO DUBBING | Verified |
| Different voices across target languages | Stable Charon/Algieba casting; 18/18 checks and per-language model-listening distinction audit | Verified automatically; human naturalness remains unscored |
| Actual media in new demo | All nine preview asset SHA256 values match the authored manifest; composition 2179 frames at 30 fps | Verified, editable preview |
| Product language switching | Actual 40-second player, named lanes, Japanese switching retained 5.34 seconds | Verified locally |
| Production UI/API/worker | Serving revision 00010-rih, corrected image, five-file Hosting release, live health response | Deployed and verified |
| Manual edits preserve input | Exact-text third cloud preview; content/meaning check passed; explicit underfill warning | Verified in cloud |
| Updated slide deck | Current PDF 914,396 bytes; actual podcast story and separately labelled creator benchmark | Prepared and shown |
| New public representative sample | Deterministic 19-file/18-row publication plan; no execution | Awaiting user's pending publication choice |
| Public submission film/repository/form | Final URLs still pending; editable preview and form/deck drafts exist | Separate outstanding publication/submission decisions |

Local studio and primary Remotion routes both returned HTTP 200 on this audit. Production `/api/health` returned `{"ok":true}`. Existing original media and uncommitted work remain preserved. No additional paid calls were made during this audit.

## User-directed short demo revision

The user rejected the 72.63-second edit as long, disconnected, missing Gemini visibility and overly long dialogue. The primary `VibeRickDubPodcast` is now a 24-second/720-frame persistent comparison layout: the two-person source, Gemini translation/voice/listening workflow and all three language panels appear together. Six complete checked clips from units 2/3 are reused, with no new AI calls. Language focus moves over 0.8 seconds; audio voices alternate without overlapping. `demo/remotion/short-edit-manifest.json` records actual durations, placement and byte hashes. The longer edit remains `PodcastLongDraft`. This revision supersedes the previous primary-preview duration, and does not change the published product or pending sample-publication approval.

## Studio-led demo revision and positioning

The user asked for simultaneous subtitles, timestamps, market/human-labor value and visible Gemini capabilities. The primary preview now uses `StudioDemo.tsx` (28 seconds): large native moving interview video, simultaneous KO/JA/ZH caption panels, numbered speakers, measured per-language speech intervals and a source clock. Original measured start offsets are preserved for the selected two turns, including the short Japanese overlap; no global source/lip-alignment accuracy is inferred.

Gemini 3.8 Flash TTS documentation was checked: model coverage is over 130 languages. The demo explicitly distinguishes that provider capability from the app's four validated languages. Voice cloning is a consented creator feature; this public-figure interview uses two presets. Audience segments are creators, podcasters and course teams. Human-labor value is workflow consolidation (translation, recording, caption timing, checking) rather than a fabricated savings percentage or market-size estimate. `demo/remotion/studio-edit-manifest.json` records all selected audio hashes and placement. No new paid generation or public publication occurred.


## End-to-end hackathon finish — active goal, 2026-10-11

User confirmed the two-person team is complete. Product promise is automatic multilingual completion, with review/editing secondary. Headline: “You made the video. We’ll handle the languages.” YouTube automatic dubbing is the intended comparison; MrBeast is a familiarity cue, not an endorsement or proof of automatic-dubbing use. No new paid calls are authorized by this implementation turn; re-confirm a concrete budget before new billable generation. Public posting remains a final reviewed approval step.

Local first UI pass: outcome-led landing, labelled creation form, full-width player, language-specific video/audio/subtitle downloads, optional line inspector and optional production details. Quality warnings remain above collapsed details. Syntax check and two existing studio regression tests passed. Browser verified real local creator fixture, Japanese track/caption switch, optional inspector expansion and landing page; no landing console errors. Not deployed. No new voice generation.

Remaining full goal (not completion claims):
- Product: mobile/keyboard QA, selected-language quality warnings including in-progress/partial results, reliable create/preview/accept/download journey, final representative sample and deployment verification.
- Evidence: permitted two-speaker representative footage or permission; creator clone A/B; held-out human listening; same-source YouTube comparison if available; measured active time and cost, no invented savings.
- Video: outcome-first opening using actual complete utterances; short product cut and <3-minute English submission film; product capture, voiceover, audio/visual QA, final export.
- Submission: final English template deck PDF <5MB, <=1024-character description, public source repository with clean provenance and reproducible setup, working public prototype and video links, final user review and submission receipt.
- Harmonize README, deck, description, website, demo duration and metrics to one final evidence set.

Do not mark goal complete until each remaining deliverable is verified. Current public demo remains the historical sample and current primary video remains the 28-second studio comparison.


### Launch opening and quality states — follow-through

Added a separate `VibeRickDubLaunchOpening` (532 frames / 30 fps = 17.73 s), preserving the requested podcast comparison. Three existing creator utterances play exclusively and completely: source 4.310 s in 140 frames, English 4.252 s in 138 frames, Japanese 4.098 s in 134 frames, then a four-second product promise. Existing media reused; no paid generation. This is a creator-voice proof draft, not the final submission film. The small embedded camera in the existing screen recording is a visual limitation; do not claim the footage has been fully listened to or approved.

Product output labels now distinguish loaded pass results, flagged lines, unavailable language versions, pending generation and missing quality evidence. Loaded line data supersedes older aggregate report counts. Added a regression test for these cases; 3 studio tests pass. README headline and 1024-character submission draft now reflect automatic completion with optional edits. Final video, representative sample rights, full product acceptance, deck consistency, public source publication, deployment and final submission are still outstanding.


### Submission deck and full local verification

Outcome-first deck generated from the official template into `deck/outcome-review-2026-10-11/VibeRick-Dub-outcome.pptx` and PDF. 15 output slides retain the template branding, with only the download-instructions slide removed. All slides were rasterized and reviewed in a contact sheet; slide 2 was subsequently simplified to editable output labels and inspected at 1400 pixels. Actual current studio capture retained at `docs/review-2026-10-10/outcome-studio.jpg`. PDF 843,244 bytes; SHA256 `73cfe6ca6ffb1cf239af539df3bcc3ec5136546799fbacc486738b1796186cc9`. Repository/video links are intentionally pending, so this is not send-ready.

Updated problem, business hypothesis, automatic repair, optional editing, reliability and scale discussion. Removed unsupported hardcoded speaker-similarity comparison table and replaced it with implemented behavior boundaries. Existing measured pause comparisons remain scoped to their runs. English submission narration draft is in `demo/remotion/demo.md`, with complete audio examples and marked rights/narration/capture dependencies.

Full offline suite: **173 passed, 1 live test deselected** (`uv run --offline pytest -q`). No paid inference, public posting, deployment or submission occurred in this phase. Team size is confirmed by the user. Representative two-person footage question remains pending; there is independent product/repository/video assembly work remaining, so the goal is active, not blocked.


### Reproducible source and assembled submission draft

Removed automatic Keychain key searches and cross-key TTS fallback from `dub/config.py`; missing explicit text/TTS keys now fail before any subprocess credential lookup. Added credential-boundary regression tests. GCP project/account are environment-overridable for reproduction while preserving explicit VibeRick defaults. This configuration revision remains local and requires confirming deployed explicit secret bindings before release.

`tools/build_source_release.py` produces an allowlisted deterministic source ZIP (82 files) and SHA256 manifest in `runs/source-release/`. No private runs, media, consent recordings, ownership tokens, internal ops docs or Git history are included. **175 tests passed, 1 live deselected** in a separate lightweight environment and in the extracted source package. An isolated import check confirmed `dub/config.py` resolved inside the extracted package. One upstream TestClient deprecation warning remains, not a test failure. Publication still awaits review.

Added `VibeRickDubSubmissionDraft`, 3398 frames / 113.27 seconds. It opens on real English/Korean outputs, then product, second-speaker reply, pipeline, archived repair, consented creator voice, architecture and downloads. Original/translated first sentences stop before the second speaker begins; later reply starts at the measured source turn. Narrative audio is pending approval; `submission-script.json` contains eight concrete voiceover sections. Local draft marks pending footage rights and narration rather than claiming a final film. The 17.73-second creator comparison and original 28-second studio video remain separately available.

Two pending user inputs: representative two-speaker footage/permission and up to US$5 for new project-scoped narration generation/validation. These do not authorize publication. No paid call, repo publication, cloud change, final export or submission was performed in this phase.


### Release preflight and browser acceptance

Read-only live metadata on 2026-10-11 confirms API revision `viberick-dub-00010-rih` serves 100% traffic. API and worker both explicitly bind `GEMINI_API_KEY` and `GEMINI_TTS_API_KEY` from Secret Manager; the worker also has its proxy binding. Only variable names and secret-reference names were queried, never values. This supports compatibility of the local removal of Keychain fallback; no new image or traffic change was made.

All nine local download artifacts (video/audio/SRT for English, Japanese, Chinese) exist. All six media files decoded completely with FFmpeg; each SRT contains timestamped cues. This does not certify naturalness or translation quality.

Browser at an observed **390 CSS px**: landing and result have no horizontal overflow (document width 371 including reserved scrollbar area); result language controls and captions remain usable. This is emulation, not a physical-phone test. Added keyboard-focus preservation across track rerender and Back-navigation cleanup of media/listeners. Initial browser verification detected stale cached JS; HTML now references content-hashed CSS/JS URLs. Fresh-code verification confirms English retains BUTTON focus/pressed=true; Back returns to root, hides studio and removes media source. Narrow-screen evidence: `docs/review-2026-10-10/outcome-mobile.jpg`.

The source handoff ZIP was refreshed after these fixes. Four focused studio/config tests passed. Current static UI is ready for a reviewed Hosting release; backend config change requires its own image release. No generation or public sample mutation is part of the static UI release. Existing public sample is still the older creator run; the new representative sample remains a separate pending content decision.


### Final local handoff audit before user-dependent work

Added offline narration attachment (`tools/attach_submission_narration.py`): exact current script matching, complete section coverage, local media boundary, measured audio duration plus 0.4-second tail, and strict <180-second film ceiling. Validation occurs before atomic script update. Five tests cover measured duration and rejection without partial mutation. Film now loads attached audio automatically. No audio has been generated or attached; all eight narrative sections remain pending.

Added `VibeRickDubProductDraft` alongside `VibeRickDubSubmissionDraft`; both preserve separate source/dub audio and use the same script/output evidence. They are local animatics, not final rendered/public videos. Lint/TypeScript passed. The source ZIP was refreshed. Full offline suite: 180 passed, one live test excluded.

Completion is unproven: new UI not deployed; backend config update not deployed; source repository not public; final narrated movies not rendered/uploaded; interview reuse permission or replacement not provided; human listening and matched competitor/labor evidence not completed; final form not submitted. The existing public baseline still works but does not establish completion of this revision.

Blocking inputs have remained unanswered across successive goal continuations: explicit paid-narration approval or user recordings, representative interview rights/source choice, public-release approval, and GitHub owner. Do not start paid generation, publish third-party footage, infer a GitHub owner, or equate passing local checks with final submission. Team size is already confirmed and must not be re-asked.
