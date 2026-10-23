# 转换模型对比（2026-10-23 起）

现在的转换模型是 DDSP-SVC 6.3（rectified flow），从这里开始换成当前最好的模型。这一块单独记在本文，脚本都放在本文件夹（`tools/bakeoff/`），实例上的工作目录是 `/root/autodl-tmp/bakeoff/`。训练数据、翻唱流程的进展仍记在 [PROGRESS.md](../autodl/PROGRESS.md)。

**测试对象只用花丸晴琉**（用户定）：所有候选都转成她的声音，和她的 DDSP-SVC 4 万步定版模型比。

## 为什么要换

干净输入试点（[clean_stems.md](../clean_stems.md)「试点」，2026-10-23）：Moni Blue 的录音室原始主唱，转换前 SingMOS 4.57，转换后 3.55；从原曲分离出的干声转换后 3.38。用户听下来 3 号（干净输入转换）和 4 号（分离输入转换）差别不大，3 号也发虚。所以输入干净只能解决一小部分，发虚主要来自转换本身。

试听时 3 号显得特别轻，原因是 DDSP-SVC 保留输入的音量：多轨里的原始主唱录得很轻（-25.6、-28.7 LUFS），分离出的干声是母带后的电平（-15.2、-13.8 LUFS），所以 3 号比 4 号轻 7～10 LU。5、6 号混音前对齐过响度（差 0.5 LU 以内）。本对比里所有输出都对齐响度后再听。

## 候选（2026-10-23 查的现状）

范围按用户要求不限于 SVC：凡是能用她的样本微调、或者拿她的声音做参考的歌声模型都算。

### SVC（歌声转歌声，可以直接换进现在的流程）

| 模型 | 发布 | 能用她的数据微调 | 公开证据 | 许可 |
|---|---|---|---|---|
| DDSP-SVC 6.3（现用，基线） | master 最后提交 2025-01 | 能（现在就是） | Poly-SVC 论文（2026-05）主观测试：单旋律自然度 3.83，相似度 3.33 | MIT |
| Seed-VC 唱歌版（44 kHz，Whisper-small，200M） | 2024-10；仓库 2025-11 归档 | 能，官方 `train.py` | 同一张表：自然度 3.85，相似度 3.74。SVCC 2025 里基于它的系统 S5，歌手相似度和真人没有显著差别 | GPL-3.0 |
| YingMusic-SVC（Seed-VC 改进 + Flow-GRPO） | 2025-11 | 官方没放训练代码，架构是 Seed-VC | 自报（主唱干净的设置）：CMOS 4.26 对 Seed-VC 3.98；混着伴奏、和声时优势更大 | 代码 MIT |
| SoulX-Singer-SVC（由 4.2 万小时的 SoulX-Singer 微调） | 2026-03 | 没有训练代码 | 论文附录：和 YingMusic-SVC、Vevo-SVC 接近 | Apache-2.0；只列中、英、粤语；**输出 24 kHz**（12 kHz 以上没有） |
| Vevo2（Amphion） | 2026-03 | 没有 | 零样本 SVC 和 Seed-VC 接近；输出 24 kHz | 权重 CC BY-NC-ND |
| RIFT-SVC v3（rectified flow transformer） | 2025-03，最后提交 2025-11 | 能，按人微调 | 没有公开评测 | CC BY-NC-SA |
| HQ-SVC（AAAI 2026） | 2025-12 | 没有 | 只和 SaMoye-SVC 比过 | Apache-2.0 |

