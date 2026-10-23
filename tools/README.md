# 训练语料一键预处理（UVR5）

`prepare_dataset.py` 把原始歌曲处理成 DDSP-SVC 可以直接训练的干声切片。它用 [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) 在命令行下运行 UVR5 的全部模型（含最新的 Roformer 社区模型），不需要 UVR5 图形界面。

| 步骤 | 作用 | 默认模型 |
|---|---|---|
| `vocals` | 分离人声和伴奏 | `bs_leap_xe_voc.ckpt`（BS-Roformer Leap Xe，unwa） |
| `dereverb` | 去混响、去回声 | `dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt` |
| `karaoke` | 去和声，只留主唱 | `karaoke_bs_roformer_anvuew.ckpt` |
| `slice` | 按静音切片，转 44.1kHz 单声道，丢弃过短片段 | - |
| `split` | 输出到 `data/train/audio`，随机抽 10 段到 `data/val/audio` | - |

模型的选择依据见 [autodl/PROGRESS.md](autodl/PROGRESS.md#去伴奏模型2026-10-19-选定)。三个模型都不在 audio-separator 的列表里，用 `tools/autodl/fetch_uvr_models.py` 从 Hugging Face 下载到 `pretrain/uvr/`。

2026-10-20 起不再去噪：前三步做完后，去噪模型（aufr33 aggressive）对结果的改动只有 -47～-52 dB。

## 安装

建议单独建一个环境，避免 audio-separator 自带的 torch 版本影响训练环境：

```bash
python -m venv .venv-uvr && source .venv-uvr/bin/activate
pip install "audio-separator[gpu]"   # 没有显卡用 "audio-separator[cpu]"
```

## 使用

```bash
# 完整流程：原始歌曲 -> data/train/audio、data/val/audio
python tools/prepare_dataset.py -i raw_songs -o data

# 素材本来就是干声，只做去混响和切片
python tools/prepare_dataset.py -i dry_vocals -o data --steps dereverb,slice,split

# 多说话人：每个说话人跑一次，用 --spk 指定编号
python tools/prepare_dataset.py -i singer_a -o data --spk 1 -w work_a
python tools/prepare_dataset.py -i singer_b -o data --spk 2 -w work_b
```

- 每一步的结果保存在 `preprocess_work/` 的单独文件夹里。中断后用同一条命令重跑，已经处理过的文件会自动跳过。
- 想换模型用 `--vocals-model`、`--dereverb-model`、`--karaoke-model`。可选模型用 `audio-separator --list_models` 查看。
- 切片长度默认 3–15 秒（`--min-len`、`--max-len`）。`--min-len` 必须大于 `configs/reflow.yaml` 里的 `duration`（默认 2 秒）。
- 处理完建议抽听几段 `preprocess_work/3_karaoke/` 和最终切片，再开始训练。

## 速度参考

在 4 核 CPU 上，30 秒音频四个 UVR 步骤（当时还有去噪）合计约 10 分钟，大约是实时速度的 20 倍慢，只适合试跑少量文件。CPU 上可以加 `--overlap 2` 提速，音质会略有损失。大批量数据请在 GPU 机器（如 AutoDL）上运行。

## 翻唱：原曲 + 官方 off vocal

> 2026-10-23 起，原曲减伴奏（再分离）得到的人声不再作为转换的输入：用户试听后认为效果很差。干净导唱的来源调研和新管线见 [clean_stems.md](clean_stems.md)。下面的流程留作记录；其中 `offvocal.py` 的对齐和抵消测量、`cover_mix.py` 的混音，新管线还会用到。

选有官方 off vocal（伴奏）的歌，原唱用相减得到，比分离模型干净，伴奏直接用来混音。

```bash
# 对齐（跟随时间漂移）、相减；输出 vocal.wav、inst.wav 和抵消深度，判断两条是不是同一母带
python tools/offvocal.py 原曲.m4a off_vocal.m4a -o covers/歌名/phase

# vocal.wav 走 prepare_dataset.py 的 vocals,karaoke,dereverb 三步，干的主唱用 main_reflow.py 转换，再混音
python tools/cover_mix.py --inst covers/歌名/phase/inst.wav --source covers/歌名/phase/vocal.wav \
    --vocals work/1_vocals/歌名.wav --lead work/2_karaoke/歌名.wav --dry work/3_dereverb/歌名.wav \
    --conv 转换结果.wav -o 混音.wav
```

- 抵消深度看最安静的 3 秒：无损的同一母带能到 -50 dB 以下，B 站、YouTube 的有损音源约 -20～-40 dB，高于 -15 dB 说明不是同一个混音或母带。
- 两条音轨最好出自同一张碟、同一个人的上传（B 站卡拉 OK 投稿常把 On Vocal 和 Off Vocal 放在 P1、P2）。
- 混音时，转换后的主唱加上人工混响，合起来按 BS.1770 响度对齐去混响前的原主唱。人工混响按原曲去混响前后每个八度的比例来补，每个频段不超过人声本身，所以低频切得和原曲一样，高频也一样亮。原唱的和声（vocals − lead）保留，`--no-backing` 可以去掉。
- `--source` 不能省：分离工具（audio-separator）会把峰值超过 0.9 的输入整条压到 0.9，而原曲减伴奏常常超过 1，分出来的分轨会整体轻 1～5 dB。cover_mix.py 按 vocal.wav 把它们放大回原来的音量。vocal.wav 是浮点 WAV，不要转成 FLAC，转了会削波。
- EQ（2026-10-22 起）：转换后的声音比它替代的原唱暗，2～4 kHz 少 2～5 dB，响度相同也会被伴奏盖住。所以先按八度 EQ 到原唱干声（`--dry`）的频谱，每个八度最多动 `--eq-max` dB（默认 6，设 0 就不做 EQ），最低和最高的八度只减不加。日志里的 `EQ +0/-1/...` 是各八度的增益。
- 人声音量：转换的部分（主唱和混响，全转换时还有和声）再乘一个共同的增益，让混音里的人声和原曲人声一样响（BS.1770）。原因是叠在主唱上的和声，和原主唱叠起来比和转换后的主唱叠起来更响。`--lift N` 让人声比原曲再响 N dB。
- 限幅：整首先降一个固定增益，降到只有 1% 的 20 ms 帧还需要限幅器再压 1 dB 以上，然后才过 -1 dBFS 的限幅器。只用限幅器的话，密集段落里人声每一拍都会顶出伴奏的满幅，整首跟着一下下被压，听起来像在抽动。

### 混音设置因曲而异（2026-10-23）

没有一套设置对所有歌都最好，每首歌要单独试听、单独定。可调的有三项：

| 设置 | 选项 | 什么时候用 |
|---|---|---|
| EQ | `--eq-max`，默认 6 dB；0 是不做 EQ；也可以取 3 这样的中间值 | 转换后的声音发闷、被伴奏盖住时用默认值。如果 EQ 后变得刺耳、齿音重，或者原唱干声本身频谱偏（低频轰、高频被有损音源切掉），就调小或关掉 |
| 和声 | 保留原唱（默认）；全转换（`--harm-conv` 等，见 `autodl/cover_scripts/run6.sh`）；不要和声（`--no-backing`） | 原唱和声轻、和主唱分得开时，保留原唱最自然；和声很响或和主唱叠得紧时，原唱音色露出来，就用全转换；伴奏本身带和声时，原曲减伴奏只剩主唱，没有可保留的原唱和声 |
| 人声音量 | `--lift`，单位 dB，0 是和原曲一样响 | 转换后的声音没有原唱穿透，同样响也显得靠后，一般要加一点。目前试过 +0、+2、+4 |

做法：同一首先出几个版本放进试听网页的「转换结果」，听完挑一个，把定下的设置记进下表。以后换模型或重做时，照表重混。

| 歌 | 说话人 / 模型 | EQ | 和声 | 人声音量 | 定稿文件 |
|---|---|---|---|---|---|
| 两人份的幸福（王心凌） | 花丸晴琉 4 万步 | 默认（6） | 保留原唱 | +2 dB | `infer_out/covers_final/两人份的幸福（王心凌）.flac` |

- 两人份的幸福（2026-10-23，花丸晴琉）：比较过旧混音、EQ、全转换 +0/+2/+4 dB、保留原唱 +2 dB，用户选了 EQ 加保留原唱加 +2 dB。原唱和声比主唱低约 9 dB。命令同 `autodl/cover_scripts/remix_eq.sh` 里的普通版，另加 `--lift 2`。

### 咬字检查和修补（`diction.py`，还没在歌上用过）

转换后有的字会唱错。`diction.py` 按换气把干声切成乐句，用 Qwen3-ASR 识别原唱和几个候选转换（同一模型的其他随机种子、其他步数），按歌词逐个单位比较：中文是不带声调的拼音音节，日语是假名的拍，英语是单词。转换比原唱错得多的句子，换成候选里错得最少的那一版，在前后换气的中点拼接，交叉淡化 20 ms。歌词不会喂给识别器，否则它会把唱错的听成对的。

```bash
# asr 环境：ddsp 环境加上 qwen-asr、pypinyin、pykakasi（tools/autodl/setup_asr.sh）
python tools/diction.py --dry 3_dereverb/歌名.wav --lyrics 歌名.lrc --lang Chinese \
    --conv 40k.wav 40k_种子1.wav 50k.wav ... -o 修补后.wav --report 修补后.json
```

- 识别器靠不靠得住要先看它听原唱本人的错误率（2026-10-22，Qwen3-ASR-1.7B，`autodl/cover_scripts/asr_bench.py`）。中文：两人份的幸福 1.2%、我会好好的 2.1%、爱你 8.9%（另有 96 个音节没识别出来）。日语：アイドル 6.6%、勇者 14.3%、晴る 22.6%。中文基本可用，日语不可靠。VocalParse 加载时词表大小对不上（152101 对 151936），没测成。
- 另一种做法（之后再试）：人耳听出唱错的地方，报大概的秒数和字。按秒数找到那一句，把各候选的这一句切出来比较，挑一个拼进去。拼接用 `diction.py` 里的 `phrases`、`splice`。
- 2026-10-22 实际跑过的翻唱脚本在 [autodl/cover_scripts/](autodl/cover_scripts/)，说明见那里的 README。

## legacy/

原 6.3 分支上的自用脚本（VAD 切片、验证集调整、局域网传文件、启动训练），原样保留在 `legacy/` 里。
