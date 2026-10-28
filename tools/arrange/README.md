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
