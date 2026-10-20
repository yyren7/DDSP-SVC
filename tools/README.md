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

## legacy/

原 6.3 分支上的自用脚本（VAD 切片、验证集调整、局域网传文件、启动训练），原样保留在 `legacy/` 里。
