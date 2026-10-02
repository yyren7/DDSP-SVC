# 训练语料一键预处理（UVR5）

`prepare_dataset.py` 把原始歌曲处理成 DDSP-SVC 可以直接训练的干声切片。它用 [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) 在命令行下运行 UVR5 的全部模型（含最新的 Roformer 社区模型），不需要 UVR5 图形界面。

| 步骤 | 作用 | 默认模型 |
|---|---|---|
| `vocals` | 分离人声和伴奏 | `mel_band_roformer_vocals_fv4_gabox.ckpt` |
| `karaoke` | 去和声，只留主唱 | `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` |
| `dereverb` | 去混响、去回声 | `UVR-DeEcho-DeReverb.pth` |
| `denoise` | 去噪 | `denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt` |
| `slice` | 按静音切片，转 44.1kHz 单声道，丢弃过短片段 | - |
| `split` | 输出到 `data/train/audio`，随机抽 10 段到 `data/val/audio` | - |

默认模型按 Applio 文档推荐的 UVR 流程选取，第一次运行时自动下载到 `pretrain/uvr/`（约 3 GB）。

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

# 素材本来就是干声，只做去混响、去噪和切片
python tools/prepare_dataset.py -i dry_vocals -o data --steps dereverb,denoise,slice,split

# 多说话人：每个说话人跑一次，用 --spk 指定编号
python tools/prepare_dataset.py -i singer_a -o data --spk 1 -w work_a
python tools/prepare_dataset.py -i singer_b -o data --spk 2 -w work_b
```

- 每一步的结果保存在 `preprocess_work/` 的单独文件夹里。中断后用同一条命令重跑，已经处理过的文件会自动跳过。
- 想换模型用 `--vocals-model`、`--karaoke-model`、`--dereverb-model`、`--denoise-model`。可选模型用 `audio-separator --list_models` 查看。
- 切片长度默认 3–15 秒（`--min-len`、`--max-len`）。`--min-len` 必须大于 `configs/reflow.yaml` 里的 `duration`（默认 2 秒）。
- 处理完建议抽听几段 `preprocess_work/4_denoise/` 和最终切片，再开始训练。

## 速度参考

在 4 核 CPU 上，30 秒音频四个 UVR 步骤合计约 10 分钟，大约是实时速度的 20 倍慢，只适合试跑少量文件。CPU 上可以加 `--overlap 2` 提速，音质会略有损失。大批量数据请在 GPU 机器（如 AutoDL）上运行。

## legacy/

原 6.3 分支上的自用脚本（VAD 切片、验证集调整、局域网传文件、启动训练），原样保留在 `legacy/` 里。
