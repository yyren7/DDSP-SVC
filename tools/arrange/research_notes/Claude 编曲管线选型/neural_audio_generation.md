# Neural audio generation for instrumental music vs a MIDI + sample-library pipeline (state as of 2026-10-28)

Scope: neural models and services that generate or render instrumental audio. The focus is how precisely an agent (Claude, composing in code) can control melody, harmony, structure and individual tracks, plus realism. A coordinator requirement was added mid-task: the user needs note-level control on every change. That means many melody fragments in different keys and modes, frequent re-orchestration, splicing, and exact edits to any single note or instrument sound. Each option is therefore judged on three tests: (a) does it honour an exact given MIDI or score note-for-note, per instrument; (b) can a local edit (one note, bar or instrument) be re-rendered without changing the rest; (c) is a fixed seed reproducible. The verdict matrix is in the last section.

Source-quality note: many 2026 facts here come from secondary blogs (dubspot.com, mer.vin, aicybr.com, it-jim.com) because vendor pages were thin or returned 403 errors. Primary sources (arXiv, GitHub, Hugging Face, vendor API reference) are used where they could be fetched. Conflicts are flagged inline.

## 1. Text-to-music and song models: API, licence, conditioning, stems, legal state

### Takeaway
None of the commercial song models takes MIDI, a chord chart or a note list as input. That covers Suno v6, Udio, ElevenLabs Music v2/v2.5, Lyria 3.5, Stable Audio 2.5/3.0, MiniMax and Mureka. They are steered by text, structure tags, section timings, BPM/key words in the prompt, and in some cases a reference audio clip. ACE-Step 1.5 (MIT) is the most controllable open model, with explicit BPM, key and time-signature fields, seed, repaint, cover and add-track tasks, but it still has no symbolic input. The legal position is in flux. Suno moved to licensed v6 models in September 2026 and was sued again by Sony and UMG; Udio downloads have been off since October 2025.

### Cited Findings

