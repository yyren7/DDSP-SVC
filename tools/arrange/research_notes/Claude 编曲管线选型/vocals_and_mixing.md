# Vocals for a code-composed instrumental (SVS -> SVC) and scripted mixing/mastering, as of October 2026

Research date: 2026-10-28. "Accessed 2026-10-28" applies to every web page below unless a different date is given. Dates in brackets are publication/release dates of the thing described.

Context these notes assume: the user already converts dry vocals to specific singers (e.g. a VTuber trained on her own dry vocals) with DDSP-SVC and RIFT-SVC, and already has loudness-matched mixing scripts. Hardware: Windows 11 PC plus a rented Linux GPU server (AutoDL). Claude composes the instrumental in code first and adds vocals later.

## 1. SVS engines that take a score (melody MIDI + Chinese/Japanese lyrics) and can be scripted or run headless

### Takeaway
Only the open-source and engine-style tools can be driven unattended: openvpi DiffSinger (`scripts/infer.py` on `.ds` files), NEUTRINO (MusicXML plus a batch file), the VOICEVOX engine's HTTP singing endpoints, NNSVS, and the new zero-shot models (SoulX-Singer, Vevo2, TCSinger 2). OpenUtau, Synthesizer V Studio 2, ACE Studio 2 and VoiSona are GUI-first, and I found no documented headless render for any of them. Licensing differs sharply. VoiSona's terms (revised 2026-02-24) explicitly forbid using its output as input to voice conversion. Synthesizer V and DiffSinger voicebank terms are set per voicebank. SoulX-Singer is Apache-2.0 but covers only Mandarin, English and Cantonese, not Japanese.

### Cited Findings