SVCC 2025（[分析论文](https://arxiv.org/html/2509.15629)）：最好的系统是在 Vevo1.5 上做 LoRA/DPO 微调的（自回归 + 扩散），纯扩散的 Seed-VC、Serenade 系在它后面；最好的系统自然度约 3.7，真人约 3.9。

### 歌声合成（按歌词和旋律让她重唱，原唱的音色和残留都进不来）

- SoulX-Singer（2026-02，Apache-2.0）：零样本，跟原唱的音高曲线（或 MIDI）和歌词唱。SoulX-Singer-Eval 上中文 SingMOS 4.39（真人 4.45）。不支持日语。
- VocalRender（2026-07）：主观上胜过 SoulX-Singer（N-CMOS 高 0.42），但要输入完整乐谱，权重是否公开未确认。
- YingMusic-Singer（2026-03 第二版）：旋律取自音频，加歌词。

### 不做的

- 商用克隆（ACE Studio、Kits.ai、Synthesizer V）：服务条款要求对声音有权利，不能上传真人主播的声音；网上的比较多是推广文。
- Vevo2：24 kHz 输出，许可最严。HQ-SVC：证据太弱。RIFT-SVC：先不做，Seed-VC 微调赢不了再考虑。

## 做法

### 测试材料（实例 `bakeoff/set/`）

- **句子**：花丸晴琉 4 万对 8 万盲听用的 36 句（`speakers/hanamaru_hareru/abtest_steps80/_source/`）。她自己的 12 句来自留出的 4 首歌，测重建；菲比、旬夏各 12 句，测转换。DDSP-SVC 4 万步的结果就是那次的 `all@40000/`。
- **整首**：
  - Moni Blue「April Blues」、Rubblebucket「Carousel Ride」的多轨原始主唱（英语，干净输入），基线是 `clean_pilot/<歌>/conv_clean_hanamaru_hareru_40000.wav`。
  - 晴る（日语）、两人份的幸福（中文）的翻唱干声 `covers/cand/<歌>/dry.wav`，基线是同目录的 `0_40k.wav`。
- **零样本参考音频**：`set/ref/ref.wav`，所有零样本模型用同一份。从她训练用的歌里挑（不含留出的 4 首，免得重建时偷看答案）：每首取 `eval_lines.py` 信号分最高、4～10 秒、有声比例 85% 以上的一句，按分数取到 15 秒以上。结果是 1027_アナタノオト、0207_This_is_運命、0126_鳴呼、素晴らしきニャン生 各一句，都是满分，共 16.6 秒（`ref.json`）。参考不超过 15～20 秒，是因为 Seed-VC 一次只看 30 秒，参考占得越多，每段源音频越短。
- **调用设置**：都不移调。YingMusic 默认会自动移调，还额外加 3.5 个半音，这里关掉。扩散步数和引导系数用各项目给唱歌推荐的值：Seed-VC 50 步、0.7，YingMusic 100 步、0.7，SoulX 32 步、3.0（`convert.py` 的 `DEFAULTS`）。
- **兼容处理**：候选都用 torchaudio 读写音频，而 torchaudio 2.9 要 TorchCodec 和 FFmpeg 的库，`convert.py` 改用 soundfile 读写。YingMusic 导入的混伴奏模块要用 2.9 里已删掉的 `sox_effects`，我们不混伴奏，所以给它一个空模块。

### 评分

- 机器分：沿用 `abtest.py score`（SingMOS-Pro、Audiobox Aesthetics、DNSMOS、和她验证句的 WavLM 声纹相似度、对输入的音高误差），整首按 `clean_pilot_score.py` 的 8 秒窗口算。
- 输出一律按输入的有声段响度对齐（`abtest.py` 的做法），再进盲听。
- 盲听：只听机器分排前一两名的，和 DDSP-SVC 4 万步配对，用试听网页的「A/B 盲听」。

### 顺序和预计时间

1. 第一轮，零样本：YingMusic-SVC、SoulX-Singer-SVC、Seed-VC。装环境 3～5 小时，转换和打分每个模型 10～20 分钟。
2. 第二轮，微调：用她的 7.15 小时训练集微调 Seed-VC（第一轮里 YingMusic 明显更好的话，试着用同一套训练代码微调它）。预计 4～8 小时，跑几百步后按实测速度重估。
3. 另做：SoulX-Singer 按歌词和旋律重唱两首中文歌。2～3 小时。

## 进度

| 环节 | 状态 |
|---|---|
| 现状调研 | 完成（2026-10-23），见上面「候选」 |
| 实例上克隆三个候选仓库 | 完成（21:50） |
| 环境和权重（`setup.sh`） | 完成（22:50 前后）：venv `conda_envs/bk` 建在 ddsp 环境上（torch 2.9.1，transformers 4.46.3），权重共约 6 GB。实例上 git clone GitHub 时断时续，重试后才成功；hf-mirror 偶尔超时，会自动重试 |
| 测试集（`make_set.py`） | 完成：40 项（36 句 + 4 首），基线放在 `out/ddsp40k/`。10-24 加了第 5 首「爱你」（中文，重唱测试的第二首），共 41 项 |
| 她的训练片段（第二轮用） | 重建完成：清理时删掉的 `data_all/train/audio` 用 `build_clips.py all` 重做，2593 段、7.15 小时，和当初一样；12 句验证句逐字节相同 |
| 第一轮转换和打分（`round1.sh`） | 完成（23:00～23:45），结果见下面「第一轮结果」。SoulX 第一次失败：DDSP-SVC 根目录的 `preprocess.py` 挡住了 SoulX 没有 `__init__.py` 的 `preprocess/`，`convert.py` 进入候选目录时把 DDSP-SVC 根目录移出 `sys.path` 后重跑 |
| 盲听材料 | 做好（10-24 00:10），等用户听，见下面「试听」 |
| 第二轮：微调 Seed-VC（`finetune_seedvc.sh`） | 进行中（10-23 23:53 起）。batch 4，学习率 1e-5（train.py 固定），每 2500 步存档。占显存 16 GB；GPU 利用率只有 20～35%，瓶颈在数据加载和每步的 OpenVoice 音色扰动；另一个会话的 Blender 渲染同时在用 GPU 时约 2 秒一步，单独跑约 1.1 秒一步。训到 1 万步（约 15 个 epoch）后由 `round2.sh` 停下，四个存档各转一遍再打分。第一次启动缺 `se_db.pt`（OpenVoice 扰动的目标音色库），已补进 `setup.sh` |
| 重唱（`svs.py`） | 准备中：`setup_svs.sh` 在装依赖、下载 SVS 模型和中文预处理模型。要用 GPU 的步骤排在第二轮停下训练之后 |

## 第一轮结果（零样本，2026-10-23）

### 36 句（`lines_ab/scores.jsonl`）

“别人的”是菲比、旬夏的 24 句转成她的声音，也就是实际用法；“她自己的”是留出的 4 首里的 12 句，测重建。像她：和她验证句的 WavLM 声纹余弦。音高误差：转换结果对输入的 RMVPE 音高，单位音分。

| 系统 | SingMOS（别人的 / 她自己的） | 制作质量 PQ | 好听程度 CE | 像她 | 音高误差 |
|---|---|---|---|---|---|
| 输入原声 | 4.14 / 3.88 | 7.71 / 7.64 | 5.86 / 5.35 | 0.877 / 0.946 | |
| DDSP-SVC 4 万步 | 3.71 / 3.69 | **7.69** / **7.80** | 5.66 / 5.62 | 0.887 / **0.940** | **29 / 26** |
| Seed-VC | 3.90 / 3.90 | 7.46 / 7.61 | 5.63 / 5.90 | 0.911 / 0.923 | 50 / 52 |
| YingMusic-SVC | 3.87 / 3.91 | 7.54 / 7.65 | **5.81** / **5.92** | **0.912** / 0.933 | 49 / 48 |
| SoulX-Singer-SVC | **4.24** / **4.30** | 7.12 / 7.26 | 5.44 / 5.86 | 0.899 / 0.910 | 44 / 40 |

### 4 首整歌（`scores_songs.jsonl`，8 秒窗口）

| 系统 | SingMOS | 制作质量 PQ | 好听程度 CE | 像她 | 音高误差（不含 Rubblebucket） |
|---|---|---|---|---|---|
| 输入原声 | 3.67 | 7.55 | 6.29 | 0.788 | |
| DDSP-SVC 4 万步 | 3.32 | **7.52** | 5.51 | 0.890 | **25** |
| Seed-VC | 3.64 | 7.25 | 5.52 | **0.902** | 42 |
| YingMusic-SVC | 3.62 | 7.40 | **5.88** | 0.896 | 35 |
| SoulX-Singer-SVC | **3.94** | 6.74 | 5.33 | 0.882 | 34 |

Rubblebucket 的原始主唱轨有鼓的串音，所有系统在这首上的音高误差都在 120 音分以上（输入的音高本身就提错了），所以音高误差的平均不算这首。

### 看法（以盲听为准）

- 三个零样本模型的自然度（SingMOS）和像她，都比 DDSP-SVC 4 万步高，SoulX 的自然度甚至高过输入原声。
- 但它们的音高误差都比 DDSP-SVC 大一截（重建她自己的句子时 40～52 音分，DDSP 26 音分），是不是听得出“跑调”要靠耳朵。
- SoulX 的制作质量分最低，应该是 24 kHz 输出没有 12 kHz 以上的缘故。
- 速度（4090D，22 分钟音频）：Seed-VC RTF 0.18，SoulX 0.23，YingMusic 0.30（100 步）。

## 试听

试听网页 `spk=hanamaru_hareru`：

- 「A/B 盲听」里的 `bk_soulx`、`bk_yingmusic`：DDSP-SVC 4 万步对 SoulX、对 YingMusic，各 36 句，听法同以前的 steps80。按机器分选了自然度最高的 SoulX 和各项最均衡的 YingMusic；Seed-VC 等第二轮微调完再和微调版一起听。
- 「转换结果」里的 `bakeoff_r1/<歌>/`：4 首整歌的干声，`0_输入` 之后是 甲～丁 四个系统，顺序每首随机，对照表在实例的 `bakeoff/bakeoff_r1.json`（网页读不到），听完告诉 Claude 每首哪个最好、哪个最差。

## 实例上的布局

| 位置 | 内容 |
|---|---|
| `/root/autodl-tmp/bakeoff/repos/` | 候选模型的代码（`seed-vc`、`YingMusic-SVC`、`SoulX-Singer`）和权重（各自的 `checkpoints/`、`pretrained_models/`；YingMusic 的 `checkpoints/` 链接到 Seed-VC 的） |
| `/root/autodl-tmp/bakeoff/set/` | 测试材料和参考音频 |
| `/root/autodl-tmp/bakeoff/out/<系统>/` | 每个系统的输出，`info.json` 记设置和耗时 |
| `/root/autodl-tmp/bakeoff/lines_ab/` | 36 句的机器打分（`abtest.py` 的格式，`scores.jsonl`） |
| `/root/autodl-tmp/bakeoff/scores_songs.jsonl` | 整首的 8 秒窗口打分 |
| `/root/autodl-tmp/bakeoff/ft/seedvc/` | 第二轮 Seed-VC 微调的各步存档 |
| `speakers/hanamaru_hareru/abtest_bk_<系统>/` | 给试听网页的一对一盲听（`score.py ab <系统>`） |
| `/root/autodl-tmp/conda_envs/bk` | 三个候选共用的环境 |

## 来源

- Poly-SVC：https://arxiv.org/html/2605.12310v1
- SVCC 2025 分析：https://arxiv.org/html/2509.15629
- Seed-VC：https://github.com/Plachtaa/seed-vc
- YingMusic-SVC：https://arxiv.org/html/2512.04793v1 ，https://github.com/GiantAILab/YingMusic-SVC
- SoulX-Singer：https://arxiv.org/html/2602.07803v1 ，https://github.com/Soul-AILab/SoulX-Singer
- Vevo2：https://arxiv.org/abs/2508.16332 ，https://github.com/open-mmlab/Amphion
- RIFT-SVC：https://github.com/Pur1zumu/RIFT-SVC
- HQ-SVC：https://arxiv.org/abs/2511.08496
- VocalRender：https://arxiv.org/html/2607.27768
- YingMusic-Singer：https://arxiv.org/html/2603.24589
- DDSP-SVC：https://github.com/yxlllc/DDSP-SVC
