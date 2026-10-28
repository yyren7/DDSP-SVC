# MCP servers, Claude skills/plugins and DAW/notation remote-control interfaces for agent-driven composition and arrangement (state as of 2026-10-28)

Method note: star counts, last-push dates, licenses and open-issue counts (GitHub's `open_issues_count`, which includes open PRs) were read from the GitHub REST/search API on 2026-10-28 unless stated otherwise; PyPI release data from the PyPI JSON API on the same day. "Last push" means the most recent push to any branch, not necessarily a release. Anything last pushed before 2025-10 is flagged as possibly stale.

## Q1. Which MCP servers exist for DAWs (Ableton, REAPER, Bitwig, FL Studio, Logic, Cubase, Studio One, Ardour, LMMS, others), which are maintained, and which are most capable?

### Takeaway
Only Ableton Live and REAPER have several actively maintained, capable MCP servers (all community-built; none from the vendor). For Ableton the ecosystem is the largest by stars (ahujasid/ableton-mcp, 3.2k stars), but the most capable servers are the newer, smaller ones (LivePilot, wstierhout, bschoepke, Producer Pal). For REAPER there are about six maintained servers, with TwelveTake and xDarkzx the most complete for note-level MIDI work. Bitwig, FL Studio, Logic, Cubase, Ardour and LMMS servers are either thin, platform-restricted (Logic is macOS-only), blocked by the host's API (FL Studio cannot load plugins or render), or abandoned.

### Cited Findings

**Ableton Live (Windows/macOS only)**
- ahujasid/ableton-mcp: 3,255 stars, last push 2026-09-22, MIT, 49 open issues+PRs (the web page showed 15 issues and 34 PRs). It is a Remote Script that opens a socket server inside Live, plus a Python MCP server. Advertised features: create/modify MIDI and audio tracks; create, edit and trigger clips; add notes to MIDI clips; load instruments and effects "from Ableton's library"; transport; tempo; and "Build full songs autonomously in Arrangement View". It does not list export/render. — [GitHub](https://github.com/ahujasid/ableton-mcp)
- ahujasid/ableton-mcp limitations, from its README: complex arrangements may need to be broken into smaller steps; it is designed for Ableton's default devices and browser items; timeouts can occur; connection problems often need a restart of both Claude and Live; do not run it in two clients at once. Anonymous telemetry is on by default (`ABLETON_MCP_DISABLE_TELEMETRY=true` turns it off). — [GitHub](https://github.com/ahujasid/ableton-mcp)
- ahujasid/ableton-mcp on PyPI: `ableton-mcp` 1.4.5 uploaded 2026-09-22, 17 releases since 2025-03-20. — [PyPI](https://pypi.org/project/ableton-mcp/)
- Simon-Kansara/ableton-live-mcp-server (built on AbletonOSC): 396 stars, last push 2025-03-26. **Possibly stale.** — [GitHub](https://github.com/Simon-Kansara/ableton-live-mcp-server)
- uisato/ableton-mcp-extended: 280 stars, last push 2026-05-07, MIT, Live 11+ (any edition). Features: add, delete, transpose and quantize notes in clips, plus batch note edits. Its roadmap marks "VST Plugin Support" as done, with third-party parameters reached through Live's "Configure" function. — [GitHub](https://github.com/uisato/ableton-mcp-extended)
- bschoepke/ableton-live-mcp: 235 stars, last push 2026-10-06, MIT. The agent can eval arbitrary Python inside Live, so it "can do pretty much anything that is possible via Ableton's Object model". It ships an "Agent Audio Tap" Max for Live device that captures audio at any point in the signal chain for analysis. The README says the agent can be told to use third-party plugins such as Serum and Keyscape. It was tested only on Live Suite 12.3.8 on macOS, and the author warns it "could corrupt" a set. — [GitHub](https://github.com/bschoepke/ableton-live-mcp)
- dreamrec/LivePilot: 90 stars, last push 2026-10-22, license NOASSERTION; 474 tools in 57 domains; Live 12; macOS and Windows. Architecture: a Remote Script on TCP 9878, with all LOM calls run on Live's main thread, plus an optional M4L bridge that reaches deeper LOM areas the ControlSurface API cannot. To keep the model's tool surface small it now exposes only a 26-tool loop plus `search_tools`/`call_tool`. — [GitHub](https://github.com/dreamrec/LivePilot)
- wstierhout/ableton-live-mcp: 62 stars, last push 2026-10-23, MIT, 156 tools, Live 11 or 12. Features: write and edit MIDI notes (including probability); load instruments and effects on any track; read and set any device parameter; place and read arrangement clips; write clip automation; "record a section to a WAV without the Export dialog"; "diff the session since the last check". Offline tools (no Live needed) summarize, extract MIDI from, diff and lint saved `.als` files. `ABLETON_TOOLSETS` limits which tool groups load. — [GitHub](https://github.com/wstierhout/ableton-live-mcp)
- jpoindexter/ableton-mcp: 59 stars, last push 2026-05-01, MIT; "200+ tools for near-complete LOM coverage". Features: get notes in a range, move notes (time and pitch), replace all notes, a REST API, and an M4L device. — [GitHub](https://github.com/jpoindexter/ableton-mcp). The glincker/ableton-skills compatibility table calls it "less actively maintained" and recommends uisato's server. — [GitHub](https://github.com/glincker/ableton-skills)
- xiaolaa2/ableton-copilot-mcp (built on ableton-js): 93 stars, last push 2026-07-29, MIT. — [GitHub](https://github.com/xiaolaa2/ableton-copilot-mcp)
- adamjmurray/producer-pal: 349 stars, last push 2026-10-28. The README states GPL-3.0 (the API reports NOASSERTION). It runs as a Max for Live device (v2.4.0), a Claude Desktop extension, or `npx producer-pal`. It also offers a REST API, so "scripts, coding agents, and your own tools can read and edit a Live Set with plain HTTP", plus an Agent Skill for Claude Code. — [GitHub](https://github.com/adamjmurray/producer-pal); [producer-pal.org](https://producer-pal.org)
- user1303836/kumi: 23 stars, last push 2026-10-28, 31 open issues, MIT. It is a standalone terminal agent (not an MCP server) for Ableton Live 12 (macOS 13+ / Windows 10/11), REAPER 7+ (macOS/Windows/Linux) and Renoise 3.5+, with a choice of model (Anthropic API included). It is tested with Live and REAPER on macOS; per the README, use on Windows and Linux "is new". — [GitHub](https://github.com/user1303836/kumi)

**REAPER (Windows/macOS/Linux)**
- bonfire-systems/reaper-mcp: 166 stars, last push 2026-10-25, MIT, 0 open issues; PyPI `reaper-mcp-server` 0.4.0 released 2026-10-25. It has about 60 tools: project/tempo/time signature; tracks, buses and sends; track templates; `create_midi_item`, `add_midi_note`, `create_chord_progression`, `create_drum_pattern`; `add_fx`, `get/set_fx_parameter`, `load_fx_preset`; volume/pan automation; `render_project`, `render_stems`, `render_regions`; loudness and spectrum analysis. It requires REAPER 7 and goes through python-reapy's "distant API". — [GitHub](https://github.com/bonfire-systems/reaper-mcp); [PyPI](https://pypi.org/project/reaper-mcp-server/)
- python-reapy, which bonfire and wegitor depend on: last PyPI release 0.10.0 on 2020-12-29; repo last push 2024-01-27, 32 open issues. **Stale dependency.** — [PyPI](https://pypi.org/project/python-reapy/); [GitHub](https://github.com/RomeoDespres/reapy)
- dschuler36/reaper-mcp-server: 132 stars, last push 2026-10-16, MIT. **Read-only by design.** It parses `.RPP` files (tempo, tracks, FX chains, items, routing), lists the installed plugins from REAPER's plugin cache (VST2/VST3/AU/JS/CLAP), and analyzes audio sources (pre-FX). — [GitHub](https://github.com/dschuler36/reaper-mcp-server)
- xDarkzx/Reaper-MCP: 109 stars, last push 2026-10-25, Apache-2.0, v0.8.3; 181 tools in 26 modules. It uses a file-based Lua IPC bridge (`command.json`/`response.json` in `%TEMP%\reaper_mcp` on Windows, `/tmp/reaper_mcp` on Linux), and CI runs 3 OSes × 4 Python versions. — [GitHub](https://github.com/xDarkzx/Reaper-MCP)
- TwelveTake-Studios/reaper-mcp: 96 stars, last push 2026-10-21, MIT, v1.9.3; PyPI `twelvetake-reaper-mcp` has 27 releases since 2025-12-11. It has 180 tools, uses a Lua bridge and a JSON-file mailbox, and runs on "stock REAPER only". Its "full live suite" passes through REAPER 7.79. `--install-bridge --autostart` adds the bridge to `__startup.lua`, and every AI change is "one named step in REAPER's undo history". — [GitHub](https://github.com/TwelveTake-Studios/reaper-mcp); [PyPI](https://pypi.org/project/twelvetake-reaper-mcp/)
- shiehn/total-reaper-mcp: 87 stars, last push 2026-08-03, MIT. It claims "100% ReaScript coverage" (600+ tools in the `full` profile; the default `dsl-production` profile has 53). It is developed and tested on macOS; on Windows the setup is manual and `REAPER_MCP_BRIDGE_DIR` must be set. Only the file-based bridge is implemented. — [GitHub](https://github.com/shiehn/total-reaper-mcp)
- wegitor/reaper-reapy-mcp: 87 stars, last push 2026-07-07, MIT, reapy-based. Tools include `add_midi_notes`, `get_midi_notes`, `clear_midi_item`, `duplicate_item`, `render_project`; "Checked on Linux: Yes". — [GitHub](https://github.com/wegitor/reaper-reapy-mcp)
- wretcher207/reaper-daemon: 22 stars, last push 2026-10-21, MIT. It is a pure-Lua file bridge (JSON command files, no socket, no port) with an optional stdio MCP server, on macOS, Windows and Linux. It is also a Claude plugin with 5 skills (setup, drum programming, drum humanizing, guitar/bass parts, MIDI for an existing arrangement). Rendering and audio capture are off until you explicitly allow them. — [GitHub](https://github.com/wretcher207/reaper-daemon)

**Bitwig Studio**
- WeModulate/bitwig-mcp-server: 76 stars, last push 2025-04-10. **Possibly stale.** — [GitHub](https://github.com/WeModulate/bitwig-mcp-server)
- fabb/WigAI: 62 stars, last push 2026-10-18. It is now **archived**; the author lists forks as of Oct 2026, e.g. glassdimly/wigai-full ("devices, presets, browser, notes, arranger") and csabacsaba/WigAI ("clip note writing"). WigAI was a Bitwig extension with an MCP endpoint at `http://localhost:61169/mcp`, requiring Bitwig 5.2.7+ and Java 21; the original covered only transport, selected-device parameters and clip/scene launching. — [GitHub](https://github.com/fabb/WigAI)
- Other Bitwig servers (ptaczek/daw-mcp, 22 stars; beat-twin, bitwig-control-deck and others at 0–3 stars) are tiny. — [GitHub search](https://github.com/search?q=bitwig+mcp&type=repositories)

**FL Studio (Windows/macOS)**
- karl-andres/fl-studio-mcp: 241 stars, last push 2026-09-30, MIT. It works over virtual MIDI (loopMIDI on Windows) plus a piano-roll script. It can add notes, delete specific notes, clear notes, and "Read piano roll state". It **cannot load plugins** ("The FL Studio scripting API does not support loading new VST/AU plugins") and has no pattern management. The piano-roll script is triggered by sending FL the keystroke Ctrl+Alt+Y, which briefly brings FL to the foreground on Windows. — [GitHub](https://github.com/karl-andres/fl-studio-mcp)
- rosasynthesiz/flstudio-mcp: 113 stars, last push 2026-10-15, MIT, 67 tools, targets FL Studio 2025. "Plugins, audio files, and rendering are UI-only. FL's API cannot load a plugin, load an audio file, or render audio." Because "FL exposes no API to run a pyscript", note writing has to be armed once per session by hand. — [GitHub](https://github.com/rosasynthesiz/flstudio-mcp)
- synopsys0/postfader-fl-studio-mcp: 8 stars, last push 2026-10-26, Apache-2.0, 85 tools, requires FL Studio 2026 (26.1.3+). "Every supported change is read back from FL Studio". Audio analysis works only on exported files, because FL does not expose live output. — [GitHub](https://github.com/synopsys0/postfader-fl-studio-mcp)

**Logic Pro (macOS only)**
- MongLong0214/logic-pro-mcp: 159 stars, last push 2026-10-28, 35 open issues, MIT. Notes can be imported as generated SMF; it advertises "fail-closed" control with readback. — [GitHub](https://github.com/MongLong0214/logic-pro-mcp)
- koltyj/logic-pro-mcp: 130 stars, last push 2026-09-05, MIT. — [GitHub](https://github.com/koltyj/logic-pro-mcp)
- From the MongLong README: "Logic Pro does not ship a first-party API for agentic composition". — [GitHub](https://github.com/MongLong0214/logic-pro-mcp)

**Cubase, Studio One, Ardour, LMMS, others**
- Cubase: there are a handful of tiny servers. yokadeeds-dev/yoka-cubase-mcp (7 stars, AGPL-3.0, last push 2026-10-16) drives Cubase over the Mackie Control protocol (~450 commands). muhwagwa0112/cubase-complete-mcp (2 stars) targets Cubase 15 on Windows via MIDI Remote. hedidjs/cubase-mcp has 11 stars, last push 2025-11-14. — [GitHub search](https://github.com/search?q=cubase+mcp&type=repositories)
- Studio One: no MCP server found. A March/April 2026 guide also says Cubase, Studio One, Logic, Pro Tools and FL Studio had "zero MCP servers" at that time, which is now outdated for Logic, FL Studio and Cubase. — [ChatForest](https://chatforest.com/guides/mcp-music-audio-production/)
- Ardour: pyroqbit/ardour-mcp (7 stars, last push 2025-06-16; **possibly stale**); raibid-entertainment/ardour-mcp (6 stars, 2025-11-20); others have 0–1 stars. — [GitHub search](https://github.com/search?q=ardour+mcp&type=repositories)
- LMMS: only 0–2-star repos (e.g. ZipseLu/lmms-mcp, 2 stars, 2026-08-21). — [GitHub search](https://github.com/search?q=lmms+mcp&type=repositories)
- Pro Tools: a skrul MCP server uses PTSL for session/track/clip/marker/transport control. — [Sonic Field](https://sonicfield.org/ai-agents-enter-the-studio-the-mcp-turn-in-audio)
- Conceptual-Machines/magda-core: an AI-native open-source DAW (C++23/JUCE/Tracktion Engine, GPL-3.0) with built-in AI chat that generates and runs a DSL, CI on Linux/macOS/Windows; 251 stars, 88 open issues, last push 2026-10-27. — [GitHub](https://github.com/Conceptual-Machines/magda-core)
- Generic MIDI: tubone24/midi-mcp-server (57 stars, last push 2026-04-12, MIT) generates MIDI files from text. — [GitHub](https://github.com/tubone24/midi-mcp-server)

### Inferences
- For a Windows PC with realistic third-party sample instruments, the viable "drive a live DAW" candidates are REAPER (TwelveTake, xDarkzx, reaper-daemon) and Ableton (LivePilot, wstierhout, bschoepke, Producer Pal). FL Studio is disqualified for an unattended pipeline because its API can load neither plugins nor audio and cannot render. Logic is macOS-only. Bitwig's ecosystem is fragmented forks of an archived project.
- Star counts are a poor proxy for capability here. ahujasid's server is the most starred, but newer servers expose note-ID-level editing, offline file diffing and audio capture that its README does not advertise.
- Several of the strongest repos (bonfire, kumi, LivePilot, postfader) are under a year old and change weekly, so pin versions.

### Gaps
- Per-tool details of ahujasid/ableton-mcp after v1.4.x (whether it can read back and edit existing notes by ID) were not verifiable from the README; the source code was not inspected.
- Producer Pal's exact note-editing tools and notation format were not confirmed (the docs pages fetched did not list them).
- The capabilities of the glassdimly/wigai-full fork and the Bitwig API's note-read granularity were not verified.

## Q2. Notation software: MuseScore, Dorico, Sibelius, LilyPond — can Claude write a full score and render it?

### Takeaway
Yes, for MuseScore, with caveats. The robust pattern is code → MusicXML (via music21 or a text DSL) → MuseScore CLI export to PDF/MIDI/audio, which needs no GUI session. Live editing of an open score through QML/WebSocket plugins also works but is fragile. Dorico has only experimental servers built on an undocumented Remote Control API, and Sibelius has none. Notation pipelines give engraved scores and General-MIDI-quality audio (Muse Sounds CLI export has had bugs), not production-grade multi-track mixes.

### Cited Findings
- tskovlund/mcp-score: 31 stars, last push 2026-10-26, MIT, "alpha", Python 3.14+. The assistant writes a music21 script that exports MusicXML (a bundled `score-generate` skill does this in Claude Code). With MuseScore Studio 4.4.2+ running, MCP tools "read passages, add notes, dynamics and chord symbols, set barlines, keys, time signatures and tempo, append measures, transpose, and undo". `render_score` exports PDF, PNG, MIDI, audio or MusicXML through the MuseScore command line, with MuseScore installed but not running. Dorico 4+ support is "Experimental. Undocumented Remote Control API, command-only, not verified against a running instance". — [GitHub](https://github.com/tskovlund/mcp-score)
- ghchen99/mcp-musescore: 129 stars, last push 2026-10-13, MIT; a WebSocket QML plugin for MuseScore 3.x/4.x, Python 3.13+. — [GitHub](https://github.com/ghchen99/mcp-musescore)
- JordanSucher/musescore-mcp: 31 stars, last push 2025-04-20. **Possibly stale.** — [GitHub](https://github.com/JordanSucher/musescore-mcp)
- justerlex/mcp-musescore (a fork): some actions crash MuseScore Studio 4.7.5 because they run nested commands inside the plugin. — [GitHub](https://github.com/justerlex/mcp-musescore) (via search summary)
- Ranger013/EasyMuseMCP: 0 stars, last push 2026-10-26, MIT. It compiles a compact text notation to MusicXML 4.0 and drives the MuseScore CLI in windowless mode to produce `.mscz/.pdf/.png/.svg/.midi/.mp3`, taking about 2–6 s per piano page. It validates measure durations. Pitfalls its author found on MuseScore 4.7:
  - repeats are silently dropped unless every part has the repeat barline;
  - exit codes are unreliable, because MuseScore sometimes crashes after writing the file, so success is judged by the output existing;
  - `--score-parts` emits base64 JSON to stdout instead of files.

  Its stated limits: edits are at measure/element granularity, with no live editing of an open MuseScore window. — [GitHub](https://github.com/Ranger013/EasyMuseMCP)
- MuseScore 4 CLI: `--score-mp3` was not implemented in MS4; use `-o file.mp3`, or a JSON job file with `-j`. — [musescore.org](https://musescore.org/en/node/351310); [GitHub issue #18033](https://github.com/musescore/MuseScore/issues/18033)
- "Command-line export of .wav, .mp3 and .flac files is broken in MuseScore 4.1.1 with Muse Sounds" (issue #19160; current status not verified). — [GitHub](https://github.com/musescore/MuseScore/issues/19160)
- "Can't run MuseScore CLI in headless mode" (MS4 issue #17247): the MS3 `offscreen` platform trick reportedly no longer works in MS4. — [GitHub](https://github.com/musescore/MuseScore/issues/17247)
- musescore/MuseScore itself is very active: 15.3k stars, last push 2026-10-27. — [GitHub](https://github.com/musescore/MuseScore)
- music21 10.5.1 was released 2026-10-22 (actively maintained). — [PyPI](https://pypi.org/project/music21/)
- Dorico servers are small: happycastle114/dorico-mcp-server (14 stars, last push 2026-01-06), romanstark/dorico-maestro (3 stars, AGPL-3.0, 2026-10-13), holonen/dorico-remote ("Dorico SE 6.2 via API"). — [GitHub search](https://github.com/search?q=dorico+mcp&type=repositories)
- Sibelius: no MCP server exists per ChatForest (2026). — [ChatForest](https://chatforest.com/guides/mcp-music-audio-production/)
- LilyPond: wspringer/lilypond-mcp (1 star, engraves LilyPond into PDF/EPS/SVG/PNG) and deer/music.build (5 stars). — [GitHub search](https://github.com/search?q=lilypond+mcp&type=repositories). An HN commenter built a VST in which an LLM writes LilyPond that becomes multi-track MIDI ("pumps out 4-5 tracks of MIDI that is just what I asked for"). — [HN](https://news.ycombinator.com/item?id=46428922)
- linxule/mcp-music-studio: 76 stars, AGPL-3.0, last push 2026-10-26. Scores are written in ABC notation and played with 128 GM instruments, with WAV/MIDI download; it is available as a hosted remote MCP server. — [GitHub](https://github.com/linxule/mcp-music-studio)

### Inferences
- Notation is a good representation for writing, reviewing and diffing melodies and harmony (MusicXML or music21 code is text and git-friendly). It is a weak final renderer for "most realistic instrument sounds"; the realistic path is MusicXML/MIDI → DAW with sample libraries.
- MuseScore on the headless Linux server is risky (the headless issue; Muse Sounds export bugs). Rendering on the Windows PC is safer.

### Gaps
- Whether Muse Sounds CLI audio export works in MuseScore 4.6/4.7 (Oct 2026) was not verified.
- No source found on whether the Dorico Remote Control API can read note data back.

## Q3. Live-coding environments: Sonic Pi, Strudel, TidalCycles, SuperCollider, Csound

### Takeaway
MCP servers exist for all five, and Strudel and SuperCollider have the most active ones. They suit synth/electronic sketches and have good headless/offline options (SuperCollider NRT render, Strudel via Playwright). They are not suited to realistic acoustic-instrument arrangements, and they have no VST sample-library hosting comparable to a DAW.

### Cited Findings
- williamzujkowski/live-coding-music-mcp (Strudel): 248 stars, last push 2026-10-19, AGPL-3.0. It has 28 tools (pattern editing, playback, audio analysis, history, sessions, MIDI import/export), automates Strudel.cc in a real browser through Playwright, and keeps isolated multi-session browser and audio-capture state. — [GitHub](https://github.com/williamzujkowski/live-coding-music-mcp)
- Other Strudel projects: p-poss/dj-claude (38 stars, last push 2026-06-02) and phildougherty/strudel-mcp-bridge (22 stars, 2025-10-22). — [GitHub search](https://github.com/search?q=strudel+mcp&type=repositories)
- jeremyruppel/claude-collider (SuperCollider): 59 stars, last push 2026-10-16, MIT; it auto-boots SuperCollider and exposes 9 MCP tools. — [GitHub](https://github.com/jeremyruppel/claude-collider)
- pimvanoerle/sclang-mcp (SuperCollider): 0 stars, last push 2026-10-18, MIT. `sc_render` renders to WAV "offline (faster than realtime, no audio device needed)" and returns peak/RMS so the agent can detect silence or clipping; it runs on macOS and Linux. Patterns must terminate, because infinite `Pbind`s time out. — [GitHub](https://github.com/pimvanoerle/sclang-mcp)
- Tok/SuperColliderMCP: 26 stars, last push 2025-05-14. **Possibly stale.** — [GitHub](https://github.com/Tok/SuperColliderMCP)
- Sonic Pi: vinayak-mehta/mcp-sonic-pi (19 stars, last push 2025-03-22, **possibly stale**); abhishekjairath/sonic-pi-mcp (19 stars, 2026-03-22). — [GitHub search](https://github.com/search?q=sonic+pi+mcp&type=repositories)
- TidalCycles: Benedict/tidal-cycles-mcp-server (17 stars, last push 2026-10-20, MIT). The tidalcycles/Tidal GitHub repo is **archived** (last push 2025-06-13). — [GitHub](https://github.com/Benedict/tidal-cycles-mcp-server); [GitHub](https://github.com/tidalcycles/Tidal)
- Csound: erno-szabados/musmcp (3 stars, last push 2026-02-19) for Csound-powered sample synthesis. — [GitHub](https://github.com/erno-szabados/musmcp)
- An HN commenter pointed Claude at Strudel's docs and got a playable song in the browser. — [HN](https://news.ycombinator.com/item?id=46891689)

### Inferences
- SuperCollider NRT rendering is the one fully headless, display-free render path in this survey that fits the AutoDL server, but it is synthesis-based.
- Tidal's GitHub archive likely reflects a move to another forge; check the current upstream before depending on it.

### Gaps
- No quality assessment was found of multi-track, harmony-heavy pieces made through these servers.

## Q4. Official or semi-official offerings: DAW vendors (Ableton, Image-Line, Steinberg, PreSonus, Cockos, Apple, Bitwig) and Anthropic

### Takeaway
No DAW vendor ships an MCP server that controls a session. Anthropic's official Ableton connector (2026-04-28) is documentation-only. Ableton's Extensions SDK (public beta, 2026-06-02) is the only new vendor scripting surface, and it runs from a right-click menu inside Live 12 Suite, not as an agent endpoint. Splice has a beta MCP for assets. There is no official Anthropic music skill; the music skills and plugins are community-made.

### Cited Findings
- Anthropic announced an official Ableton connector on 2026-04-28 in a batch of nine creative connectors: Adobe, Blender, Ableton, Splice, Autodesk Fusion, SketchUp, Affinity by Canva, Resolume Arena, Resolume Wire. It answers from Ableton's manuals and "can't open your set, see your clips, or change anything" (secondary sources). — [findskill.ai](https://findskill.ai/blog/anthropic-claude-ableton-connector-music-producer-honest-walkthrough/); [Gearnews](https://www.gearnews.com/claude-ai-ableton-live-tech/); [Dawbrain](https://www.dawbrain.com/blog/2026-08-12-claude-ableton-connector)
- Sonic Field (2026-04-29) calls Ableton's connector an "experimental" knowledge assistant over the Live/Push/Move/Max for Live manuals. Splice's MCP server is in beta (sound description, stacks, asset download dependent on credits). It reports no official MCP from Bitwig, Steinberg, PreSonus, Image-Line, Cockos, Apple or Native Instruments. — [Sonic Field](https://sonicfield.org/ai-agents-enter-the-studio-the-mcp-turn-in-audio)
- Ableton Extensions SDK (2026-06-02, public beta with Live 12.4.5):
  - JavaScript on Node.js; developers need Node v24.16.0 and macOS or Windows.
  - Extensions "read and edit the structure of your Set" (tracks, clips, MIDI notes, parameters, devices, tempo), are triggered from Live's right-click context menu, and "run once".
  - They can "connect to external services".
  - Live 12 Suite only.
  - The post does not mention MCP or rendering. — [Ableton blog](https://www.ableton.com/en/blog/introducing-extensions-sdk/)
- Community Claude Code plugins and skills for music:
  - patrickking67/producer: 12 skills and 12 commands, installed via `/plugin marketplace add`, Ableton Live 12. — [awesomeclaudeplugins](https://awesomeclaudeplugins.com/patrickking67/producer)
  - Korben00/ableton-producer-skills: built on the Extensions SDK, v0.1.0. — [GitHub](https://github.com/Korben00/ableton-producer-skills)
  - glincker/ableton-skills: 44 stars, MIT; it works with any Ableton MCP and defaults to stock devices. — [GitHub](https://github.com/glincker/ableton-skills)
  - reaper-daemon ships as a Claude plugin with 5 skills. — [GitHub](https://github.com/wretcher207/reaper-daemon)
- Cross-DAW interchange from vendors: DAWproject 1.0 (open XML format, MIT, 1,049 stars, last push 2025-07-12) is supported by Bitwig Studio 5.0.9, Studio One 6.5 and Cubase 14, and REAPER via the third-party ProjectConverter. — [GitHub](https://github.com/bitwig/dawproject)

### Inferences
- Every session-controlling path is community software riding on vendor scripting APIs (Ableton Remote Scripts/LOM, ReaScript, FL MIDI scripting, Bitwig controller API, Cubase MIDI Remote), so breakage on DAW updates is the main maintenance risk.

### Gaps
- Anthropic's own announcement page was not fetched; the connector details come from secondary coverage.
- No vendor statement was found on roadmaps for official MCP support.

## Q5. REAPER: how complete is ReaScript for building a whole project from code and rendering it from the command line?

### Takeaway
REAPER is the strongest candidate for a pure-code pipeline. ReaScript (Lua/Python/EEL) has note- and CC-level get/set/insert/delete, FX add/delete/move, preset and raw plugin-state get/set, full track/item state chunks, markers, tempo and render settings. The `reaper -renderproject file.rpp` CLI renders and exits, and since REAPER 6.80 a script can run on startup (`reaper.exe project.rpp script.lua`). REAPER has native Linux builds. Running it fully display-less on Linux is unconfirmed (it likely needs Xvfb), and Windows-only VST instruments will not run on the Linux server natively.

### Cited Findings
- REAPER is at v7.83 (2026-10-24), with builds for Windows x64/32-bit/arm64ec (beta), Linux x86_64/i686/aarch64/armv7l, and macOS Universal. "REAPER supports Linux on Intel and ARM architectures." — [reaper.fm download](https://www.reaper.fm/download.php)
- Licensing: "You get 60 days of evaluation free, with full functionality". The discounted license applies to personal use, businesses with yearly gross revenue under USD 20,000, and education/non-profits. — [reaper.fm purchase](https://www.reaper.fm/purchase.php)
- The ReaScript API docs used here were "Generated by REAPER v7.83". — [ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html). Relevant functions:
  - **Notes**: `MIDI_GetNote` returns selected, muted, startppqpos, endppqpos, chan, pitch, vel. `MIDI_SetNote(take, noteidx, selected, muted, startppq, endppq, chan, pitch, vel, noSort)` sets any subset ("Properties passed as NULL (or negative values) will not be set"), with the caveat that "Setting multiple note start positions at once is done more safely by deleting and re-inserting the notes". `MIDI_InsertNote`/`MIDI_DeleteNote` exist, and `MIDI_DisableSort`/`MIDI_Sort` support batch edits.
  - **CC**: `MIDI_SetCC(take, ccidx, …, chanmsg, chan, msg2, msg3, noSort)` plus Get/Insert.
  - **Bulk**: `MIDI_GetAllEvts`/`MIDI_SetAllEvts` take a packed buffer of {offset, flag, msglen, msg[]}.
  - **Items**: `CreateNewMIDIItemInProj(track, start, end, qnIn)`.
  - **FX**: `TrackFX_AddByName(track, fxname, recFX, instantiate)`, `TrackFX_Delete`, and `TrackFX_CopyToTrack(src, src_fx, dest, dest_fx, is_move)`, which copies, moves or reorders FX. `TrackFX_SetPreset` activates a named preset, and "Full paths to .vstpreset files are also supported for VST3". `TrackFX_GetNamedConfigParm`/`SetNamedConfigParm` support `vst_chunk[_program]`, a "base64-encoded VST-specific chunk", so raw plugin state can be saved and restored. `fx_ident` is also available.
  - **State**: `GetTrackStateChunk`/`SetTrackStateChunk` "Sets the RPPXML state of a track".
  - **Project**: `Main_SaveProject`, `AddProjectMarker` (markers/regions), `SetTempoTimeSigMarker`. `GetSetProjectInfo` keys include `RENDER_SETTINGS`, `RENDER_BOUNDSFLAG`, `RENDER_CHANNELS`, `RENDER_SRATE`, `RENDER_STARTPOS/ENDPOS`, `RENDER_TAILFLAG/TAILMS`, `RENDER_NORMALIZE`, `RENDER_DITHER`, etc.
- Command line, per the ReaTeam CLI reference:
  - Startup and saving: `-renderproject filename.rpp` ("render project and exit"), `-new`, `-template`, `-saveas`, `-close[all][:save|:nosave][:exit]` (`:exit` since 7.29), `-nosplash`, `-ignoreerrors`.
  - Diagnostics and conversion: `-fxoffline` (since 7.74), `-peaktest` (dry-run render reporting peak output level, since 7.62), and `-batchconvert filelist.txt`, whose CONFIG block covers SRATE/NCH/NORMALIZE/BRICKWALL/FXCHAIN/OUTPATH, etc.
  - Scripts: "Since build 6.80 passing either project/template or a media file AND a script file is supported, e.g. `reaper.exe projectfile.rpp scriptfile.lua`". `-nonewinst` runs scripts in an already-running instance.
  - An `.RfxChain` or `.vstpreset` passed on the command line instantiates the plugin on a new track (since 6.43). — [ReaTeam Doc](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)
- A 2016 forum thread reports that calling action 41824 ("render project with last settings") from ReaScript fixed a stereo-output problem. A 2024 thread shows a Lua script that auto-confirms the overwrite prompt during render, which shows that render dialogs and prompts can interrupt unattended runs. — [Cockos forum 2016](https://forums.cockos.com/showthread.php?t=176225); [Cockos forum 2024](https://forums.cockos.com/showthread.php?p=2751592)
- rcraggs/reaper-auto-render is a bash script that batch-renders projects with `-renderproject` (it hardcodes a macOS binary path). — [GitHub](https://github.com/rcraggs/reaper-auto-render/blob/main/auto-render.sh)
- The MCP servers expose this API surface directly:
  - xDarkzx: `midi_get_notes`, `midi_set_note` ("Edit an existing note (position, length, pitch, velocity, mute)"), `midi_delete_note`, `midi_insert_notes_batch`, `midi_quantize`, CC insert, and `project_export_audio` (wav/mp3/ogg/flac/aiff). It removed `midi_get_ccs` on purpose, because reading CC1/CC11 across an orchestral arrangement "would blow the AI's context window". — [xDarkzx TOOLS.md](https://github.com/xDarkzx/Reaper-MCP/blob/main/docs/TOOLS.md)
  - TwelveTake: `save_fx_preset` "always returns an error, because REAPER's API cannot save a named FX preset", and `render_region` is "Not implemented". — [GitHub](https://github.com/TwelveTake-Studios/reaper-mcp)
- shiehn/total-reaper-mcp says REAPER 6.83+ "includes embedded Lua 5.4 and full ReaScript API". — [GitHub](https://github.com/shiehn/total-reaper-mcp)

### Inferences
- A complete headless build could look like this: (1) generate the project from code, either by writing the `.rpp` directly or with a startup Lua script that builds tracks, items, notes, FX and state chunks and calls `Main_SaveProject`; then (2) run `reaper -renderproject out.rpp` (or a script that sets the `RENDER_*` keys and calls the render action, then exits with `-close:nosave:exit`). None of this needs an MCP server.
- Named-preset saving is not in the API (per TwelveTake), but raw plugin state round-trips through `vst_chunk` or Get/SetTrackStateChunk. `.RfxChain` and `.RTrackTemplate` files are a practical way to store per-instrument presets on disk.
- On the AutoDL Linux server, REAPER itself can run, but expect to need Xvfb. Only Linux-native plugins would load, so a project that uses Windows VST3 sample libraries should be rendered on the Windows PC.

### Gaps
- No primary source confirms whether REAPER for Linux can run `-renderproject` without an X display (the forum thread on Linux CLI rendering was behind a JS wall).
- Exact license prices were not re-verified in this session (the purchase page text read only covered the eligibility criteria and the 60-day evaluation).
- How render progress and error dialogs behave under `-renderproject` with missing plugins was not verified (`-ignoreerrors` exists, but its coverage of render-time dialogs is unknown).

## Q6. Ableton Live: what can the Live Object Model, Remote Scripts, Max for Live and the Extensions SDK do and not do?

### Takeaway
Since Live 11 the LOM has full note-ID-based MIDI editing (add, get, modify, delete and duplicate by ID, with per-note probability and velocity deviation), and tracks can insert and delete devices. Third-party plugins can be loaded through the browser, but their parameters are visible only after the user "Configures" them. Live has **no render/export API**: export needs the GUI Export dialog (AppleScript on macOS) or workarounds such as recording or capturing audio in real time. Live runs only on Windows and macOS, so nothing Ableton-based can run on the Linux server.

### Cited Findings
- LOM Clip note API: `add_new_notes` (11.0, returns note IDs), `get_notes_extended` (11.0), `get_all_notes_extended` (11.1), `apply_note_modifications` (11.0, "replaces remove-then-set editing"), `remove_notes_by_id` (11.0), `get_notes_by_id` (11.0), `duplicate_notes_by_id` (11.1.2, optional transpose), `get_selected_notes_extended` (11.0). Note dictionaries carry `note_id, pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity`. Clip envelope functions listed: `has_envelopes`, `clear_all_envelopes`, `clear_envelope`. — [Cycling '74 LOM Clip](https://docs.cycling74.com/apiref/lom/clip/)
- The LOM Track class lists `insert_device`, `delete_device`, `create_midi_clip`, `duplicate_clip_to_arrangement`, etc. — [Cycling '74 LOM Track](https://docs.cycling74.com/apiref/lom/track/)
- "Live exposes no render API, so this drives the Export dialog with AppleScript". Producer Pal's export skill is macOS only. — [Producer Pal: Extending](https://producer-pal.org/extending)
- AbletonOSC paper (NIME 2023): for external VST/AU plugins, "it is necessary to expose parameters to Live using the 'Configure' dialogue" before they can be accessed. The paper calls this an inherent LOM limitation that also applies to Max for Live. — [NIME 2023 PDF](https://nime.org/proceedings/2023/nime2023_60.pdf) (via search summary)
- Stock AbletonOSC does not expose the browser's `load_item()`, so a patched Remote Script is needed. A Push Hack bridge loads scanned VST3 plugins, which needs the plugin scan flag on, and notes that the LOM is single-threaded. — search summary of [federico-pepe/push-hack-browser-bridge](https://github.com/federico-pepe/push-hack-browser-bridge)
- wstierhout's server records "a section to a WAV without the Export dialog", which is a real-time capture workaround. — [GitHub](https://github.com/wstierhout/ableton-live-mcp)
- bschoepke's "Agent Audio Tap" M4L device captures audio anywhere in the chain. — [GitHub](https://github.com/bschoepke/ableton-live-mcp)
- LivePilot's M4L bridge provides "deep LOM access through Max's LiveAPI that the ControlSurface API can't reach". — [GitHub](https://github.com/dreamrec/LivePilot)
- ideoforms/AbletonOSC: 835 stars, last push 2025-11-19. ideoforms/pylive: 632 stars, last push 2025-07-23. leolabs/ableton-js: 532 stars, last push 2026-10-21. — [GitHub](https://github.com/ideoforms/AbletonOSC); [GitHub](https://github.com/ideoforms/pylive); [GitHub](https://github.com/leolabs/ableton-js)
- The Extensions SDK (Live 12.4.5 Suite beta) edits tracks, clips, notes, devices and tempo from a context-menu-triggered, run-once JS extension; rendering is not mentioned. — [Ableton blog](https://www.ableton.com/en/blog/introducing-extensions-sdk/)
- Kumi lists Ableton Live 12 support only on macOS 13+ and Windows 10/11. — [GitHub](https://github.com/user1303836/kumi)

### Inferences
- Ableton gives excellent live, note-ID-level read/write, but an unattended "build then render" job on Windows would need GUI automation of the Export dialog (no AppleScript on Windows) or real-time capture. That makes Ableton a worse fit than REAPER for batch regeneration of many variants.
- Third-party instrument swaps are possible (browser load plus `delete_device`), but controlling a plugin's parameters requires a manual Configure step per plugin instance.

### Gaps
- Whether Live 12.x (≥12.3) exposes any offline bounce/freeze-flatten call through the LOM was not confirmed; the Producer Pal statement says no render API exists.
- `Browser.load_item` behaviour for VST3 instruments on Windows was not verified from Ableton docs (the Cycling '74 browser page could not be parsed).

## Q7. Which approaches give the agent a reliable read-back loop, and which are fire-and-forget?

### Takeaway
Read-back is best in REAPER (`MIDI_GetNote` per note, state chunks, RPP parse) and Ableton (note IDs via `get_notes_extended`, set diffing), and in the newer servers that verify each write (postfader for FL, MongLong for Logic, reaper-daemon's `verify_change` for audio). Older or simpler servers (early ahujasid/ableton-mcp, Sonic Pi/OSC senders, karl-andres-style MIDI senders, generic virtual-MIDI MCPs) are largely fire-and-forget. Audio-level "listening" loops exist (Agent Audio Tap, verify_change, sclang peak/RMS), but they measure levels and spectra; they do not judge musical correctness.

### Cited Findings
- reaper-daemon's `verify_change` "captures the track before and after a move and reports what changed in the audio, so you are not taking its word for it". It needs audio writes to be enabled. — [GitHub](https://github.com/wretcher207/reaper-daemon)
- postfader-fl-studio-mcp: "Every supported change is read back from FL Studio" and it starts read-only. — [GitHub](https://github.com/synopsys0/postfader-fl-studio-mcp)
- MongLong0214/logic-pro-mcp names the anti-pattern of "Single-channel control that can write to Logic but cannot reliably read what Logic actually did". It separates "evidence" from "claims" and returns plugin state "only after project identity, target track, physical insert slot, plugin identity, and readback all agree". — [GitHub](https://github.com/MongLong0214/logic-pro-mcp)
- wstierhout's server can "diff the session since the last check", and can diff two saved `.als` versions offline. — [GitHub](https://github.com/wstierhout/ableton-live-mcp)
- xDarkzx: `midi_get_notes` reads every note in an item, and `midi_count_events` is a "cheap substitute for a full read". It enforces per-call limits (`MAX_TOTAL_NOTES_PER_CALL`) to keep each command under about 2 s of REAPER main-thread time. — [GitHub](https://github.com/xDarkzx/Reaper-MCP); [TOOLS.md](https://github.com/xDarkzx/Reaper-MCP/blob/main/docs/TOOLS.md)
- sclang-mcp starts from "The main problem with an agent making music is that it can't hear", and returns peak/RMS after an offline render. — [GitHub](https://github.com/pimvanoerle/sclang-mcp)
- The bschoepke demo prompt log includes the follow-up "doesn't seem like the new thing has any notes". The agent had reported adding a track but no notes landed, which shows why explicit read-back matters. — [GitHub](https://github.com/bschoepke/ableton-live-mcp)
- Older/simpler examples:
  - sandst1/mcp-server-midi sends virtual MIDI notes/CC. — [Sonic Field](https://sonicfield.org/ai-agents-enter-the-studio-the-mcp-turn-in-audio)
  - abhishekjairath/sonic-pi-mcp controls Sonic Pi over OSC. — [GitHub search](https://github.com/search?q=sonic+pi+mcp&type=repositories)

### Inferences
- For note-level work, the agent's contract should be: write → read back the exact note list (pitch/start/length/velocity/channel, plus CC where needed) → compare against intended data → fix. This is straightforward with ReaScript `MIDI_GetNote`/`MIDI_GetAllEvts` or LOM `get_notes_extended`, and impractical with FL, MIDI-only senders, or live-coding servers.
- Large orchestral CC data can overflow the context window (xDarkzx's reason for removing CC reads). Comparing in code, by hashing or diffing note lists in a script and returning only the differences, scales better than dumping events to the model.

### Gaps
- No systematic benchmark comparing read-back reliability across servers was found.

## Q8. (Added) Per option: can the agent edit individual existing notes in place and read them back precisely, swap the instrument plugin while keeping the MIDI, and save/restore plugin presets/state from code?

### Takeaway
REAPER can do all three natively: per-note get/set, MIDI living in items independent of the FX chain, and plugin state via `vst_chunk`, `.vstpreset` or state chunks. Ableton can do note-level edits by ID and device insert/delete; preset/state handling for third-party plugins is weaker and parameters need Configure. FL Studio can read and write piano-roll notes but cannot load or swap plugins. Logic is macOS-only. MuseScore edits at element/measure level. Live-coding servers regenerate code, not notes.

### Cited Findings
- **REAPER, notes**: `MIDI_GetNote`/`MIDI_SetNote`/`MIDI_InsertNote`/`MIDI_DeleteNote` plus `MIDI_SetCC` give precise PPQ-tick positions, channel, pitch and velocity. — [ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html)
- **REAPER via MCP**: xDarkzx `midi_set_note` edits "position, length, pitch, velocity, mute" of an existing note. — [TOOLS.md](https://github.com/xDarkzx/Reaper-MCP/blob/main/docs/TOOLS.md). wegitor has `get_midi_notes`. — [GitHub](https://github.com/wegitor/reaper-reapy-mcp). TwelveTake has batch note insert, velocity edits, transpose, quantize and snap-to-scale. — [GitHub](https://github.com/TwelveTake-Studios/reaper-mcp)
- **REAPER, instrument swap**: `TrackFX_Delete` plus `TrackFX_AddByName` operate on the track's FX chain, while MIDI lives in media-item takes; `TrackFX_CopyToTrack` moves FX between tracks. — [ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html)
- **REAPER, presets/state**: `TrackFX_SetPreset` (by name, or a `.vstpreset` path for VST3) and `vst_chunk` (base64 plugin state) via `TrackFX_Get/SetNamedConfigParm` cover presets and raw state. Track templates (`.RTrackTemplate`) carry "exact FX state, routing, folder structure and items". Named-preset *saving* is not exposed (TwelveTake). — [ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html); [bonfire-systems](https://github.com/bonfire-systems/reaper-mcp); [TwelveTake](https://github.com/TwelveTake-Studios/reaper-mcp)
- **Ableton, notes**: `get_notes_extended` and `apply_note_modifications` edit notes in place by ID (pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity). — [Cycling '74 LOM Clip](https://docs.cycling74.com/apiref/lom/clip/). Servers exposing this: wstierhout ("write and edit MIDI notes"), uisato ("Add, delete, transpose, and quantize notes"), jpoindexter ("Move notes … replace all notes"). — [wstierhout](https://github.com/wstierhout/ableton-live-mcp); [uisato](https://github.com/uisato/ableton-mcp-extended); [jpoindexter](https://github.com/jpoindexter/ableton-mcp)
- **Ableton, swap and parameters**: `Track.insert_device`/`delete_device` exist. — [LOM Track](https://docs.cycling74.com/apiref/lom/track/). Third-party plugin parameters need the Configure step. — [NIME 2023](https://nime.org/proceedings/2023/nime2023_60.pdf)
- **FL Studio**: piano-roll read and write are possible; plugin loading, audio loading and rendering are not. — [karl-andres](https://github.com/karl-andres/fl-studio-mcp); [rosasynthesiz](https://github.com/rosasynthesiz/flstudio-mcp)
- **MuseScore (EasyMuseMCP)**: "编辑粒度是「小节 / 元素」，没有逐音符拖拽式编辑" (edit granularity is measure/element; no per-note drag editing). mcp-score reads and edits live passages through the plugin. — [EasyMuseMCP](https://github.com/Ranger013/EasyMuseMCP); [mcp-score](https://github.com/tskovlund/mcp-score)

### Inferences
- For "many fragments in many keys/modes, frequent re-orchestration, splicing, note-level control of every note and every sound", REAPER's model fits best. A track is FX chain + items, and an item is a MIDI take, so re-orchestration means replacing the FX chain or state chunk while the items stay untouched; splicing means moving or copying items/notes in PPQ.
- Per-instrument sound state can be versioned as files (`.RfxChain`, `.vstpreset`, or extracted `vst_chunk` base64), though the content is binary and opaque.

### Gaps
- Whether glassdimly/wigai-full (Bitwig) supports per-note in-place edit with read-back was not verified.
- Ableton device-state save/restore from code for third-party VSTs (preset files via browser) was not verified.

## Q9. (Added) Project-as-code (text files in git → regenerate the DAW project) vs DAW project as source of truth; RPP tooling and diff readability

### Takeaway
REAPER's `.rpp` is plain text, and Python/JS/Lua libraries exist to generate and parse it. MIDI is stored as hex event lines with relative tick offsets, and plugin state as base64 blobs, so raw RPP diffs show structure well, MIDI poorly and plugin sound state not at all. Practitioners building agent workflows (Hallucinote, mcp-score, EasyMuseMCP) keep a higher-level text representation in git as the source of truth and treat the DAW or notation program as a render surface. The Ableton `.als` route is reported as painful.

### Cited Findings
- RPP MIDI encoding, per the ReaTeam "State Chunk Definitions" doc: `<SOURCE MIDI` → `HASDATA 1 960 QN` (PPQ resolution) followed by lines such as `e 300 90 2b 60`. Fields: `e`=selected / `E`=not selected, "msg start offset", status byte, data1, data2; the example `e 60 80 2b 00` is a note-off 60 ticks later. Plugin data inside `<VST …>` is "Binary data, leave it alone (variable number of lines)", i.e. base64. — [ReaTeam State Chunk Definitions](https://github.com/ReaTeam/Doc/blob/master/State%20Chunk%20Definitions)
- reathon (Python, generate RPP): 85 stars, last push 2025-05-07, GPL-3.0; PyPI 0.0.9 released 2025-05-07. "The majority of the interface is a reflection of the .rpp file structure…you may need to know a bit about the underlying structure of REAPER's file format". — [GitHub](https://github.com/jamesb93/reathon); [PyPI](https://pypi.org/project/reathon/)
- rpp (Perlence, Python parse/emit with `loads`/`dumps`): 80 stars, BSD-3-Clause, last push and release 2023-04-29 (v0.5). **Possibly stale.** — [GitHub](https://github.com/Perlence/rpp); [PyPI](https://pypi.org/project/rpp/)
- rppxml (C++/WDL-backed Python parser and writer, also handles `.RfxChain`/`.RTrackTemplate`): 3 stars, last release 0.1.4 on 2025-02-15. Its README claims a 14.8 MB file loads in about 1.48 s versus 19.1 s with `rpp` (self-reported). — [GitHub](https://github.com/IcEarthlight/rppxml); [PyPI](https://pypi.org/project/rppxml/)
- Other parsers: rppp (JavaScript parser with `dump()`), the ReaTeam Lua RPP-Parser ("parses, edits, stringifies, and writes", and can create files from scratch), and dschuler36's MCP RPP parser. — [GitHub rppp](https://github.com/CharlesHolbrow/rppp); [ReaTeam wiki](https://github.com/ReaTeam/ReaScripts/wiki/RPP-Parser); [dschuler36](https://github.com/dschuler36/reaper-mcp-server)
- Hallucinote (Show HN, about Aug 2026): "git-first representation"; "Ableton serves as an audio rendering and performance capture surface, not the primary record"; each song has a decision log. MIDI round-trips (perform in Live → pull into Hallucinote → push back); audio round-trip is not yet supported. — [HN](https://news.ycombinator.com/item?id=49271123)
- HN, "Experiments with Ableton-MCP" thread (about Dec 2025): a user building an `.als` diff tool said ableton-mcp "still lacks many features" and "the XML schema of .als files is inconsistent", so most verification was manual. — [HN](https://news.ycombinator.com/item?id=46428922)
- An HN commenter described a Claude Code skill that edits Ableton's XML to arrange loops. — [HN](https://news.ycombinator.com/item?id=46891689)
- mcp-score's generation path writes music21 scripts that export MusicXML, and EasyMuseMCP uses a text DSL that compiles to MusicXML. Both treat code/text as the source and MuseScore as the renderer. — [mcp-score](https://github.com/tskovlund/mcp-score); [EasyMuseMCP](https://github.com/Ranger013/EasyMuseMCP)
- DAWproject's README notes that Standard MIDI files are "often a lower-level representation (no ramps)" that "forces consolidation on export", which is why DAWproject carries audio, notes, automation and plug-in state in XML. — [GitHub](https://github.com/bitwig/dawproject)

### Inferences
- A practical hybrid for this user:
  - Keep the musical source of truth in git as readable text (e.g. per-fragment JSON/YAML note lists, or music21/MusicXML), plus an orchestration map (part → instrument → `.RfxChain`/preset file path).
  - Generate the `.rpp` (or build it via a Lua startup script) and render with `-renderproject`.
  - For "see exactly what changed", diff the text sources (note-level, human-readable) instead of the RPP. Optionally add a script that parses two RPPs (rppxml/rpp) and prints a note-level diff decoded from the `E` lines.
- Raw RPP diffs will be noisy for MIDI: hex bytes, and offsets that appear relative to the previous event, so one inserted note can change the offset of the next line. Plugin changes show only as changed base64.
- Treating the DAW project as the source of truth gives the user GUI editing for free, but makes regeneration, splicing and bulk re-orchestration depend on live-session tooling and undo history instead of git history.

### Gaps
- No first-hand forum report was found comparing the two approaches for REAPER at scale; the evidence is from adjacent projects (Hallucinote, mcp-score, EasyMuseMCP) and HN comments.
- Whether REAPER rewrites MIDI `E` lines deterministically on save, i.e. whether a round-trip produces a stable diff, was not tested.

## Q10. (Added) Can the user open the same project in a GUI, hand-edit notes, and can the agent pick up those edits afterwards?

### Takeaway
Yes, with REAPER and Ableton. All their MCP bridges run inside the live GUI session, so the agent reads the current state, including the user's manual edits, through the same note-read calls, and agent edits land as undoable steps. In a project-as-code workflow the agent must re-import GUI edits, by parsing the saved `.rpp`/`.als` or reading notes live, and reconcile them into the text source. Hallucinote explicitly supports such a MIDI round-trip for Ableton.

### Cited Findings
- REAPER bridges run inside the user's REAPER GUI. TwelveTake makes every AI edit "one named step in REAPER's undo history". reaper-daemon wraps every change in an undo block so Ctrl+Z reverts it. — [TwelveTake](https://github.com/TwelveTake-Studios/reaper-mcp); [reaper-daemon](https://github.com/wretcher207/reaper-daemon)
- `reaper.exe -nonewinst … script.lua` runs a script in an already-running REAPER instance (for example, to export the current notes to a text file). — [ReaTeam CLI](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)
- dschuler36's server parses saved `.RPP` files without REAPER running. — [GitHub](https://github.com/dschuler36/reaper-mcp-server)
- Ableton: wstierhout offers live tools plus offline `.als` "extract MIDI" and "diff two versions". Kumi copies the last saved Set before large changes and makes each request one Live undo step. — [wstierhout](https://github.com/wstierhout/ableton-live-mcp); [kumi](https://github.com/user1303836/kumi)
- Hallucinote MIDI round-trip: perform in Live, pull into the git-first representation, push back. — [HN](https://news.ycombinator.com/item?id=49271123)
- MuseScore: mcp-score reads passages from the open score through its plugin. — [GitHub](https://github.com/tskovlund/mcp-score)

### Inferences
- The agent needs an explicit "sync from DAW" step before regenerating; otherwise regeneration from git overwrites the user's GUI edits. A stable identity per fragment/item (item GUIDs exist in RPP; Live has note IDs) makes reconciliation tractable.

### Gaps
- No tool was found that does automatic three-way merge of GUI edits into a git-tracked text source for REAPER.

## Q11. OS fit (Windows 11 PC running Claude Code; headless Linux AutoDL server) and unattended operation

### Takeaway
The Windows 11 PC can host every candidate except Logic. The headless Linux server realistically supports only: REAPER (native Linux build, needs a display server or Xvfb, unverified; Linux-native plugins only), SuperCollider NRT, Strudel via headless Chromium, and music21/MusicXML/MIDI generation. Ableton, FL Studio and Cubase do not run there. MuseScore 4 headless is unreliable.

### Cited Findings
- REAPER has Linux x86_64/aarch64 builds; the Windows version "works well with WINE". — [reaper.fm](https://www.reaper.fm/download.php)
- Linux-capable REAPER MCP bridges:
  - xDarkzx uses `/tmp/reaper_mcp` on Linux. — [GitHub](https://github.com/xDarkzx/Reaper-MCP)
  - TwelveTake uses `~/.config/REAPER/Scripts/mcp_bridge_data`, and its "x86_64-linux dev shell is tested and working". — [GitHub](https://github.com/TwelveTake-Studios/reaper-mcp)
  - reaper-daemon runs on macOS, Windows and Linux. — [GitHub](https://github.com/wretcher207/reaper-daemon)
  - wegitor: "Checked on Linux: Yes". — [GitHub](https://github.com/wegitor/reaper-reapy-mcp)
- Ableton tooling is Windows/macOS. LivePilot: "macOS + Windows". Kumi: Live on macOS 13+ / Windows 10/11. — [LivePilot](https://github.com/dreamrec/LivePilot); [kumi](https://github.com/user1303836/kumi)
- Producer Pal's export skill is macOS-only (AppleScript). — [producer-pal.org](https://producer-pal.org/extending)
- FL Studio MCPs require Windows or macOS plus loopMIDI/IAC; karl-andres's note bridge foregrounds FL via keystroke on Windows. — [karl-andres](https://github.com/karl-andres/fl-studio-mcp); [postfader](https://github.com/synopsys0/postfader-fl-studio-mcp)
- MuseScore 4 CLI headless issue (#17247). — [GitHub](https://github.com/musescore/MuseScore/issues/17247)
- sclang-mcp renders offline with "no audio device needed" on Linux. — [GitHub](https://github.com/pimvanoerle/sclang-mcp)
- fadelabs/phantom (mixing-analysis MCP + Claude Code skills, 42 stars): "Windows is not supported: the Essentia dependency has no Windows wheel" (macOS/Linux only). — [GitHub](https://github.com/fadelabs/phantom)

### Inferences
- Split the pipeline: compose, generate and diff text and MIDI anywhere (including Linux); render realistic instruments in REAPER on the Windows PC, where Windows VST3/Kontakt-class libraries are installed; use the Linux GPU server for the neural/vocal parts. The REAPER Linux path is worth testing only if the instrument set is Linux-native (or bridged via yabridge, which was not researched here).
- "Unattended" in REAPER means a startup script or `-renderproject` with all dialogs suppressed. With Ableton it means real-time capture or GUI automation; with FL Studio it is not possible (render is UI-only).

### Gaps
- Not verified: REAPER `-renderproject` under Xvfb on Ubuntu; plugin compatibility on Linux; yabridge with REAPER for Windows VSTs.

## Q12. Concrete examples of people using Claude/LLMs this way for complex multi-track music, and what went wrong

### Takeaway
Public demos show LLMs can produce multi-track MIDI sketches, and that they handle session organization well. Reported failures:
- sound design and effects choices ("absolutely terrible results");
- missing tool features and timeouts on complex arrangements;
- agents claiming parts that contain no notes;
- bland or derivative musical output;
- tool-count and context limits.

Practitioners who keep the musician in control of sound choice and mixing report better outcomes.

### Cited Findings
- bschoepke demos (Codex + Ableton): a full EDM track with vocals (macOS `say`), chiptunes and 80s drum machines, built with a chain of corrective follow-ups: "i want midi for everything but vocals…", "needs some fills", "the vocals are squished too much", "add some dynamics, the song is basically one volume", "doesn't seem like the new thing has any notes", "the element is a bit muddy/indistinct". A second demo is a piano duet using Keyscape (a third-party plugin). — [GitHub](https://github.com/bschoepke/ableton-live-mcp)
- HN, "Experiments with Ableton-MCP" (jhurliman, about Dec 2025; 102 points):
  - Organizing, renaming and coloring 100+ track sessions "works extremely well".
  - Effect prompts gave "absolutely terrible results".
  - ableton-mcp "still lacks many features".
  - An LLM writing LilyPond produced "4-5 tracks of MIDI that is just what I asked for", with the human assigning sounds.
  - The author found tool efficiency improved after adding docstrings with examples. — [HN](https://news.ycombinator.com/item?id=46428922)
- HN, "Claude Composer" (josh.ing, about Feb 2026; 125 points): Claude Code built tracks without an audio model. Commenters found the output bland ("these songs suuuuuck") and argued AI tools "are operating on the entirely wrong abstraction layer". Others said symbolic MIDI/notes output is more useful because you can "plug them into a DAW and build something worthwhile". — [HN](https://news.ycombinator.com/item?id=46891689)
- ahujasid/ableton-mcp README: complex arrangements may need splitting into smaller steps; timeouts occur; connections often require restarting both Claude and Live. — [GitHub](https://github.com/ahujasid/ableton-mcp)
- Tool-surface limits:
  - xDarkzx warns that its 181-tool default surface "will silently truncate" on smaller models (e.g. Groq Llama 3 caps at 128 tools) and offers `REAPER_MCP_PROFILE`. — [GitHub](https://github.com/xDarkzx/Reaper-MCP)
  - LivePilot cut its exposed surface from 474 to a 26-tool loop plus search/call. — [GitHub](https://github.com/dreamrec/LivePilot)
  - wstierhout notes that 156 tools "is a lot for a model to choose from". — [GitHub](https://github.com/wstierhout/ableton-live-mcp)
- Safety: bschoepke warns the MCP "could corrupt" a Live Set. Sonic Field cautions that many community repos are "tiny, partial, experimental" and that connecting them to local studio environments raises trust risks. — [GitHub](https://github.com/bschoepke/ableton-live-mcp); [Sonic Field](https://sonicfield.org/ai-agents-enter-the-studio-the-mcp-turn-in-audio)
- xDarkzx's approach for orchestral realism: "The AI writes every note, rhythm, CC curve, and keyswitch itself", using a `00_core.md` instruction file that includes a "BBC Spitfire CC reference". — [GitHub](https://github.com/xDarkzx/Reaper-MCP)

### Inferences
- The failure modes point to the same design for this user: put harmony and melody generation in deterministic code or validated text (key/mode checks, measure-duration checks); keep instrument choice in an explicit orchestration map that the user approves; make every DAW write followed by a programmatic read-back diff; render offline and check levels before any listening.

### Gaps
- No detailed public post-mortem was found of a long (>5 min), many-track, orchestral-realism piece made through any of these MCP servers.
- No reports were found specifically about REAPER + Claude multi-track composition quality; REAPER coverage in public discussion is mostly about mixing and mastering.
