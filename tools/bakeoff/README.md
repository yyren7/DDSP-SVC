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
| SoulX-Singer-SVC（由 4.2 万小时的 SoulX-Singer 微调） | 2026-03 | 没有训练代码 | 论文附录：和 YingMusic-SVC、Vevo-SVC 接近 | Apache-2.0；只列中、英、粤语 |
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
- **零样本参考音频**：从她训练集里挑最干净的几句拼成约 20 秒，所有零样本模型用同一份。不用验证集里的句子，免得重建时偷看答案。

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
| 环境和权重（`setup.sh`） | 进行中：venv `conda_envs/bk` 已装好，权重在下载 |
| 测试集（`make_set.py`）、转换（`convert.py`）、打分（`score.py`） | 脚本已写好，未运行 |

## 实例上的布局

| 位置 | 内容 |
|---|---|
| `/root/autodl-tmp/bakeoff/repos/` | 候选模型的代码（`seed-vc`、`YingMusic-SVC`、`SoulX-Singer`） |
| `/root/autodl-tmp/bakeoff/set/` | 测试材料和参考音频 |
| `/root/autodl-tmp/bakeoff/out/<系统>/` | 每个系统的输出 |
| `/root/autodl-tmp/conda_envs/bk_<模型>` | 每个模型自己的环境 |

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