**Suno**
- Suno v5.5 was released 2026-03-26, with "voice capture and personalization" features — [MBW headline](https://www.musicbusinessworldwide.com/suno-launches-v5-5-ai-model-with-voice-capture-and-personalization-features). The full article was not fetched.
- Suno v6 was announced 2026-09-09, co-developed with Warner Music Group, BMG and Believe. It comes in three variants: v6, v6-wild (Pro/Premier only) and v6-mini (everyone). "As v6 rolls out, we will retire our previous models and move Suno entirely onto the v6 generation." Listed features: partial song editing, mashups from multiple sources, audio isolation, sampling, and prompting with text, audio, images or video. The article does not say which catalogues were used or how training was done — [The Next Web, 2026-09-09](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models)
- Suno Studio 2.0 shipped 2026-08-13 and is Premier-only ($30/mo, or $24/mo billed annually). It adds MIDI import, recording and editing on the timeline, audio-to-MIDI by dragging audio onto a MIDI track, and a built-in wavetable synth on every MIDI track. It also adds a beta chat bar ("create instruments and vocals… generate MIDI clips, arrange sections"), stem splitting (Split from Mix, Advanced Split), and export of 32-bit/48 kHz multitracks and stem WAVs with no Studio cap. Limitations: web only, with no VST/AU hosting and no DAW sync. "Some new generations can sit slightly ahead of or behind the beat." The article gives no detail on MIDI export quality and no stem count — [Dubspot, 2026-08-19](https://blog.dubspot.com/suno-studio-2-0)
- Download caps outside Studio from 2026-09-03: Free 7 lifetime, Pro 20/month, Premier 60/month — [Dubspot, 2026-08-19](https://blog.dubspot.com/suno-studio-2-0). This conflicts in part with [TNW, 2026-09-09](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models), which says free-tier songs "can be played and shared but not downloaded" and that paid users have monthly limits with paid top-ups.
- Claims about Suno MIDI export conflict. A January 2026 video summary said the "MIDI" option effectively exported stems that users had to convert themselves — [lilys.ai summary](https://lilys.ai/notes/zh/suno-ai-20260128/suno-studio-v5-midi-export). A Spanish blog claims "up to 12 synchronized stems in MIDI format" in "v5.5" — [donweb blog](https://blog.donweb.com/editor-musica-ia-suno-flujo-trabajo-v55/). Neither could be confirmed on suno.com.
- Suno "Covers" (since Sept 2024) "transform anything from voice recordings to fully-produced tracks while preserving the original melody" — [AlternativeTo, 2024-09](https://alternativeto.net/news/2024/9/suno-ai-s-new-covers-feature-lets-users-reimagine-music-in-any-different-style)
- Suno has no public official API. Community MCP servers wrap third-party resellers (sunoapi.org, AceDataCloud, runapi.ai) or Suno's internal web endpoints, and the browser-based ones "may break when Suno updates" — [glama/Socket/GitHub listings summarised in search; e.g. CodeKeanu/suno-mcp](https://github.com/CodeKeanu/suno-mcp), [AceDataCloud mcp-suno](https://www.getdrio.com/mcp/io-github-acedatacloud-mcp-suno)

**Legal state (Suno and Udio)**
- June 2024: WMG, UMG and Sony sued both Suno and Udio. 2025-10-29: UMG settled with Udio, and the two plan a joint licensed platform in 2026. 2025-11-26: WMG settled with Suno; Suno will build models trained on licensed Warner music and acquired Songkick. Sony had settled with neither as of 2026-05-19 (Suno case in D. Mass., Udio in S.D.N.Y.) — [Dubspot, 2026-05-19](https://blog.dubspot.com/suno-udio-ai-music-lawsuits-2026)
- WMG also settled with Udio in November 2025, with a licensed service "coming in 2026" — [MBW](https://www.musicbusinessworldwide.com/warner-music-settles-udio-lawsuit-strikes-licensing-deal-with-ai-platform)
- 2026-09-18: Sony Music and UMG filed a second suit against Suno (*UMG Recordings, Inc. et al. v. Suno, Inc.*, D. Mass.). They allege the licensed v6 still benefits from the unlicensed earlier models: "user feedback and model learnings" carried over — [RuntimeWire, 2026-09-18](https://runtimewire.com/article/sony-umg-suno-v6-copyright-lawsuit)
- A German court ruled that Suno breached copyright in a case brought by GEMA. Sony is suing Udio over 30,000 songs and seeking $4.5bn — [TNW, 2026-09-09](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models). One search summary dated the GEMA ruling 31 July 2026, but this was not verified.
- Udio disabled all downloads (audio, video, stems) around 2025-10-29/30, briefly reopened them for 48 hours in November, and kept them off. A help-centre update cited as 2026-02-17 still says they are disabled. As of around September 2026 there was no confirmed launch date for the licensed relaunch — [Udio download coverage via search; Digital Music News](https://www.digitalmusicnews.com/2025/11/20/will-udio-still-exist-in-2026/), [annielytics Udio timeline](https://www.annielytics.com/tools/ai-timeline/company/udio/). Source quality here is mixed.

**ElevenLabs Music**
- API: `POST /v1/music`, with `model_id` one of `music_v1` (default), `music_v2` or `music_v2_5`. Body fields:
  - `prompt` or `composition_plan`, which are mutually exclusive.
  - `music_length_ms` (3–600 s, prompt only).
  - `force_instrumental`, prompt only.
  - `seed`, documented as "help make results more consistent; exact reproducibility isn't guaranteed; can't be used with prompt".
  - `store_for_inpainting`, `finetune_id`, `sign_with_c2pa`.

  In v2 plans, a composition plan is a list of chunks, each with `text`, `duration_ms` (3–120 s), `positive_styles`/`negative_styles`, `context_adherence`, optional `conditioning_ref` and `condition_strength`. "For v2 models, durations are always enforced." — [ElevenLabs API reference, fetched 2026-10](https://elevenlabs.io/docs/api-reference/music/compose)
- The `/v1/music/plan` endpoint creates an editable plan and costs no credits (it is rate-limited) — [ElevenLabs composition-plan guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans)
- Music v2 was announced 2026-05-26/27. It adds section-level re-prompting "without redoing the whole song", genre switches mid-track, and inpainting with `negative_ranges`, which is Enterprise-only on the API. It is "trained on licensed material" with label partnerships, and commercial rights vary by tier — [mer.vin, 2026-05-27](https://mer.vin/2026/05/elevenlabs-music-v2-genre-switching-ai-songs-with-section-level-editing/). A Japanese write-up describes the v2 API landing in a June 2026 changelog — [Classmethod](https://dev.classmethod.jp/articles/elevenlabs-music-v2-composition-plan/)
- Stems: "you can separate generated music into stems in the download menu" in the web app. No stems parameter on the compose API was found — [ElevenLabs best practices](https://elevenlabs.io/docs/overview/capabilities/music/best-practices)

**Google Lyria**
- Lyria 3.5 was announced 2026-09-04, with model ID `lyria-3.5` for full songs and `lyria-3-clip-preview` for 30 s clips. `lyria-3-pro-preview` is deprecated. Inputs are text and image; the prompt can specify genre, instrumentation, BPM, key, mood, vocal or instrumental, structure (`[Verse]`/`[Chorus]` tags) and lyrics. Output is MP3, 44.1 kHz stereo, with a SynthID watermark. Price is $0.08 per full song ($0.04 per clip) — [aicybr guide](https://aicybr.com/blog/google-lyria-3-5-gemini-api-guide). Model-ID naming conflicts across secondary sources — [Unite.ai/pillitteri via search](https://pasqualepillitteri.it/en/news/14486/lyria-3-5-gemini-app-api-en)
- fal.ai's `google/lyria-3.5` endpoint exposes only `prompt`, `image_url` and a safety flag, with no seed, duration or audio input. It returns MP3 plus lyrics and costs $0.10 per generation — [fal llms.txt](https://fal.ai/models/google/lyria-3.5/llms.txt)
- Lyria RealTime (`lyria-realtime-exp`) is a WebSocket stream of 48 kHz 16-bit stereo PCM, steered by weighted text prompts and live config (key/scale, tempo, density, brightness). Maximum control latency is 2 s — [Gemini API model page](https://ai.google.dev/gemini-api/docs/models/lyria-realtime-exp?authuser=2), [DeepMind Lyria RealTime](https://deepmind.google/models/lyria/realtime/)

**Stability AI**
- Stable Audio 2.5 (Sept 2025) adds audio inpainting: "input their own audio, select where they want it to start." It is available via the Stability API, fal, Replicate, ComfyUI and on-premise enterprise — [Stability AI](https://stability.ai/news/stability-ai-introduces-stable-audio-25-the-first-audio-model-built-for-enterprise-sound-production-at-scale). On fal: max 190 s, 4–8 steps, a `seed` input that is echoed in the output, $0.20 per clip — [fal llms.txt](https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/llms.txt)
- Stable Audio 3.0 was announced 2026-05-20 in four sizes:

  | Variant | Size | Max length | Weights |
  |---|---|---|---|
  | Small SFX | 459M | 2 min | open |
  | Small | 459M | 2 min | open |
  | Medium | 1.4B | 6:20 | open |
  | Large | 2.7B | not stated | closed (API, fal) |

  Features: inpainting of one or several sections, causal continuation, and LoRA training for Small and Medium. It is trained "entirely on licensed data". Under the Community License users own outputs and may use them commercially below $1M annual revenue; above that, enterprise licensing applies. No melody, MIDI or stem features are mentioned — [The Decoder, 2026-05-20](https://the-decoder.com/stability-ai-launches-stable-audio-3-0-with-up-to-six-minute-tracks-and-open-weights/). The $1M threshold is confirmed by [stability.ai/license](https://stability.ai/license). One analysis claims a threshold clause was removed in a later licence revision (unverified) — [conductatlas](https://conductatlas.com/platform/stability-ai/stability-ai-model-license/commercial-licensing-revenue-threshold/)

**Meta MusicGen**
- MusicGen-melody weights are CC-BY-NC 4.0 (non-commercial) and the code is MIT. Melody conditioning comes from an audio file via chroma (`generate_with_chroma`; reported chroma cosine similarity 0.44). It uses a 32 kHz EnCodec tokenizer and was trained on about 20K hours of licensed music (Meta MI Sound Collection, Shutterstock, Pond5). No MIDI or stem conditioning — [HF model card](https://huggingface.co/facebook/musicgen-melody)

**ACE-Step 1.5 (open, MIT)**
- The licence is MIT per the GitHub repo. ComfyUI Wiki lists Apache-2.0, which conflicts; the repo is the primary source. The XL (4B DiT) series came out 2026-04-02. Tasks: Text2Music, Cover, Repaint, Extract, Lego, multi-track layering, Vocal2BGM, stem separation, audio understanding (BPM, key, time signature, caption), and LRC timestamps. Metadata control covers duration, BPM, key/scale and time signature. Length is 10 s to 10 min, lyrics in 50+ languages. Interfaces: Gradio, Python API, REST API, CLI and a VST3 plugin (separate repo) — [GitHub ace-step/ACE-Step-1.5](https://github.com/ace-step/ACE-Step-1.5). Release date conflicts: 28 Jan vs 3 Feb 2026 — [ComfyUI Wiki](https://comfyui-wiki.com/en/news/2026-01-23-ace-step-1-5-music-generation), [Gigazine](https://gigazine.net/gsc_news/en/20260204-ace-step-music-generation)
- REST API parameters:
  - `task_type`: text2music, cover, repaint, lego, extract or complete.
  - `seed`, plus `use_random_seed` (default true).
  - `repainting_start`/`repainting_end` in seconds.
  - `audio_cover_strength` from 0 to 1 ("lower values e.g. 0.2 suit style transfer").
  - `reference_audio`.
  - `bpm` (30–300), `key_scale` (e.g. "C Major", "Am") and `time_signature`. If omitted, the LM fills them in; user values take priority.
  - `inference_steps`: turbo 1–20, base 32–64 recommended.

  The docs list no allowed track names for lego or extract — [ACE-Step API.md](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/docs/en/API.md)
- Only `acestep-v15-base` supports Lego, Extract and Complete; sft and turbo do not — [HF base model card](https://huggingface.co/ACE-Step/acestep-v15-base/blob/main/README.md)
- From the technical report:
  - Cover "re-synthesizes timbre while keeping the melodic skeleton"; Repaint regenerates a segment; Layering adds complementary instruments; Completion orchestrates "a full arrangement around a single motif".
  - Conditioning is captions, timbre and lyric encoders, and source latents. No symbolic, MIDI or chord conditioning; determinism is not discussed.
  - In Music Arena, subjective quality ranks between Suno v4.5 and Suno v5. Style and lyric alignment score 39.1/26.3 vs Suno v5's 46.8/34.2, using the authors' own reward models.

  [arXiv 2602.00744](https://arxiv.org/html/2602.00744v1)
- A practitioner test (2026-05-21) called ACE-Step 1.5 the best for "research, fine-tuning, and downstream tooling" but heard "a persistent metallic shimmer". It concluded "there is not an open-source Suno yet" — [IT-JIM](https://www.it-jim.com/blog/best-open-source-ai-music-generator/)

**Other open song models (IT-JIM test, 2026-05-21; informal: 3 prompts, 1 seed each)** — [IT-JIM](https://www.it-jim.com/blog/best-open-source-ai-music-generator/)
- LeVo 2 (Tencent SongGeneration line): best audio quality ("the most natural-sounding clips of any model in our slate"), but under Tencent's non-commercial licence. About 4B parameters, VRAM tiers of 10/22/28 GB, max 4:30. Paper: [arXiv 2606.30642](https://arxiv.org/pdf/2606.30642)
- YuE: Apache-2.0, about 12x slower than real time on an RTX 4090; "did not stand out".
- DiffRhythm 2: Apache-2.0, "artificial and rhythmically unstable" ([arXiv 2510.22950](https://arxiv.org/pdf/2510.22950)). HeartMuLa: Apache-2.0, 3B, "generic and AI-blurry". Search coverage gave its paper as arXiv 2601.10547 (January 2026), not opened. Its codec (HeartCodec) is the latent space SpanSynth-Edit builds on. Muse: MIT code, Apache weights, data released; "better general quality than ACE-Step 1.5 in their cells". Khala: CC BY-NC, "unstable".
- SongBloom: requires a reference audio clip at inference; 2B parameters, 150 s max — [arXiv 2506.07634](https://arxiv.org/pdf/2506.07634) (as summarised in search). Research on finer control exists, e.g. SegTune "structured and fine-grained control" ([arXiv 2510.18416](https://arxiv.org/pdf/2510.18416)) and "MIDI-Informed Singing Accompaniment Generation" ([arXiv 2602.22029](https://arxiv.org/pdf/2602.22029)). Not read in full.

**MiniMax and Mureka**
- MiniMax Music 2.6 has an instrumental flag and a separate `music-cover` model that takes reference audio (6 s–6 min, 50 MB). It costs about $0.15 per generation on resellers; commercial terms are unclear and conflict between sources — [Scenario help](https://help.scenario.com/articles/1574698333-minimax-music-the-essentials), [Atlas Cloud](https://www.atlascloud.ai/models/minimax-music-2.6)
- Mureka: integrations list model settings V7.5–V9.5. Stem extraction and reference upload are separate features not exposed by those commands. Commercial-rights claims come only from aggregators — [VideoClaw MUREKA.md](https://cdn.jsdelivr.net/npm/videoclaw@3.0.0-alpha.15/docs/MUREKA.md), [eachlabs](https://www.eachlabs.ai/mureka/mureka/mureka-stem-song)

### Inferences
- For a pipeline where Claude writes the notes, all of these are "describe it and get audio" engines. The notes Claude wrote do not survive, apart from approximate melody retention through audio "cover" modes (Suno Covers, ACE-Step Cover, MiniMax music-cover, MusicGen chroma).
- ACE-Step 1.5 is the only option with open weights, a commercial-friendly licence, explicit BPM/key/time-signature fields, a seed, and time-range repaint, all callable over REST from Claude on AutoDL. That makes it the best neural sketch or bed generator to script. LeVo 2 may sound better but is non-commercial.
- Suno and Udio carry legal risk as of October 2026: Sony/UMG litigation is active against v6, the GEMA ruling stands, and Udio cannot export. Downloads are also capped. They are the weakest base for a release pipeline even before controllability is considered.

### Gaps
- Suno v6's own controls (BPM/key fields, audio-upload limits, stem count, MIDI export fidelity) and current output-ownership terms: Suno pages and MBW returned 403 errors; only secondary coverage was available.
- Lyria 3.5 commercial and ownership terms, and whether a seed is exposed in the native Gemini API (fal exposes none).
- ByteDance Seed-Music and any 2026 ByteDance or Tencent API product: no 2026 source found.
- No head-to-head blind listening test of instrumental-only output (as opposed to songs) across Suno v6, ElevenLabs v2.5, Lyria 3.5 and Stable Audio 3.0 was found.

## 2. MIDI/score-conditioned neural rendering (MIDI to realistic audio)

### Takeaway
True MIDI-to-audio neural renderers exist mainly as research models in 2025–2026, plus one commercial product for monophonic solo lines (ACE Studio 2 AI Instruments). The research models are SpanSynth-Edit (QMUL, Sept 2026, checkpoints released), P-MUSE (Aug 2026), TokenSynth (2025, code and weights), MIAO, MIDI-VALLE (piano) and a MIDI-to-drums model. They follow MIDI far better than text-to-music, but note adherence is measured statistically (onset F1), not guaranteed. None has been shown to beat a good sample library for piano, strings or guitar in a published comparison.

### Cited Findings
- **SpanSynth-Edit** (Chang, Bhandari, Dixon, Benetos; QMUL; arXiv 2609.25546, submitted 2026-09-22):
  - Flow-matching DiT (480.8M parameters) on frozen HeartCodec latents. "MIDI Span" conditioning encodes each instrument-labelled note's lifecycle per frame, and surrounding audio is used as timbre context.
  - Trained on 660 h of paired performance MIDI and audio from 17 datasets (piano, guitar, bass, drums, strings, wind, orchestral). Generates the mixture jointly, not stems.
  - Editing re-synthesises a selected region from revised MIDI using the surrounding audio. Tested edits: add an instrument, insert or delete notes, delete a track. Kept notes are measured by F_keep.
  - Slakh+drums synthesis FAD is 1.33, vs 4.85 for SpecDiff and 4.16 for U-MusT. On MAESTRO it does not lead: MIDI-VALLE has higher PQ, and U-MusT has lower FAD (2.59 vs 2.89).
  - Note adherence: onset F1 is higher on several datasets, but on Slakh it trails SpecDiff on 37-class instrument-labelled F.
  - No comparison with FluidSynth or sample libraries; a Salamander SoundFont was used only to render POP909 test inputs.
  - Inference: 32 Euler steps, 0.93 s per 20.48 s of audio on a GH200 in BF16, with 3.37 GiB peak memory. "Model demo, checkpoints, data, and benchmark samples are available" at the project page.

  [arXiv HTML](https://arxiv.org/html/2609.25546v1)
- **P-MUSE** (Jing et al.; arXiv 2608.01920, 2026-08-03): a MIDI-to-music model that renders a target MIDI sequence "while cloning instrument timbre from a prompt recording". Prompt MIDI is optional. Generation and local editing share a fill-in-the-middle formulation. Instruments: piano, guitar, bass, drums. The abstract gives no metrics; the code and weights release is unstated (demo at p-muse.github.io) — [arXiv](https://arxiv.org/abs/2608.01920)
- **TokenSynth** (Kim et al.; arXiv 2502.08939, 2025-02-13): given about 5 s of single-instrument reference audio and arbitrary MIDI, it "generates output audio that plays given MIDI notes with the timbre of given reference audio". Polyphonic and zero-shot, with text-to-instrument as well. A decoder-only transformer predicts DAC tokens. Code, weights and demos are on GitHub (KyungsuKim42/tokensynth) — [arXiv](https://arxiv.org/html/2502.08939v1)
- **MIAO** (Scientific Reports, 2025): a multi-instrument MIDI-to-audio synthesiser reporting 33% lower FAD than MIDI-DDSP on Slakh2100 — [Nature Sci Rep](https://www.nature.com/articles/s41598-025-17410-6)
- **MIDI-VALLE** (ISMIR 2025): expressive piano synthesis with a VALL-E-style codec LM, reporting over 75% lower FAD than a state-of-the-art baseline on ATEPP and MAESTRO. Piano only — [ISMIR 2025 poster](https://ismir2025program.ismir.net/poster_208.html)
- **Break-the-Beat!** (arXiv 2605.14555, May 2026): controllable MIDI-to-drum audio synthesis — [arXiv PDF](https://arxiv.org/pdf/2605.14555). Not read beyond the title.
- **CoSaRef** (arXiv 2410.16785): annotation-free MIDI-to-audio that "first generates a synthetic audio track using concatenative synthesis based on MIDI input, then refines it with a diffusion-based deep generative model" — [arXiv](https://arxiv.org/html/2410.16785v2)
- Multi-aspect conditioning for diffusion-based music synthesis renders symbolic input with chosen acoustic conditions, trained on MIDI-aligned scores and automatic multi-instrument transcription — [project page](https://benadar293.github.io/multi-aspect-conditioning/)
- **MIDI-DDSP** (pre-2025): a hierarchical model for "detailed control of musical performance" — [project page](https://midi-ddsp.github.io/)
- **ACE Studio 2 AI Instruments** (Sound on Sound review, March 2026):
  - Voicebanks are built from real performances. The engine adds human-style expression and auto-assigns articulation changes from the MIDI.
  - The initial set is "non-chordal options such as violin, cello, trumpet or saxophone". The reviewer had "plenty of success" with usable strings and brass via a Vocal-to-MIDI then AI Instrument workflow.
  - DAW integration is via the ACE Bridge 2 plugin or ARA, with no third-party VST/AU in its canvas. Price: perpetual Artist $497, Artist Pro $660.
  - Not covered by the review: determinism, stem export, an API.

  [SOS](https://soundonsound.com/reviews/ace-studio-2). A KVR user said the violin "sounds more authentic than large sample libraries with articulations" (anecdotal) — [KVR thread](https://www.kvraudio.com/forum/viewtopic.php?p=9210718). The instrument count conflicts: "over 40" per [MIDI.org](https://midi.org/?p=7324) vs "fairly limited" per [RouteNote](https://create.routenote.com/blog/ace-studio-2-0-ai-music-tool/)
- **Magenta RealTime 2** (released 2026-06-04): MIDI notes steer pitch and harmony, while text and audio prompts steer style. Note control was trained on audio–MIDI pairs whose MIDI labels were inferred by MT3. There are two note modes (the model chooses attacks from held notes, or the user supplies onsets) and a drums on/off switch — [mcp.directory guide](https://mcp.directory/blog/magenta-realtime-2-open-live-music-model-2026), [IT之家 2026-06-05](https://www.ithome.com/0/960/419.htm). Sizes are 230M and 2.4B. Weights are CC BY 4.0, code Apache-2.0. MIDI is injected every 40 ms frame. Real-time runs only on Apple Silicon via MLX; offline inference runs on NVIDIA through Python. Described as "not batch track rendering" — [mer.vin, 2026-06-05](https://mer.vin/2026/06/magenta-realtime-2-open-local-live-music-model-with-midi-and-200ms-latency/), [GitHub magenta-realtime](https://github.com/magenta/magenta-realtime)
- Practitioner view (VI-Control thread, date not retrieved): an orchestral composer used Suno as a "render engine" for their own MIDI. A reply said "ACE works on rendering MIDI performances with AI into convincing soloists", and that polishing a rough full-score MIDI rendition is "not yet something the tools fully do" — [VI-Control](https://vi-control.net/community/threads/using-ai-assisted-production-for-original-compositions-as-an-entry-level-composer.169841/). The page returned 403; the quotes come from the search snippet.

### Inferences
- **Per-instrument, note-faithful rendering** is possible in principle with TokenSynth (single-instrument timbre clone, weights available) and ACE Studio AI Instruments (monophonic solo strings, brass and winds). Each track is rendered separately, so a one-note edit only re-renders that track. This is the closest neural match to the user's requirement.
- **Mixture renderers** (SpanSynth-Edit, P-MUSE, Magenta RT 2) render the whole mix at once. Editing one instrument re-synthesises a region of the mix, so other instruments in that region may change slightly; F_keep is below 1 by construction of the metric. They also produce no stems for later mixing.
- For piano, sample libraries remain the safe default (MIDI-VALLE and SpanSynth-Edit show neural piano can be strong, but there is no head-to-head with commercial libraries). For solo legato strings and winds, neural rendering (ACE Studio) is the area where practitioners report it beating samples. No 2025–2026 source rated neural guitar rendering as release-quality.

### Gaps
- No published listening test comparing any neural MIDI renderer against commercial sample libraries (e.g. Spitfire, Kontakt strings, Pianoteq) was found.
- Whether ACE Studio exposes any scripting or API, and whether re-rendering the same MIDI is bit-identical: not covered by the review.
- Licences for SpanSynth-Edit checkpoints and the TokenSynth code: not stated in the material read.
- Independent evaluation of how exactly Magenta RT 2 follows pianoroll input: none found.

## 3. Stem-level editing, inpainting, audio-to-audio and timbre transfer

### Takeaway
"Add a track that fits" exists in ACE-Step 1.5 (Lego and Layering, base model only), Suno Studio and v6, and Stable Audio inpainting by region. Time-range inpainting exists in ACE-Step (Repaint), Stable Audio 2.5/3.0, ElevenLabs v2 (Enterprise API) and Suno v6 ("partial song editing"). All of these work at audio-region or section granularity, steered by text; none at note granularity. Timbre transfer (RAVE/Neutone, DDSP) keeps the input's pitch and timing per track. It can therefore replace one instrument's sound while keeping its notes, if that instrument is available as an isolated stem, but quality is generally below sample libraries.

### Cited Findings
- ACE-Step 1.5: Repaint (`repainting_start`/`end`), Cover (`audio_cover_strength`), Lego, Extract and Complete (base model only), reference audio, and track separation — [API.md](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/docs/en/API.md), [HF base card](https://huggingface.co/ACE-Step/acestep-v15-base/blob/main/README.md). Editing training used 6M stem-separated tracks — [arXiv 2602.00744](https://arxiv.org/html/2602.00744v1). fal hosts ACE-Step remix, inpaint and outpaint endpoints — [fal](https://fal.ai/explore/text-to-music-apis)
- Stable Audio 3.0: inpainting of individual or several sections, plus continuation — [The Decoder](https://the-decoder.com/stability-ai-launches-stable-audio-3-0-with-up-to-six-minute-tracks-and-open-weights/). Stable Audio 2.5: inpainting from user audio — [Stability AI](https://stability.ai/news/stability-ai-introduces-stable-audio-25-the-first-audio-model-built-for-enterprise-sound-production-at-scale)
- ElevenLabs v2: re-prompting a single section leaves the other sections unchanged; API inpainting is Enterprise-only — [mer.vin](https://mer.vin/2026/05/elevenlabs-music-v2-genre-switching-ai-songs-with-section-level-editing/). There is also a `music.upload` method for later inpainting that can extract a composition plan from uploaded audio (Enterprise) — [ElevenLabs music skill page](https://mcpservers.org/de/agent-skills/elevenlabs/music)
- Suno Studio 2.0: stem split (Split from Mix, Advanced Split), chat-driven instrument creation, and multitrack and stem export — [Dubspot](https://blog.dubspot.com/suno-studio-2-0). Suno v6: partial song editing and audio isolation — [TNW](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models)
- Neutone Morpho (v1.1.4 manual, 2026-06-24) "resynthesises input audio into the timbre of pre-trained machine-learning models while preserving the input's temporal shape", for example flute to violin. The Neutone library includes RAVE models such as "RAVE.violin" and "RAVE.drumkit". The Neutone SDK is open source. Other RAVE-based tools include Scyclone and SEMILLA V2 (VST3, 2026-07-13, loads RAVE .ts models) — [Neutone Morpho manual](https://neutone.supabase.co/storage/v1/object/public/morpho-public/manual/2026-06-25_NeutoneMorpho_Manual.pdf), [Qosmo](https://qosmo.jp/en/products/timbre-transfer/), [SonicField](https://sonicfield.org/semilla-v2-neural-audio-instrument)
- A 2026 PMLR paper covers a "Neural Codec Language Model for Controllable Timbre Transfer in Music Synthesis" — [PMLR v303](https://proceedings.mlr.press/v303/liu26b.html). Not read.

### Inferences
- **Replacing one instrument while keeping its notes:** the reliable route is per-track. Render or record that track alone, then apply timbre transfer (RAVE/Neutone, or a DDSP-type model like the user's DDSP-SVC trained on an instrument dataset). Alternatively, re-render that track's MIDI through TokenSynth or ACE Studio. Doing it inside a mixed neural output needs separation first, and separation artefacts compound.
- Region inpainting (ACE-Step Repaint, Stable Audio, ElevenLabs) is suitable for fixing a bad bar in a neural bed. It cannot target "the oboe in bar 12, note 3".

### Gaps
- No 2025–2026 evaluation was found of polyphonic timbre transfer (e.g. guitar chords to strings) quality, or of the determinism of RAVE-based plugins.
- How well Suno Studio's audio-to-MIDI and ACE-Step's Extract perform on dense orchestral mixes: no measurements found.

## 4. MCP servers and API wrappers Claude can call

### Takeaway
Official routes: the ElevenLabs MCP server (`compose_music` and `create_composition_plan`) and REST APIs for ElevenLabs, Gemini (Lyria 3.5, Lyria RealTime), Stability, and fal.ai, which hosts ACE-Step, MiniMax, Stable Audio 2.5 and Lyria 2/3.5. ACE-Step 1.5 ships its own REST API, so it can be self-hosted on AutoDL and called from Claude over HTTP or SSH. Suno has only unofficial MCPs that rely on resellers or scraping, with terms-of-service and breakage risk.

### Cited Findings
- The official ElevenLabs MCP (github.com/elevenlabs/elevenlabs-mcp, run via `uvx elevenlabs-mcp`, stdio) has a `compose_music` tool (prompt or composition plan, which saves the audio file) and `create_composition_plan`. Every call spends credits — [Docker Hub mcp/elevenlabs](https://hub.docker.com/r/mcp/elevenlabs), [mcp.directory guide, June 2026](https://mcp.directory/blog/elevenlabs-mcp-complete-guide-2026)
- fal endpoints:
  - `fal-ai/ace-step/prompt-to-audio`, plus remix, inpaint and outpaint (about $0.012 per 60 s per one aggregator).
  - `fal-ai/minimax-music/v2.6` (about $0.15).
  - `fal-ai/stable-audio-25/text-to-audio` ($0.20, 190 s max).
  - `fal-ai/lyria2` ($0.10 per 30 s).
  - `google/lyria-3.5` ($0.10).

  Prices and names vary across fal pages — [fal text-to-music APIs](https://fal.ai/explore/text-to-music-apis), [fal Lyria 3.5 llms.txt](https://fal.ai/models/google/lyria-3.5/llms.txt), [fal Stable Audio 2.5 llms.txt](https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/llms.txt), [TanStack AI audio docs](https://tanstack.com/ai/latest/docs/media/audio-generation)
- Lyria 3.5 is reachable through the Gemini API (generateContent and the Interactions API) with a standard API key — [aicybr](https://aicybr.com/blog/google-lyria-3-5-gemini-api-guide), [LiteLLM Gemini music docs](https://docs.litellm.ai/docs/providers/gemini/music.md)
- ACE-Step 1.5 provides a REST API (async HTTP), Python API, CLI and Gradio — [GitHub](https://github.com/ace-step/ACE-Step-1.5)
- Suno MCPs: CodeKeanu/suno-mcp (via sunoapi.org), AceDataCloud mcp-suno (hosted MCP), runapi.ai suno-mcp (npm), and a PyPI browser-automation MCP that uses internal endpoints and "may break" — [GitHub](https://github.com/CodeKeanu/suno-mcp), [Socket npm](https://socket.dev/npm/package/@runapi.ai/suno-mcp), [Socket PyPI](https://socket.dev/pypi/package/mcp-suno)
- Symbolic side, for contrast: DAW-control MCPs such as "Ableton MCP Extended" exist — [glama listing](https://glama.ai/mcp/servers/uisato/ableton-mcp-extended). Not evaluated here.

### Inferences
- For automation from Claude Code on Windows, the lowest-risk neural calls are ElevenLabs (official MCP), fal (one key, many models) and a self-hosted ACE-Step REST server on AutoDL. Suno MCPs should be avoided for anything that will be released.

### Gaps
- Whether the ElevenLabs MCP exposes `seed`, the v2/v2.5 model IDs, or inpainting: tool schemas were not read.

## 5. Hybrid workflows used in practice (2025–2026)

### Takeaway
Two hybrids recur. (1) Neural first: generate with Suno or ACE-Step, split stems, transcribe to MIDI (Suno Studio audio-to-MIDI, YourMT3+, MuScriptor), then edit. Transcription accuracy collapses as polyphony grows, so the MIDI needs heavy manual cleanup. (2) Symbolic first: compose in MIDI, render with samples, then pass through a neural "cover" or "refine" step for realism. This is done ad hoc (Suno Covers, ACE-Step Cover, CoSaRef in research), but it does not preserve the notes exactly.

### Cited Findings
- Suno Studio 2.0 audio-to-MIDI (drag audio onto a MIDI track) and stem export — [Dubspot](https://blog.dubspot.com/suno-studio-2-0). Guides also describe exporting Suno stems to a DAW and transcribing them — [Songscription blog](https://www.songscription.ai/blog/get-stems-from-a-suno-song), [Dubspot DAW guide](https://blog.dubspot.com/export-ai-stems-to-your-daw-2026)
- YourMT3+ (2024): a multi-instrument transcriber (MoE transformer) competitive on 10 public datasets, but "further testing on pop music recordings highlights the limitations of current models" — [arXiv 2407.04822](https://arxiv.org/pdf/2407.04822)
- 2025 AMT Challenge: going from 1 to 3 instruments, the F-measure dropped by more than 0.28 (MIROS) and 0.36 (YourMT3-YPTF-MoE-M). "Polyphonic transcription [is] the primary challenge" — [arXiv 2603.27528](https://arxiv.org/pdf/2603.27528)
- MuScriptor (Rouard, Krause, Roebel, Simon-Gabriel, Défossez; ISMIR 2026; arXiv 2607.08168, July/Aug 2026): an "open-weight multi-instrument music transcription model" for real recordings, with instrument-presence conditioning. The abstract gives no baseline numbers — [arXiv](https://arxiv.org/abs/2607.08168)
- Symbolic-first render then AI: the VI-Control practitioner used Suno as a "render engine" for their own MIDI. Replies said a full-score polish is "not yet" done well, while ACE Studio handles soloists — [VI-Control](https://vi-control.net/community/threads/using-ai-assisted-production-for-original-compositions-as-an-entry-level-composer.169841/) (snippet only). ACE-Step's `audio_cover_strength` (low ≈ style transfer) is the open-model knob for this — [API.md](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/docs/en/API.md). CoSaRef formalises "concatenative or sample render, then diffusion refinement" — [arXiv 2410.16785](https://arxiv.org/html/2410.16785v2)
- The ACE Studio "scratch-sing, Vocal-to-MIDI, AI Instrument" workflow gave usable strings and brass — [SOS](https://soundonsound.com/reviews/ace-studio-2)

### Inferences
- For this user, neural-first then transcription is the wrong direction. It converts Claude's exact intent into lossy audio and back into lossy MIDI. Use neural generation only to audition ideas, then re-write the idea as MIDI by hand or with Claude, using transcription as a rough guide.
- Symbolic-first then neural polish is viable only as a final, optional "print" stage on stems that are already approved. Keep the sample-rendered version as the master, and accept the neural pass only where it preserves the notes, checked by transcribing the output and diffing it against the source MIDI.

### Gaps
- No quantitative report was found of how often Suno, ACE-Step or MiniMax covers change pitches or rhythms when fed a sample-library render.
- No Reddit thread with concrete settings for MIDI-render-to-AI-cover was retrieved; searches surfaced only the VI-Control thread.

## 6. Open models on a single rented GPU (AutoDL, RTX 4090/A100 class) and run times

### Takeaway
ACE-Step 1.5 is fast enough for an interactive loop: about 1–2 s per full song on an A100, under 10 s on an RTX 3090, and under 4 GB VRAM for small configurations. The XL model needs 20 GB or more without offload, which fits a 24 GB 4090. SpanSynth-Edit is light (about 3.4 GiB, faster than real time). Stable Audio 3.0 Small and Medium are near-instant. YuE is impractically slow (about 12x real time). LeVo 2's top tier needs about 28 GB, more than a 4090 has.

### Cited Findings
- ACE-Step 1.5: under 2 s per song on an A100 and under 10 s on an RTX 3090. About 1 s for a 240 s track on an A100 with 8 distilled steps and no CFG. Under 4 GB VRAM for small configurations; entry tier ≤6 GB (2B turbo, INT8, CPU offload); XL needs ≥12 GB with offload or ≥20 GB without. LoRA: "8 songs, 1 hour on 3090 (12GB VRAM)" — [GitHub](https://github.com/ace-step/ACE-Step-1.5), [arXiv 2602.00744](https://arxiv.org/html/2602.00744v1). No RTX 4090 figure was published.
- SpanSynth-Edit: 0.93 s per 20.48 s of audio, 3.37 GiB peak, on a GH200 in BF16 — [arXiv 2609.25546](https://arxiv.org/html/2609.25546v1)
- Stable Audio 3.0: Small and Small SFX take 0.44 s for a 2-minute track on an H200; Medium takes 1.31 s per track (hardware unstated). Small and Medium weights are open — [The Decoder](https://the-decoder.com/stability-ai-launches-stable-audio-3-0-with-up-to-six-minute-tracks-and-open-weights/)
- YuE: about 12x slower than real time on an RTX 4090. LeVo 2: VRAM tiers of 10, 22 and 28 GB — [IT-JIM](https://www.it-jim.com/blog/best-open-source-ai-music-generator/)
- Magenta RT 2: offline inference on NVIDIA through the Python path; real-time only on Apple Silicon — [mer.vin](https://mer.vin/2026/06/magenta-realtime-2-open-local-live-music-model-with-midi-and-200ms-latency/)

### Inferences
- On an AutoDL 4090 (24 GB): ACE-Step 1.5 (including XL), SpanSynth-Edit, TokenSynth, Stable Audio 3.0 Medium and LeVo 2's lower tiers should all fit. A 3-minute YuE song would take about 36 minutes (12x real time).
- ACE-Step's REST server can run beside the existing DDSP-SVC/RIFT-SVC jobs on the same AutoDL instance. The user's memory notes that the runner hard-resets the AutoDL repo to GitHub master, so model servers should live outside that repo.

### Gaps
- No measured 4090 timings for ACE-Step XL, TokenSynth, P-MUSE or LeVo 2.
- No Windows-native run reports were checked. AMD published an ACE-Step 1.5 blog for Ryzen AI and Radeon — [AMD](https://www.amd.com/en/blogs/2026/commercial-grade-ai-music-generation-on-amd-ryzen-ai-and-radeon-ace-step-1-5.html) — but it was not read.

## 7. Note-level control (coordinator requirement): exact MIDI, local edit, fixed-seed reproducibility

### Takeaway
No text-to-music or song model passes the user's three tests. They cannot honour a given score note-for-note, cannot re-render one note or one instrument in isolation, and are at best "more consistent" with a seed. These should be marked inspiration/reference only, or for post-processing on finished stems. Only per-track MIDI-to-audio renderers come close: ACE Studio AI Instruments (commercial, monophonic), TokenSynth (research, weights out), and with caveats SpanSynth-Edit and P-MUSE (mixture-level, research). Timbre transfer on an isolated track also qualifies as a post-process. Even these follow MIDI statistically, not exactly, so the MIDI + sample-library pipeline remains the master for exact note control.

### Cited Findings
- ElevenLabs `seed`: "help make results more consistent. Exact reproducibility isn't guaranteed"; only usable with `composition_plan` — [ElevenLabs API](https://elevenlabs.io/docs/api-reference/music/compose)
- ACE-Step: `seed` with `use_random_seed=false`. Repaint takes a time range. No MIDI or chord conditioning; determinism is not discussed in the paper — [API.md](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/docs/en/API.md), [arXiv 2602.00744](https://arxiv.org/html/2602.00744v1)
- Stable Audio 2.5 on fal accepts a `seed` and returns it — [fal](https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/llms.txt). Lyria 3.5 on fal exposes no seed — [fal](https://fal.ai/models/google/lyria-3.5/llms.txt)
- Suno Studio MIDI tracks play a built-in wavetable synth (not the generative model), and new generations "can sit slightly ahead of or behind the beat" — [Dubspot](https://blog.dubspot.com/suno-studio-2-0)
- SpanSynth-Edit measures note adherence (onset F1, instrument-labelled F) and kept-note preservation (F_keep) rather than guaranteeing them; it trails SpecDiff on 37-class instrument F on Slakh — [arXiv 2609.25546](https://arxiv.org/html/2609.25546v1)
- Magenta RT 2 note control was learnt from MT3-inferred labels — [mcp.directory](https://mcp.directory/blog/magenta-realtime-2-open-live-music-model-2026)
- TokenSynth "plays given MIDI notes with the timbre of given reference audio" per single instrument — [arXiv 2502.08939](https://arxiv.org/html/2502.08939v1). ACE Studio renders AI instruments from MIDI, one instrument per track — [SOS](https://soundonsound.com/reviews/ace-studio-2)
- Neutone/RAVE timbre transfer preserves "the input's temporal shape" — [Neutone Morpho manual](https://neutone.supabase.co/storage/v1/object/public/morpho-public/manual/2026-06-25_NeutoneMorpho_Manual.pdf)

### Inferences (verdict matrix)
(a) = exact MIDI note-for-note, per instrument. (b) = local edit of one note, bar or instrument without changing the rest. (c) = fixed-seed reproducibility. "Unverified" means no source tested it.

| Option | (a) Exact MIDI, per instrument | (b) Local edit isolated | (c) Fixed seed | Use for this user |
|---|---|---|---|---|
| Suno v5.5/v6 + Studio 2.0 | No. Text, audio or image prompts only; Covers keep the melody approximately; Studio MIDI drives a plain synth, not the model | Region or section regenerate ("partial song editing"); not note- or instrument-level | No seed exposed (no official API) | **Inspiration/reference only.** Stems for reference listening. Legal risk (Sony/UMG suit, GEMA) |
| Udio | No | Not exportable | No | **Not usable** (downloads off since Oct 2025) |
| ElevenLabs Music v2/v2.5 | No (text plus section plan with durations) | Section re-prompt; inpainting Enterprise-only; section granularity | Seed only with composition plan; "not guaranteed" | **Inspiration/reference**, or section-timed beds |
| Google Lyria 3.5 | No (text and image) | No editing documented | No seed on fal; native API unverified | **Inspiration only** |
| Lyria RealTime / Magenta RT 2 | Partial. MRT2 pianoroll steers pitch and harmony, but labels came from MT3, it outputs a mixture, and it is not per-instrument | No (streaming jam model) | Unverified | **Sketch/inspiration** (live jamming). Not for final renders |
| Stable Audio 2.5 / 3.0 | No | Time-range inpainting, region-level | Seed accepted (2.5 via fal); bit-exactness unverified | **Post-processing / SFX / texture beds** |
| MusicGen-melody | No (chroma contour from audio) | No | Local torch seed (unverified) | **Inspiration only**; weights non-commercial |
| ACE-Step 1.5 | No (no symbolic input; Cover keeps the "melodic skeleton" from audio) | Repaint by time range; Lego adds a track (base model); region and track granularity, not note-level | `seed` parameter; local determinism plausible, unverified | **Inspiration, accompaniment beds, optional neural "cover" polish** of approved stems (verify notes by transcription) |
| LeVo 2, YuE, DiffRhythm 2, HeartMuLa, SongBloom, Muse | No | No or limited | Local seed (unverified) | **Inspiration only**; LeVo 2 and Khala non-commercial |
| MiniMax 2.6, Mureka | No (music-cover is audio-referenced) | No | Unverified | **Inspiration only** |
| SpanSynth-Edit (research) | Mostly. Instrument-labelled MIDI in; adherence high but not exact; outputs a mixture, not stems | Region re-render from revised MIDI with context; kept notes measured, F_keep < 1 | Not discussed | **Experimental renderer**. Worth an AutoDL trial; not a replacement for samples yet |
| P-MUSE (research) | Designed to follow target MIDI; piano, guitar, bass, drums; timbre from a prompt | Fill-in-the-middle local editing | Not stated | **Experimental**; code availability unknown |
| TokenSynth (research) | Per single instrument: plays the given MIDI in a cloned timbre | Per-track re-render, so the rest is untouched | Unverified | **Experimental per-track renderer**. Closest neural fit to "edit any note or instrument" |
| ACE Studio 2 AI Instruments | Per monophonic instrument from MIDI (violin, cello, trumpet, sax…); auto articulation | Per-track; edit the MIDI and re-render the track | Not covered | **Usable for final solo lines** (strings, brass, winds) beside samples; no API found, so not Claude-automatable |
| RAVE/Neutone/DDSP timbre transfer | Keeps the input track's pitch and timing, so notes come from your render | Per-track | RAVE sampling may be stochastic (unverified) | **Post-processing** of individual stems |
| Transcription (YourMT3+, MuScriptor, Suno audio-to-MIDI) | Not a renderer; accuracy drops sharply with polyphony | n/a | Deterministic inference likely (unverified) | **Reference extraction only**; never the master MIDI |

- Bottom line for the pipeline:
  - Claude writes MIDI and renders it with samples. That stays the master, because it is the only path that is exact, local and reproducible.
  - Neural models sit around it: idea generation (ACE-Step, ElevenLabs, Lyria), per-track realism upgrades for monophonic solo lines (ACE Studio, TokenSynth, timbre transfer, or DDSP-SVC-style models trained on instruments), and optional final polish.
  - Every neural pass is checked by transcribing its output and diffing it against the source MIDI.

### Gaps
- No vendor documents bit-exact reproducibility. Whether ACE-Step, Stable Audio or TokenSynth give identical output for a fixed seed across GPUs or library versions is untested here, and would need a quick AutoDL test (same seed, two runs, compare waveform hashes).
- No source measured whether ACE Studio re-renders unchanged notes identically after an edit elsewhere in the same track.
