# 把总谱写成代码，让 Claude 逐音掌控编曲

和 Claude 契合度最高、也最能满足“每个音符、每个音色都能单独改，看得清改了什么，随时能复现”的方案，是一条**“项目即代码”管线**。Claude Code 在 git 仓库里直接写**一行一个音符、每个音自带绝对起点**的文本事件文件，按段落 × 乐器分文件存放，另外配旋律片段库、和弦表、控制器侧车文件和各音源的演奏法映射表。这些文件由 Python 编译：music21 管调式、移调、和声与声部进行校验，pretty_midi 生成带 CC、键位切换和速度表的多轨 MIDI。之后在 Windows 11 上用 Spotify Pedalboard 一轨一个实例加载商用 VST3 采样音源离线渲染，DawDreamer 和 REAPER 命令行做后备，每条 stem 按哈希缓存。同一份源里的主旋律再编译成 DiffSinger 乐谱，在 AutoDL 上合成向导人声，交给你现有的 DDSP-SVC / RIFT-SVC 换成指定歌手。核心是**一个代码库加一个项目 skill，不是某个 MCP 服务器**；只有你想在 DAW 图形界面里手改音符时，才需要 REAPER 的 MCP。这样排的理由是三道关：逐音精确、局部修改不波及其余、相同输入可复现。只有“符号源 + 采样渲染”三关全过；Suno、ElevenLabs、Lyria、ACE-Step 等文生音乐模型三关全挂；拿 DAW 会话当真相源，则 diff 难读，状态也不在 git 里。唯一一项专门用 Claude 做的作曲研究指向同样的做法：Claude Code + Opus 4.8 用显式起点的逐小节文法，配合参考片段检索和“测量—修改”循环，全曲结构检查通过率从 **62% 升到 94%**（[Libretto](https://arxiv.org/abs/2606.22708)）。预算只决定映射表背后挂哪套音源：免费档软件费 $0（REAPER 转正 $60），约 $520 档加 Pianoteq 9 和 EZdrummer 3，不设上限档换 Komplete 15、CSS 或 BBC SO Pro、Superior Drummer 3。眼下最大的未知数，是 Kontakt 系音源能否在 Pedalboard 里无界面、无掉音、逐位一致地渲染。这一点要先在你的电脑上实测；测试结果只决定用哪个渲染后端，整体架构不变。

## 推荐管线：git 里一行一个音符，Windows 上一轨一条 stem

主控面选“代码库 + skill”而不选“DAW + MCP”，是因为 Claude Code 最可靠的动作本来就是读写文本、运行脚本、阅读 diff，而 DAW 类 MCP 服务器会把 Claude 推到它不擅长的地方。这类服务器动辄给模型塞 156 到 474 个工具。wstierhout 的作者承认 156 个工具“对模型来说太多”；LivePilot 已把对外暴露的工具从 474 个砍到一个 26 工具的循环，再加搜索与调用入口（[wstierhout](https://github.com/wstierhout/ableton-live-mcp)；[LivePilot](https://github.com/dreamrec/LivePilot)）。xDarkzx 的 REAPER 服务器干脆删掉了读取 CC 的工具，因为读一整首管弦编曲的 CC1/CC11“会撑爆 AI 的上下文”（[xDarkzx TOOLS.md](https://github.com/xDarkzx/Reaper-MCP/blob/main/docs/TOOLS.md)）。写入还可能不落地：bschoepke 的演示日志里，智能体报告建好了音轨，用户却回了一句“新东西好像一个音符都没有”（[bschoepke](https://github.com/bschoepke/ableton-live-mcp)）。已经在做智能体编曲的实践者，多半把可读文本放进 git 当唯一真相，把 DAW 或打谱软件当渲染面。Hallucinote 明说“Ableton 是音频渲染与演奏采集面，不是主记录”；mcp-score 和 EasyMuseMCP 都是先由代码或文本编译出 MusicXML，再交给 MuseScore（[Hallucinote](https://news.ycombinator.com/item?id=49271123)；[mcp-score](https://github.com/tskovlund/mcp-score)；[EasyMuseMCP](https://github.com/Ranger013/EasyMuseMCP)）。落到这个仓库，代码可以放在已有的 `tools/arrange/` 下，skill 写成 `.claude/skills/arrange/SKILL.md`。skill 里规定：事件格式、构建与校验命令、工作顺序、去哪取参考片段，以及“每次修改一个 commit，附 musicdiff 报告”。

### Claude 写显式起点的文本事件，ABC 和 MusicXML 只当编译产物

逐音修改能否保持“局部”，取决于格式。ABC 最省 token：ChatMusician 统计每首平均 288 个 token，约为 MIDI 类表示的 **38%**（[ChatMusician](https://arxiv.org/html/2402.16153v1)）。但 ABC 里音符的起点要靠累加前面的时值才能算出，改一个时值，同小节后面所有音都会跟着挪。MuPT 还指出，常规多轨 ABC 逐轨顺序书写，“与大模型的逐 token 预测不太兼容”（[MuPT](https://qmro.qmul.ac.uk/xmlui/bitstream/handle/123456789/106408/Ma%20MuPT:%20A%20Generative%202025%20Accepted.pdf?sequence=2&isAllowed=y)）。Libretto 为 Claude 设计的文法让每个音符“直接带着绝对起点槽位”：字符比 ABC 多，但改时值不会推动后面的起点（[Libretto](https://arxiv.org/pdf/2606.22708)）。本地实测同一段 4 小节 3 轨片段的大小：手写 ABC 211 字符，LilyPond 400 字符，紧凑 JSON 事件表 654 字符，music21 导出的 MusicXML **12,341 字符，约为 ABC 的 58 倍**；MIDI 为 470 字节，是二进制，没法手写（本地实测，脚本 [probe2.py](../research_notes/Claude%20编曲管线选型/probes/probe2.py)，输出在同目录 `probe_out/`）。所以源文件用显式起点、一行一音、按固定顺序排序，单音修改在 git 里就是一行 diff；MusicXML 和 MIDI 都由脚本生成，只当构建产物。建议的文件形态如下。网格是 16 分音符，槽位 1、5、9、13 是拍点，与 Libretto 一致；每小节的和弦标签单独放在和弦表里。

```text
# parts/chorus1/vln1.notes    bar slot dur pitch vel art
33  1  4  A5  84  legato
33  5  2  G5  76  legato
33  7  2  E5  72  staccato
# perf/vln1.yaml  另存 CC1/CC11/CC64 曲线、连奏重叠时长、人性化随机种子
```

光有格式不够，数小节、判断乐理这类事要交给代码。LilyBench 中开源模型数对小节数的准确率只有 **0–3%**（[LilyBench](https://arxiv.org/html/2606.08722)）。MSU-Bench 的摘要片段显示，Claude Opus 4 / Sonnet 4 的读谱理解总分约 **41–43%**（[MSU-Bench](https://aclanthology.org/2026.acl-long.493.pdf)，数字来自检索摘要，未逐页核对）。Libretto 给出的缓解办法最可操作。把 1–3 段目标风格的参考片段放进上下文，通过率从 **25% 升到 75%**。加一个有上限的“生成—测量—修改”循环（最多 3 轮，保留当前最佳），全曲通过率从 62% 升到 94%。同一任务上 Opus 通过 6/8，Sonnet 与 Haiku 各 3/8（[Libretto](https://arxiv.org/pdf/2606.22708)）。它记录的失败形态，正是校验脚本该盯的东西：每小节两个和弦匀速滚动的“和弦传送带”、过于级进的音阶式旋律、缺乏起伏的织体密度。`validate.py` 因此要逐小节检查：时值总和；小节数是否与曲式表一致；和弦标签能否被 music21 解析；各乐器音域；旋律与低音对调式、和弦的贴合度。平行五八度和声部交叉用 music21 的 `VoiceLeadingQuartet` 检查（[music21 voiceLeading](https://www.music21.org/music21docs/moduleReference/moduleVoiceLeading.html)）。失败信息用“织体太稀”“和声太不稳”这样的音乐语言反馈给 Claude，不要只丢数字指标。工作顺序也按证据来：曲式 → 和弦 → 旋律 → 低音 → 鼓 → 铺底与弦乐 → 副旋律 → 加花。旋律与和声的决定交给 Opus。

### 片段库和 music21 变换承担多调式、移调与拼接

你会频繁让 Claude 生成多段旋律、换调式、在段落之间拼接，所以片段必须是一等公民。每个片段单独存一个小文件，记录这些内容：事件、拍号、主音、调式（包括五声和自定义音级集合）、音域、弱起、每小节隐含的和弦、角色标签，以及它从哪个父片段经过哪串变换而来。变换层基本有现成代码。music21 10.5.1（2026-10-22 发布）提供 `transpose`、`invertDiatonic`、`augmentOrDiminish`，支持 `key.Key('D','dorian')` 这类教会调式，并能用 `RomanNumeral('V7', key.Key('C'))` 与 `romanNumeralFromChord` 在和弦与级数之间双向换算（[PyPI music21](https://pypi.org/project/music21/)；本地实测 `m21probe.py`）。本地实测也查出两处空缺：**music21 没有通用的逆行**，只有十二音 `ToneRow` 有；**也没有五声音阶类**。这两样要自己写几十行。按调式音级平移可以照搬 LilyPond `\modalTranspose` 的规则：音按调内音级移动，调外音保持不动（[LilyPond](https://lilypond.org/doc/v2.24/Documentation/notation/changing-multiple-pitches)）。

拼接分四步。先算出片段 A 的出口和弦与末音，以及片段 B 的入口。再找一个在两个调里都有合法级数的共同和弦，或者用新调的副属和弦。然后让 Claude 在这个约束下写 1–4 小节过渡。最后用声部进行检查和旋律最大跳进检查验收。要有心理准备：Libretto 的“补写中间空缺”任务单次只通过 **12%**，加上循环也只到 **39%**（[Libretto](https://arxiv.org/pdf/2606.22708)）。过渡段是全流程最弱的一环，最好让 Claude 一次给出几个候选，由你挑。

### 演奏数据和音色映射分开存，换配器只改一张表

音源决定真实感的上限，演奏数据决定能不能够到这个上限。长音乐器靠 CC1 曲线（在力度层之间交叉渐变）、CC11 曲线（表情音量）和连奏重叠；打击乐和拨弦乐器靠力度与时值（[VI-Control](https://vi-control.net/community/threads/rant-about-cc1-cc11-and-velocity.168479/)）。因此源里每个音只写与音源无关的演奏法名称，由 `library_map/<音源>.yaml` 在编译时翻译成键位切换音符、CC32 值或音色切换。演奏法的分类可以借用 MIDI 2.0 管弦演奏法 Profile，MIDI 协会在 2026 年 2 月称它已定稿（[MIDI.org](https://midi.org/the-state-of-midi-2-0-high-resolution-performance-and-the-rise-of-profiles-update-feb-2026)）；不过调研没有找到能直接接受它的商用 VST3 音源。Spitfire 的 UACC 用 CC32 的固定值选择演奏法，各产品之间基本统一，但有例外：Studio Woodwinds Pro 的 marcato 实际在 41，界面上却标 52（[Spitfire 支持](https://support.spitfireaudio.com/en/articles/11816123)；[VI-Control](https://vi-control.net/community/threads/resolved-spitfire-uacc-not-working-correctly.92528/post-4545388)）。所以每张映射表都要锁定音源版本，并对每个演奏法做一次冒烟渲染。Babylonwaves Art Conductor（€99）收录了 1,000 多个音源的键位数据，可以当填表的原料（[KVR](https://www.kvraudio.com/news/babylonwaves-releases-art-conductor-11-2-62971)）。这样做之后，把长笛声部改给双簧管、把 Spitfire 换成 VSL，音符文件一行都不用动，只换映射表；映射不到的演奏法按 `marcato → staccato → short` 这样的回退链处理。

### Pedalboard 逐轨渲染、按哈希缓存，插件状态存档可复现

渲染放在 Windows 11 上，因为只有在这里商用音源才能稳定授权和运行。默认宿主是 Spotify Pedalboard（文档版本 v0.9.26）。它在 Windows 上能加载 VST3 乐器，按时间戳喂入 MIDI 离线渲染，用 `raw_state` 或 `.vstpreset` 格式的 `preset_data` 存取完整的插件状态；对后台异步加载采样的插件，还有 `initialization_timeout` 参数（[Pedalboard API](https://spotify.github.io/pedalboard/reference/pedalboard.html)）。后备是 DawDreamer v0.9.0：支持 VST2/3、处理器图和采样级自动化，`save_state/load_state` 不开界面就能恢复状态；它的兼容表显示，Kontakt 以 Windows VST2 `.dll` 的形式可以用（[DawDreamer](https://dirt.design/DawDreamer/)；[兼容表](https://dirt.design/DawDreamer/compatibility.html)）。

Kontakt 是这条链上最大的风险。DawDreamer 第 180 号 issue 中，Kontakt 7.6 VST3 在 macOS 上崩溃，换 Pedalboard 同样失败，经 REAPER 渲染却正常；JUCE 论坛另有报告，Kontakt 7 VST3 在 Windows 上无法载入 JUCE 7.0.5 宿主（[DawDreamer #180](https://github.com/DBraun/DawDreamer/issues/180)；[JUCE 论坛](https://forum.juce.com/t/ni-kontakt-7-vst3-windows-does-not-load-into-juce-host/58412)）。离线导出时 Kontakt 掉音也是各家 DAW 都有的老问题。常见对策是把 DFD 预载缓冲调到最大、打开离线渲染模式、关闭多核，或者改用 Sampler 模式（[VI-Control](https://vi-control.net/community/threads/kontakt-dropouts-only-while-rendering-exporting-and-freezing.123886/)）。第三道保险是 REAPER 命令行：脚本生成 `.rpp`，`reaper.exe -renderproject` 渲染完就退出；从 6.80 起还能在启动时带一个 Lua 脚本，再用 `-close:nosave:exit` 收尾（[ReaTeam CLI](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)）。REAPER 当前版本是 v7.83。它的 ReaScript 能逐音读写（`MIDI_GetNote`/`MIDI_SetNote`），能用 `TrackFX_AddByName` 加载插件，还能以 base64 形式存取插件状态 `vst_chunk`（[ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html)）。无论最后哪个宿主胜出，源文件和编译器都不用改，渲染器只是一个可替换的后端。

每个声部用一个插件实例，出一条 stem。缓存键是下列内容合起来的 sha256：编译后的 MIDI 字节、插件版本、状态字节、采样率、缓冲区大小、渲染长度。改一个音，只重渲那一轨。插件可能**输出静音却不报错**，一个基于 Pedalboard 的封装就明确警告过这一点（[ComfyUI VST Synth Adapter](https://comfy.icu/node/ComfyUIVSTSynthAdapter)）。所以每条 stem 都要查峰值和 RMS，异常就直接报错。可复现性靠三件事：每次新建实例，固定缓冲区，所有人性化随机数在 Python 里设种子。Kontakt 内置的全局轮换采样计数器无法从宿主重置（[KVR 论坛](https://www.kvraudio.com/forum/viewtopic.php?t=393914)）。这类插件只能渲两次比哈希；哈希不一致时，改用零差测试，要求两次渲染的残差低于 −90 dBFS。

AutoDL 上不跑商用音源，原因有四。SWAM 官方不支持 Linux（[Audio Modeling](https://kb.audiomodeling.com/support/solutions/articles/206000050983-can-i-run-swam-instruments-on-linux-)）；Kontakt 8 在 Wine/yabridge 下曾随 Native Access 2 一起失效（[NI 社区](https://community.native-instruments.com/discussion/41978/how-much-would-you-charge-to-make-a-linux-version)）；Wine 没有真正的无头模式，得靠 Xvfb 虚拟显示（[Wine bug 49500](https://list.winehq.org/pipermail/wine-bugs/2020-July/538535.html)）；而且每台机器都要多占一个激活名额。GPU 对采样回放也毫无帮助。

### 每次修改产出四样审阅材料：源码 diff、musicdiff、钢琴卷帘、单轨试听

“看清改了什么”靠四样材料。第一样是源文件的 git diff，一行一音时最干净。第二样是对编译出的 MusicXML 跑 musicdiff 6.0（需要 Python 3.12+）：它按“第几小节、第几行谱、第几拍”报告差异，也能输出把改动标红的谱面 PDF（[musicdiff](https://pypi.org/project/musicdiff/)）。本地实测：两份三轨总谱只差一个音（第 2 小节 F5 改成 G5 并加跳音），musicdiff 文本模式只输出一条 `@@ measure 2, staff 1, beat 2.0 @@ -(Note) F5 … +(Note) G5 …, articulations=[staccato]`；直接 diff 两份 MusicXML 却有 **31 行**变化，主要是因为 music21 每次导出都随机生成声部 ID（本地实测 `probe2.py`）。所以构建脚本要么把 ID 固定下来，要么干脆不把 MusicXML 放进 git。musicdiff 只比记谱，不管 CC、力度和键位切换，这些靠侧车文件的文本 diff。第三样是图：pretty_midi 的 `get_piano_roll` 和 `get_downbeats` 足够画带小节线的单轨钢琴卷帘（鼓和 CC 用卷帘看最清楚，本地实测确认接口存在），Verovio 6.3.0 能把 MusicXML 渲染成 SVG 总谱（[Verovio](https://book.verovio.org/toolkit-reference/input-formats.html)）。第四样是改动那一轨的试听片段。

如果你想在 DAW 里手改，可以把源编译成 `.rpp`，在 REAPER 里打开修改。改完后，用 RPP 解析器或 TwelveTake 的 REAPER MCP 把音符读回来、量化、写回事件文件，git diff 就会精确显示你手改了哪些音。TwelveTake 让 AI 的每次修改都成为 REAPER 撤销历史中的一个具名步骤（[TwelveTake](https://github.com/TwelveTake-Studios/reaper-mcp)）。关键是**重新生成之前必须先同步**，否则会覆盖你的手改。

### 同一条旋律变成人声向导：DiffSinger → DDSP-SVC / RIFT-SVC

先写纯音乐、后加人声，在这条管线里几乎不花额外成本：主旋律本来就在源里，作曲时顺手按目标歌手的音域检查一遍，以后给每个音挂上歌词就行。无人值守的最短路径是把主旋律编译成 `.ds` 文件，在 AutoDL 上依次跑 openvpi DiffSinger 的 `python scripts/infer.py variance` 和 `acoustic`（Apache-2.0，输出 44.1 kHz），再送进你现有的 DDSP-SVC / RIFT-SVC（[DiffSinger](https://github.com/openvpi/DiffSinger)；[GettingStarted](https://raw.githubusercontent.com/openvpi/DiffSinger/main/docs/GettingStarted.md)）。`.ds` 的完整字段规范调研没能拿到，要对照 DiffSinger 自带的样例确认。日语还可以在 Windows 上用 NEUTRINO（把 MusicXML 放进指定目录，运行 `Run.bat` 即出 WAV），或用 VOICEVOX 引擎的 HTTP 歌唱接口 `/sing_frame_audio_query`（[NEUTRINO 教程](https://dev.classmethod.jp/articles/tutorial-about-neutrino-neural-singing-synthesizer/)；[VOICEVOX](https://deepwiki.com/VOICEVOX/voicevox_engine)）。中文可选 SoulX-Singer，它是 Apache-2.0，可以用 MIDI 做条件，但**不支持日语**（[SoulX-Singer](https://github.com/Soul-AILab/SoulX-Singer)）。

有两条硬约束必须写进 skill。第一，SVC 只换音色，音高曲线和时值都照搬向导。有人总结过：“唱得差或编得差的 Synth-V 演唱，RVC 救不回来”（[vi-control](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-209)）。所以颤音、滑音、气口都要在 SVS 阶段写进乐谱。第二是许可。VoiSona 2026-02-24 修订的条款明文禁止把它的合成声用作声音转换的输入（[VoiSona 条款](https://voisona.com/static/pdf/en/terms.pdf)）。DiffSinger 声库的条款一库一议，每个都要查“能不能用作声音转换的输入”，不能只看“能不能训练”。Synthesizer V 2 的脚本可以写入每个音、音素和音高曲线，但手册里没有渲染导出函数，只能半自动（[SV 脚本手册](https://resource.dreamtonics.com/scripting/)）。和声与叠唱走同样的流程，每条和声线单独合成、单独转换。长期来看，可以在取得歌手本人同意后，用她自己的干声训练 DiffSinger 声学模型，省掉 SVC 这一步，代价是要用 MFA 或 SOFA 做音素对齐（[MakeDiffSinger](https://github.com/openvpi/MakeDiffSinger)）。

### 混音靠确定性效果链和硬指标，大模型只写评语

混音同样写成代码，并接上你现有的响度匹配脚本。Pedalboard 自带压缩、限幅、滤波、卷积混响、移调等效果，也能挂 VST3（[Pedalboard](https://github.com/spotify/pedalboard)）。pyloudnorm 按 ITU-R BS.1770-4 测响度（[pyloudnorm](https://gitee.com/shirlim/pyloudnorm)）。Matchering 2.0 对照参考曲匹配 RMS、频响、峰值和立体声宽度来做母带（[Matchering](https://github.com/sergree/matchering)）。ISMIR 2026 的一项研究发现，先在组内（鼓、低音、和声、人声）混、再在组间平衡的两段式混音，明显好于一次混完（[arXiv 2609.02835](https://arxiv.org/abs/2609.02835)）；代码生成的 stem 天然带标签、已经分好组。

决定是否放行用硬指标：Spotify 把响度归一化到 −14 LUFS，建议真峰值低于 −1 dBTP（[Spotify](https://support.spotify.com/artists/article/loudness-normalization/)）。软分数用 Audiobox Aesthetics（[audiobox-aesthetics](https://github.com/facebookresearch/audiobox-aesthetics)），歌声可以参考 SingMOS-Pro 数据集（[SingMOS-Pro](https://arxiv.org/html/2510.01812v4)）。不要拿通用音频大模型的打分做决定。MuseCritic 的测试中，Gemini-3.1-Pro 与专家评分的相关系数只有 **0.49–0.62**，Qwen3-Omni 的成对偏好准确率是 **53.75%**，接近瞎猜（[MuseCritic](https://arxiv.org/html/2608.11755)）。HN 上也有人反馈，让大模型凭提示词选效果“结果糟透了”（[HN](https://news.ycombinator.com/item?id=46428922)）。

还有一条许可提醒和你平时训练模型直接相关。NI 的 EULA 禁止把它的产品和音频内容用于训练 AI（[NI EULA](https://native-instruments.com/en/company/legal-information/end-user-license-agreement)）；据检索摘要，Spitfire 的 EULA 也有同类条款（[Spitfire EULA](https://www.spitfireaudio.com/info/eula/)）。所以**渲染出来的乐器 stem 不能拿去训练 DDSP 或任何模型**，只能用在作品本身。

## 三档预算只换音源，不换架构

三档的宿主、编译器、校验和混音完全一样。Pedalboard、DawDreamer、music21、pretty_midi、musicdiff、Matchering 都免费，差别只在映射表背后挂的音源。REAPER 有 60 天全功能试用，个人折扣授权 $60，商业授权 $225（[REAPER](https://www.reaper.fm/purchase.php)）。建议三档都保留它做 Kontakt 后备。

| 档位 | 管弦 | 键盘 | 鼓 | 吉他与其他 | 合计 |
|---|---|---|---|---|---|
| 免费 | Spitfire Symphony Orchestra Discover（免费，Kontakt Player，44 件乐器，3 个真连奏音色）（[Spitfire](https://www.spitfireaudio.com/products/spitfire-symphony-orchestra-discover)）+ BBC SO Discover（33 件，无真连奏，二手来源）（[rubato PR](https://github.com/philipdallen/rubato/pull/387)）+ Spitfire LABS | 调研未覆盖，空缺 | **空缺**：没找到接近 SD3 水准的免费鼓 | Ample Guitar M Lite（自带扫弦器）（[BPB](https://bedroomproducersblog.com/free-vst-plugins/guitar/)）；服务器后备用 VSCO 2 CE（CC0）+ sfizz（[Versilian](https://versilian-studios.com/vsco-community/)） | $0（REAPER 转正 $60） |
| 约 $520 | 仍用两套 Discover；或把这笔钱换成 BBC SO Core $449（[Spitfire](https://www.spitfireaudio.com/en-us/collections/bbc-symphony-orchestra)） | Pianoteq 9 Standard €269，命令行支持 `--headless`、`--midi`、`--wav`、`--preset`、`--no-prefs`，Windows 和 Linux 都能用（[SOS](https://www.soundonsound.com/node/4934244)；[Modartt](https://forum.modartt.com/viewtopic.php?id=11200)） | EZdrummer 3 $179（[Toontrack](https://www.toontrack.com/product/ezdrummer-3/)） | 同免费档 | $60 + €269 + $179 ≈ $520 |
| 不设上限 | Cinematic Studio Strings 约 $399（需完整 Kontakt，第三方报价）（[MPW](https://musicproductionwiki.com/articles/best-plugins-for-strings)），或 BBC SO Pro 标价 $999 / VSL Synchron | Keyscape 约 $379–399 + Omnisphere 3 约 $479（[Dubspot](https://blog.dubspot.com/plugins/compare/keyscape-vs-omnisphere-3)）；Pianoteq Pro €399 | Superior Drummer 3 $399（[Toontrack](https://www.toontrack.com/product/superior-drummer-3/)） | Komplete 15 Collector's Edition 首发价 $1,799（[SOS](https://www.soundonsound.com/news/native-instruments-komplete-15-incoming)）；露脸的独奏弦乐和管乐用 SWAM（$227–699，不支持 Linux，需要极细的 CC）（[Sweetwater](https://www.sweetwater.com/store/detail/SWAMSoStrBun--audio-modeling-swam-solo-strings-bundle)；[ILIO](https://www.ilio.com/swam-strings-bundle)）；Art Conductor €99 | 按所列价格合计约 $4,300 起，促销季会低不少 |

免费档有一个被低估的用处：SSO Discover 是 Kontakt 音源，它跑通了，CSS、Komplete 这类同样基于 Kontakt 的付费音源大概率也能跑通。所以**花钱之前，先用它零成本验证整条 Kontakt 渲染路径**。免费档最大的缺口是鼓，调研没有找到够格的免费鼓音源。约 $520 档里最适合代码驱动的是 Pianoteq：它是物理建模，不依赖磁盘串流采样，自带无头命令行导出和 `--no-prefs` 启动选项，也有 Linux 版，必要时可以在 AutoDL 上渲染钢琴。不设上限档要注意，Session Guitarist 扫弦这类依赖脚本的 Kontakt `.nki`，在 Kontakt 7.6 之前于 DawDreamer 离线导出时掉过音（[DawDreamer #180](https://github.com/DBraun/DawDreamer/issues/180)），买之前要实测。不想一次性买断的话，EastWest ComposerCloud+ 订阅每月 $19.99–29.99，可以用整个曲库（[Soundsonline](https://www.soundsonline.com/orchestral/hollywood-strings-2)）。

## 六类备选方案都先输在“逐音掌控”这一关

| 排名 | 方案 | 逐音精确 | 局部修改 | 可复现与可 diff | 主要扣分 |
|---|---|---|---|---|---|
| 1 | **推荐：代码总谱 + Windows 逐轨采样渲染** | 是 | 一轨一条 stem | git 一行一音 + musicdiff | Kontakt 无头渲染待测 |
| 2 | REAPER 工程作真相源 + MCP（TwelveTake、xDarkzx） | 是，PPQ 级读写 | 是 | 能撤销，但 RPP 里的 MIDI 是相对偏移的十六进制，插件状态是 base64 | 状态在会话里，diff 难读，工具多 |
| 3 | Ableton Live + MCP（LivePilot、wstierhout） | 是，按 note ID | 是 | `.als` 差异工具有限 | 没有渲染 API；第三方插件参数要手动 Configure |
| 4 | MusicXML → MuseScore 4 + Muse Sounds | 记谱级 | 小节或元素级 | MusicXML 可 diff | 不能挂 VST；Muse Sounds 自行加力度变化；导出据报只能实时 |
| 5 | 神经 MIDI→音频（TokenSynth、SpanSynth-Edit、ACE Studio 2） | 只在统计意义上 | 逐轨或按区域重合成 | 未验证 | 不保证逐音；ACE Studio 没有 API |
| 6 | Live coding（Strudel、SuperCollider） | 是，但都是合成器音色 | 重新生成代码 | 文本可 diff | 没有真实采样音源；Claude 写 Strudel 偏弱 |
| 7 | 文生音乐（Suno v6、ElevenLabs、Lyria 3.5、ACE-Step 1.5） | 否 | 只到段落或区域 | 种子“不保证”复现 | 三关全挂；Suno、Udio 有诉讼和下载限制 |

**REAPER 工程当真相源**是最接近第一名的方案。逐音的 `MIDI_GetNote`/`SetNote`、删插件再加插件而 MIDI 条目原封不动、用 `vst_chunk` 存取状态，这些它都有（[ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html)）。问题在于真相落在了会话里。RPP 文件里的 MIDI 存成形如 `e 300 90 2b 60` 的十六进制行，偏移量相对于上一个事件，插入一个音就会改动下一行；插件数据则标注为“二进制数据，别碰”（[ReaTeam State Chunk](https://github.com/ReaTeam/Doc/blob/master/State%20Chunk%20Definitions)）。这样一来，拼接、批量换配器和重新生成都只能依赖会话工具和撤销历史，而不是 git 历史。TwelveTake 也承认它的 `save_fx_preset` 总是报错，因为 REAPER 的 API 存不了具名预设（[TwelveTake](https://github.com/TwelveTake-Studios/reaper-mcp)）。所以 REAPER 在推荐方案里的位置是渲染后端和可选的手改界面，不当真相源。

**Ableton Live** 从 Live 11 起可以按 note ID 读改音符（`get_notes_extended`、`apply_note_modifications`）（[Cycling '74 LOM](https://docs.cycling74.com/apiref/lom/clip/)），但“Live 不提供渲染 API”，导出只能用 AppleScript 驱动导出对话框，而 AppleScript 只有 macOS 才有（[Producer Pal](https://producer-pal.org/extending)）；第三方插件的参数要先在 Configure 里手动暴露才能访问（[NIME 2023](https://nime.org/proceedings/2023/nime2023_60.pdf)）。在 Windows 上批量重渲许多变体，基本做不到。另外三家直接出局：FL Studio 的 API 不能加载插件、不能加载音频、也不能渲染（[flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp)）；Logic 只有 macOS 版（[logic-pro-mcp](https://github.com/MongLong0214/logic-pro-mcp)）；Bitwig 的 WigAI 已归档，只剩零散分叉（[WigAI](https://github.com/fabb/WigAI)）。

**MuseScore 打谱路线**在出谱和 diff 上很强，但做不到逐音色掌控。Muse Sounds 会自己加谱面上没写的力度变化，用户评价它的质量“要么很好，要么很差”（[Steinberg 论坛](https://forums.steinberg.net/t/musescore-4-muse-sounds/822977?page=8)）；MuseScore 不支持第三方音频插件（[Scoring Notes](https://www.scoringnotes.com/news/noteperformer-reverses-course/)）；论坛报告它的音频导出只能实时进行（[musescore.org](https://musescore.org/en/node/345238)）；EasyMuseMCP 的编辑粒度只到“小节/元素”（[EasyMuseMCP](https://github.com/Ranger013/EasyMuseMCP)）。推荐方案已经能用 Verovio 出谱，用不着 MuseScore。

**神经 MIDI 转音频**离要求最近，但做不到“保证逐音”。SpanSynth-Edit 一次渲染整个混音；按乐器区分的音符准确率是统计出来的，在 Slakh 的 37 类乐器 F 值上还不如 SpecDiff；编辑时整个区域重新合成，没改的音也未必原样保留（[SpanSynth-Edit](https://arxiv.org/html/2609.25546v1)）。TokenSynth 能按单个乐器用参考音色演奏给定的 MIDI，权重已公开（[TokenSynth](https://arxiv.org/html/2502.08939v1)）。ACE Studio 2 的 AI 乐器只做单声部的弦乐、铜管和萨克斯，售价 $497/$660，评测里没提 API（[SOS](https://soundonsound.com/reviews/ace-studio-2)）。它们适合作为可选的单轨升级，给露脸的独奏线换上更自然的音色，事后再扒谱与源 MIDI 比对；单声部扒谱相对可靠，乐器从 1 件增加到 3 件时，扒谱 F 值会下降 0.28 以上（[AMT Challenge](https://arxiv.org/pdf/2603.27528)）。

**Live coding** 用的是合成器，不是真实采样。Boogiebench 的作者发现“Anthropic 的模型表现低于预期”（[HN](https://news.ycombinator.com/item?id=46437861)），也有人记录 Claude 在 Strudel 里编造了不存在的采样文件名（[thoughtwax](https://thoughtwax.com/2025/06/live-coding/)）。

**文生音乐模型**三关全挂。Suno 在 2026-09-09 宣布全面换成 v6（[TNW](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models)），9 月 18 日索尼与环球又对它提起第二起诉讼（[RuntimeWire](https://runtimewire.com/article/sony-umg-suno-v6-copyright-lawsuit)）；Udio 从 2025 年 10 月起关闭了下载（[Digital Music News](https://www.digitalmusicnews.com/2025/11/20/will-udio-still-exist-in-2026/)）。ElevenLabs 的 seed 文档原话是“不保证精确复现”（[ElevenLabs](https://elevenlabs.io/docs/api-reference/music/compose)）。ACE-Step 1.5 是 MIT 许可，有 seed、BPM 和调性字段，能按时间段重绘，但不接受任何符号输入（[ACE-Step API](https://raw.githubusercontent.com/ace-step/ACE-Step-1.5/main/docs/en/API.md)）。它在 RTX 3090 上不到 10 秒出一首（[ACE-Step](https://github.com/ace-step/ACE-Step-1.5)），可以放在 AutoDL 上当灵感机，但不能当母版。

格式层面的备选也排在后面。ABC 的问题上面已经说过。LilyPond 在开源模型上零样本编译成功率是 48.6–79.3%，给了调内的手写示例能升到 97.1–99.9%（[LilyBench](https://arxiv.org/html/2606.08722)），适合当出谱目标，不适合当源。MIDI-GPT 能按轨、按小节补写，但权重限非商用（[MIDI-GPT](https://github.com/Metacreation-Lab/MIDI-GPT)），只适合给鼓的加花、伴奏织体提一些候选，候选还要导回事件文件，接受同样的校验与 diff。

## 拍板前要在两台机器上跑通的九项测试

| # | 机器 | 测什么 | 通过标准 | 不通过怎么办 |
|---|---|---|---|---|
| 1 | Windows | Pedalboard 无界面加载每个选定的 VST3 乐器（Kontakt 8 Player + SSO Discover、BBC SO Discover、LABS、Ample，以及之后要买的鼓和钢琴），渲染同一段 MIDI | 每条 stem 的峰值和 RMS 正常，长音无断续 | 先调 Kontakt（DFD 预载调到最大、开离线模式、关多核）；再试 DawDreamer + Kontakt VST2 `.dll`；最后退到 REAPER `-renderproject` |
| 2 | Windows | 同一 MIDI、同一状态连渲两次 | sha256 相同；有内部随机的插件残差低于 −90 dBFS | 把该插件记入清单，改用容差比较 |
| 3 | Windows | `raw_state` / `preset_data` 保存 → 重载 → 再保存 | 字节一致，渲染结果也一致 | 改用 REAPER `.RfxChain` 或 `vst_chunk`；Kontakt 状态引用磁盘上的库路径，路径和版本写进清单 |
| 4 | Windows | 每个演奏法的键位 / UACC 冒烟渲染 | 每个演奏法听起来都对 | 修映射表，锁定音源版本 |
| 5 | Windows | 大音色的加载与渲染耗时；改一个音之后重渲全流程的耗时 | 你自己能接受的迭代时间（调研没有找到实测数据） | 用常驻渲染进程让音色保持加载，拿一点复现风险换速度 |
| 6 | Windows | REAPER 生成 `.rpp` → `-renderproject` → `-close:nosave:exit` 全程无人值守 | 没有对话框卡住；缺插件时明确失败 | 用启动 Lua 脚本设置 `RENDER_*`，并自动确认覆盖提示 |
| 7 | Windows | musicdiff 6.0（Python 3.12+），加上固定 MusicXML 声部 ID 的补丁 | 改一个音只报一条差异 | 在构建脚本里后处理 ID |
| 8 | Claude | 16 小节 × 8 轨的试点：一次通过率、修订轮数、Opus 与 Sonnet 对比、各格式实际消耗的 token 数 | 3 轮内通过校验，token 用量可以接受 | 调整文件粒度，增加参考片段 |
| 9 | AutoDL | DiffSinger 向导（选许可允许作 SVC 输入的声库）→ DDSP-SVC / RIFT-SVC，与真人干声输入的结果对比 | 咬字、气口、句尾没有明显的 SVC 伪影 | 换音域更接近的向导声库，加强 SVS 阶段的表情；长期考虑用歌手干声训练 DiffSinger |

顺序很重要。第 1–3 项决定渲染后端，也决定免费档能不能用，应该在买任何付费音源之前用 SSO Discover 做完。第 8 项决定作曲质量能达到什么程度。现有证据最多只覆盖 5 个声部，没有任何研究评测过 10–30 轨的大模型编曲（Libretto 的规模上限是五声部），也没有关于动漫常用和声套路的数据，所以试点的数字比任何文献都更有参考价值。第 9 项决定人声这一端的上限。部署时有一个细节：AutoDL 上的 runner 会把仓库硬重置到 GitHub master，所以 DiffSinger 的声库、模型和可能用到的 ACE-Step 服务都要放在仓库目录之外。此外还有两件没测成的事要人工核实：一是 Spitfire EULA 全文（调研时抓取失败），二是你要用的每个声库关于“声音转换输入”的条款。

## 结论

这次选型真正决定成败的，不是选哪个 DAW 或哪个 MCP，而是**真相放在哪里**。一旦真相是 git 里的逐音文本，渲染器、DAW，甚至歌手的声音，都成了可替换的后端：换配器变成改一张映射表，换宿主变成换一个渲染函数，旋律一改，人声向导自动跟着变。“配器经常换、片段经常拼”这种工作方式，在其他方案里每次都是一场手术，在这里只是一次 commit。另一个不那么显眼的结论是：Claude 被测出来的短板——数不清小节、读谱理解只有四成左右、旋律容易平淡、过渡段写不好——恰好都能交给确定性代码检查。这条管线把这些短板变成看得见的校验失败，而不是藏在音频里的错误。Libretto 的数据也说明，提升最大的是参考片段和修改循环，不是更花哨的工具界面，所以 skill 最该投入的地方是参考片段库和反馈措辞。

风险集中在管线两端：一端是商用插件的无头渲染（Kontakt），一端是人声向导的表现力。两者都能先用零成本的方式验证：前者用免费的 SSO Discover，后者用开源的 DiffSinger 声库。神经音频模型留在外围，可以用来找灵感、升级个别独奏线，但永远不当母版。
