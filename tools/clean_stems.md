# 干净干声和伴奏的来源调研（2026-10-23）

翻唱时拿来做音色转换的输入人声（下称“导唱”），以后不再用原曲减伴奏或分离模型得到的人声。用户听下来这种做法效果很差：残留的伴奏、混响、和声和有损音源的编码噪声都会跟着进转换，转换后的人声发虚、发脏。本文调研怎样拿到干净的导唱和与之对齐的伴奏，并据此提出管线。这是 [PROGRESS.md](autodl/PROGRESS.md) 待办 B 的第一步，还没写代码。

## 结论

1. **J-pop、华语流行几乎没有官方单独发行的干声。**只有少数官方企划（TuneCore Japan 的 Rework with、各种 remix 比赛）会放出含人声的分轨，覆盖的歌很少，不能指望想翻哪首就有哪首。
2. **所以管线要分层**：
   - 先查这首歌有没有官方分轨，有就直接用。
   - 没有的话，**另外生成一条干净的导唱**：真人录（自己唱或者请人唱），或者用歌声合成渲染。
   - 原曲减伴奏、分离模型得到的人声，**不再作为转换的输入**。最多拿来参考音符和时间，比如从中扒 MIDI 给歌声合成用。
3. **欧美歌好办得多**（用户可以接受欧美歌）：独立音乐人的歌有研究、教学用的多轨库，带录音室原始干声，免费或便宜；知名歌有 Karaoke Version 的重录多轨、DJ pool 的官方 acapella。见“欧美歌”一节。
4. **对其余的歌来说，现实的选择是真人导唱或歌声合成导唱。**两者都是干声，录在官方伴奏上或者按伴奏的节拍渲染，天然对齐。哪个效果好要实测：建议先拿一首歌，把这两种和现在的做法放在一起比，再定默认做法。

## 什么算“干净”

| 要求 | 原因 |
|---|---|
| 干：不带混响、延迟 | 混响会被当成人声一起转换，转换后发浑。混响在混音时再按需要加 |
| 只有主唱，没有伴奏渗漏 | 渗漏进来的乐器会被转成“人声”，听起来就是杂音 |
| 和声单独一轨，或者没有 | 叠在一起的和声会让音高提取和内容编码出错 |
| 无损，或者高码率 | 有损编码的噪声和高频截止会跟着转换 |
| 和伴奏同一版本、时间对齐 | 转换后要直接混回伴奏 |
| 音域合适 | 和目标说话人差得太远时，用 `-k` 移调也会失真 |

## 来源一览