**openvpi DiffSinger (open source, scriptable)**
- The openvpi fork is a refactored, extended DiffSinger. It outputs 44.1 kHz audio (up from 24 kHz), is licensed Apache-2.0, has ~3.2k stars, points to MakeDiffSinger for dataset creation, and its disclaimer prohibits generating someone's voice without their consent (page accessed 2026-10-28) — [openvpi/DiffSinger](https://github.com/openvpi/DiffSinger)
- Inference "is based on DS files": `python scripts/infer.py acoustic my_song.ds --exp my_experiment` and `python scripts/infer.py variance my_song.ds --exp my_experiment`. Deployment is through ONNX via `python scripts/export.py acoustic|variance --exp ...`, and the NSF-HiFiGAN vocoder is exported with `python scripts/export.py nsf-hifigan --config CONFIG --ckpt CKPT`. It needs Python >= 3.10 and recommends PyTorch >= 2.4.0. Training is `scripts/binarize.py`, then `scripts/train.py --config ... --exp_name ... --reset` — [DiffSinger GettingStarted.md](https://raw.githubusercontent.com/openvpi/DiffSinger/main/docs/GettingStarted.md)
- The community fork adds a controllable "variance" model covering pitch, energy and breathiness, with 44.1 kHz output — [Heges/DiffSinger (search summary)](https://github.com/Heges/DiffSinger)
- The original DiffSinger paper (AAAI 2022) was evaluated on a Chinese singing dataset — [arXiv 2105.02446](https://arxiv.org/abs/2105.02446v6)

**OpenUtau (GUI editor and host for DiffSinger/ENUNU voicebanks)**
- MIT license. Offers an "Easy-to-use plugin system" with an Editing Macros API and a Phonemizers API, supports ENUNU AI singers, imports VSQX, and pre-renders vocals before playback. The repo README mentions no command-line or headless mode (accessed 2026-10-28) — [stakira/OpenUtau](https://github.com/stakira/OpenUtau)
- OpenUtau loads Vogen, ENUNU/NNSVS, DiffSinger and VOICEVOX voicebanks. It has officially supported DiffSinger since at least 2024-03-31 — [Moegirl: OpenUtau](https://zh.moegirl.org.cn/OpenUtau); DiffSinger voicebank compatibility was first added 2023-01-08 — [pixiv dic: DiffSinger](https://dic.pixiv.net/a/DiffSinger)
- The documented render path is in the GUI: "File > Export Audio > Export wav Files" (one WAV per track) or "Mixdown To Wav File" — [OpenUtau wiki Getting Started (mirror)](https://github-wiki-see.page/m/openutau/OpenUtau/wiki/Getting-Started)
- A third-party Rust crate parses and writes OpenUtau's `.ustx` project format. The page does not say it can render audio — [docs.rs ustx](https://docs.rs/ustx)
- "OpenUtau For DiffSinger" can export a `.ds (v2)` project for the matching dictionary (Chinese page, via search summary) — [Moegirl: DiffSinger](https://zh.moegirl.org.cn/DiffSinger)
- Searches for an official OpenUtau CLI or headless render issue found none (2026-10-28) — [search results incl. fishaudio/OpenUtau fork](https://github.com/fishaudio/OpenUtau)

**Synthesizer V Studio 2 Pro (Dreamtonics)**
- The scripting API supports JavaScript (ECMAScript 5.1, Duktape) and Lua 5.4. Scripts can set note onset, duration, pitch, detune, lyrics, phonemes (`Note.setPhonemes`), language override and attributes, plus pitch control curves, automation, voice per group reference, and mixer gain, pan and mute. The manual lists no function to render, export or bounce audio; the closest is a `Track.setBounced` flag. "Synthesizer V Studio 2 Pro supports scripting" — [SV Scripting Manual](https://resource.dreamtonics.com/scripting/)
- 2.1.1 "significantly expands" scripting. The 2.1.2 beta adds a Scripts panel with custom UI panels. 2.1.0 added ARA for Pro Tools and redesigned pitch controls — [KVR news 2.1.1](https://www.kvraudio.com/news-print.php?id=64457); [Dreamtonics forum 2.1.2 beta](https://forum.dreamtonics.com/t/synthesizer-v-studio-2-pro-2-1-2-beta/4476); [rekkerd 2.1.1](https://rekkerd.org/dreamtonics-updates-synthesizer-v-studio-2-pro-to-v2-1-1)
- Vocal modes became controllable as parameters in 1.8.1 (forum post) — [SynthV forum: Set Vocal Modes script](https://forum.synthesizerv.com/t/topic/8091)
- A third-party MCP server (`mcp-svstudio`) drives SV Studio through a Lua handler. The handler runs inside the app ("run StartServerRequestHandler from the Scripts menu"), so the GUI must be open. It is not headless — [glama: mcp-svstudio README](https://glama.ai/mcp/servers/@ocadaruma/mcp-svstudio/blob/69a099645e67f54558601db48b2503393f1b2d86/README.md)
- Each voice database has its own `license.txt`. Works made with a Lite voice database must say so. One forum post claims voice providers agreed to synthetic-voice training, but that is secondhand — [SynthV forum: purchase/install guide](https://forum.synthesizerv.com/t/topic/6220); [vi-control FAQ](https://vi-control.net/community/threads/faq-what-is-synthesizerv.136072/)
- Dreamtonics Vocoflex does real-time voice morphing from ~10 s of audio and reportedly embeds a unique license ID watermark in its output (2024) — [Sound On Sound: Vocoflex](https://www.soundonsound.com/news/real-time-voice-morphing-dreamtonics-vocoflex); [techno-edge (JP, 2024-04)](https://www.techno-edge.net/article/img/2024/04/17/3198/15675.html)

**ACE Studio 2.0 (Timedomain)**
- Review [March 2026]: you enter MIDI notes and lyrics and pick a voicebank, and it renders in the cloud or in a local "Turbo" mode. The Verse25 engine exposes Power, Soft, Breathy and Chest parameters plus breath noise, all automatable. Other features: Blend Voices, Choir Mode (multiple voices from one clip with Offset and Spread), voice cloning ("clone your own voice (or that of another singer you have recorded)"), Vocal To MIDI, MIDI file import, a Stem Splitter, and ACE Bridge 2 or ARA for DAW integration. Pricing: Artist $497 or Artist Pro $660 one-time, or rent-to-own. The review does not cover an API, scripting, or output licensing — [Sound On Sound: ACE Studio 2](https://soundonsound.com/reviews/ace-studio-2)
- I found no official developer API. An aggregator lists an "ACE Studio API" with custom pricing (Aug 2026), which is unverified — [costbench (aggregator)](https://www.costbench.com/software/ai-music-apis/ace-studio-api/hidden-costs/)

**VoiSona (Techno-Speech; CeVIO AI lineage)**
- The terms, revised 2026-02-24, allow commercial and non-commercial use of Synthesized Voices. However, Art. 7.3(4) does not permit using "Synthesized Voices as input data, training data, or fragment data to generate artificial voice or carry out voice quality conversion", and Art. 13(16) lists the same as a prohibited act — [VoiSona Terms of Use (EN translation PDF)](https://voisona.com/static/pdf/en/terms.pdf)

**NEUTRINO (Japanese, free)**
- Neural SVS that estimates timing, pitch and timbre from MusicXML. Free since 2020-02-22. Workflow: put the MusicXML in `NEUTRINO\score\musicxml`, set `BASENAME` and `ModelDir` in `Run.bat`, run it, and WAV files appear in `Output`. MuseScore is the recommended score editor — [Moegirl: NEUTRINO](https://zh.moegirl.org.cn/NEUTRINO); [classmethod tutorial](https://dev.classmethod.jp/articles/tutorial-about-neutrino-neural-singing-synthesizer/); [nicovideo dic](https://dic.nicovideo.jp/a/neutrino(%E6%AD%8C%E5%A3%B0%E5%90%88%E6%88%90%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%B3))

**VOICEVOX engine (Japanese, HTTP API)**
- The engine exposes singing synthesis at `/sing_frame_audio_query` and `/frame_synthesis`, converting scores into singing — [DeepWiki: voicevox_engine](https://deepwiki.com/VOICEVOX/voicevox_engine); [VOICEVOX/voicevox_engine](https://github.com/VOICEVOX/voicevox_engine)
- A Score is built from notes whose lengths are in frames, and the first note must be a rest. VOICEVOX CORE splits each note's lyric into consonant and vowel phonemes. Live API docs are at `http://127.0.0.1:50021/docs` — [laravel-voicevox](https://root.packagist.org/packages/revolution/laravel-voicevox); [VOICEVOX CORE docs](https://docsearch.algolia.com/mcp/docs/repo/voicevox/voicevox_core)

**NNSVS / ENUNU (Japanese)**
- NNSVS by r9y9 was first released 2020-05-10; its toolkit paper appeared at ICASSP 2023. ENUNU is the UTAU plugin front-end. I found no 2025–2026 release notes — [NNSVS/ENUNU guide](https://nnsvs.carrd.co/); [arXiv 2210.15987](https://export.arxiv.org/abs/2210.15987)

**New open zero-shot SVS models (2025–2026)**
- SoulX-Singer [arXiv 2602.07803, v1 2026-02-08, v2 2026-03-16]: zero-shot SVS trained on more than 42,000 h of vocals. Languages are Mandarin, English and Cantonese; Japanese is not listed. It is conditioned on a MIDI score or an F0 contour. Code and weights are Apache-2.0. The CLI demos are `bash example/infer.sh` and `bash example/infer_svc.sh`, with web UIs `webui.py` and `webui_svc.py`. Preprocessing uses RMVPE, Paraformer, Parakeet-tdt-0.6b-v2 and ROSVOT, and the README warns that alignment "may not perfectly align" and recommends its Midi-Editor. SoulX-Singer-SVC was released 2026-03-16 — [Soul-AILab/SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer); [arXiv 2602.07803](https://arxiv.org/abs/2602.07803v1)
- Vevo2 (Amphion/CUHK-SZ) [arXiv 2508.16332, Aug 2025, v3 Mar 2026]: one model for TTS, text-to-singing, SVS, style-preserving or style-converting singing voice conversion, editing, and humming- or instrument-to-singing. It was trained on ~7k h of internal singing data. Checkpoints are at HF `RMSnow/Vevo2`. The arXiv version is CC BY-NC-SA 4.0 (the checkpoint license is unverified), and a GitHub issue says it was accepted to IEEE TASLP — [HF RMSnow/Vevo2](https://huggingface.co/RMSnow/Vevo2); [arXiv 2508.16332](https://arxiv.org/html/2508.16332v3)
- TCSinger 2 (ZJU, ACL 2025 Findings): multilingual zero-shot SVS with style transfer and control. Code is at AaronZ345/TCSinger2 (per an aggregator); license unverified — [arXiv 2505.14910](https://arxiv.org/html/2505.14910v1); [ACL Anthology](https://preview.aclanthology.org/new-sigs/2025.findings-acl.687/); [gittrend](https://gittrend.io/repo/AaronZ345/TCSinger2)

**DiffSinger voicebank licenses**
- There is no blanket OpenUtau/DiffSinger rule; terms are per voicebank. Example: the NoLyui DiffSinger voicebank prohibits releasing voice-conversion or music software that keeps its voice quality. Some DiffSinger vocoders ship under CreativeML Open RAIL-M use restrictions — [NoLyui terms](https://nolyui.carrd.co/); [PC-DDSP-LoFiVocoder README](https://huggingface.co/usamireko/LoFiVocoder/blob/main/README.md)

### Inferences
- For an agent to drive everything end to end, the shortest headless path is LLM score -> `.ds` file (or MusicXML) -> `python scripts/infer.py variance` then `acoustic` on AutoDL -> WAV. Any trained DiffSinger model works. OpenUtau is still useful as a human-in-the-loop editor and for exporting `.ds` files, but not as a renderer in the loop.
- Japanese: NEUTRINO (MusicXML batch) and VOICEVOX (HTTP API, local) are the easiest to script from Windows. DiffSinger Japanese voicebanks also work through `infer.py`. SoulX-Singer is not an option for Japanese lyrics as of 2026-10.
- Chinese: DiffSinger (opencpop-lineage voicebanks) and SoulX-Singer (zero-shot, MIDI-conditioned, Apache-2.0) are both scriptable on Linux.
- Synthesizer V 2 and ACE Studio 2 probably give the most natural expression for both languages (vocal modes, Verse25 parameters, Retakes), but a person has to export each render. SV scripts can write every note, phoneme and pitch curve from an LLM-generated score, so a person only presses export. That is a semi-automated option.
- VoiSona must not be used as a guide vocal for SVC, because its terms forbid using output as voice-conversion input. Check each SV or DiffSinger voicebank's license for "input to voice conversion" (not just "training"), and keep a copy of the license with each project.

### Gaps
- VOCALOID 6 and CeVIO AI: I did not research scripting, headless rendering or voice-conversion terms this session.
- I could not get the actual Synthesizer V AI voice database EULA clause on voice conversion; only secondhand forum claims, some of which say it is against the license.
- I could not find the NEUTRINO terms on voice conversion or AI use, or NEUTRINO's latest version number.
- I found no head-to-head quality comparison (MOS) of SV2, ACE Studio 2, DiffSinger, NEUTRINO and SoulX-Singer for Chinese or Japanese.
- I did not fetch a `.ds` file field specification. SOFA and MakeDiffSinger use `ph_seq`, `ph_dur` and `ph_num` (see section 2), but the full `.ds` JSON schema is unverified.

## 2. The SVS -> SVC chain, and the alternative of training an SVS model on the target singer

### Takeaway
Rendering a guide vocal with SVS and converting it with an SVC model is a known, community-practised workflow (SynthV -> RVC is documented since 2023). The consistent warning is that SVC changes only timbre and inherits the guide's timing, pitch, phrasing and weaknesses, so expression has to be programmed into the SVS for the target singer's style. I found no peer-reviewed study of SVS-guide -> SVC artifacts. Two other routes exist. You can train a DiffSinger model on the singer's own dry vocals; this needs phoneme-level alignment (MFA or SOFA) and note labels for the variance model. Or you can use a zero-shot SVS/SVC family (SoulX-Singer plus SoulX-Singer-SVC, or Vevo2) that does both steps in one model family.

### Cited Findings
- Workflow: export the SynthV output as WAV, then run RVC's "infer" with the target model. You get what sounds like the same melody re-recorded in another voice (Japanese, 2023–2024) — [techno-edge 2023-04-09](https://www.techno-edge.net/article/2023/04/09/1130.html); [vi-control thread p.210](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-210)
- "A poorly sung vocal or badly programmed Synth-V performance cannot be improved by RVC." It works best when the SV performance is built for the target voice's style. One example split a four-part choral score into MIDI parts, imported them as separate SV tracks and converted each with RVC. A listener found the RVC choir had "more diversity of tone" than plain SV (forum, via search summary; the page returned 403 on direct fetch) — [vi-control thread p.209](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-209)
- A forum poster says training an RVC model on Synthesizer V voices is "technically against the license agreement" (unverified secondhand) — [vi-control thread p.210](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-210)
- VoiSona explicitly forbids using its output as voice-conversion input (Art. 7.3(4), 13(16); revised 2026-02-24) — [VoiSona Terms](https://voisona.com/static/pdf/en/terms.pdf)
- Bilibili RVC cover tutorials cover manual harmony separation, removing muted or silent notes, patching notes, and transposition, which are the same cleanup steps an SVS guide would need — [bilibili BV1FkVg6aEJX](https://www.bilibili.com/video/BV1FkVg6aEJX/)
- SoulX-Singer-SVC is "finetuned from SoulX-Singer" and converts from "waveform and F0 inputs" without lyric or MIDI transcription (released 2026-03-16) — [Soul-AILab/SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer)
- Vevo2 offers both SVS and "style-preserved" or "style-converted" singing voice conversion in one framework (2025–2026) — [HF RMSnow/Vevo2](https://huggingface.co/RMSnow/Vevo2)

**Training an SVS model directly on the target singer (DiffSinger)**
- MakeDiffSinger layout: `raw/wavs/` plus `transcriptions.csv`. The recommended from-scratch pipeline is "acoustic-forced-alignment: make dataset from scratch with MFA for acoustic model training", and "variance-temp-solution" extends acoustic datasets into variance datasets. Tools: AudioSlicer (slicing), MinLabel (word `.lab` transcriptions) and SlurCutter (edit MIDI in `.ds` files for variance training) — [openvpi/MakeDiffSinger](https://github.com/openvpi/MakeDiffSinger)
- SOFA (an alternative forced aligner) uses DiffSinger-format CSV with `name`, `ph_seq` and `ph_dur` columns. The variance pipeline adds `ph_num` for phoneme duration training — [SOFA discussion #5](https://github.com/qiuqiao/SOFA/discussions/5); [MakeDiffSinger variance README (mirror)](https://huggingface.co/ameerazam08/MakeDiffSinger/blob/main/variance-temp-solution/README.md)
- openvpi lists a "Generative Adaptive MIDI Extractor" project for note extraction (aggregator listing) — [oosmetrics: openvpi](https://oosmetrics.com/u/openvpi)
- The DiffSinger disclaimer forbids generating someone's voice without consent — [openvpi/DiffSinger](https://github.com/openvpi/DiffSinger)
- ACE Studio 2 voice cloning also works from recordings of "another singer you have recorded". The reviewer suspects it needs "an extensive, varied set of clean recordings" (Mar 2026) — [Sound On Sound: ACE Studio 2](https://soundonsound.com/reviews/ace-studio-2)

### Inferences
- This chain fits the user's existing DDSP-SVC/RIFT-SVC setup. SVC keeps the guide's F0 and timing, so any robotic quality is decided at the SVS stage. The agent should therefore add vibrato, pitch drift, note-onset scoops and breath events in the score/`.ds` (or SV pitch curves) rather than expecting SVC to add them.
- A gender or range mismatch between the guide voicebank and the target singer probably hurts most. Picking a guide voicebank with a similar register (or transposing via the SVC key shift) is a standard mitigation in cover work, but I found no 2026 source that measures this.
- The user already has the target singers' dry vocals, so a DiffSinger acoustic model trained on them would remove the SVC step and its licensing questions (with the singer's consent). The cost is phoneme labeling: Japanese and Chinese both need MFA or SOFA alignment plus note labels for a variance model. A hybrid that keeps the current stack is an open-licensed DiffSinger guide -> the existing DDSP-SVC model.
- The SoulX-Singer family could prompt zero-shot directly with the singer's dry vocal for Chinese songs. It cannot do Japanese.

### Gaps
- I found no systematic write-up (paper or detailed bilibili/Zhihu post) on the specific artifacts of an SVS guide -> SVC conversion (consonant smearing, breath loss, phrase-end handling) or on proven fixes. Search results in Chinese and Japanese stayed generic.
- I found no data-size guidance (minutes or hours of dry vocals) for training a DiffSinger voicebank; the official READMEs fetched do not state one.
- I did not check Seed-VC's or RVC's current singing-mode performance on SVS-generated inputs.

## 3. Backing vocals, harmonies and doubles

### Takeaway
Since the LLM writes the score, the cleanest option is to write each harmony or backing part as its own melody line, render each with SVS, and convert each through SVC. Practitioners do this, for example a 4-part choir split into MIDI parts in SV and then put through RVC. Built-in "choir" or "blend" modes (ACE Studio 2) and AI harmony plugins (SoundID VoiceAI) are GUI tools. Doubles are usually made by adding small pitch and timing variance to a re-render or re-conversion; a plain pitch-shift copy of the lead is the fallback.

### Cited Findings
- 4-part choral score -> MIDI parts -> separate Synthesizer V tracks -> RVC per part; the result had "more diversity of tone" than plain SV — [vi-control thread p.209](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-209)
- ACE Studio 2 Choir Mode "generates multiple voices from one clip" with Offset, Spread and gain, and Blend Voices mixes voicebanks on one track. "The results can be impressive" (Mar 2026) — [Sound On Sound: ACE Studio 2](https://soundonsound.com/reviews/ace-studio-2)
- Vendor guidance (Sonarworks, 2025–2026, promotional): start from a comped and tuned lead, then generate harmonies with a voice-transformation tool. Doubling = "slight pitch variation for thickness". Pro tools add timing variance to push backing vocals slightly ahead of or behind the lead. Tools lean toward Western pop/rock styles — [Sonarworks: backing vocals with AI](https://www.sonarworks.com/blog/learn/whats-the-fastest-way-to-create-backing-vocals-with-ai); [Sonarworks: harmonies with voice AI](https://www.sonarworks.com/blog/learn/how-do-you-add-harmonies-using-voice-ai-tools)
- Pedalboard has a built-in `PitchShift` effect, plus Rubber Band integration for time stretching — [spotify/pedalboard](https://github.com/spotify/pedalboard)
- Vevo2 supports instrument-to-singing and humming-to-singing, which could turn a synth harmony line into sung audio — [HF RMSnow/Vevo2](https://huggingface.co/RMSnow/Vevo2)

### Inferences
- Agent recipe:
  1. Have the LLM write explicit harmony voices (3rds or 6ths above, octave below) as separate MIDI tracks with the same lyrics, or "ah/oo" pads.
  2. Render each with SVS, varying the seed or voicebank, and convert each with the target singer's SVC model.
  3. For doubles, re-render the lead with a different seed or small timing offsets (tens of ms) and slightly different pitch curves instead of copying the lead.
  4. In the mix, pan doubles and harmonies wide, high-pass them, and duck them under the lead.
- Pitch-shifting the converted lead by more than about 3 semitones usually exposes formant artifacts. Score-based rendering avoids this, which is why the score route is preferred here.

### Gaps
- I found no open-source, scriptable "auto-harmony from lead" model with documented Chinese or Japanese quality. I did not research Harmony Engine, Waves or similar plugins.

## 4. Scripted mixing and mastering of many stems plus vocals

### Takeaway
Reliable unattended building blocks exist. Spotify Pedalboard (GPL-3.0; built-in effects plus VST3 hosting on Windows and Linux) and DawDreamer (processor graphs, VST and Faust, parameter automation) cover rendering, and pyloudnorm covers BS.1770 loudness. Matchering (GPL-3.0) does reference-matched mastering on RMS, frequency response, peak and stereo width. REAPER can be driven by Python ReaScript, reapy or third-party MCP servers. Learned automatic mixing (Diff-MST 2024, MEGAMI 2025–2026, two-stage systems at ISMIR 2026) is research-grade, with code but not production-ready. Commercial assistants (iZotope Ozone 12 Master Assistant, LANDR) cannot be scripted from code; LANDR has a partner-only mastering API with custom pricing. LLM-driven effect-parameter prediction (LLM2Fx, LLM2Fx-Tools at ICLR 2026) shows an agent can choose effect chains and parameters through tool calls.

### Cited Findings

**Rendering and effects libraries**
- Pedalboard (Spotify): GPL-3.0. Built-in Chorus, Distortion, Phaser, Clipping, Compressor, Gain, Limiter, Highpass, Lowpass and Ladder filters, Convolution, Delay, Reverb, PitchShift, MP3/GSM compression, Resample and Bitcrush. Boards chain like lists (`board = Pedalboard([Chorus(), Reverb(room_size=0.25)])`). `load_plugin("...vst3")` loads VST3 plugins on macOS, Windows and Linux (AU on macOS only), and parameters are set as attributes (`effect.ratio = 15`). Files can be processed in chunks with `AudioFile`. It releases the GIL. Limitations: Linux x86_64 wheels need AVX, Linux VSTs need glibc > 2.27, and testing covers Python 3.10–3.15 (accessed 2026-10-28) — [spotify/pedalboard](https://github.com/spotify/pedalboard)
- DawDreamer: offline batch processing with directed acyclic graphs of processors. Supports VST instruments and effects, including multi-input effects such as a sidechain compressor, plugin state load/save, FAUST effects and instruments, and parameter automation at audio rate and at PPQN. `pip install dawdreamer`, Python 3.8+ (PyPI 0.6.x) — [DBraun/DawDreamer](https://GitHub.com/DBraun/DawDreamer); [PyPI dawdreamer 0.6.9](https://pypi.org/project/dawdreamer/0.6.9/); [arXiv 2111.09931](https://arxiv.org/abs/2111.09931)
- pyloudnorm: a Python loudness meter implementing ITU-R BS.1770-4, with control over gating block size and weighting filters. The repo was last pushed roughly two years before indexing — [pyloudnorm mirror](https://gitee.com/shirlim/pyloudnorm); [science.ecosyste.ms listing](https://science.ecosyste.ms/projects/198271)
- REAPER: Python ReaScript (Python 2.7–3.x, enabled in preferences), the `reapy` pythonic wrapper (usable inside or outside REAPER), and a queued batch render in the render dialog — [ReaScript docs](https://www.reaper.fm/sdk/reascript/); [python-reapy](https://pypi.org/project/python-reapy); [Cockos wiki ReaScript](https://www.cockos.com/wiki/index.php/ReaScript)
- Third-party REAPER MCP servers claim tens to 170+ tools for tracks, FX, mixing, mastering, rendering and audio QC (unverified) — [bonfire-systems/reaper-mcp](https://github.com/bonfire-systems/reaper-mcp); [itsuzef/reaper-mcp README](https://cdn.jsdelivr.net/gh/itsuzef/reaper-mcp@main/README.md)

**Reference-matching and auto-mastering**
- Matchering 2.0: takes a TARGET and a REFERENCE and matches RMS, frequency response, peak amplitude and stereo width, then applies its own "Hyrax" brickwall limiter. GPL-3.0. Python API: `mg.process(target=..., reference=..., results=[mg.pcm16(...), mg.pcm24(...)])`. Needs Python >= 3.8, >= 4 GB RAM and libsndfile (install manually on Linux); FFmpeg only for MP3. There is also a Docker web app, a ComfyUI node and a UVR5 integration. A reviewer notes results depend on "carefully selecting a proper song as reference" — [sergree/matchering](https://github.com/sergree/matchering)
- LANDR mastering API: launched 2022-05-04 with partners OffTop and DAO. It offers "three previewable loudness settings and mastering styles". Pricing is custom per aggregators; a $2.50/track figure is unverified — [LANDR press clip](https://landr.rockpaperscissors.biz/artist/18336/press_clips/28148/white); [fast-and-wide](https://www.fast-and-wide.com/equipment-releases/processing-and-control/16953-landr-ai-mastering-api); [costbench (aggregator)](https://costbench.com/software/ai-music-apis/landr-api/)
- iZotope Ozone 12: Master Assistant has a "custom flow" with module choices, LUFS targets and genre modifiers. I found no CLI, scripting API or documented batch automation — [ProSoundWeb: Ozone 12](https://www.prosoundweb.com/izotope-announces-new-ozone-12-mastering-suite/); [Sound On Sound: Ozone 12 Advanced](https://www.soundonsound.com/reviews/izotope-ozone-12-advanced?amp)
- Spotify normalizes to -14 LUFS integrated (ITU 1770) and leaves 1 dB headroom for lossy encodes. Its support pages recommend true peak below -1 dBTP; one regional page says below -2 dBTP when the master is louder than -14 LUFS (pages inconsistent) — [Spotify for Artists: loudness normalization](https://support.spotify.com/artists/article/loudness-normalization/)

**Automatic mixing research and tools**
- Diff-MST [ISMIR 2024; arXiv 2407.08889]: takes raw tracks plus a reference song and predicts parameters for a differentiable mixing console (transformer controller, production-style loss). It handles an arbitrary number of unlabeled tracks, and code is linked. The Diff-MSTC Cubase prototype takes up to 20 tracks plus a reference — [arXiv 2407.08889](https://arxiv.org/pdf/2407.08889); [ISMIR 2024 LBD 475](https://ismir2024program.ismir.net/lbd_475.html)
- MEGAMI [arXiv 2511.08040, 2025-11-11; submitted to ICASSP 2026; Aalto + Sony AI]: treats mixing as generative, using conditional diffusion in an effect-embedding space with a permutation-equivariant processor for unlabeled tracks. It trains on dry and wet data via CLAP-space effects removal. Listening tests show "performances approaching human-level quality across diverse musical genres" — [arXiv 2511.08040](https://arxiv.org/html/2511.08040v1); [Sony AI](https://ai.sony/publications/automatic-music-mixing-using-a-generative-model-of-effect-embeddings)
- "Understanding Automatic Mixing: A Subtask-Oriented Analysis of Two-Stage Mixing System" [arXiv 2609.02835, 2026-09-02, ISMIR 2026; co-author Joshua Reiss]: two-stage (intra-group then inter-group) variants "significantly outperformed" single-stage baselines. Bad grouping causes clear degradation, while changed loudness relationships have weaker, model-dependent effects. The authors recommend separating local balance from global mix coordination — [arXiv 2609.02835](https://arxiv.org/abs/2609.02835)
- automix-toolkit (Steinmetz): models, datasets and training recipes for deep-learning automixing, with pretrained checkpoints from HF and an inference notebook for drum mixes. Sony's FxNorm-automix is a separate implementation (2022) — [science.ecosyste.ms: automix-toolkit](https://science.ecosyste.ms/projects/198271); [arXiv 2208.11428 (FxNorm)](https://ar5iv.labs.arxiv.org/html/2208.11428); [gittrend: sony/FxNorm-automix](https://gittrend.io/repo/sony/FxNorm-automix)

**LLM-driven effects/mixing**
- LLM2Fx [arXiv 2505.20770, May 2025, WASPAA 2025, Sony AI/KAIST]: an LLM predicts EQ and reverb parameters from text, zero-shot, outputting structured JSON that is applied to effect modules. Few-shot examples and prompt design matter — [arXiv 2505.20770](https://arxiv.org/abs/2505.20770); [Sony AI](https://ai.sony/publications/can-large-language-models-predict-audio-effects-parameters-from-natural-language)
- LLM2Fx-Tools [arXiv 2512.01559, Dec 2025 / rev. Jan 2026, ICLR 2026]: an LLM understands the audio, picks effect types and their order, and estimates parameters through tool calling with chain-of-thought planning. Introduces the LP-Fx dataset; described as the first LLM tool-calling work for audio effects — [arXiv 2512.01559](https://arxiv.org/abs/2512.01559v2); [ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10009732)

### Inferences
- What is safe to run unattended today: deterministic DSP chains in Pedalboard or DawDreamer (HPF/EQ/compression on vocals, bus compression, reverb sends, sidechain ducking), BS.1770 gain staging per stem with pyloudnorm, and Matchering against a well-chosen reference for the final master, followed by a pyloudnorm check of integrated LUFS and true peak. The instrumental is produced by code, so stems already arrive clean, labelled and grouped. That matches the two-stage finding: mix within groups (drums, bass, harmony, vocals) first, then balance the groups.
- Learned automixers (Diff-MST, MEGAMI) are worth trying on AutoDL as a first-draft parameter generator. They are trained mostly on Western multitracks, so treat their output as a starting point to check with metrics, not a final mix.
- Ozone and Neutron can be hosted as VST3 in Pedalboard or DawDreamer with parameters set from code, but the AI "assistant" analysis cannot be triggered from code (no API found). Treat them as static plugins with presets.
- GPL-3.0 (Pedalboard, Matchering) matters only if the user's scripts are redistributed. Private use is unaffected.

### Gaps
- I did not verify REAPER's command-line render flag (commonly cited as `-renderproject`) against the official documentation this session.
- I found no published comparison of Matchering against Ozone or LANDR masters on Chinese or Japanese pop.
- Licenses for the Diff-MST and MEGAMI code and checkpoints were not checked.

## 5. Agent feedback loop: objective metrics and audio-understanding models for self-judging a mix

### Takeaway
Objective measurement is solid and easy to run: BS.1770 LUFS and true peak via pyloudnorm, spectral balance against a reference (the same features Matchering matches), and no-reference aesthetic predictors such as Meta Audiobox Aesthetics (`pip install audiobox_aesthetics`; CE/CU/PC/PQ scores). Singing-specific MOS data exists (SingMOS, SingMOS-Pro with overall, lyrics and melody ratings), and SongEval covers whole songs in English and Chinese, including "vocal breathing and phrasing". General audio LLMs are weak as raters as of 2026. In MuseCritic's tests, Gemini-3.1-Pro reached only ~0.49–0.62 correlation with expert song ratings, and Qwen3-Omni scored 53.75% on Music Arena pairwise preference (near chance). Use LLMs for written critiques, and use calibrated predictors plus metrics for go/no-go decisions.

### Cited Findings
- Audiobox Aesthetics (Meta) [arXiv 2502.05139, Feb 2025]: predicts Content Enjoyment, Content Usefulness, Production Complexity and Production Quality. Human labels are on a 1–10 scale; example output is `{"CE": 5.146, "CU": 5.779, "PC": 2.148, "PQ": 7.220}`. Install with `pip install audiobox_aesthetics`; CLI `audio-aes input.jsonl --batch-size 100 > output.jsonl`; Python `initialize_predictor().forward([...])`. Mostly CC-BY 4.0; Python 3.9, PyTorch >= 2.2 — [facebookresearch/audiobox-aesthetics](https://github.com/facebookresearch/audiobox-aesthetics); [Meta AI publication](https://ai.meta.com/research/publications/meta-audiobox-aesthetics-unified-automatic-quality-assessment-for-speech-music-and-sound/)
- AudioMOS Challenge 2025, Track 2: predict the four Audiobox Aesthetics axes for TTS, TTA and TTM systems — [arXiv 2509.01336](https://arxiv.org/html/2509.01336v1)
- SongEval [arXiv 2505.10793, May 2025, ASLP-lab NWPU]: 2,399 full songs (>140 h), rated by 16 professional annotators on coherence, memorability, vocal breathing and phrasing, structure clarity and overall musicality. English and Chinese, nine genres. Dataset and toolkit on HF `ASLP-lab/SongEval` and GitHub; used for the ICASSP 2026 Automatic Song Aesthetics Evaluation Challenge — [arXiv 2505.10793](https://arxiv.org/html/2505.10793v1); [HEAR (challenge entry)](https://arxiv.org/html/2511.18869v2)
- MuseCritic [arXiv 2608.11755, v1 2026-08-12, v2 2026-10-01]: a critique-then-score reward model on SongEval's five dimensions. In-domain macro LCC 0.9068 and SRCC 0.8838, MSE 0.2316. Gemini-3.1-Pro as a judge got LCC 0.49–0.62 per dimension (vocal naturalness lowest at 0.4921) and MSE 1.3061. On Music Arena (733 pairs): MuseCritic 71.35%, the SongEval predictor 70.80%, Qwen3-Omni 53.75% (lowest). The authors: "an unadapted LLM-as-a-Judge cannot reliably reproduce five-dimensional expert judgments of song aesthetics". Code at github.com/WuqnEl/MuseCritic — [arXiv 2608.11755](https://arxiv.org/html/2608.11755)
- SingMOS [arXiv 2406.10911, 2024]: 3,421 singing clips (4.25 h) from SVS, SVC and vocoder systems, CC-BY-SA-NC 4.0. PS-SQA (VoiceMOS 2024) adds pitch and spectral features to an SSL MOS predictor — [arXiv 2406.10911](https://arxiv.org/pdf/2406.10911); [arXiv 2411.11123](https://arxiv.org/html/2411.11123v1)
- SingMOS-Pro [arXiv 2510.01812, Oct 2025]: 7,981 clips (11.15 h) from 41 models and 44,247 ratings from 78 annotators, covering overall, lyrics and melody. CC-BY-4.0 on HF `TangRain/SingMOS-Pro`. A separate "Singing MOS Predictor" repo has a pretrained model (tied to the preview SingMOS data) — [arXiv 2510.01812](https://arxiv.org/html/2510.01812v4); [HF dataset](https://huggingface.co/datasets/TangRain/SingMOS-Pro/commit/aa7591c6edc10bf73267da0a3bb8d47162f2d021)
- MixAssist [arXiv 2507.06329, July 2025, COLM 2025]: 431 audio-grounded conversation turns from 12 producers. Qwen-Audio fine-tuned on it "significantly outperformed" the other models tested at giving useful mixing advice (LLM-judge plus human expert comparisons) — [arXiv 2507.06329](https://arxiv.org/abs/2507.06329)
- CMI-RewardBench uses Qwen3-Omni with consistency filtering to label 110k music reward samples. Qwen-Audio-3.0-Gen-Preview's SongBench includes a mixing component — [arXiv 2603.00610](https://arxiv.org/html/2603.00610v2); [arXiv 2607.27011](https://arxiv.org/pdf/2607.27011)
- For speech, Gemini 2.0/2.5 and GPT-4o-audio judges agree strongly on relative rankings (EmergentTTS-Eval, 2025) — [arXiv 2505.23009](https://arxiv.org/pdf/2505.23009)
- Matchering's matched features (RMS, frequency response, peak, stereo width) make a concrete reference-comparison feature set — [sergree/matchering](https://github.com/sergree/matchering)
- Spotify's target of -14 LUFS integrated with true peak below -1 dBTP (or -2 dBTP if louder) is a release-check threshold — [Spotify for Artists](https://support.spotify.com/artists/article/loudness-normalization/)

### Inferences
- A practical loop the agent can run each iteration:
  1. Hard gates:
     - integrated LUFS and true peak (pyloudnorm, plus oversampled peak) within target;
     - no clipping;
     - vocal-to-instrumental loudness ratio within the range measured on reference songs (the user's scripts already do loudness matching);
     - per-band spectral difference from 1–3 genre references (Matchering-style average spectrum, smoothed to 1/3 octave);
     - stereo correlation and mono compatibility.
  2. Soft scores:
     - Audiobox Aesthetics PQ/CE on the full mix and on the vocal stem alone;
     - a SingMOS-style predictor on the converted dry vocal to catch SVC artifacts;
     - SongEval or MuseCritic on the full song for breathing, phrasing and musicality.
  3. LLM critique (Gemini or Qwen3-Omni) only for qualitative notes such as "vocal buried in the chorus" or "sibilance". Do not use its numeric score.
  4. Change the Pedalboard parameters (LLM2Fx-Tools style), re-render, and stop when the gates pass and the soft scores stop improving.
- Masking analysis was not found as a packaged tool. It can be approximated in code by comparing the vocal-stem and instrumental band energies (critical bands) in the 1–5 kHz presence region frame by frame, then applying dynamic EQ or sidechain ducking where the instrumental exceeds the vocal.
- Vocal naturalness is the weakest dimension for Gemini (LCC 0.49), and SVS -> SVC artifacts are the main risk in this pipeline. So vocal quality should be gated by singing-specific predictors and human spot checks, not by a general audio LLM.

### Gaps
- No packaged, validated "masking analysis" tool for multitrack mixes turned up this session.
- I did not find benchmark numbers for Gemini or Qwen3-Omni on judging mix quality specifically (as opposed to song aesthetics), nor for Chinese or Japanese material specifically.
- SingMOS-Pro baseline predictor numbers and the current Singing MOS Predictor checkpoint status were not read.
- "MusicEval" was named in the brief but not researched separately.
