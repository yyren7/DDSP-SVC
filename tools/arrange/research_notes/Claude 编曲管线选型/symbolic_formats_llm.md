# Symbolic music representations, libraries and evidence for LLM (Claude) composition — as of 2026-10-28

Scope note: everything below was collected on 2026-10-28. Library versions and release dates come from live PyPI / npm registry queries on that day. Results from before 2025 are flagged **[pre-2025, possibly outdated]**, because the models they tested (GPT-4, LLaMA-2 and similar) are well behind current frontier models. Measurements I ran myself in this session are labelled **(local probe)**. The probe scripts are in [probes/](probes/) (`m21probe.py`, `probe2.py`, outputs in `probe_out/`).

---

## 1. Representations: which text/code formats can an LLM write directly, and which are token-efficient, least error-prone, and expressive enough for many tracks, articulations, dynamics, CC, tempo and keyswitches?

### Takeaway
No published study compares formats for *frontier chat LLMs* (Claude, GPT, Gemini) writing multi-track music. The evidence that does exist points one way: compact text notations (ABC) are the most token-efficient, but they are fragile for multi-track timing because note onsets are implicit. Score formats (MusicXML) carry the most notational meaning, but they are far too verbose to write by hand. Grammars with explicit per-note onsets (bar, slot, duration) are what the one Claude-specific agent paper (Libretto, Opus 4.8) chose. For a Claude Code workflow, the best fit is a compact **explicit-onset event format or Python data structure as the authored source**, with MIDI (for expression and CC) and MusicXML (for score) compiled from it.

