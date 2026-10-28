# Rendering MIDI to realistic instrument audio entirely from code (state as of 2026-10-28)

All prices and version facts below were checked on 2026-10-28 unless a different date is stated. Prices from retailers/aggregators move with sales; vendor list prices are flagged where found.

## 1. Programmatic plugin hosts: which can load commercial VST3 instruments headless and render deterministically?

### Takeaway
On Windows, two Python/JUCE hosts (Spotify Pedalboard and DawDreamer) can load VST3 instruments and render MIDI offline with no GUI. REAPER's command line (`-renderproject`) is the most robust fallback for awkward commercial plugins, especially Kontakt and script-heavy libraries. Kontakt is the main weak spot in headless Python hosts: several reports show load failures and offline dropouts. On Linux, use sfizz, FluidSynth, Pianoteq, Carla and Ardour's Lua tools with native-Linux plugins.

### Cited Findings
**Spotify Pedalboard (Python, JUCE-based)**
- Current docs are "Pedalboard v0.9.26". The README says it "Supports VST3® instrument and effect plugins on macOS, Windows, and Linux" and "instrument and effect Audio Units on macOS". Linux VSTs need glibc > 2.27. It releases the GIL so it can use several cores. — [Pedalboard GitHub](https://github.com/spotify/pedalboard); [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- Instrument support has existed since v0.7.4. The README example is `audio = instrument([Message("note_on", note=60), Message("note_off", note=60, time=5)], duration=5, sample_rate=44100)`, using mido messages or `(midi_bytes, timestamp_in_seconds)` tuples. Each message is sent at its timestamp. Messages later than `duration` are ignored. Signature parameters: `num_channels` (default 2), `buffer_size` (default 8192), `reset`. — [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- `is_instrument` is "True iff this plugin is not an audio effect and accepts only MIDI input". Instrument plugins cannot go inside a `Pedalboard` chain, which "may only contain effects plugins". — [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- `load_plugin(..., initialization_timeout=...)`, added in v0.7.6, exists because "Some plugins load resources asynchronously in the background on startup". `plugin_name=` selects one plugin from a multi-plugin bundle, and omitting it raises `RuntimeError`. `parameter_values=` sets parameters by name at load time. — [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- VST3 plugins can run on background threads since v0.8.8. The docs warn that some plugins "generate incorrect output, or outright crash if called from background threads". `show_editor()` may only be called on the main thread and blocks. — [Pedalboard API reference (offset 100k)](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- Pedalboard cannot load VST2 instruments. A third-party wrapper warns that an instrument needing "host features beyond a basic note event ... may return silence with no error". — [ComfyUI VST Synth Adapter (wrapper around Pedalboard)](https://comfy.icu/node/ComfyUIVSTSynthAdapter)

**DawDreamer (Python, JUCE-based, GPLv3)**
- Latest release is v0.9.0 (2026-08-12); v0.9.1 is listed as unreleased. It runs on macOS (Apple Silicon and Intel), Windows and Linux, plus Colab and Docker. Features: DAG processor graphs, VST2/3 instrument and effect hosting with state management and automation, Faust, RubberBand time-stretch with Ableton warp markers, MIDI playback/record/export, and multiprocessing. — [DawDreamer docs](https://dirt.design/DawDreamer/)
- API: `engine = RenderEngine(SR, BUFFER)`, `make_plugin_processor(name, path)`, `load_midi(path, beats=False, all_events=True)`, `add_midi_note(...)`, `engine.render(seconds)`, and `get_audio()` returning a (channels, samples) array. `set_bus()` and `enable_all_buses()` handle multi-output plugins, and `get_latency_samples()` reports latency. Parameters are always normalized to 0–1. Automation works at audio rate or PPQN rate. `open_editor()` is blocking. — [DawDreamer plugin processor guide](https://dirt.design/DawDreamer/user_guide/plugin_processor.html)
- The docs warn: "Not all plugins are compatible with headless (no-GUI) rendering". — [DawDreamer plugin processor guide](https://dirt.design/DawDreamer/user_guide/plugin_processor.html)
- Compatibility table (most entries date from 2021–2023):
  - Working: Kontakt on Windows as VST2 `.dll` with `.nkm` multis (issue #23); Spitfire LABS on Windows `.dll` and on macOS (needs `time.sleep(1)`, issue #78); Serum and Sylenth1 (`.fxp` presets work); TAL-Noisemaker; Dexed VST3 on macOS; u-he Diva and Repro as Linux `.so`.
  - Not working: Addictive Drums 2 (issue #67), HALion (issue #41), Dexed 0.9.6 VST3 on Windows.
  - "Common issues" lists: "Some plugins require authorization/installation before use", "Some plugins require GUI interaction for initialization", and "May need `open_editor()` before use".
  — [DawDreamer Plugin Compatibility](https://dirt.design/DawDreamer/compatibility.html)

**Known Kontakt problems in headless hosts**
- DawDreamer issue #180 (opened 2023-10-14, still open): Kontakt 7.6 VST3 segfaults in DawDreamer on macOS while working in Logic and Cubase. The logs show failed connections to NI's `odr_agent` and a missing `NIHardwareConnectionService`. The maintainer suggested Pedalboard. A 2023-11-28 follow-up says Pedalboard fails the same way. Driving REAPER through reapy logs the same errors but renders the audio correctly. The reporter wanted 7.6 because it fixed offline rendering of script-based `.nki` libraries such as Session Guitarist Acoustic Strummer and Action Drums, which had "audio dropouts and artifacts in DawDreamer exports". — [DawDreamer issue #180](https://github.com/DBraun/DawDreamer/issues/180)
- JUCE forum, 2023-10-20: the "latest Kontakt 7 VST3 (updated Oct 12) refuses to load into a JUCE 7.0.5 host on Windows". macOS worked, and no fix is shown. — [JUCE forum](https://forum.juce.com/t/ni-kontakt-7-vst3-windows-does-not-load-into-juce-host/58412)
- Kontakt dropouts that occur only during offline bounces are a long-standing, cross-DAW problem. Users' theory is that Kontakt doesn't know it is non-realtime and doesn't wait for disk streaming. Reported workarounds:
  - set the DFD preload buffer to maximum and enable Kontakt's "offline render mode" (offline interpolation "Standard");
  - disable multiprocessor support;
  - load groups in Sampler (RAM) mode instead of DFD.
  
  One NI community post says NI fixed this in a Kontakt 7 update; other users still reported it. — [VI-Control](https://vi-control.net/community/threads/kontakt-dropouts-only-while-rendering-exporting-and-freezing.123886/); [NI Community](https://community.native-instruments.com/discussion/15633/dropouts-on-long-notes-only-when-offline-rendering-in-kontakt-7-kontakt-6)
- A JUCE forum thread reports that some VST3s render silence in a headless VST3 host, possibly needing their UI to load first. It has no confirmed answer. — [JUCE forum](https://forum.juce.com/t/headless-vst3-host-some-plugins-render-silence/58169)

**REAPER command line**
- Flags:
  - `-renderproject filename.rpp`: "render project and exit"
  - `-batchconvert filelist.txt`
  - scripts on the command line: `reaper.exe project.rpp script.lua`. Since 6.80 a project/template or media file can be passed together with a script.
  - `-nosplash`, `-newinst|-nonewinst`
  - `-close[all][:save|:nosave][:exit]` (`:exit` needs 7.29+)
  - `-cfgfile file.ini` (alternate resource directory), `-ignoreerrors`, `-splashlog`, `-template`
  - `-noactivate`, supported on macOS/Linux since 7.29
  
  The page has no headless mode. — [ReaTeam REAPER-CLI.md (community-maintained)](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)
- A 7.30 changelog item (via a third-party mirror) reads "fix command line render occasionally canceling itself". — [search summary of REAPER changelogs](https://reaper.fm/download.php)
- python-reapy controls a *running* REAPER instance through the distant API, so it is not headless. — [python-reapy](https://pypi.org/project/python-reapy/0.7.2/)
- Price: $60 discounted license (personal use, businesses under $20k/yr gross revenue, education/non-profit) or $225 commercial. One key may be installed on several computers but used on one at a time. Free upgrades through v8.99. — [REAPER purchase page](https://www.reaper.fm/purchase.php)
- REAPER has Linux builds; the 5.x notes mention Linux instance reuse and `-newinst`. — [REAPER 5.x old downloads](https://www.reaper.fm/download-old.php?ver=5x)

**Carla, Ardour, sfizz, Pianoteq (Linux-friendly)**
- Carla: a 2023 commit adds `runHostWithoutUI` in `carla_host.py` for headless engine start. Another commit is "Fix running carla-single headless on linux". Full OSC control is available. kuriborosu is "A simple Audio and MIDI file render, powered by Carla Plugin Host" (work in progress). I found no documented freewheel/offline mode. — [Carla commit](https://git.kx.studio/falkTX/Carla/commit/f81036f9a919442692ccde37f5a19531d5da3052.patch); [kuriborosu](https://github.com/falkTX/kuriborosu); [Carla GitHub](https://github.com/falkTX/Carla)
- Ardour session utilities:
  - `ardour8-export <session-dir> <snapshot-name>` exports a session from the command line.
  - `ardour8-lua` is a headless Lua interpreter: set the backend ("None (Dummy)"), load the session, then `simple_export()` / `run_export()`.
  - A forum answer says stem export can only be started from the GUI.
  
  — [Debian ardour8-lua man page](https://dyn.manpages.debian.org/trixie/ardour/ardour8-lua.1); [Ardour export.cc](https://git.ardour.org/ardour/ardour/src/branch/fallthru/session_utils/export.cc); [Ardour discourse](https://discourse.ardour.org/t/batch-processing-on-cli/100929)
- sfizz: `sfizz_render --sfz X.sfz --midi X.mid --wav out.wav` with `-b/--blocksize` and `-s/--samplerate`. A third-party script also passes `--quality` and `--polyphony`. — [sfizz_render man page](https://man.archlinux.org/man/sfizz_render.1.en); [SFZ-Instruments README](https://huggingface.co/datasets/projectlosangeles/SFZ-Instruments/blob/main/README.md)
- Pianoteq CLI (`--help`, 2023 build):
  - `--preset NAME`, `--list-presets`, `--fxp FILE`, `--midimapping`
  - `--midi FILE`, `--wav FILE` (export and quit), `--flac`, `--mp3`, `--rate`, `--bit-depth 16/24/32`, `--dither`, `--normalize`, `--normalize-db`, `--mono`
  - `--headless`, `--play-and-quit`
  - `--serve [IP:]PORT`, a JSON-RPC remote-control server (`--serve ""` gives localhost:8081)
  
  Batch use: `--midi C:\MyMidiFiles --wav C:\MyMidiFiles` converts a whole folder. — [Modartt forum --help dump](https://forum.modartt.com/viewtopic.php?id=11200); [Modartt forum batch Windows](https://forum.modartt.com/viewtopic.php?id=9387)
- A Pianoteq 8 `--headless` user on Arch Linux got no *live* audio output with bare ALSA. This affects realtime playback, not file export. — [Modartt forum](https://forum.modartt.com/viewtopic.php?id=12625)

### Inferences
- For an agent pipeline on Windows 11:
  - Use Pedalboard as the default instrument host (actively maintained, v0.9.26, raw state bytes, `.vstpreset` I/O).
  - Use DawDreamer when you need a routed graph, sample-accurate parameter automation, or VST2 `.dll` (the format in which Kontakt is listed as working).
  - Keep REAPER `-renderproject` (with a script that builds the .rpp) as the fallback for Kontakt/NI script libraries and anything else that misbehaves in JUCE hosts. Issue #180 shows REAPER rendered correctly where both Python hosts failed.
- Every commercial plugin must be tested one by one. Silent output with no error is a known failure mode, so a pipeline should check every stem's peak/RMS and fail loudly.
- FluidSynth (`fluidsynth -ni -F out.wav font.sf2 song.mid`) and Csound can render SF2/SFZ-style material from the CLI. I did not re-verify their docs this session (from prior knowledge). Neither hosts commercial VST3 instruments in practice.

### Gaps
- No 2025–2026 report confirms that Kontakt 8 VST3 loads and renders cleanly in Pedalboard or DawDreamer on Windows. It has to be tested locally.
- No source found on Spitfire's own plugin (BBC SO / LABS VST3) or Toontrack SD3/EZD3 working in Pedalboard specifically.
- No documented offline/freewheel render path for Carla. kuriborosu's maturity is unknown.
- No official REAPER doc page for CLI flags was fetched; the ReaTeam doc is community-maintained.

## 2. Sample and physical-model libraries: realism tiers, prices and license terms

### Takeaway
- **Free tier:** the strongest free orchestral options are Spitfire Symphony Orchestra Discover (Kontakt Player, includes three true-legato patches) and BBC SO Discover (Spitfire plugin). CC0/CC-licensed SFZ sets (VSCO 2 CE, Sonatina) are rougher but render on Linux through sfizz.
- **Premium tier:** CSS, BBC SO Pro, VSL Synchron, EastWest, Superior Drummer 3, Keyscape/Omnisphere, Komplete 15 and Pianoteq/SWAM all license per user with activation.
- **License terms:** Spitfire and NI EULAs forbid AI/LLM training on their content. I found no clause banning automated rendering of your own music, though the Spitfire EULA couldn't be fetched directly.

### Cited Findings
**Free**
- Spitfire Symphony Orchestra Discover: free, launched 2025-11-20. 44 instruments, 74 techniques (one source says 73), one mic signal, 3 legato patches (versus 42 in full SSO), about 5.68 GB. Runs in the free Kontakt Player or full Kontakt v7.5.2–8.x and is installed through the Spitfire Audio App. — [Spitfire product page](https://www.spitfireaudio.com/products/spitfire-symphony-orchestra-discover); [Spitfire FAQ](https://support.spitfireaudio.com/en/articles/12808705-spitfire-symphony-orchestra-discover-faq); [AudioTechnology](https://www.audiotechnology.com/by-brand/spitfire-audio/better-sweet-symphony); [MusicTech](https://musictech.com/news/gear/spitfire-symphony-orchestra-discover/)
- BBC SO Discover: free since July 2022, 33 instruments / 47 techniques / one mixed signal / about 200 MB, with no true legato (per a merged 2026-10-23 PR in another project that cites Sound on Sound and MusicTech reviews; secondary source). BBC SO Discover is a proprietary Spitfire plugin, while SSO Discover is a Kontakt library. — [philipdallen/rubato PR #387](https://github.com/philipdallen/rubato/pull/387)
- VSCO 2 Community Edition (Versilian): free, CC0 (public domain), 24-bit WAV, with SFZ versions. Sonatina Symphonic Orchestra is CC Sampling Plus 1.0. Virtual Playing Orchestra's own license wasn't clearly stated in what I found. — [Versilian VSCO CE](https://versilian-studios.com/vsco-community/); [VPO license doc](https://os.zynthian.org/factory_sfz/Other/VPO3-perf/Documentation/license.htm)
- Free guitars: Ample Guitar M Lite has a built-in Strummer and is rated the closest free option to a believable strummed or fingerpicked acoustic guitar. — [Bedroom Producers Blog, 2026](https://bedroomproducersblog.com/free-vst-plugins/guitar/)
- Spitfire LABS works in DawDreamer, as listed in §1. — [DawDreamer compatibility](https://dirt.design/DawDreamer/compatibility.html)

**Mid and premium (prices are list or street; date checked 2026-10-28)**
| Product | Price found | Notes / source |
|---|---|---|
| BBC Symphony Orchestra Core | $449 | [Spitfire collection page](https://www.spitfireaudio.com/en-us/collections/bbc-symphony-orchestra) |
| BBC Symphony Orchestra Professional | $999 list; $599–999 street (Aug 2026) | [Spitfire](https://www.spitfireaudio.com/en-us/collections/bbc-symphony-orchestra); [Equipboard](https://equipboard.com/items/spitfire-audio-bbc-symphony-orchestra) |
| Spitfire Symphony Orchestra (full) | £449, or £499 per a reviewer comment (conflict) | [rubato PR #387](https://github.com/philipdallen/rubato/pull/387) |
| Cinematic Studio Strings | $399 (needs full Kontakt 6+); CS Solo Strings $199 | Third-party, May 2026: [MusicProductionWiki](https://musicproductionwiki.com/articles/best-plugins-for-strings). Not vendor-verified. |
| EastWest ComposerCloud+ (subscription, whole catalog) | $19.99/mo (sale) to $29.99/mo | [Soundsonline](https://www.soundsonline.com/orchestral/hollywood-strings-2); [Sound On Sound](https://www.soundonsound.com/news/eastwest-black-friday-sale) |
| VSL Synchron Strings Pro (Standard) | €445 list / €269 sale (undated); Synchron Strings Bundle €899 / €549 sale | [VSL Synchron strings](https://www.vsl.co.at/synchron/strings) (via search summary) |
| Toontrack Superior Drummer 3 | $399 ($319 crossgrade); Orchestral Edition $599 | [Toontrack SD3](https://www.toontrack.com/product/superior-drummer-3/); [SD3 Orchestral](https://www.toontrack.com/product/superior-drummer-3-orchestral-edition/) |
| Toontrack EZdrummer 3 | $179 ($99 upgrade) | [Toontrack EZD3](https://www.toontrack.com/product/ezdrummer-3/); [Soundshaper review, 2026-10-06](https://www.soundshaper.org/blog/ezdrummer-3) |
| Spectrasonics Omnisphere 3 | about $479 (list $499) | [Full Compass](https://www.fullcompass.com/brand/spe-spectrasonics/software-computers/); [Dubspot](https://blog.dubspot.com/plugins/compare/keyscape-vs-omnisphere-3) |
| Spectrasonics Keyscape | about $379–399 | [Equipboard](https://equipboard.com/items/spectrasonics-keyscape); [Dubspot](https://blog.dubspot.com/plugins/compare/keyscape-vs-omnisphere-3) |
| Spectrasonics Trilian | about $279–399 | [Equipboard](https://equipboard.com/items/spectrasonics-trilian-total-bass-module) |
| NI Komplete 15 Collector's Edition | launch $1,799 / £1,619 (update $499, upgrade from Standard $1,199, from Ultimate $599); UK street about £1,397 | [Sound On Sound](https://www.soundonsound.com/news/native-instruments-komplete-15-incoming); [Andertons](https://www.andertons.co.uk/komplete-15-collectors-edition--esd/) |
| Pianoteq 9 | Stage €139 / Standard €269 / Pro €399 / Studio bundle €929; App Store Stage $139 | [Sound On Sound](https://www.soundonsound.com/node/4934244); [App Store](https://apps.apple.com/app/id6736754495) |
| Audio Modeling SWAM | Solo Strings Bundle $227 (Sweetwater limited offer); SWAM Strings Bundle $699 regular / $468 sale | [Sweetwater](https://www.sweetwater.com/store/detail/SWAMSoStrBun--audio-modeling-swam-solo-strings-bundle); [ILIO](https://www.ilio.com/swam-strings-bundle) |
| NotePerformer 5 (notation playback engine) | $129 perpetual | [Scoring Notes](https://www.scoringnotes.com/news/noteperformer-5/) |
| REAPER | $60 / $225 | [REAPER](https://www.reaper.fm/purchase.php) |

- Sales are frequent: Spitfire sales reportedly run 25–70% off. — [Cakewalk forum](https://discuss.cakewalk.com/topic/80943-bbcso-core/)

**Guitars (realism notes)**
- Ample Guitar: the Strummer auto-detects chords and offers hundreds of patterns.
- Shreddage 3: detailed articulations (tapping, hammer-ons, pull-offs, slides, vibrato) plus fret noise; rated best for rock and metal.
- NI Session Guitarist: pattern-based (hold a chord and it plays recorded strums or riffs); the Strummed Acoustic version is rated most convincing for strumming.

No source ranked them rigorously. The reviews are vendor-adjacent blogs. — [MusicRadar 2026](https://www.musicradar.com/music-tech/plugins/best-guitar-vsts); [ModWheel](https://modwheel.net/guitars/best-acoustic-guitar-vsts); [Pluginoise](https://pluginoise.com/11-best-electric-guitar-plugins/)

**Physical modeling**
- Pianoteq: CLI and headless export are documented in §1. It runs on Windows, macOS and Linux (including ARM boards such as the Raspberry Pi), and App Store licenses are valid across platforms. — [App Store listing](https://apps.apple.com/app/id6736754495); [Sound On Sound](https://www.soundonsound.com/node/4934244)
- Audio Modeling SWAM: "Linux is not supported". Officially it runs on Windows, macOS and iOS; a third-party Wine guide exists. — [Audio Modeling KB](https://kb.audiomodeling.com/support/solutions/articles/206000050983-can-i-run-swam-instruments-on-linux-)

**License restrictions**
- Spitfire EULA §10: the licensee must not use Spitfire libraries to train AI systems or LLMs without express written consent, and use is limited to music creation (search-result excerpt). The URL fetched on 2026-10-28 returned a Splice privacy policy instead of the EULA, so I could not read the clause in full. — [Spitfire EULA](https://www.spitfireaudio.com/info/eula/)
- A secondary source summarizes the Spitfire EULA as forbidding reformatting the samples for another sampler (for example extracting them to SFZ for sfizz). — [rubato PR #387](https://github.com/philipdallen/rubato/pull/387)
- The NI EULA bars use of products and audio content "for purposes of data mining and training artificial intelligence technologies", and bars using the samples to build a competing sample product. — [NI EULA](https://native-instruments.com/en/company/legal-information/end-user-license-agreement)
- The Audiobro EULA explicitly prohibits generative-AI training on its samples. — [Audiobro EULA](https://audiobro.com/eula/)

### Inferences
- Rendering music that Claude composes is "music creation", not AI training, so the clauses found would not appear to block the pipeline. Two caveats:
  - Feeding the rendered stems into a model training set (for example DDSP-SVC or any instrument-synthesis training) would fall under the Spitfire/NI/Audiobro AI-training bans.
  - Running these plugins on a rented cloud server counts as an extra activation. NI and Spitfire activations are per machine, and REAPER allows only one computer in use at a time.
- Rough realism ranking for this use, from the sources plus common practice (treat as an opinion):
  - **Orchestra:** SSO Discover > BBC SO Discover > VSCO 2/Sonatina (free); CSS/CS series, BBC SO Pro, VSL Synchron, EastWest Hollywood (premium).
  - **Piano:** Pianoteq or Keyscape.
  - **Drums:** SD3 > EZD3.
  - **Guitar:** Ample (note by note) or Session Guitarist (strums).
  - **Solo winds and strings:** SWAM (needs very detailed CC data).

### Gaps
- The full text of the Spitfire EULA could not be retrieved, so I couldn't confirm whether it has any clause on automated or server rendering.
- No official 2026 list price was found for CSS, Orchestral Tools (Berlin/Metropolis Ark), Ample Sound, Shreddage, Addictive Drums 2, Komplete 15 Standard/Ultimate, or the SWAM vendor store.
- No objective blind-test realism ranking across vendors was found. Forum opinions are split (see §3).

## 3. MuseScore 4 / Muse Sounds: command-line rendering and quality

### Takeaway
MuseScore Studio can export audio from the CLI with `-o file.mp3` (or `-j` job JSON) and `--sound-profile "Muse Sounds"`. The 4.1-era bug that produced silent files was fixed in 4.2. Muse Hub is Windows/macOS-only; Linux uses MuseSounds Manager. Muse Sounds quality is uneven by instrument, and the input must be a score (MusicXML/MSCZ) rather than a DAW-style performance.

### Cited Findings
- `-o/--export-to` picks the output format from the file extension and runs in converter mode without the GUI. `--sound-profile` is used with `-o .mp3` or `-j` and accepts "MuseScore Basic" or "Muse Sounds". `-j` batch jobs support mp3/ogg/flac/wav/mid outputs. `QT_QPA_PLATFORM` is listed among the environment variables but not explained. — [MuseScore handbook: command-line usage](https://handbook.musescore.org/appendix/command-line-usage)
- Issue #19160: CLI wav/mp3/flac export with Muse Sounds came out completely silent in 4.1.1. The cause was "The MuseSampler module is not initialised in command line mode." It was fixed in PR #19217 (closed 2023-09-05) and shipped in 4.2. A reporter also saw much lower export levels (−37 dBFS versus −15 dBFS in MS3) because normalization was missing (issue #16105). — [MuseScore issue #19160](https://github.com/musescore/MuseScore/issues/19160)
- Other export issues: Muse Sounds staves drift out of sync if the sample rate isn't 48 kHz (#19232). Some 4.6 exports crash (#30342). Parts muted in the Mixer export silently (#27025, done for 4.6). — [#19232](https://github.com/musescore/MuseScore/issues/19232); [#30342](https://github.com/musescore/MuseScore/issues/30342); [#27025](https://github.com/musescore/MuseScore/issues/27025)
- A forum post says MuseScore 4 audio export "only renders in real-time, not offline faster than realtime". — [musescore.org forum](https://musescore.org/en/node/345238)
- Muse Hub is officially supported only on Windows and macOS. Linux users get Muse Sounds through MuseSounds Manager (DEB/RPM/TAR, x86_64; minimum 2.2.0). Support articles are dated May–Aug 2026. — [MuseHub system requirements](https://support.musehub.com/en/articles/15070585-system-requirements); [Getting MuseSounds on Linux](https://support.musehub.com/en/articles/15070617-getting-musesounds-on-linux); [MuseSounds missing](https://support.musehub.com/en/articles/15070619-musesounds-missing-in-musescore-studio)
- Quality: forum users are split. Some find Muse Sounds strings "more expressive and ... tonally more realistic", others call the library "wildly variable: they're either very good or very bad". It adds unwritten dynamic changes ("natural variations and interpretation"), which some users find distracting. — [Steinberg forum thread](https://forums.steinberg.net/t/musescore-4-muse-sounds/822977?page=8)
- NotePerformer 5 ($129) dropped third-party VST3 hosting (NPPE) in 5.0.1, days after its May 2025 launch. It has no MuseScore integration because MuseScore does not support third-party audio plugins. — [Scoring Notes: NotePerformer reverses course](https://www.scoringnotes.com/news/noteperformer-reverses-course/); [musescore.org](https://musescore.org/en/node/367473)

### Inferences
- MuseScore + Muse Sounds suits a "score → decent orchestral/choral audio" path because its articulation and dynamics interpretation is automatic: Claude would write MusicXML, not keyswitch/CC data. Note-level control over timbre is limited to what notation and the mixer expose. It cannot mix in arbitrary VSTs.
- A Linux server path through MuseSounds Manager plus `QT_QPA_PLATFORM=offscreen` is plausible but unverified. Real-time-only export would make re-renders slow.

### Gaps
- No source confirms whether 4.6 CLI audio export with Muse Sounds runs faster than real time, works headless on Linux, or needs a Muse account to be logged in.
- No measured comparison of Muse Sounds against commercial libraries.

## 4. Realism from performance data: articulations, CCs, humanization, and tools that generate it

### Takeaway
With modern libraries, most of the remaining realism gap comes from performance data:
- correct articulation switching (keyswitch, UACC/CC32, program change)
- continuous CC1 (dynamics crossfade) and CC11 (expression) curves
- velocity for short notes
- legato note overlaps
- timing offsets
- guitar strum direction and pattern
- drum ghost-note velocities

Neural "performance rendering" research is still piano-centric (RenCon 2025, Pianist Transformer, Midihum). There's no off-the-shelf orchestral or band humanizer model, so the pipeline has to generate these curves itself, by rule or by learned model.

### Cited Findings
- Most libraries use CC1 to crossfade dynamic layers and CC11 as plain volume/expression. Practitioners disagree on combining them: some say ride CC1 and use CC11 only as a last resort, others say CC1 alone is not enough on some libraries. — [VI-Control: CC1/CC11/velocity](https://vi-control.net/community/threads/rant-about-cc1-cc11-and-velocity.168479/); [VI-Control: CC11 approaches](https://vi-control.net/community/threads/what-are-you-doing-with-your-cc11-modulation-lets-hear-your-different-approaches.138488/)
- Spitfire UACC: send CC32 with a fixed value to select an articulation (for example 26 = Legato muted, 52 = Short marcato, 56 = pizzicato in Chamber Strings). Spitfire says CC32 values are consistent across its products, older ones excepted. Exceptions exist: Studio Woodwinds Pro marcato works at 41 though the UI says 52. UACC KS instead uses the velocity of a keyswitch note (default C-2). — [Spitfire support](https://support.spitfireaudio.com/en/articles/11816123); [syntheticorchestra.com](https://syntheticorchestra.com/blog/10.shtml); [VI-Control UACC thread](https://vi-control.net/community/threads/resolved-spitfire-uacc-not-working-correctly.92528/post-4545388)
- Performance-rendering research:
  - RenCon 2025 at ISMIR 2025 revived the expressive performance rendering competition. It notes that MIDI velocity isn't tied to loudness, so a velocity mapping doesn't transfer between instruments. One entry, "Midihum", uses XGBoost with 400+ engineered features to humanize velocity. — [RenCon 2025 paper (NIME 2026)](https://nime.org/proceedings/2026/nime2026_79.pdf); [arXiv 2605.02059](https://arxiv.org/pdf/2605.02059)
  - Pianist Transformer (arXiv 2512.02652): a self-supervised score→performance model with eight tokens per note (velocity, duration, IOI, pedal). — [arXiv](https://arxiv.org/html/2512.02652v2)
  - RenderBox: expressive performance rendering with text control. — [arXiv 2502.07711](https://arxiv.org/pdf/2502.07711)
  - A 2025 U-Net model fills in MIDI velocity only, leaving timing untouched. — [arXiv 2508.07751](https://arxiv.org/html/2508.07751v1)
  - MIDI-VALLE renders expressive piano MIDI straight to audio. — [EmergentMind summary](https://www.emergentmind.com/topics/midi-valle)
- Notation playback engines that interpret phrasing automatically: NotePerformer (MusicTech 8/10 for realistic phrasing, weak on solo strings and jazz) and Muse Sounds (adds its own dynamics). — [MusicTech review](https://musictech.com/reviews/noteperformer-for-sibelius/); [Steinberg forum](https://forums.steinberg.net/t/musescore-4-muse-sounds/822977?page=8)
- Guitar strumming automation lives in the instruments themselves: Ample's Strummer and Session Guitarist's patterns. Session Guitarist Strummer is a script-based Kontakt `.nki` that had offline dropouts in DawDreamer before Kontakt 7.6. — [Bedroom Producers Blog](https://bedroomproducersblog.com/free-vst-plugins/guitar/); [DawDreamer #180](https://github.com/DBraun/DawDreamer/issues/180)
- Expression-map and articulation-set ecosystems:
  - Babylonwaves Art Conductor (€99): ready-made maps for Cubase/Nuendo (Expression Maps), Logic (Articulation Sets), Studio One (Sound Variations), Digital Performer and Cakewalk, plus a Dorico set (Sept 2025) covering 1,000+ libraries. "Art Conductor 26.0" is dated 2026-02-26. — [KVR news](https://www.kvraudio.com/news/babylonwaves-releases-art-conductor-11-2-62971); [KVR news print](https://www.kvraudio.com/news-print.php?id=64881)

### Inferences
- **Library vs MIDI:** a good library sets the timbre ceiling (number of dynamic layers, true legato, round-robins, mic positions). The MIDI decides whether that ceiling is reached. For sustained instruments (strings, brass, winds, SWAM), CC1/CC11 curves and legato overlaps matter more than the library; for percussive ones (piano, drums, plucked guitar), velocity and timing are most of it. This is a practitioner opinion, not a measured split; no source quantifies it.
- **Practical generator** (Claude writes code that emits MIDI):
  - Shape CC1 per phrase: swell into long notes, decay on releases.
  - Add CC11 for fine shaping.
  - Overlap legato notes by 20–80 ms, with velocity standing for transition speed in libraries that use it.
  - Pick short versus long articulations from note length.
  - Apply seeded timing jitter of a few ms, larger for sections.
  - Alternate down/up strums on 8ths and 16ths.
  - Set drum ghost-note velocity around 20–40 and accent backbeats.
  
  The numbers are typical practice from prior knowledge, not sourced.
- Midihum-style velocity humanizers and Pianist Transformer could feed piano parts before Pianoteq or Keyscape. Nothing comparable for orchestral or guitar parts was found.

### Gaps
- No open neural model for orchestral, guitar or drum humanization of MIDI (CC curves, articulations) was found.
- No source with pick-direction control documented for specific guitar libraries.

## 5. Linux headless GPU server vs the Windows 11 desktop

### Takeaway
Commercial sample libraries (Kontakt/NI, Spitfire, Toontrack, Spectrasonics, SWAM) belong on the Windows 11 PC. On Linux they are unsupported (SWAM explicitly) or fragile under Wine/yabridge, which also needs a virtual X display. The AutoDL server suits native-Linux engines: sfizz with free SFZ libraries, FluidSynth, Pianoteq, u-he synths, Muse Sounds via MuseSounds Manager (unverified headless), and neural models. Its GPU does nothing for sample playback.

### Cited Findings
- yabridge (official page: GitHub) bridges Windows VST2/VST3/CLAP to Linux and is tested with Wine Staging 9.21. — [yabridge GitHub](https://github.com/robbert-vdh/yabridge)
- Kontakt 8 under Wine/yabridge broke with Native Access 2 (NI forum, Jan 2025). Users report downgrading Wine to 9.21, or an unofficial guide using a patched wine-cachyos build. Some couldn't install the Kontakt 8 Player at all. — [NI community](https://community.native-instruments.com/discussion/41978/how-much-would-you-charge-to-make-a-linux-version); [VI-Control](https://vi-control.net/community/threads/arch-linux-installing-kontakt-native-access-help-needed.166116/); [Kontakt-8-Portable-Linux-Guide (unofficial)](https://github.com/Ferziellee/Kontakt-8-Portable-Linux-Guide)
- Wine has no fully headless mode; the usual workaround is Xvfb (`Xvfb :99 & export DISPLAY=:99`). yabridge has no GUI of its own, so the display requirement comes from the plugin GUIs. — [Wine bug 49500](https://list.winehq.org/pipermail/wine-bugs/2020-July/538535.html); [scivision Xvfb](https://scivision.dev/xvfb-on-windows-subsystem-for-linux)
- Native Linux support:
  - Pedalboard VST3 (glibc > 2.27).
  - DawDreamer `.so`/`.vst3` (u-he Diva and Repro confirmed).
  - REAPER for Linux.
  - Pianoteq (Linux, including ARM).
  - Ardour/Carla/sfizz.
  - MuseSounds Manager for Muse Sounds.
  
  — [Pedalboard](https://github.com/spotify/pedalboard); [DawDreamer compatibility](https://dirt.design/DawDreamer/compatibility.html); [App Store Pianoteq](https://apps.apple.com/app/id6736754495); [MuseHub Linux](https://support.musehub.com/en/articles/15070617-getting-musesounds-on-linux)
- Audio Modeling SWAM: Linux not supported. — [Audio Modeling KB](https://kb.audiomodeling.com/support/solutions/articles/206000050983-can-i-run-swam-instruments-on-linux-)
- Spitfire's BBC SO Discover is a proprietary plugin, and its EULA reportedly forbids converting samples to SFZ, so there is no legal "port to sfizz" path. — [rubato PR #387](https://github.com/philipdallen/rubato/pull/387)

### Inferences
- Recommended split:
  - **Windows 11 PC:** all VST3 sample libraries, authorized once through Native Access / Spitfire App / Toontrack Product Manager, then rendered by Pedalboard/DawDreamer/REAPER CLI. Claude Code runs here, so no remote orchestration is needed.
  - **AutoDL:** the existing SVC vocal pipeline, plus optional Linux-native instrument renders (sfizz/Pianoteq) if CPU is free.
- Running Kontakt/Spitfire on AutoDL would cost extra activations, needs Wine + Xvfb + yabridge (whose hosts are DAWs, not Pedalboard), and has a real risk of silent or dropout renders. It is not recommended.

### Gaps
- No source confirms that Pedalboard or DawDreamer on Linux can load a yabridge-wrapped Windows VST3 (yabridge is tested with DAW hosts).
- No source confirms that Spitfire, Toontrack or Spectrasonics plugins have native Linux builds (I believe they don't, but found no 2026 confirmation).

## 6. Describing articulations and expression once and mapping them to each library automatically (orchestration changes often)

### Takeaway
There is an open standard for library-independent articulations: the MIDI 2.0 Orchestral Articulation Profile (M2-123-UM, adopted around NAMM 2024 and described as finalized in Feb 2026). It carries articulation in the Note On attribute and defines "articulation equivalence" across instrument families. Commercial VST3 libraries still expect MIDI 1.0 keyswitches, CC32 (Spitfire UACC) or program changes. The practical design is an internal articulation vocabulary plus per-library YAML mapping tables that compile to keyswitches/CCs at render time. Existing formats are host-specific (Cubase .expressionmap, Logic Articulation Sets, Studio One Sound Variations, Dorico expression maps, REAPER Reaticulate .reabank). Only Reaticulate's is plain text and open.

### Cited Findings
- The MIDI 2.0 Orchestral Articulation Profile (M2-123-UM 1-0) was one of six profiles adopted around NAMM 2024 (one page dates the release to April 2024). It encodes articulation in the MIDI 2.0 Note On Attribute Type/Data fields and supports "articulation equivalence" across eight instrument categories. A Feb 2026 MIDI Association update calls it finalized, alongside the Drum Note Mapping and Piano profiles, and a demo was planned for NAMM 2026. A third-party vendor (MultitrackStudio) cites "over 100 articulations" (secondary). — [MIDI.org: state of MIDI 2.0 (Feb 2026)](https://midi.org/the-state-of-midi-2-0-high-resolution-performance-and-the-rise-of-profiles-update-feb-2026); [MIDI.org orchestral tag](https://midi.org/tag/orchestral); [MultitrackStudio articulations](https://multitrackstudio.com/articulations.php)
- Reaticulate (free, REAPER) extends REAPER's plain-text `.reabank` program-change banks to trigger the custom events that switch articulations. The file is `Reaticulate.reabank` in REAPER's Data folder. There's no GUI bank editor (text editing is the norm); newer versions import banks from the clipboard or drag-and-drop. Community bank collections exist, including a GitHub repo and VSL BBO banks. — [Reaticulate site](https://backiee.wasmer.app/http_reaticulate_com); [Levitanus/reaticulate-banks](https://github.com/Levitanus/reaticulate-banks); [VSL forum](https://forum.vsl.co.at/topic/57225/for-reaper-users-reaticulate-banks-for-bbo-brass-packs-and-bbo-ganymede)
- Reaticulate bank lines use the syntax `//! c=short-dark i=spiccato o=cc:32,42/cc:32,48`: an articulation outputs CC32 values, which makes it Spitfire UACC-compatible. — [VI-Control Reaticulate thread](https://vi-control.net/community/threads/reaticulate-articulation-management-for-reaper-0-2-0-now-available.66851/page-18)
- Converters and generators:
  - Composer Tools Pro converts its presets to and from Cubase Expression Maps (one articulation group per map).
  - An online JSON-based expression-map generator (by Marius Kappes) emits `.expressionmap`.
  - XDAW is mentioned as converting expression maps to Logic Articulation Sets.
  - A Python repo "Expression-2-Reaticulate" (Kabraxist; 8 stars, last push over a year ago) apparently converts expression maps to Reaticulate.
  - r-koubou's ArticulationUtility is obsolete and points to "KeySwitchManager". The KeySwitchManager GitHub URL returned 404 on 2026-10-28.
  
  — [Composer Tools Pro converter](https://www.midikinetics.com/composer-tools-pro-expression-map-converter/); [VI-Control expression map workflow](https://vi-control.net/community/threads/cubase-expression-maps-a-workflow-to-build-them-quicker.160313/); [repos.ecosyste.ms expressionmap topic](https://repos.ecosyste.ms/topics/expressionmap)
- Art Conductor (€99) builds its maps separately for each platform (Cubase, Logic, Studio One, DP, Cakewalk, Dorico) rather than converting them. It covers 1,000+ libraries, so it is a ready source of per-library keyswitch/UACC data. — [KVR Art Conductor 11.2](https://www.kvraudio.com/news/babylonwaves-releases-art-conductor-11-2-62971)
- Spitfire's UACC values are designed to be consistent across products (with older-product and per-library exceptions), and the Expert View shows each value. — [Spitfire support](https://support.spitfireaudio.com/en/articles/11816190-using-logic-pro-articulation-sets-with-spitfire-libraries); [VI-Control](https://vi-control.net/community/threads/resolved-spitfire-uacc-not-working-correctly.92528/post-4545388)
- MuseScore/Muse Sounds maps notation articulations (staccato, accents, techniques) to its sounds internally. Third-party libraries in Muse Hub appear under Muse Sounds. — [Scoring Notes: Muse Hub platform](https://www.scoringnotes.com/news/muse-hub-transforms-into-a-platform-for-playback-options-and-audio-tools/); [MuseScore handbook](https://handbook.musescore.org/appendix/command-line-usage)

### Inferences
- **Recommended data model** (for Claude's code):
  - The score/part stores per-note `articulation` (canonical names; you could borrow the MIDI 2.0 Orchestral Articulation Profile categories), `dynamic` (a 0–1 curve) and `timbre` hints (mute, sul pont, mic mix).
  - Each `library_map/<library>.yaml` maps canonical articulation → {keyswitch note | CC32 value | program change | channel}, dynamic → {CC1 range, CC11 range, velocity curve}, plus legato rules and preferred lead-in time.
  - A compiler pass emits library-specific MIDI.
  
  Reassigning a part from flute to oboe, or Spitfire to VSL, then only changes the map lookup. Unmapped articulations need a fallback chain (for example `marcato → staccato → short`). Reaticulate `.reabank` text can be generated from the same YAML if REAPER is used.
- Library keyswitches change between versions, as the UACC discrepancies show, so each map should be pinned to a library version and checked with a smoke-render test per articulation.

### Gaps
- No commercial VST3 library was found that accepts the MIDI 2.0 Orchestral Articulation Profile directly, and no Python implementation of it was found.
- KeySwitchManager's formats and status couldn't be verified (404). No maintained, general-purpose open Python library for articulation mapping was found.
- The Dorico expression map file format and its machine readability weren't researched in depth.

## 7. Re-render speed and determinism after small changes

### Takeaway
Render each part to its own stem with its own plugin instance and cache stems by a hash of the inputs; a one-note or one-instrument change then re-renders only that stem. Output is usually bit-identical when you reuse the same plugin binary, preset state, sample rate and buffer size, load a fresh instance per render, and seed all humanization in your own code. Two things break it: plugin-internal round-robin counters and random generators (Kontakt's can't be reset from the host), and some offline-render dropout bugs. Verify with output hashes or null tests rather than assuming.

### Cited Findings
- Kontakt's built-in ("global") round-robin counter can't be reset or automated from a DAW, so scripts are the workaround. A KSP-scripted random round robin that resets its seed at transport start "will always render the same result". — [KVR forum](https://www.kvraudio.com/forum/viewtopic.php?t=393914); [VI-Control: round robin reset](https://vi-control.net/community/threads/round-robin-reset-how.74277/); [Normal Sounds RR script](https://normalsounds.com/blog/random-round-robin-with-kontakt-scripting/)
- Design pattern from another project (Strudel/Stave): randomness derived from a hash of time position rather than a stateful stream makes "two independent renders of the same document produce identical values". — [Stave issue #1395](https://github.com/MrityunjayBhardwaj/Stave/issues/1395)
- Pedalboard `reset`: set it to False only when processing one continuous stream in chunks. On reset, plugin parameter values remain unchanged. The "Unknown" reload type forces full reinstantiation on every reset. Pedalboard also suggests padding with silence or reloading the plugin to avoid audio bleeding between `process()` calls. — [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html); [Pedalboard PyPI](https://pypi.org/project/pedalboard/0.9.2)
- Kontakt offline renders can drop samples nondeterministically: some users say raising the buffer improves the odds but "still gives the same problems from time to time". — [VI-Control](https://vi-control.net/community/threads/kontakt-dropouts-only-while-rendering-exporting-and-freezing.123886/)
- DawDreamer has a multiprocessing guide ("Rendering on a Thread Pool", "Thread-Safety Rules"). Pedalboard warns that some plugins misbehave on background threads. — [DawDreamer docs](https://dirt.design/DawDreamer/); [Pedalboard API reference](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- Pianoteq exports MIDI → WAV per file and can batch whole folders. MuseScore 4 export reportedly runs in real time only. — [Modartt forum](https://forum.modartt.com/viewtopic.php?id=9387); [musescore.org](https://musescore.org/en/node/345238)

### Inferences
- **Caching key per stem:** sha256 of (compiled library-specific MIDI bytes, plugin file hash or version, saved plugin state bytes, sample rate, buffer size, render length, host version). Tempo and length changes invalidate every stem, but most edits touch one part.
- **Determinism checklist:**
  - Fresh plugin instance per stem render, which resets RR counters and any free-running LFOs/random.
  - Fixed buffer size.
  - Single-threaded per plugin instance (consider disabling Kontakt multiprocessor support).
  - Kontakt DFD preload at max or Sampler mode, plus offline mode.
  - Seeded RNG for all humanization in Python.
  - Leading silence or pre-roll for plugins with async sample loading (`initialization_timeout`, LABS `time.sleep(1)`).
  - Render twice and compare hashes in CI.
  
  Exact bit-identity also depends on whether the plugin uses internal randomness (analog-drift synths, random RR) with no seed control. Those cases need a tolerance-based null test (for example residual < −90 dBFS) instead.
- **Speed:** plugin load and sample preload, not DSP, likely dominate small re-renders for big Kontakt/Spitfire patches. Keeping a long-lived render worker that holds instruments loaded, and resetting state between stems, would trade some determinism risk for speed. This is unmeasured.

### Gaps
- No measured load or render times found for Kontakt, Spitfire or SD3 in Pedalboard/DawDreamer, or for Pianoteq offline export speed.
- No vendor documentation on seeding or disabling round-robin randomness in Spitfire, Toontrack or Spectrasonics plugins.

## 8. Saving and recalling exact instrument presets/state for reproducible renders

### Takeaway
Pedalboard (`raw_state` bytes, `preset_data` as .vstpreset bytes, `load_preset`) and DawDreamer (`save_state`/`load_state`, `load_vst3_preset`, `load_preset` for .fxp) can both capture and restore full plugin state from code without opening a GUI. Store those blobs alongside the score in git/LFS, keyed by plugin version. Pianoteq takes `--preset`/`--fxp` on the CLI, and REAPER keeps state inside .rpp projects.

### Cited Findings
- Pedalboard:
  - `raw_state` is "A bytes object representing the plugin's internal state", "usually an XML-encoded string prefixed with an 8-byte header and suffixed with a single null byte". Invalid data may crash the plugin.
  - `preset_data` gets or sets state "as bytes in .vstpreset format".
  - `load_preset()` loads `.vstpreset` files.
  - `parameter_values=` on `load_plugin` sets named parameters.
  
  — [Pedalboard API reference (offset 100k)](https://spotify.github.io/pedalboard/reference/pedalboard.html)
- DawDreamer:
  - `save_state(path)`/`load_state(path)` store complete plugin state (parameters and internal buffers) in DawDreamer-specific files, and `load_state` works without opening the editor.
  - `load_preset()` loads `.fxp`; `load_vst3_preset()` loads `.vstpreset`.
  - `get_patch()`/`set_patch()` capture normalized parameter tuples.
  - The compatibility table lists Kontakt's preset type as `.nkm` and says some plugins don't support programmatic preset loading.
  
  — [DawDreamer plugin processor guide](https://dirt.design/DawDreamer/user_guide/plugin_processor.html); [DawDreamer compatibility](https://dirt.design/DawDreamer/compatibility.html)
- Pianoteq CLI: `--preset NAME`, `--fxp FILE`, `--midimapping NAME`, `--no-prefs` (start without saved preferences, useful for reproducibility). — [Modartt forum --help](https://forum.modartt.com/viewtopic.php?id=11200)
- REAPER CLI: `-cfgfile` for an isolated resource directory and `-template`. — [ReaTeam REAPER-CLI.md](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)

### Inferences
- **Workflow:** for each library/patch, open the GUI *once* on Windows (Pedalboard `show_editor` or DawDreamer `open_editor`) to choose the instrument, mics and settings. Then save `raw_state`/`preset_data`, or the DawDreamer state file, as `presets/<library>/<patch>@<plugin-version>.bin`. All later renders are headless.
- A Kontakt state blob references library files on disk by path, so moving or updating libraries breaks recall. Record library versions and paths in the manifest. I also believe REAPER stores each FX's state as base64 chunks inside the plain-text .rpp, which makes REAPER projects diffable recall files; that is from prior knowledge and wasn't verified this session.
- The pipeline should record plugin and library versions and refuse to render if they differ from the manifest (or warn and re-baseline the stem cache).

### Gaps
- No source confirms that Kontakt 8 / Spitfire plugin state round-trips byte-exact through Pedalboard `raw_state` (it needs a local test: save, reload, re-save, compare).

## 9. Recommended stacks at three budget levels (for an agent pipeline: Windows 11 renders instruments, AutoDL does vocals)

### Takeaway
All three tiers keep the same architecture: Python on Windows generates library-specific MIDI from a library-independent score, renders one stem per part via Pedalboard (fallback DawDreamer, then REAPER CLI), caches stems by hash, and mixes. The budget only changes which libraries sit behind the YAML maps.

### Cited Findings
- Building blocks and costs:
  - Hosts and tools: Pedalboard, DawDreamer and sfizz are free/open source; REAPER $60/$225.
  - Free sounds: SSO Discover (Kontakt Player), BBC SO Discover, LABS, VSCO 2 CE (CC0), Ample Guitar M Lite (free), Muse Sounds (free).
  - Paid: Pianoteq 9 Stage €139 / Standard €269; EZdrummer 3 $179; SD3 $399; BBC SO Core $449 / Pro $999; CSS about $399 (needs full Kontakt); Keyscape about $379–399; Omnisphere 3 about $479; Komplete 15 CE launch $1,799; ComposerCloud+ $19.99–29.99/mo; SWAM bundles $227–699; Art Conductor €99.
  
  — sources as cited in §1–§6 ([REAPER](https://www.reaper.fm/purchase.php), [SSO Discover](https://www.spitfireaudio.com/products/spitfire-symphony-orchestra-discover), [VSCO CE](https://versilian-studios.com/vsco-community/), [Toontrack EZD3](https://www.toontrack.com/product/ezdrummer-3/), [Toontrack SD3](https://www.toontrack.com/product/superior-drummer-3/), [Spitfire BBC SO](https://www.spitfireaudio.com/en-us/collections/bbc-symphony-orchestra), [Sound On Sound Pianoteq 9](https://www.soundonsound.com/node/4934244), [Sound On Sound Komplete 15](https://www.soundonsound.com/news/native-instruments-komplete-15-incoming), [MusicProductionWiki CSS](https://musicproductionwiki.com/articles/best-plugins-for-strings))

### Inferences
- **Free ($0):**
  - Strings, brass and winds: SSO Discover (has true legato) plus BBC SO Discover for extra colours, with Spitfire LABS for pads and textures.
  - Guitar: Ample Guitar M Lite.
  - Fallback/server: VSCO 2 CE or Sonatina via sfizz.
  - Synths: free synths. Surge XT and Vital are common choices but weren't verified this session.
  - Drums: no free drum sampler of SD3 quality was found (gap).
  - Host: Pedalboard. Optional alternative for orchestral sketches: MuseScore CLI with Muse Sounds.
- **About $500:** REAPER $60 + Pianoteq 9 Standard €269 (piano, EP, physical-model extras; renders on both Windows and Linux) + EZdrummer 3 $179, roughly $520 total. The orchestra stays on SSO/BBC SO Discover.
  - Alternative: put the money into BBC SO Core $449 for the orchestra and keep piano and drums free.
  - Use Reaticulate in REAPER as the fallback render path, with banks generated from the YAML maps.
- **Unlimited:**
  - Komplete 15 Collector's Edition (full Kontakt, Session Guitarist, NI keys, synths).
  - Cinematic Studio Series or BBC SO Pro / VSL Synchron for orchestra.
  - Superior Drummer 3, Keyscape + Omnisphere 3 + Trilian, Pianoteq Pro.
  - SWAM solo instruments for exposed wind and string lines (needs detailed CC data).
  - Ample/Shreddage guitars, Art Conductor maps (€99) to seed the per-library YAML tables.
  - Render on the Windows 11 PC; consider a second Windows render box rather than Linux/Wine if throughput matters.
  - The license constraint on any tier: do not use rendered stems as AI training data (Spitfire/NI/Audiobro EULAs).

### Gaps
- No comparative test of which free drum or bass instruments are most realistic; no free drum library was researched in detail.
- Prices for Orchestral Tools, Ample Sound, Shreddage and Addictive Drums 2 weren't found. Addictive Drums 2 is also listed as not working in DawDreamer (#67).
