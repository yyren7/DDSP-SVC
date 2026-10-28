# 编曲（2026-10-28 起）

编曲相关的任务都放在本文件夹（`tools/arrange/`）：脚本、说明和进展记录。翻唱的转换、混音仍见 [../README.md](../README.md)，转换模型对比见 [../bakeoff/README.md](../bakeoff/README.md)。

## 管线选型（2026-10-28 调查）

用户要求 Claude 纯代码作曲：先写纯音乐，之后加人声；乐器音色尽量逼真；每次修改都要能精确到每个音符、每个音色，并看得清改了什么。

调查报告：[reports/Claude 编曲管线选型.md](reports/Claude%20编曲管线选型.md)，五个方向的原始笔记和本地实测脚本在 [research_notes/Claude 编曲管线选型/](research_notes/Claude%20编曲管线选型/)。结论是“项目即代码”：

- 原稿是 git 里的文本事件文件，一行一个音符，每个音写明小节、起点、时值、音高、力度和演奏法。MIDI 和 MusicXML 都由脚本生成，不进 git。
- 演奏法写通用名称，每个音源一张对照表，换配器只改对照表。
- 乐器在 Windows 电脑上用 Pedalboard 逐轨渲染（只用 CPU、内存和硬盘），按哈希缓存，改一个音只重渲那一轨。商用音源只支持 Windows/macOS，不放 AutoDL。
- 人声：主旋律编译成 DiffSinger 乐谱，在 AutoDL 上合成引导人声，再用 DDSP-SVC / RIFT-SVC 换成目标歌手。
- 文生音乐模型（Suno 等）做不到逐音控制，只用来找灵感。

## 用法（2026-10-28 起）

环境：`python -m venv .venv`，`.venv/Scripts/python -m pip install -r requirements.txt`，以下命令都在本文件夹下用 `.venv/Scripts/python` 运行。格式和每个脚本的细节写在脚本开头。Claude 的工作流程写在 [.claude/skills/arrange/SKILL.md](../../.claude/skills/arrange/SKILL.md)。

| 脚本 | 作用 |
|---|---|
| `score.py` | 读原稿：`songs/<曲>/song.yaml`（速度、拍号、调、声部、曲式、混音）和每段一个文件夹，`<声部>.notes` 一行一个音（`小节 位置 时值 音高 力度 [演奏法]`），`chords.txt` 和弦，`<声部>.cc` 控制器曲线 |
| `validate.py` | 检查：小节越界、音域、同音重叠、和弦能否解析（错误）；调外音、低音不在和弦根音、平行五八度、和声节奏或旋律过于单调（警告） |
| `build.py <曲> [--fmt]` | 检查后生成 `build/<曲>/`：通用 MIDI、按音源翻译的逐轨 MIDI（`render/`）、MusicXML、钢琴卷帘 `roll.png` |
| `frag.py` | 片段变换：移调、沿调式平移、换调式、倒影、逆行、增减时值、平移、截取小节；结果是新的 `.notes`，文件头记来源 |
| `review.py <曲> [版本]` | 和 git 某版本逐音对比（加 `--musicdiff` 再附谱面差异） |
| `render.py <曲>` | 每个声部用独立的插件实例离线渲染成单轨，按哈希缓存，再按 `mix:` 混成 `build/<曲>/<曲>.wav`；`--capture` 保存插件状态，`--repro` 测两次渲染是否一致，`--smoke <音源>` 把每个音色的每种演奏法各弹一个音（`build/smoke/`），用来检查新音源 |

`library_map/<音源>.yaml` 是对照表：每个音色对应的插件、状态、音域、演奏法（切换键、CC 或音色号）。sfz 音源（`state_from: sfz`，用 sfizz 播放，如 VSCO 2 CE）只写 sfz 文件路径，插件状态由 `render.py` 生成；其他插件（如 Kontakt）要先用 `--capture` 打开插件窗口，手动加载一次音色，再保存状态。音源装在仓库外的 `D:\audio_libs\`。

试点曲 `songs/pilot/`：16 小节 8 个声部，D 多利亚调 8 小节，经 A7sus4、B7sus4 上行全音进入 E 多利亚调 8 小节。

## 渲染实测（2026-10-28，sfizz 1.2.3 + VSCO 2 CE 1.1.0）

试点曲 8 轨都用 VSCO 2 CE 渲染，对应调查报告“九项测试”里免费档的第 1、2、4、5 项：

- 耗时：8 轨首次渲染共 54 秒，其中每轨加载 sfizz 和采样约 3 秒，渲染本身最慢的是竖琴，10 秒。不改动时重跑 1 秒；改一个音只重渲那一轨，约 4 秒。进程内存 260–630 MB。
- 可重复：同一轨从新实例渲染两次，结果逐字节相同（测了竖琴、大提琴、长笛）。
- 准确：起音比谱面晚 0–70 毫秒，是采样自带的起音，长笛的气声最长。单独发声的长音，木管和圆号的音高误差在 18 音分以内，弦乐在 13 音分以内。弦乐有几个音在起音后 0.12 秒测出差一个全音，那是前一个音的余音，0.3 秒后测到的都是谱面上的音。
- 演奏法：`--smoke vsco2` 里每种演奏法都出声；长笛、单簧管的 stac 和小提琴、中提琴的 spic、pizz 到 0.4 秒已衰减 26–42 dB，长音只降 1–4 dB。大提琴和独奏低音提琴的短音余响较长（0.4 秒时降 10–13 dB），低音提琴的 pizz 到 0.4 秒只降 3 dB（已对照 sfz 确认 E6 是拨弦），用的时候要注意。
- 遇到的问题（`render.py` 都已处理）：Pedalboard 扫描不了 `sfizz.vst3` 文件夹，要指向里面的 DLL，并写 `plugin_name: sfizz`；`initialization_timeout` 在加载时和每次渲染前都会空等满这段时间，sfizz 设为 0；sfizz 的 DLL 会让进程退出时卡死，所以脚本结束时直接终止进程；Pedalboard 的 MIDI 事件格式是 (字节, 秒)。

还没测：Kontakt 8 Player + Spitfire SSO Discover（第 1–3、5 项的商用插件部分），等 Native Access 装好。