### Cited Findings
**Token efficiency and sequence length**
- ChatMusician (Feb 2024) reports that ABC averaged **288.21 tokens per song, about 38% of MIDI-based representations**, and credits ABC's repeat markers for this **[pre-2025]** — [ChatMusician, arXiv 2402.16153](https://arxiv.org/html/2402.16153v1); [ACL Findings 2024](https://aclanthology.org/2024.findings-acl.373.pdf)
- The 2026 JKU Linz study picked ABC because "its compact structure and broad public corpus availability simplify tokenization and training compared with the more verbose **kern or XML-based encodings." It also notes that in symbolic music "small local errors can invalidate entire sequences" (arXiv 2601.22764, 30 Jan 2026) — [How Far Can Pretrained LLMs Go in Symbolic Music?](https://arxiv.org/pdf/2601.22764)
- Libretto (June 2026), an agent grammar used with Claude Code + Opus 4.8, "uses more characters than ABC, but avoids the duration accumulation needed to recover note starts and prevents duration edits from shifting downstream onsets." In ABC, "note starts must be recovered by accumulating earlier durations in the bar," whereas in Libretto "each note directly carries its absolute onset slot" — [Libretto, arXiv 2606.22708](https://arxiv.org/abs/2606.22708) (PDF text)

**Multi-track problems in ABC**
- MuPT (ICLR 2025) states that typical ABC writes each track sequentially, "which makes multi-track ABC somehow incompatible with LLMs on next token prediction." It introduces **SMT-ABC (synchronized multi-track ABC)**, which interleaves the tracks bar by bar — [MuPT, ICLR 2025 (QMUL repository PDF)](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/106408/Ma%20MuPT:%20A%20Generative%202025%20Accepted.pdf?sequence=2&isAllowed=y); Libretto also notes that MuPT's "synchronized multi-track ABC [was introduced] to improve bar alignment across" tracks — [Libretto](https://arxiv.org/pdf/2606.22708)
- ABC cannot express continuous pitch glides and microtonal inflections, for example raga *meend* (June 2026) — [Exploring LLMs for South Asian Music, arXiv 2606.05522](https://arxiv.org/html/2606.05522v1)
- Verovio's ABC importer does **not support tuplets, user-defined symbols or multi-voice music** — [Verovio input formats](https://book.verovio.org/toolkit-reference/input-formats.html)

**MIDI as an authored format**
- ChatMusician and MuPT both argue that MIDI's performance-timing detail causes "quantization errors and unstable rhythms when being tokenized" **[pre-2025 / early 2025]** — [ChatMusician](https://arxiv.org/pdf/2402.16153); [MuPT](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/106408/Ma%20MuPT:%20A%20Generative%202025%20Accepted.pdf?sequence=2&isAllowed=y)
- LilyBench (June 2026) describes MIDI as performance-oriented, exposing "neither score structure nor variable reuse," and calls LilyPond a "richer score language closer to code that fits full-score generation and structural reasoning" — [LilyBench, arXiv 2606.08722](https://arxiv.org/html/2606.08722)

**MusicXML (score semantics) vs MIDI vs ABC for trained models (25 Oct 2026)**
- MxlTok, a MusicXML tokeniser with about 750 base tokens (vs 200–400 for typical MIDI tokenisers), was tested across 26 small models trained from scratch on PDMX. On generation, the objective JS score was **89.2 for MxlTok-PF, 79.4 for REMI+ and 56.0 for ABC**. In a 16-participant human study (960 judgments), **ABC ranked lowest** and MusicXML part-first ranked highest for overall preference. When the scores were first converted to MIDI, the advantage disappeared: "the advantage of MusicXML lies in the notational content lost upon conversion to MIDI." **Frontier LLMs were not tested** — [Does Notation Matter? arXiv 2610.34247](https://arxiv.org/html/2610.34247)

**LilyPond as an authored format (open models only, June 2026)**
- Zero-shot compile rates were 48.6–79.3% (Codestral-22B best). Few-shot prompting *lowered* them to 19.9–45.2%. Hand-written in-key examples raised them to **97.1–99.9%**. Phi-4, Qwen2.5-Coder-14B, DeepSeek-Coder-V2-Lite and Codestral-22B were tested; no Claude, GPT or Gemini — [LilyBench](https://arxiv.org/html/2606.08722)

**Libretto grammar (the one format designed for and tested with Claude)**
- The format is a header (KEY, METER, TEMPO, GRID, BARS), then a VOICES line, then one block per bar with a required chord label. Notes are written `pitch@onsetSlot>durationSlots` and chords are joined with `+`, e.g. `BASS : G1@1>2 G1@4>1 Bb1@7>1`. It uses integer slots on a 16th grid (beats at 1, 5, 9, 13) and adaptive or triplet grids. It "deliberately abstracts away velocity, micro-timing, original timbre, and unpitched percussion." A 96-bar funk example has five voices: BASS, GTR, KEYS, HORNS, LEAD — [Libretto PDF, Methods + App. A](https://arxiv.org/pdf/2606.22708)

**Live-coding languages (Strudel)**
- Boogiebench (HN, about Dec 2025 – Jan 2026) has LLMs write Strudel pieces ranked by user-vote ELO. Its author reports: "Models often struggle but are rapidly improving," and "The Anthropic models seem to underperform other model families relative what we'd expect" (Claude Opus and GPT-5.2 named) — [Boogiebench on HN](https://news.ycombinator.com/item?id=46437861)
- A June 2025 blog found that Claude's Strudel code "had hallucinated some sample filenames that don't actually exist" but was "a great start" — [thoughtwax, Live-coding music with AI](https://thoughtwax.com/2025/06/live-coding/)
- HN commenters report that the best LLMs produce syntactically valid Strudel but do not grasp the semantics of the mini-notation; another calls AI-generated Strudel "garbage" (search-snippet attribution; the exact thread among these was not verified) — [HN 45577498](https://news.ycombinator.com/item?id=45577498); [HN 46052478](https://news.ycombinator.com/item?id=46052478)

**Expressivity of the MIDI layer (verified locally)**
- pretty_midi 0.2.11.post0's `Instrument` objects hold `notes`, `pitch_bends`, `control_changes`, `program` and `is_drum`. `PrettyMIDI` exposes `get_tempo_changes`, `time_signature_changes`, `key_signature_changes`, `lyrics`, `get_piano_roll`, `adjust_times`, `synthesize`/`fluidsynth`, `get_beats`/`get_downbeats` **(local probe)**; landing-page docs — [pretty_midi docs](https://craffel.github.io/pretty-midi/)

### Inferences
- **(local probe) Size of the same 4-bar, 3-track excerpt** (Dorian lead with mf and accent, 4-chord pad, bass; 120 bpm): hand-written ABC was 211 characters; hand-written LilyPond 400; a compact JSON event list `[part, onset, dur, [pitches]]` 654; music21-exported MusicXML 12,341 (about 58× the ABC); MIDI 470 bytes, binary and not authorable. These are characters, not Claude tokens, but the ordering should hold. MusicXML is a compile target, not something Claude should write by hand for a 3–4 minute, 10–30 track piece.
- **Explicit-onset formats suit note-level editing.** In ABC or LilyPond, changing one duration shifts every later onset in the bar, and the LLM must re-add up every bar. Libretto's slot design, or a Python/JSON list of `(bar, beat, dur, pitch, vel, art)` events, keeps each edit local. That makes edits reviewable, and bar-sum checks become trivial.
- **What each format can express** (from the findings plus general format knowledge): MIDI written through code (pretty_midi or mido) is the only layer that natively carries CC curves (CC1/CC11/CC64), pitch bend, keyswitches (as low-pitch notes), per-track program and channel, and a tempo map. MusicXML and LilyPond carry notated articulations, dynamics, slurs and tempo marks, but MIDI-style controller curves are not first-class in either. ABC (even SMT-ABC) and Strudel are weakest at many-track, CC-heavy orchestral arrangement. A hybrid source therefore works best: a notation-level event list (with articulation and dynamic names) plus a per-track "performance" layer (CC lanes, keyswitch map, humanize parameters) that compiles to MIDI.
- Boogiebench suggests Claude does relatively *worse* in Strudel than other model families, which argues against Strudel as the main format for this user. This is user-vote ELO, so it is weak evidence.

### Gaps
- No controlled study compares Claude (or any frontier chat model) writing ABC vs MusicXML vs LilyPond vs Python-MIDI vs JSON for validity or musical quality. MxlTok and LilyBench test trained-from-scratch or small open models only.
- No measured Claude-tokenizer token counts per format. My figures are character counts (local probe); the Anthropic token-count API was not called.
- MEI, Humdrum `**kern`, SCAMP, Abjad and REMI-style tokens have no LLM-authoring evaluations I could find. REMI and Octuple are tokenisers for trained models, not formats an LLM would write.
- The LilyPond MIDI-output feature list (which dynamics and articulations reach MIDI) could not be fetched (404 on the v2.24 page).

---

## 2. Libraries: what is actively maintained in 2026, and what can each one do?

### Takeaway
The Python core is healthy and current: **music21 10.5.1 (22 Oct 2026)** for analysis, transformation and MusicXML; **pretty_midi 0.2.11.post0 (Jul 2026)** and **symusic 0.6.0 (Apr 2026)** for MIDI with CC, pitch bend and tempo; **MidiTok 3.1.0 (Sep 2026)** for tokenisation; **musicdiff 6.0 / converter21 4.0.2 (Sep 2026)** for semantic score diffs. mido (Oct 2024) is stable but rarely updated. Magenta / note-seq / muspy / pypianoroll / midiutil have had no release since 2021–2022 and should be treated as legacy.

### Cited Findings
Registry snapshot, queried 2026-10-28 (version, upload date of latest release, summary):
- **music21 10.5.1 — 2026-10-22** — "A Toolkit for Computer-Aided Musical Analysis and Computational Musicology" — [PyPI](https://pypi.org/project/music21/); companion **music21-tools 10.2.0 — 2026-05-26** — [PyPI](https://pypi.org/project/music21-tools/)
- **pretty_midi 0.2.11.post0 — 2026-07-28** — [PyPI](https://pypi.org/project/pretty_midi/)
- **mido 1.3.3 — 2024-10-25** — "MIDI Objects for Python" — [PyPI](https://pypi.org/project/mido/)
- **miditoolkit 1.0.1 — 2023-11-23** — [PyPI](https://pypi.org/project/miditoolkit/)
- **symusic 0.6.0 — 2026-04-08** — "A high performance MIDI file parser" — [PyPI](https://pypi.org/project/symusic/)
- **MidiTok 3.1.0 — 2026-09-30** — "MIDI / symbolic music tokenizers for Deep Learning models" — [PyPI](https://pypi.org/project/miditok/)
- **partitura 1.9.0 — 2026-05-25** — "handling symbolic musical information" — [PyPI](https://pypi.org/project/partitura/)
- **SCAMP 0.13.0 — 2026-09-25** — computer-assisted composition framework, manages musical time and playback — [PyPI](https://pypi.org/project/scamp/)
- **Abjad 3.31 — 2025-10-31** — Python API for building LilyPond files — [PyPI](https://pypi.org/project/abjad/)
- **python-ly 0.9.10 — 2026-04-04** — manipulating LilyPond files — [PyPI](https://pypi.org/project/python-ly/)
- **pymusicxml 0.6.0 — 2026-09-25** — simple MusicXML export — [PyPI](https://pypi.org/project/pymusicxml/)
- **musicpy 7.16 — 2026-09-19** — "a music programming language in Python" — [PyPI](https://pypi.org/project/musicpy/)
- **verovio 6.3.0 — 2026-08-19** (PyPI and npm) — engraving MEI (and other formats) to SVG — [PyPI](https://pypi.org/project/verovio/)
- **pyfluidsynth 1.4.0 — 2026-05-30** — SoundFont rendering — [PyPI](https://pypi.org/project/pyfluidsynth/)
- **musicdiff 6.0 — 2026-09-22**; **converter21 4.0.2 — 2026-09-22** (Humdrum and MEI converters that replace music21's) — [musicdiff PyPI](https://pypi.org/project/musicdiff/); [converter21 PyPI](https://pypi.org/project/converter21/)
- **py_midicsv 4.1.2 — 2024-07-18** (MIDI↔CSV) — [PyPI](https://pypi.org/project/py_midicsv/)
- **Stale or legacy:** muspy 0.5.0 (2022-04), pypianoroll 1.0.4 (2021-02), note-seq 0.0.5 (2022-07), magenta 2.1.4 (2022-08), midiutil 1.2.1 (2018-03), mingus 0.6.1 (2020-12), basic-pitch 0.4.0 (2024-08) — [PyPI muspy](https://pypi.org/project/muspy/); [PyPI magenta](https://pypi.org/project/magenta/); [PyPI midiutil](https://pypi.org/project/MIDIUtil/)
- **JS (npm, 2026-10-28):** @strudel/core 1.2.6 (2026-01-17), @strudel/web 1.3.0 (2026-01-18); abcjs 6.7.2 (2026-10-16); opensheetmusicdisplay 2.2.1 (2026-10-12, MusicXML in the browser via VexFlow); vexflow 5.0.0 (2025-03); midi-writer-js 3.2.1 (2026-03); tone 15.1.22 (2025-04); @tonejs/midi 2.0.28 (2022-02); @magenta/music 1.23.1 (2021-11, stale) — [npm @strudel/core](https://www.npmjs.com/package/@strudel/core); [npm abcjs](https://www.npmjs.com/package/abcjs); [npm opensheetmusicdisplay](https://www.npmjs.com/package/opensheetmusicdisplay)

Capabilities verified on music21 10.5.1 **(local probe)**, with docs:
- Stream methods exist: `transpose`, `augmentOrDiminish`, `scaleOffsets`, `scaleDurations`, `quantize`, `makeMeasures`, `makeNotation`, `chordify`, `analyze` (e.g. `analyze('key')` → "C major"), `invertDiatonic`.
- Modes: `key.Key('D','dorian')` gives D E F G A B C D. Scale classes include Dorian, Lydian, Mixolydian, Phrygian, Locrian, Hypo-modes, HarmonicMinor, MelodicMinor, Octatonic, WholeTone, Chromatic, plus `ScalaScale` and `SieveScale`. **There is no dedicated pentatonic class**; build one with `ConcreteScale`, `SieveScale` or Scala files.
- Harmony: `roman.RomanNumeral('V7', key.Key('C'))` gives G B D F; `roman.romanNumeralFromChord(G7, C)` gives "V7"; `harmony.ChordSymbol('Cm7')` gives its pitches.
- 12-tone transforms exist only for `serial.ToneRow` (`originalCenteredTransformation` etc.). **No general `Stream.retrograde`** was found, so retrograde of an arbitrary phrase must be implemented (reverse the offsets).
- Voice-leading module (`VoiceLeadingQuartet`): `parallelFifth`, `parallelOctave`, `parallelUnison`, `hiddenFifth`/`hiddenOctave`, `voiceCrossing`, `voiceOverlap`, `isProperResolution` (P4, A4, d5, m7), `motionType`, plus `iterateAllVoiceLeadingQuartets()`. Documented limits: `voiceCrossing` and `isProperResolution` assume voice 1 is the higher voice; `hiddenInterval` flags all hidden intervals, not only forbidden ones; scale-degree checks are skipped when no key is set — [music21 voiceLeading docs](https://www.music21.org/music21docs/moduleReference/moduleVoiceLeading.html)
- music21's Key object "does everything a KeySignature object does but also knows more advanced aspects of tonal harmony" — [music21 User's Guide ch. 15](https://music21.org/music21docs/_sources/usersGuide/usersGuide_15_key.rst.txt)

LilyPond's built-in transformations:
- `\transpose`, `\inversion around to`, `\retrograde` (spanners and hairpins must be closed; property overrides can misbehave), `\modalTranspose from to scale motif` (shifts by scale degrees; out-of-scale notes are left unchanged), `\modalInversion`, octave checks (`\octaveCheck`, `=`) — [LilyPond 2.24 Notation: Changing multiple pitches](https://lilypond.org/doc/v2.24/Documentation/notation/changing-multiple-pitches)

Community Claude Code / MCP tooling (2025–2026, mostly small repos, maturity unverified):
- *music-gen-skill* (sirruf): Claude writes a Python script with **mido** and renders it through a SoundFont; "algorithmic composition + sampled instruments, not AI text-to-music" — [GitHub](https://github.com/sirruf/music-gen-skill)
- *logic-ai-composer* (dodomovic): Claude writes the MIDI for each part onto its own Logic Pro track, over MCP — [GitHub](https://github.com/dodomovic/logic-ai-composer)
- *midi-agent-skill* (tubone24): text-based music data → MIDI, one channel per track, GM programs — [GitHub](https://github.com/tubone24/midi-agent-skill)
- *fcp-midi* MCP server: notes, chords and dynamics per named track → .mid — [claudepluginhub](https://www.claudepluginhub.com/plugins/os-tack-fcp-midi)
- *pytheory-skill* (kennethreitz): arrangement and layering, MIDI import, MusicXML/LilyPond export — [GitHub](https://github.com/kennethreitz/pytheory-skill)
- bedwards gist (last active 2026-01-04): Claude 4.5 + Claude Code writing multi-track MIDI and lyrics with Bitwig tooling (*skipper* MCP for sample-accurate per-track timing). "No DAW was opened until the final step." No quality evaluation — [gist](https://gist.github.com/bedwards/de776e759c8fd0191c011e12ad08e443)

### Inferences
- A practical stack for this user (Python, Windows, Claude Code): **music21** (modes, keys, Roman numerals, voice-leading checks, MusicXML export) + **pretty_midi or symusic** (multi-track MIDI with CC, pitch bend, tempo map, keyswitch notes; piano-roll arrays) + **pyfluidsynth** or a DAW for audio + **musicdiff** for reviewable diffs + **Verovio, LilyPond or MuseScore** for score images. mido is fine for low-level message writing, but its release cadence is slow.
- SCAMP (Sep 2026) and Abjad (Oct 2025) are maintained, but they target contemporary-classical notation workflows. They add little over music21 + pretty_midi for pop/anime MIDI arranging.

### Gaps
- GitHub activity (stars, last push) could not be checked: the API was rate-limited. Maintenance is inferred from registry release dates only.
- LilyPond's current stable version number was not confirmed. v2.24 docs exist and v2.27 (development) docs appear in search results.
- symusic and MidiTok feature lists were not fetched beyond their registry summaries.

---

## 3. Evidence on LLM composition quality (melody, harmony, voice leading, rhythm, form, orchestration), failure modes and mitigations

### Takeaway
Benchmarks from 2025–2026 agree that general LLMs still struggle with *symbolic structure*. Typical results: bar counting near 0% for open models, ABC syntax accuracy around 40–52% averaged over nine models, and frontier models around 41–43% on score understanding (Claude Opus 4 / Sonnet 4). Recognition tasks (genre, composer) are much easier than structural ones. The one Claude-specific generation study (Libretto, Claude Code + Opus 4.8, June 2026) shows that **retrieval of reference excerpts plus a measure-and-revise loop** is what makes multi-voice output pass structural checks: full-piece pass rate 62%→94% with the loop, 25%→75% with retrieval. Opus clearly beats Sonnet and Haiku.

### Cited Findings
**Claude-specific**
- **Libretto (arXiv 2606.22708, 21 Jun 2026, Yichen Xu):** "We use Claude Code with Opus 4.8 as the LLM agent throughout all experiments," with 314 Lakh MIDI files across eight genres as the corpus — [Libretto PDF](https://arxiv.org/pdf/2606.22708); [abstract](https://arxiv.org/abs/2606.22708); [code](https://github.com/Xyc-arch/Libretto)
  - Gap filling: single-shot 6/51 pass (12%), with a loop of up to 3 rounds **20/51 (39%)**; 33/51 improve.
  - Full-piece generation: single-shot 10/16 (62%), with the loop **15/16 (94%)**. Retrieval off vs on: **2/8 (25%) vs 6/8 (75%)**, with copy risk below the gate in every genre.
  - Education drills, model comparison: "All models output valid grammar"; passes were **Opus 6/8, Sonnet 3/8, Haiku 3/8**.
  - Gradual style morphing: 11/21 pass all checks.
  - Calibration: real songs average 3.4 "extreme axes" out of 29; ungrounded full-piece generations average **5.9**. Failing gap-fills average 4.36 vs 2.25 for passes.
  - Named failure modes: without retrieval, Pop/Rock collapses to the 5th percentile for mean note duration and the 95th for diminished/augmented colour; Film reaches the 98th percentile for ascending-step ratio and the 100th for novelty. A failing Latin gap-fill shows "a chord-conveyor-belt texture with roughly two chords per bar and a scalar, highly stepwise melody" (harmonic rhythm at the 100th percentile, bar distinctness at the 100th, density variation at the 3rd).
  - The loop feedback is phrased musically ("making the texture less sparse, reducing harmonic instability…"), not as raw metric targets, and the loop "keeps the best candidate found so far."
- **MSU-Bench (arXiv 2511.20697, Nov 2025; ACL 2026):** score understanding in ABC text and PDF images, more than 15 models. Claude Opus 4 and Sonnet 4 score about the same overall (**41.22%–42.61%**); visual (PDF) accuracy is much lower (about 20%). Opus 4 has the top Level-3 score — [MSU-Bench ACL 2026](https://aclanthology.org/2026.acl-long.493.pdf); [arXiv](https://arxiv.org/abs/2511.20697) (numbers from a search snippet of the ACL PDF; not independently re-read)
- **Boogiebench (Strudel, user-vote ELO, about winter 2025/26):** "The Anthropic models seem to underperform other model families relative what we'd expect" — [HN](https://news.ycombinator.com/item?id=46437861)
- A practitioner Suno-workflow repo routes "creative work that directly impacts music quality" to Opus and coordination to Sonnet. This is a design choice, not a measurement — [bitwize-music-studio/claude-ai-music-skills](https://github.com/bitwize-music-studio/claude-ai-music-skills)
- An Aug 2026 vendor blog (promotional, no methodology): "Claude produces no audio"; MIDI drafts are "instructions, not sound," usable as raw material — [Sonx: Can Claude Make Music?](https://getsonx.com/blog/can-claude-make-music/)

**Other frontier / open-model benchmarks (2025–2026)**
- **ABC-Eval (arXiv 2509.23350, 27 Sep 2025):** 1,086 samples over 10 sub-tasks, from syntax comprehension to sequence-level reasoning, across seven LLMs. It finds "notable limitations in existing models' symbolic music processing capabilities." The model list was not visible on the abstract page — [ABC-Eval](https://arxiv.org/abs/2509.23350)
- **South Asian music (arXiv 2606.05522, Jun 2026):** 33 LLMs, including GPT-3.5, GPT-4o and Gemini 2.5 Pro; **no Claude**. Mean **ABC syntax accuracy** across the nine generation models was **43.8% / 52.0% / 39.7% / 43.4%** across levels L2–L5. QwQ-32B and Phi-4 were excluded for high ABC syntax error rates. **Gemini 2.5 Pro was best on all metrics** (human ratings 3.25–3.65). Models hit **99–100% scale adherence yet as low as 0% style accuracy**; "structurally parseable outputs do not necessarily translate to perceptually coherent … melodies" — [arXiv 2606.05522](https://arxiv.org/html/2606.05522v1)
- **LilyBench (Jun 2026, open models):** bar_count exact match was **0–3%**; error-detection macro-F1 was ≤0.041 for most models; genre recognition was 0.79–0.96 — [LilyBench](https://arxiv.org/html/2606.08722)
- **WildScore (arXiv 2509.04744, Sep 2025):** in-the-wild score reasoning by multimodal LLMs. GPT-4.1-mini scored 52.0% on a perception-only probe (search snippet) — [WildScore](https://arxiv.org/abs/2509.04744)
- **ZIQI-Eval / "Music Maestro or Musically Challenged" (arXiv 2406.15885, Jun 2024)** argues that existing benchmarks "failed to adequately address the musical capability of large language models" **[pre-2025]** — [arXiv 2406.15885](https://arxiv.org/pdf/2406.15885)
- **ChatMusician (Feb 2024):** ABC as a "second language." It beats LLaMA2 and GPT-3.5 on MusicTheoryBench zero-shot and its compositions are reported as "surpassing GPT-4 baseline" **[pre-2025; GPT-4-era baselines]** — [arXiv 2402.16153](https://arxiv.org/abs/2402.16153). By Jan 2026, a JKU study reported ChatMusician's outputs as non-readable for FMD calculation — [arXiv 2601.22764](https://arxiv.org/pdf/2601.22764)
- **NotaGen (Feb 2025, IJCAI 2025):** a trained ABC model (1.6M pieces pre-training, about 9K classical pieces fine-tuning) with CLaMP-DPO. It notes "perplexity appears to be a weak indicator of musical quality" — [NotaGen arXiv 2502.18008](https://arxiv.org/pdf/2502.18008); [IJCAI](https://www.ijcai.org/proceedings/2025/1134)
- **CLaMP 3 (Feb 2025):** cross-modal (symbolic and audio) music retrieval/embedding. It beats CLaMP 2 on text-to-music retrieval, but not on symbolic sheet-music classification — [arXiv 2502.10362](https://arxiv.org/pdf/2502.10362)
- **Mitigations named in the literature:** separating planning from realisation and giving intermediate constraints such as chord progressions or form descriptions (ComposerX multi-agent 2024, MuseCoco 2023) **[pre-2025]**, as summarised in — [arXiv 2601.22764](https://arxiv.org/pdf/2601.22764); LilyBench shows in-key hand-written examples raise compile rates to 97–99.9% — [LilyBench](https://arxiv.org/html/2606.08722)

### Inferences
- **Typical failure modes to design against**, combining the above with Libretto's diagnostics:
  - (a) Bar and beat arithmetic errors. LLMs cannot reliably count bars (LilyBench 0–3%) and ABC hides onsets behind running sums.
  - (b) Harmonic rhythm that is too fast and uniform ("chord conveyor belt").
  - (c) Scalar, stepwise, low-variety melodies with short uniform note lengths.
  - (d) Bars that repeat too much or are too distinct, with little density variation, i.e. weak large-scale form.
  - (e) Being "in scale" but stylistically generic (99–100% scale adherence with near-zero style accuracy).
  - (f) Hallucinated resources, such as sample names in Strudel.
  
  Parallel fifths and range violations are not measured in any of these benchmarks. They are classic issues, but there is no 2025–26 quantification for frontier models.
- **Mitigations most supported by evidence for Claude:**
  - (1) Retrieve 1–3 reference excerpts in the target style into context. This was the single biggest lever: 25%→75%.
  - (2) A bounded generate → measure → revise loop with musician-readable feedback, keeping the best candidate.
  - (3) Use Opus rather than Sonnet or Haiku for composition.
  - (4) Make every bar self-describing (bar number, chord label, explicit onsets) so the validator can check bar sums and alignment deterministically.
  - (5) Deterministic validators rather than self-checking: bar length, range per instrument, key/mode adherence, music21 voice-leading checks on outer voices.
- Frontier models are not dramatically better than open models at *reading* scores (MSU-Bench about 42% for Claude 4-series). Claude should rely on tools (music21 analysis) for analysis-type judgements instead of "eyeballing" the notation.

### Gaps
- No 2025–2026 paper systematically evaluates Claude (Sonnet 4.x / Opus 4.x / later) on harmony, voice leading, orchestration or long-form pop arrangement. Libretto's numbers are structural-gate pass rates, not human quality ratings, and its samples are small (8–51 per condition).
- No study tests closing the loop by rendering audio and having an audio-understanding model "listen." I found no evidence for or against that step.
- ABC-Eval's seven-model list and per-model results were not retrieved.

---

## 4. Hybrid approaches: LLM writes structure / chords / melody, a symbolic model fills parts. What is usable today, and does it help?

### Takeaway
There are usable, open, local models for *filling in* parts. **MIDI-GPT** (AAAI 2025; track/bar infilling with instrument, density and polyphony controls; non-commercial weights) is the closest fit for multi-track pop. **Anticipatory Music Transformer / MIDI-LLM** (2023/2025) handle infilling and text-to-MIDI. **Aria** (ISMIR 2025) handles piano continuation only. **Text2midi** (AAAI 2025) does caption-to-MIDI. **NotaGen** is classical ABC. None has been shown to improve an *LLM-led* pop arrangement, so the benefit is unproven and should be judged by ear per track (e.g. drum or comping variations).

### Cited Findings
- **MIDI-GPT** (Pasquier et al., arXiv 2501.17011, 28 Jan 2025; AAAI-25 39(2):1474–1482; SFU Metacreation + Steinberg). It infills "musical material at the track and bar level," conditioned on instrument type, style, note density and polyphony. It is trained on GigaMIDI; code is MIT (`midigpt` Python package, HF weights). Model use is "restricted to non-commercial purposes so far" — [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/32138); [arXiv](https://arxiv.org/html/2501.17011v1); [GitHub](https://github.com/Metacreation-Lab/MIDI-GPT); [project page](https://www.metacreation.net/projects/midi-gpt)
- **Anticipatory Music Transformer** (arXiv 2306.08620, 2023): anticipatory infilling models trained on Lakh MIDI **[pre-2025]** — [arXiv](https://arxiv.org/pdf/2306.08620)
- **MIDI-LLM** (arXiv 2511.03942, Nov 2025): Llama 3.2 1B plus AMT's MIDI vocabulary for text-to-MIDI *and infilling*. In a user study with Hookpad Aria users it gave higher quality, stronger text control and **7–13× faster inference than Text2midi** — [arXiv](https://arxiv.org/pdf/2511.03942)
- **Text2midi** (AAAI 2025, published 25 Feb 2025): a 272M-parameter encoder-decoder, pretrained on SymphonyNet and fine-tuned on MidiCaps — [AAAI/ACM DL](https://dl.acm.org/doi/10.1609/aaai.v39i22.34516); [GitHub](https://github.com/AMAAI-Lab/Text2midi). Follow-up Text2midi-InferAlign (May 2025) — [arXiv 2505.12669](https://arxiv.org/pdf/2505.12669)
- **Aria** (EleutherAI, arXiv 2506.23869, ISMIR 2025): LLaMA-3.2-style, trained on solo-piano MIDI transcriptions. Training-data figures conflict (about 60k h in the repo vs about 100k h in the paper). Apache-2.0; "most naturally suited for generating continuations of existing MIDI files rather than generating music from scratch." **Piano only** — [arXiv](https://arxiv.org/pdf/2506.23869); [GitHub](https://github.com/EleutherAI/aria); [HF aria-medium](https://huggingface.co/loubb/aria-medium)
- **NotaGen** (IJCAI 2025): classical-style ABC generation; CLaMP-DPO improved perceived musicality for NotaGen, MuPT and MET — [arXiv 2502.18008](https://arxiv.org/pdf/2502.18008)
- **Text2Score** (arXiv 2605.13431, May 2026): generates sheet music from text prompts (title and existence only; not read) — [arXiv](https://arxiv.org/pdf/2605.13431)
- **Libretto** explicitly "does not replace audio-domain systems or trained symbolic generators." Its approach is LLM + measurement, with no trained music model — [Libretto](https://arxiv.org/pdf/2606.22708)

### Inferences
- The most promising hybrid pattern is narrow: Claude owns form, chords, melody and the key parts. MIDI-GPT (or AMT/MIDI-LLM) proposes *variations* for idiomatic, texture-heavy tracks (drum fills, guitar strumming, arpeggiated keys, string pads) inside Claude-defined bars, and conditions on Claude's chords and melody. Claude or the user accepts or edits the output in the same event format. Re-import all model output into the single source of truth, so the diff and validators still apply.
- Licence check: MIDI-GPT weights are non-commercial. Aria is Apache-2.0 but piano-only.

### Gaps
- No study shows that LLM + infilling-model hybrids beat LLM-only or model-only output for multi-track pop. The MIDI-LLM user study compares only against Text2midi.
- Whether MIDI-GPT runs well on Windows / a local GPU in 2026 was not checked. Magenta/MusicVAE, MuseCoco and SongComposer were not re-examined; Magenta packages are stale (last release 2021–2022, see §2).

---

## 5. Recommended concrete pattern for an agent writing a 3–4 minute pop/anime-style arrangement with 10–30 tracks

### Takeaway
No source tests this exact scenario, so this section is synthesis. Combine the Libretto evidence (explicit bar/onset grammar, retrieval, measure-and-revise loop, Opus) with the format and library findings above. Plan top-down in small text artifacts. Author each section × instrument as a compact explicit-onset event file. Compile to MIDI and MusicXML with code. Validate deterministically. Render to a score, a piano roll and audio for listening.

### Cited Findings
- Planning separated from realisation, with chord progressions or form as intermediate constraints, is the established controllability technique (ComposerX, MuseCoco) — [arXiv 2601.22764 related work](https://arxiv.org/pdf/2601.22764)
- A bar-block grammar with a header (key, meter, tempo, grid, bar count), a voice list and a chord label per bar, generated by Claude Code + Opus 4.8, works for five-voice, 96-bar pieces. A three-round measure → feedback → regenerate loop and style retrieval raise pass rates substantially — [Libretto](https://arxiv.org/pdf/2606.22708)
- Practitioners keep MIDI and lyrics in version-controlled repos and compose fully in conversation before opening a DAW (Claude 4.5, Bitwig) — [bedwards gist](https://gist.github.com/bedwards/de776e759c8fd0191c011e12ad08e443)
- One channel per track with GM programs for multi-instrument playback — [midi-agent-skill](https://github.com/tubone24/midi-agent-skill)

### Inferences
Proposed artifact chain, each file small enough for Claude to rewrite whole:
1. **`song.yaml` (form plan):** title, tempo map, key/mode per section, sections with bar counts (e.g. Intro 8 / A 16 / B 8 / Chorus 16 / … ≈ 90–110 bars ≈ 3:30 at 120–130 bpm), energy curve, per-section orchestration matrix (which of the 10–30 tracks play), and modulation points (e.g. last-chorus +1 semitone).
2. **`chords.txt` (chord chart):** one line per bar with Roman numeral and chord symbol (pivot chords marked at modulations). Validate with music21 `RomanNumeral` / `ChordSymbol`.
3. **`lead.*` (lead sheet / topline):** melody as explicit-onset events plus phrase marks. Instrumental first; it later becomes the vocal guide. Range-check against the target vocal range now, so vocals can be added later.
4. **`parts/<section>/<track>.*` (per-section, per-instrument events):** `bar, onset (16th slot or beat), dur, pitch(es), vel/dyn, articulation`. Keep a per-track **performance sidecar** for CC1/CC11/CC64 curves, keyswitch map (articulation name → keyswitch note per sample library), pan and program. Claude edits one section × track at a time.
5. **`build.py`:** compiles 1–4 into multi-track MIDI (pretty_midi/symusic: tempo map, CC, keyswitch notes, humanize timing and velocity) and MusicXML (music21), then renders audio (FluidSynth or a DAW).
6. **`validate.py`:**
   - bar sums equal the meter
   - bar counts match `song.yaml`
   - every chord label parses
   - melody and bass notes in or out of chord / mode reported per bar
   - instrument ranges
   - music21 `VoiceLeadingQuartet` parallels and voice crossing between bass and lead (and within SATB-like string or brass groups)
   - density, harmonic-rhythm and repetition statistics per section, as Libretto-style "extreme" checks
   
   Feed failures back to Claude in musical words.
7. **Listening and inspection:** per-section audio bounce, score PNG/SVG and piano-roll PNG (see §8); `musicdiff` text report for every revision (see §7).

The order of work follows the evidence: form → chords → melody → bass → drums → pads/strings → counter-melodies → fills/ear-candy. Use Opus for melody and harmony decisions, and give 1–3 reference excerpts per section style.

### Gaps
- No published evaluation of this full pipeline for pop/anime material exists, and no study of 10–30-track LLM arrangements was found. Libretto tops out at five voices.
- No data on how Claude handles anime-specific idioms (e.g. the royal-road progression IV–V–iii–vi, fast modulations, string/brass orchestration density).

---

## 6. (New requirement) Single source of truth for a motif/fragment library: metadata, transposition and modal transformation, retrograde/inversion/augmentation, re-harmonisation, joining fragments with smooth voice leading or pivot-chord modulation

### Takeaway
music21 10.5.1 provides most of the needed operations as tested code: modal keys and scales, chromatic and diatonic transposition, diatonic inversion, augmentation and diminution, Roman-numeral harmony, key analysis and voice-leading checks. It lacks a general retrograde and a pentatonic scale class, and has no fragment-joining or pivot-chord search. Those are small custom functions. LilyPond has built-in `\modalTranspose`, `\modalInversion` and `\retrograde`, but it is better as a render target than as the data model. The recommended single source of truth is a **Python/JSON (or YAML) fragment library of explicit-onset events with metadata**, transformed through music21 and compiled to everything else.

### Cited Findings
- music21 has `Stream.transpose`, `invertDiatonic`, `augmentOrDiminish`, `scaleOffsets/scaleDurations`, `quantize`, `makeMeasures`, `chordify` and `analyze('key')`. `key.Key('D','dorian')` is supported; Dorian, Lydian, Mixolydian, Phrygian, Locrian, Harmonic/Melodic Minor, Octatonic, WholeTone, Scala and Sieve scale classes exist; **no pentatonic class**; retrograde exists only for `serial.ToneRow` **(local probe, music21 10.5.1)**. Key-object docs — [music21 User's Guide ch. 15](https://music21.org/music21docs/_sources/usersGuide/usersGuide_15_key.rst.txt)
- music21's demo page for "inversion" covers chord inversions (`chord.inversion()`), not melodic inversion of a stream — [music21 devTest inversions](https://music21.org/music21docs/testsAndInProgress/devTest_inversions.html)
- Voice-leading checks for smooth joins (parallel or hidden fifths and octaves, crossing, overlap, motion type, resolution of tendency intervals) — [music21 voiceLeading](https://www.music21.org/music21docs/moduleReference/moduleVoiceLeading.html)
- Roman numerals ↔ chords (`RomanNumeral('V7', C)` → G B D F; `romanNumeralFromChord` → "V7") and `ChordSymbol('Cm7')` parsing **(local probe)**, useful for re-harmonisation and pivot-chord detection (a chord with valid Roman numerals in both keys).
- LilyPond: `\modalTranspose` moves by scale degrees within any given scale, leaving out-of-scale notes unchanged; `\modalInversion`; `\inversion`; `\retrograde` (spanners must be closed) — [LilyPond docs](https://lilypond.org/doc/v2.24/Documentation/notation/changing-multiple-pitches)
- Libretto's gap-filling and morphing tasks are the closest published analogue to "splice fragments with a bridge." Claude (Opus 4.8) generates the missing region from surrounding context, checked for length, local fit and novelty. Pass rate is 12% single-shot vs 39% with the loop; morph pass rate is 11/21 — [Libretto](https://arxiv.org/pdf/2606.22708)

### Inferences
- **Fragment record (suggested):** `id, events[(onset, dur, pitch, vel, art)], meter, bars, tonic, mode (ionian/dorian/lydian/…/maj-pent/min-pent/custom pitch-class set), range (lowest/highest), anacrusis, implied chords per bar, tags (energy, role: hook/answer/bridge), provenance (prompt, model, parent id, transform chain)`. Store each fragment as its own small file, so git diffs stay local.
- **Transform layer (pure functions, each logged in provenance):**
  - chromatic transpose: music21 `transpose('M2')`
  - modal transposition by scale degree: map the pitch to a scale degree in the source mode, shift the degree, map back. This is custom, mirroring LilyPond `\modalTranspose`.
  - mode change on the same tonic (e.g. Ionian → Lydian, raising degree 4)
  - diatonic inversion: `invertDiatonic`
  - retrograde: custom offset reversal
  - augmentation: `augmentOrDiminish(2)`
  - rhythmic displacement
  - re-harmonisation: generate candidate Roman-numeral sequences and score melody-note/chord fit with music21
- **Joining fragments:** compute the exit chord and last melody note of fragment A and the entry of fragment B. Pick a pivot chord (a chord diatonic to both keys, checked via `RomanNumeral` in both) or a secondary dominant of the new key. Have Claude write 1–4 bridging bars under those constraints. Validate the junction with music21 voice-leading quartets on bass/lead, plus a max-leap check on the melody.
- Mode and pentatonic coverage: build pentatonic and custom modes as pitch-class sets (or `ConcreteScale`) in the library. Do not rely on music21 having a class for each.

### Gaps
- No published tool provides "fragment library + modal transforms + automatic pivot-chord splicing" off the shelf for pop. This must be built. No evaluation of LLMs at modulating smoothly between fragments was found.

---

## 7. (New requirement) Diffing and versioning symbolic music so every edit is reviewable and reversible

### Takeaway
Put the *authored text source* (event files, YAML plans) under git, where line diffs are already meaningful. Treat MusicXML and MIDI as build artifacts. For musical review, run **musicdiff 6.0** on the compiled MusicXML: it reports edits as "measure N, staff S, beat B: −F5 / +G5 staccato" and can produce marked-up PDFs. Raw MusicXML line diffs are noisy, and MIDI is binary, so it needs a text conversion (midicsv / midicomp) to diff at all.

### Cited Findings
- **musicdiff** (v6.0, 22 Sep 2026; Python 3.12+; requires music21 ≥10.5.0 and converter21 ≥4.0.2) "comput[es] and visualiz[es] (or describ[es]) the notation differences between two music scores, or between two folders." It accepts any format music21 or converter21 parses (MusicXML, Humdrum, MEI, ABC, …). It can include or exclude notes and rests, beams, tremolos, ornaments, articulations, ties, slurs, signatures, directions, barlines, chord symbols, ottavas, arpeggios, lyrics, style, metadata and voicing. Output modes are `visual` (marked-up score PDFs; needs music21 configured with e.g. MuseScore), `text` (diff-like) and `omrned` (JSON OMR normalised edit distance). It is notation-focused: "two tied eighth notes are considered different from a single quarter note." It derives from Foscarin's music-score-diff — [musicdiff on PyPI](https://pypi.org/project/musicdiff/); [libraries.io](https://libraries.io/pypi/musicdiff)
- **(local probe)** Two music21-built 3-track scores differed by one note (F5 → G5 plus staccato in bar 2). `python -m musicdiff -o text` printed exactly:
  `@@ measure 2, staff 1, beat 2.0 @@ -(Note) F5 (quarter note)` / `+(Note) G5 (quarter note), articulations=[staccato]`.
  A raw `diff` of the two MusicXML files showed **31 changed lines**, mostly because music21 regenerates random `score-part` / `score-instrument` / `midi-instrument` IDs on every export.
- The MusicDiff paper (MEC 2019/2020) argues that a music diff should compare musical structures, not their file serialisation — [MusicDiff – A Diff Tool for MEI (Paderborn)](https://ris.uni-paderborn.de/record/55841); [MEC 2019 poster](https://music-encoding.org/conference/abstracts/abstracts_mec2019/diff-DIME_sapov_posterMEC2019.pdf)
- MIDI diff options: `mididiff` computes the difference between two MIDI files and outputs MIDI — [mididiff docs](https://mididiff.readthedocs.io/en/stable/api.html); `midicomp` converts SMF ↔ plain text (per search summary); py_midicsv 4.1.2 converts MIDI ↔ CSV — [PyPI py_midicsv](https://pypi.org/project/py_midicsv/); Ardour users discuss keeping MIDI note lists as text files — [Ardour discourse](https://discourse.ardour.org/t/midi-note-lists-as-text-files/107922)
- LilyPond is plain text, so it diffs cleanly in git; `midi2ly` and `abc2ly` convert into it — [abc2ly man page](https://manpages.debian.org/jessie/lilypond/abc2ly.1.en.html)

### Inferences
- **Versioning recipe:**
  - (1) Git tracks `song.yaml`, `chords.txt`, the fragment library and `parts/**`, one note per line or one bar per line, sorted deterministically, so a single-note edit is a one-line diff.
  - (2) `build.py` is deterministic: stable part IDs, no timestamps. Patch music21's random IDs or post-process them if MusicXML is committed, or keep MusicXML and MIDI out of git (regenerated on checkout).
  - (3) Each Claude edit is one commit whose message names section, track and intent. Add `musicdiff -o text` output (and optionally the visual PDF) as the review artifact.
  - (4) Optionally, a `.gitattributes` textconv driver for `*.mid` using midicsv, so accidental MIDI commits stay readable. This setup is unverified; configure it per the git docs.
  - (5) Revert = `git revert` of the source commit, then rebuild.
- For a DAW round-trip (the user tweaks in the DAW, then exports MIDI), re-import through pretty_midi/symusic → event files and quantise. The resulting git diff shows exactly what the human changed.

### Gaps
- No ready-made git diff driver for musicdiff was found; it must be wired up by hand. musicdiff compares *notation*, so CC curves, velocity and keyswitch changes need a separate text diff of the performance sidecar or MIDI CSV.

---

## 8. (New requirement) Rendering the same source to a readable score or piano roll for note-by-note inspection

### Takeaway
Everything can be rendered from one source. Compile to MusicXML (music21) → **Verovio** (SVG, Python or JS) or **MuseScore** (PDF/PNG) or **LilyPond** (engraved PDF/PNG) for scores. Use **pretty_midi `get_piano_roll` + matplotlib** for a PNG piano roll (best for drums, CC and dense pop textures). In the browser, **OpenSheetMusicDisplay / abcjs** can show it live. musicdiff's visual mode marks up changed notes on the score.

### Cited Findings
- **Verovio 6.3.0** (Aug 2026, PyPI and npm): native MEI input, plus MusicXML (including compressed .mxl), Humdrum, Plaine & Easie, ABC (no tuplets or multi-voice) and CMME; renders to SVG; exports MEI and Humdrum — [Verovio input formats](https://book.verovio.org/toolkit-reference/input-formats.html); [PyPI](https://pypi.org/project/verovio/)
- **OpenSheetMusicDisplay 2.2.1** (12 Oct 2026): a JS engine that displays MusicXML via VexFlow; **abcjs 6.7.2** (16 Oct 2026) renders ABC — [npm OSMD](https://www.npmjs.com/package/opensheetmusicdisplay); [npm abcjs](https://www.npmjs.com/package/abcjs)
- **pretty_midi** exposes `get_piano_roll`, `get_beats` and `get_downbeats`, enough to draw a labelled piano roll per track with bar lines **(local probe)**. Landing docs — [pretty_midi](https://craffel.github.io/pretty-midi/)
- **musicdiff** visual output: "marked-up score PDFs" highlighting differences (requires music21 to be configured with a score viewer such as MuseScore) — [musicdiff PyPI](https://pypi.org/project/musicdiff/)
- Libretto pairs its text grammar with piano-roll figures to make failures "inspectable" (e.g. a visible chord-conveyor-belt texture) — [Libretto](https://arxiv.org/pdf/2606.22708)
- LilyPond and Abjad produce engraved output from text or Python; Abjad 3.31 (Oct 2025) builds LilyPond files — [PyPI abjad](https://pypi.org/project/abjad/)

### Inferences
- **Suggested inspection set per revision:**
  - (1) Per-section full-score SVG via Verovio, or MuseScore CLI on the MusicXML, with bar numbers matching the event files.
  - (2) Per-track piano-roll PNG with bar and beat grid, chord labels on top and velocity as colour. This is the best view for drums and CC lanes, which scores render poorly.
  - (3) Short audio bounce.
  - (4) musicdiff text report plus a visual PDF of the changes.
  
  All are generated by `build.py`, so they always match the git source.
- Verovio's ABC limits (no multi-voice) reinforce that ABC should not be the master format for multi-track work.

### Gaps
- The MuseScore 4 command-line export flags and LilyPond's current stable version were not verified in this session. Verovio's MIDI/timemap output was not checked; it is on a separate docs page.
