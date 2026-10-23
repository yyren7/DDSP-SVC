# 翻唱脚本（AutoDL 上的 `/root/autodl-tmp/covers/`）

这些是 2026-10-21～22 在实例上手动跑过的翻唱脚本，2026-10-23 收进仓库存档。路径都写死在实例上：工作目录是 `/root/autodl-tmp/covers/`，每首歌一个子目录，conda 环境在 `/root/autodl-tmp/conda_envs/`。要跑的话，先拷到 `covers/` 下。用到的通用工具在 `tools/` 下：`offvocal.py`、`prepare_dataset.py`、`cover_mix.py`、`diction.py`，用法见 [tools/README.md](../../README.md#翻唱原曲--官方-off-vocal)。结果和决定记在 [PROGRESS.md](../PROGRESS.md)。

## 流程

1. **找音源**：`bsearch.py` 用实例上的 B 站登录 cookies 搜索，`bscan.py` 从搜索结果里挑出分 P 或标了 On/Off Vocal 的卡拉 OK 投稿。
2. **测试候选对**：`pairs.sh` 读 `pairs.txt` / `pairs2.txt`，每行是“歌 BV号 原曲P 伴奏P [第二个伴奏P]”。它下载原曲和伴奏，用 `offvocal.py` 测两条能抵消多深，判断是不是同一母带。
3. **分离、转换、混音**：每一轮是一个脚本。
   - `run.sh`：第一版。原曲减伴奏 → 去伴奏、去和声、去混响三步 → 用 8 万步模型转换 → `cover_mix.py` 混音。
   - `run2.sh`：伴奏本身带和声时，原曲减伴奏就只剩主唱，跳过去和声。
   - `run3.sh`：同时有带和声和不带和声的伴奏时，两者相减就是单独的和声，和声也转换。
   - `run4.sh`：重做 Tell Your World，它的“和声版”伴奏里混着一份原唱主唱。
   - `run5.sh`、`run6.sh`：花丸晴琉这一轮。`run6.sh` 做全转换版：由去和声模型分出的和声也转换。用哪个步数由 `STEP` 指定，默认 40000。
   - `resume.sh`、`resume2.sh`：和 ComfyUI 共用 GPU 时，等显存空出来再接着跑。
4. **换步数重做**：`redo40k.sh` 把 run5/6 改成支持 `STEP`，并把旧的输出改名为 `_80000`。
5. **打包试听**：`infer_pack.sh [STEP]` 把混音转成 FLAC，放到 `speakers/hanamaru_hareru/infer_out/covers_<STEP>/`，试听网页「转换结果」里能听到。`pack.sh` 打包混音和重混要用的分轨，拿到别处听或重混。

## 2026-10-22 晚上：EQ、人声音量、咬字

用的都是花丸晴琉的 4 万步模型，6 首歌：晴る、勇者、我会好好的、爱你、アイドル、两人份的幸福。

- `remix_eq.sh`：用新版 `cover_mix.py`（EQ、整体音量对齐原曲、先降固定增益再限幅）重混全部 9 个混音，输出到 `infer_out/covers_40000_eq/`。
- `remix_lift.sh`：4 首全转换版，人声比原曲 +0、+2、+4 dB 各一版（`--lift`），输出到 `infer_out/covers_40000_lift/`。
- 咬字：
  - `cand.sh` 给每首做候选转换，输出到 `covers/cand/<歌>/`：4 万步的种子 1、种子 2，和 3 万、5 万、6 万步；另外链接已有的 4 万步默认版、8 万步版和干声。
  - `asr_bench.py` 测识别器听原唱的错误率，`ja_err.py` 逐句列出日语歌里歌词和识别结果不一样的地方。
  - `diction.py` 还没在这几首歌上真正跑过。
- 分析脚本，查问题时用的：
  - `vocal_balance.py`、`window_balance.py`：人声和伴奏的响度比，翻唱和原曲对比，看人声有没有被盖住。
  - `octave_diff.py`：原唱干声和转换结果各八度的差，EQ 的依据。
  - `allconv_check.py`：全转换版里，`cover_mix.py` 拿来对齐响度的原曲人声有多响。
  - `aini_gaps.py`：爱你的人声在哪里丢了。
  - `spec60.py`、`thump60.py`：两人份的幸福 54～66 秒的抽动声，查它是限幅器在压伴奏，还是转换后的人声低频有冲击。之后限幅改成了先降固定增益。