| 来源 | 能拿到什么 | 干净程度 | 和伴奏对得上吗 | 覆盖哪些歌 | 怎么获取，有什么条件 | 结论 |
|---|---|---|---|---|---|---|
| [TuneCore Japan「Rework with」](https://kai-you.net/article/96049) | 官方分轨（パラデータ），外加歌词、封面 | 官方分轨，人声那一轨是不是单独提供，每期要逐个确认 | 对得上，同一份工程 | 到目前三期：一青窈「ハナミズキ」（2023，截止 9 月 8 日）、HoneyWorks「可愛くてごめん」、椎名もた「少女A」（发行截止 2026-10-31，还在进行） | 官方允许二次创作（演唱、remix 等），作品通过 TuneCore 发行并分成，各期比例不同 | **歌对得上就优先用**。可愛くてごめん是花丸晴琉第一批翻唱里因为找不到同版本伴奏而放弃的歌，值得查一下这期的分轨还能不能下 |
| remix 比赛（[サンレコ × LDH 的 PSYCHIC FEVER「Highlights」](https://koubo.jp/contest/206060)、Marpril「sheep in the light」；[SURF Music](https://koubo.jp/article/36800) 的 m-flo「come again」（2025）、chilldspot「ネオンを消して」（2026）；[Skio Music](https://www.musicinafrica.net/node/365706)） | 人声分轨加伴奏（2mix 或分轨） | 官方录音室分轨，通常是干的或者轻度处理 | 对得上 | 只有比赛用的那几首；Skio 以欧美、电子为主 | 下载前要同意规约，一般只许用于参赛 | 碰上了再用，没法按需找 |
| DJ 商店的官方 acapella（[Beatport、Traxsource，Stems 格式](https://www.digitaldjtips.com/where-djs-get-acapellas/)） | 官方 acapella，或者四轨 stems | 官方 | 对得上 | 欧美舞曲为主 | 购买 | 基本不覆盖我们要翻的歌 |
| VTuber、同人作品（[BOOTH](https://www.moguravr.com/?p=99868)） | 常见的是 inst 和带和声的 inst | — | — | 这些人自己的原创曲 | 购买 | 这次没找到单卖 a cappella 的例子 |
| 中文音乐平台 | 官方伴奏版常见 | — | — | 华语歌 | — | 这次**没找到**官方发行的纯人声版或干声版 |
| [Karaoke Version](https://www.karaoke-version.com/blog/1560-isolate-and-download-each-track-separately-on-versao-karaoke.html) 的 Custom Backing Track | 录音室乐手**重新录制**的整首（不是原版母带），每一轨都能单独导出（静音其他轨再导出，一次导一轨） | 录音室多轨，干净 | 对得上，但伴奏是它自己重录的，不是原版 | 欧美为主，有没有日语歌没确认 | 按首购买，买了以后可以无限次导出 | 欧美歌可以用，但伴奏和人声都不是原版 |
| **真人导唱：自己录** | 戴耳机跟着官方伴奏唱的干声 | 取决于话筒和房间，干声本身是干净的 | 天然对齐 | 任何歌 | 不花钱；要有安静的房间和像样的话筒 | **候选默认做法之一**。唱功直接决定转换效果，因为音高、节奏、咬字都从导唱来 |
| **真人导唱：请人录**（仮歌、代唱） | 专业或半专业歌手的干声 | 好；要**明确要求交不加效果的干声 WAV** | 天然对齐（给对方官方伴奏） | 任何歌 | 收费。[ココナラ](https://coconala.com/services/1981436)上的一个例子：一段副歌 2,500 日元、整首 5,500 日元，作为正式作品发表另加 5,000 日元，交付 3～6 天 | 质量最稳，但每首都要花钱 |
| 网友分享的练习用干声（“ミックス練習用素材”“混音练习干声”） | 翻唱者自己的干声加伴奏 | 家里录的，质量参差 | 一般对得上 | 零散 | 规约通常只许练习，禁止转载或发表 | 这次没找到集中的素材库，只能碰运气 |
| **歌声合成导唱** | 用 Synthesizer V、ACE Studio、OpenUtau + DiffSinger 等，从 MIDI 加歌词渲染出的干声 | **完全干净**：没有混响、渗漏，音高准 | 按伴奏的节拍渲染，对得上 | 任何歌，前提是有 MIDI 和歌词 | 见下面一节 | **候选默认做法之一**。好处是每个字的发音都能指定，和待办 A（修唱错的字）正好互补 |
| 歌声数据集（[M4Singer](https://proceedings.neurips.cc/paper_files/paper/2022/hash/2de60892dd329683ec21877a4e7c3091-Abstract.html)、[GTSinger](https://arxiv.org/abs/2409.13832v7)、Opencpop） | 专业歌手在录音室录的清唱 | 很干净 | **对不上**：没有伴奏，速度和调也是歌手自己定的 | M4Singer：700 首普通话歌；GTSinger：9 种语言，包括中文、日语；Opencpop：100 首普通话流行歌 | 都只许非商业使用：M4Singer 是 CC BY-NC-SA 4.0，要申请审核；GTSinger 据转引也是 CC BY-NC-SA 4.0；Opencpop 的许可这次没打开官网，需核实 | 只适合当测试素材，不适合做翻唱 |
| 不用的 | acapella 下载站（DJ 指南说[多半是分离出来的](https://www.digitaldjtips.com/where-djs-get-acapellas/)，没法核实）、游戏解包的多轨（Rock Band 等，侵权）、AI 分离和相位抵消（正是要避免的） | — | — | — | — | 排除 |

### 欧美歌（2026-10-23 补充：用户可以接受欧美歌）

欧美这边官方或艺人认可的分轨多得多，按好不好拿分四类：

| 来源 | 内容 | 人声干净程度 | 有哪些歌 | 怎么获取 | 结论 |
|---|---|---|---|---|---|
| 研究、教学用的多轨库：[MedleyDB](https://zenodo.org/records/1649325)（另有 [2.0](https://zenodo.org/record/1715175)）、[Weathervane Music「Shaking Through」](https://weathervanemusic.org/shakingthrough/remix)、Cambridge-MT、[MUSDB18-HQ](https://zenodo.org/records/3338373) | 原始多轨（每件乐器、每条人声单独一轨，人声是**原始干声**），以及混音后的分轨；MUSDB18-HQ 只有人声、鼓、贝斯、其他四轨混音分轨 | 最好：录音室原始干声，没有混响。MedleyDB 的元数据标了每首有没有串音（`has_bleed`） | 独立音乐人的歌，不出名。MedleyDB 里女声主唱、无串音、整首的有 14 首（见下） | MedleyDB、MUSDB18-HQ：在 Zenodo 填表申请，只许非商业研究（CC BY-NC-SA 4.0）。Shaking Through：免费会员只能下最新一期，月费会员能下最新 4 期加 4 期存档，年费会员能下全部存档。Cambridge-MT：500 多个项目，教育用途免费下载；网站有 Cloudflare 验证，脚本抓不到，要用浏览器下 | **最适合先拿来试点**：能直接验证干净的输入能不能解决转换发虚、发脏 |
| [Karaoke Version](https://www.karaoke-version.com/custombackingtrack/adele/someone-like-you.html) | 录音室乐手**重新录制**的多轨（不含原版录音的任何部分），分 Lead Vocal、Backing Vocals 和各件乐器，每一轨都能单独导出 | 录音室重录，干净；但主唱是它请的歌手，伴奏也是重录的 | 欧美流行曲库很大。例：Adele「Someone Like You」分 Piano、Backing Vocals、Lead Vocal 三轨 | 每首约 2.99 美元，MP3 320 kbps，买了以后可以无限次导出 | **想翻知名欧美歌时最实际** |
| DJ pool（[DJcity](https://support.djcity.com/hc/en-us/articles/34409884914708-What-type-of-music-does-DJcity-provide)、BPM Supreme 等） | 唱片公司提供给 DJ 的官方 acapella 和 instrumental | 是官方原版。但 acapella 一般是整条人声：主唱加和声，带着混音里的效果，多数是 MP3 | 当下的流行、嘻哈、R&B、舞曲热门 | 按月订阅，授权给 DJ 使用 | 知名歌的官方原版分轨；要订阅，和声和效果还得另外处理 |
| 艺人放出的分轨、remix 比赛 | 官方分轨 | 官方录音室分轨 | 很零散。艺人放出的：Beyoncé「End of Time」、[Grimes「You'll Miss Me When I'm Not Around」](https://www.rollingstone.com/pro/features/pop-grimes-coronavirus-remix-979137/)（2020）、Charli XCX（2020 年做专辑期间）、SoundCloud 和 Fadr 的活动（[Erin LeCount「Godspeed」](https://soundcloud.com/stories/post/erin-lecount-godspeed-remix-campaign)，Fadr 已在 2025-08 停止免费下载）。remix 比赛：[Skio、Beatport 等](https://www.remiexs.com/remixcontest)，多为舞曲，例如 Jessi「Girls Like Me」、Agnis「Baba Jaga」 | 多半已经过期，或者只在比赛期内能下；规约一般只许参赛使用 | 碰上了再用 |

MedleyDB 里女声主唱、无串音、整首的歌。这份名单是从 [GitHub 上的元数据](https://github.com/marl/medleydb/tree/master/medleydb/data/Metadata)筛出来的，排除了片段和来源标为 `Mogg` 的歌（那是 Rock Band 游戏解包的多轨，没有公开音频）：

- Aimee Norwich – Child
- Cassandra Jenkins – Perfect Day
- Cat Martino – I Promise
- Cayetana – Miss Thing
- Clara Berry and Wooldog – Air Traffic、Stella、Waltz For My Victims
- Filthy Bird – I'd Like To Know
- Hop Along – Sister Cities
- Little Tybee – The Alchemist
- Liz Nelson & Jennifer Davies – Coldwar、Rainfall
- Secret Mountains – High Horse
- The Kitchenettes – Alive
- Torres – New Skin

其中来源是 Weathervane 的几首（Cassandra Jenkins、Cat Martino、Cayetana、Filthy Bird、Hop Along、Little Tybee、Secret Mountains、Torres），也能从 Shaking Through 下载。

有了官方分轨，`cover_mix.py` 基本可以照用：原唱的主唱分轨（`--lead`）、干声（`--dry`）、整条人声（`--vocals`）都能直接拿官方的，不用再从混音里分离。

**风险**：几个模型都是用中文、日语歌训练的，唱英语时咬字可能不准。内容编码 ContentVec 本身是在英语语音上训练的，这一步应该问题不大，但效果要实测。

### 歌声合成导唱的做法

- **渲染工具**：
  - [Synthesizer V Studio 2](https://www.pluginboutique.com/products/17506-Synthesizer-V-Studio-2-Pro)：普通话、日语、粤语、英语等；能导入 MIDI；工程文件 `.svp` 是 JSON 格式，脚本能读写。
  - [ACE Studio](https://www.soundonsound.com/reviews/ace-studio)：有 Vocal to MIDI，可以从**自己录的干净清唱**里提取音符和歌词，但识别出来要手修；在云端渲染，要订阅。
  - OpenUtau + DiffSinger 声库：免费开源。
- **MIDI 和歌词从哪来**：
  - 网友分享的工程文件，有 UST、SVP、MIDI 等格式（“UST配布”“工程分享”）。一般附 README，要求署名、不许转载、不许商用。不同格式之间可以用 [UtaFormatix](https://github.com/sdercolin/utaformatix3) 转换。
  - 没有现成的就自动扒：用 [openvpi/SOME](https://github.com/openvpi/SOME)（专门给歌声提 MIDI，能输出带小数的音高）提音符，再用强制对齐工具（SOFA、HubertFA）把官方歌词对到音符上。扒谱的输入可以是原曲减伴奏或分离出来的人声：这里只取音符和时间，不拿去转换，所以脏一点没关系。
- **社区里已经有人这么做**：先用 SynthV 渲染，再用 RVC 换音色（[vi-control 上的讨论](https://vi-control.net/community/threads/synthesizer-v-vocaloid-haters-might-want-to-check-this.115973/page-210)）。不过这次没找到和真人导唱的效果对比。
- **风险**：DDSP-SVC 会照搬导唱的音高曲线和强弱。合成的演唱如果平、缺表情，转出来也平，所以要花时间调。合成歌手本身的音色不要紧，转换时会被换掉；但咬字和节奏的习惯会留下来。

## 怎样确认拿到的是真干声

这次没找到公开、可靠的方法，能把“录音室干声”和“AI 分离出来的人声”区分开（[检索结果](https://arxiv.org/pdf/2509.26580)只讲了分离会有哪些瑕疵）。所以管线里要自己检查，计划写成脚本：

1. **乐句之间的空隙**：真干声的空隙只有话筒和房间的底噪，平稳、宽频、很低。分离出来的人声在空隙里常残留音乐，比如鼓点、和弦，而且和伴奏同步。可以量空隙的电平，以及它和伴奏能量包络的相关性。
2. **整首的渗漏**：看人声里的瞬态和伴奏的鼓点是不是对得上。
3. **混响尾巴**：干声在乐句结束后很快落到底噪。
4. **频宽**：有损编码会在 16 kHz 左右截掉。
5. **简介关键词**：出现 AI、UVR、MSST、Demucs、RoFormer、消音、提取、分离之类的字样，就排除。花丸晴琉第一批翻唱筛选伴奏时，已经按简介排除过注明自制伴奏、AI 消音、MSST 的投稿（见 PROGRESS 里“花丸晴琉第一批”那条）。
6. **版本核对**：如果有原曲，人声加伴奏应当能和原曲大致抵消，可以用 [offvocal.py](offvocal.py) 的对齐和抵消测量。这只能证明两轨出自同一版本，证明不了人声是干净的：原曲减伴奏得到的人声加回伴奏，也一样能抵消。

## 建议的管线（待实现）

1. **选歌**：先查有没有官方分轨（TuneCore Rework with 的列表、remix 比赛页面），有的话下载后跑上面的检查。
2. **没有官方分轨**：准备导唱，二选一：
   - 真人：戴耳机跟着官方伴奏录干声。
   - 歌声合成：拿到或扒出 MIDI，配上官方歌词，渲染成干声。
3. 导唱跑上面的检查，合格后用 DDSP-SVC 转换。
4. 用 `cover_mix.py` 混回官方伴奏。要改的地方：`cover_mix.py` 现在拿原曲分离出来的主唱当参照，用来定人声音量、补混响、做 EQ。换成导唱以后就没有原唱分轨了，人声音量（`--lift`）、混响量、EQ 改为按每首歌试听来定（见 [README](README.md#混音设置因曲而异2026-10-23)）。
5. 每首用的导唱来源、检查结果和混音设置，记进那首歌的目录和 README 里的定稿表。

## 下一步建议

0. **欧美歌先行**（2026-10-23，用户可以接受欧美歌）：
   - 先从多轨库挑一两首女声歌，用原始干声做转换，看干净的输入能不能解决发虚、发脏。MedleyDB 要申请，Shaking Through 和 Cambridge-MT 要注册或用浏览器下。
   - 想翻知名欧美歌时，用 Karaoke Version 的重录多轨。
   - 两条路都要用户先动手：填申请表、注册或者购买。
1. **试点**：挑一首歌，把三种导唱放在一起比：现在的做法（原曲减伴奏再分离，作为基线）、歌声合成导唱、真人导唱。两人份的幸福已经有定稿的混音设置，可以当作这首。真人导唱要看用户能不能录、愿不愿意录。
2. 查 TuneCore「Rework with 可愛くてごめん」和「少女A」的分轨还能不能下、包不包含单独的人声轨。
3. 写检查脚本：空隙底噪、渗漏、混响尾巴、频宽。

## 试点（2026-10-23）：输入干净了，转换是不是就不发虚、不发脏

### 选了哪两首，为什么

- **Rubblebucket「Carousel Ride」**（Cambridge-MT，Telefunken「Live From The Lab」的录音棚现场 session）。
  - 为什么选它：曲库里有名的女声歌，比如 Hurray For The Riff Raff、Amy Helm、Rubblebucket，都来自这种现场 session。乐队同场演奏，人声话筒会串进乐器声。Rubblebucket 的主唱音色高而清，和我们的模型最接近。
  - 主唱轨的串音：乐句之间的空隙比唱的时候低 33 dB，和鼓的相关系数 0.82。空隙中位数 -63 dBFS，低于转换时 -60 dB 的静音门限，所以乐句之间的串音基本被门限挡掉。作为对比，同为 Telefunken 的 Leslie Mendelson「The Hardest Part」是对唱加两把吉他，空隙只低 28 dB，和吉他的相关系数 0.97，没有选。
- **Moni Blue「April Blues」**（Cambridge-MT，录音室逐轨叠录的流行歌，《Sound On Sound》的“Mixing Pop Vocals”一文用过）。主唱轨的空隙是数字静音（-120 dBFS），和各件乐器都不相关，是完全干净的理想输入。

### 做法

- **本机准备**：[cover_scripts/clean_pilot_prep.py](autodl/cover_scripts/clean_pilot_prep.py)。
  - 把多轨对齐到官方混音的时间轴，取出原始主唱轨，存成无损 FLAC。
  - 其他轨的增益按官方混音拟合：在 100 ms × 9 个频带的能量上做最小二乘，每轨不低于中位数增益 10 dB。拟合后混出伴奏。和官方混音的对数能量相关系数：Rubblebucket 0.84，Moni Blue 0.92。
  - 主唱的叠唱轨（Moni Blue 的 DT1、DT2）是原唱的声音，不放进伴奏。
- **AutoDL 上处理**：[cover_scripts/clean_pilot.sh](autodl/cover_scripts/clean_pilot.sh)。
  - 用翻唱流程的三步分离（去伴奏、去和声、去混响），从官方混音里取出干声，代表现在的做法。
  - 原始主唱和这条分离干声，都用花丸晴琉 4 万步、`-k 0` 转换。
  - 两条转换结果用完全相同的处理混到伴奏上（[clean_pilot_mix.py](autodl/cover_scripts/clean_pilot_mix.py)）：响度对齐原始主唱在官方混音里的电平，加同样的人工混响，过 `cover_mix.py` 的限幅器。这样两个混音的差别只在转换后的人声。
- **下载**：Cambridge-MT 的页面和下载链接都有 Cloudflare 验证。用本机的 Edge（开远程调试端口）过一次验证，再拿它的 `cf_clearance` cookie 加同样的 UA 让 curl 下载，能断点续传。
- **上传**：家里到 AutoDL 的上传只有约 50～80 KB/s，所以只传整理好的几条，每首约 30 MB。

### 机器打分

用 [clean_pilot_score.py](autodl/cover_scripts/clean_pilot_score.py) 打分：取原始主唱在唱的 8 秒窗口，四个版本用同一批窗口，取平均。Rubblebucket 31 个窗口，Moni Blue 20 个。“像她”是和花丸晴琉验证句的 WavLM 声纹余弦相似度。

| 歌 | 版本 | SingMOS | aes_pq | aes_ce | DNSMOS SIG | DNSMOS BAK | 像她 |
|---|---|---|---|---|---|---|---|
| Rubblebucket | 原始主唱（干净输入） | 2.71 | 7.86 | 7.23 | 2.16 | 2.18 | 0.752 |
| | 从原曲分离出的干声 | 2.76 | 7.03 | 5.20 | 3.10 | 3.55 | 0.769 |
| | 干净输入 → 转换 | **3.04** | **7.12** | **4.80** | 3.08 | 3.56 | **0.848** |
| | 分离输入 → 转换 | 2.61 | 7.04 | 4.73 | 3.04 | 3.44 | 0.838 |
| Moni Blue | 原始主唱（干净输入） | 4.57 | 7.82 | 6.70 | 3.58 | 4.15 | 0.606 |
| | 从原曲分离出的干声 | 4.07 | 7.32 | 5.96 | 3.49 | 4.06 | 0.628 |
| | 干净输入 → 转换 | **3.55** | **7.64** | **5.92** | 3.29 | 3.70 | 0.891 |
| | 分离输入 → 转换 | 3.38 | 7.55 | 5.82 | **3.37** | **3.89** | **0.901** |

**初步结论**（以用户试听为准）：
- 干净输入的转换在 SingMOS 上比分离输入高：Moni Blue 高 0.17，Rubblebucket 高 0.43。音质分（aes_pq、aes_ce）也略高。
- 但即使输入是完全干净的录音室干声，转换后 SingMOS 也从 4.57 掉到 3.55。所以“发虚”有相当一部分来自转换本身，输入干净只能解决一部分。
- 对 Moni Blue 这种干净的录音室混音，三步分离本身损失不大（SingMOS 4.57 → 4.07）；越密、越湿的混音，分离的损失应该越大。
- Rubblebucket 原始主唱的 DNSMOS BAK 很低（2.18），这是现场串音和房间声；分离反而把它清掉了。

**试听**：试听网页 `hanamaru_hareru` 的「转换结果」里 `clean_pilot/<歌>/`，按 0～6 号顺序听：
- 0：官方混音
- 1：原始主唱
- 2：从原曲分离出的干声
- 3、4：两种输入转换后的干声
- 5、6：两种输入转换后的混音
