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

## 2026-10-23～24：全转换版 v2，和声在去混响之前转换

去混响模型会把叠录的和声当成混响删掉：暁の車 的副歌被删了 15～24 dB，Tell Your World 中位数 23.5 dB。于是转换后的和声在副歌里没了，而 `cover_mix.py` 按整首响度对齐，又把主歌的和声抬高了约 10 dB。v2 改为转换分离那一步的输出（不去混响），混音时 `--harm-dry` 和 `--harm-wet` 都传这一条，就不会再加人工混响。以后每首歌出两版：保留原唱和声的，和 v2 全转换版。

- `run7.sh`：菲比、旬夏的暁の車、Tell Your World。和声从本地 `covers/_stems/` 传上来，只做转换，混音在本地。
- `run8.sh`：菲比、旬夏的其余 11 首，和声同样从本地传上来。没有和声版伴奏的歌，用的是卡拉 OK 模型分出的原唱和声（vocals − lead）。和声先过一遍分离再转换。
- `run9.sh`：花丸晴琉的我会好好的、爱你、アイドル、两人份的幸福。转换和混音都在实例上，混音照 `remix_eq.sh`，输出到 `infer_out/covers_40000_v2/`。只用 GPU：CPU 被别的任务占满时，一条要转 20 分钟以上。
- `run9_wait.sh`：GPU 和别的任务共用时，等连续两次检查（隔 1 分钟）都有 5G 空闲再跑 run9.sh。失败了就接着等，再试，最多 10 次。PV 的 Blender 也在等显存，它是空出 8G 就开一批，加载完场景才把显存占上去，所以只看一次空闲会跟它撞上。
- `hana_v2_check.py`：她的旧全转换版和 v2 的和声，按每 6 秒一段和原唱和声比响度。
- `run10.sh`：v2 的和声保留立体声（试验，两人份的幸福 +2 dB）。v2 的和声转换后是单声道、放在正中，和主唱挤在一起（原唱和声的左右相关 0.21，v2 是 1.00）。这里把和声的左右声道分开转换，再用 `cover_mix.py --harm-stereo` 放回原位。`gpu_wait.sh`：通用版的 run9_wait.sh，等显存再跑给定的脚本，例如 `MIX=/tmp/cover_mix_stereo.py nohup ./gpu_wait.sh ./run10.sh > run10.log 2>&1 &`。实例上的仓库还没有 `--harm-stereo`，试验时把本地改好的 cover_mix.py 拷到 `/tmp/cover_mix_stereo.py` 用。
- `run11.sh`：run10.sh 的立体声和声里有两处转坏了，用种子 1～4 重转这两处。1:08 是原唱和声换音时转出一道宽频噪声，2:08 是叠唱加气声让音高一跳一跳。重转的部分从原唱和声前后最安静的地方切开，拼进现在这版（20 ms 交叉淡化），按 run10.sh 的设置混音，每处剪 9 秒放到 `covers_40000_v2/<歌名>_换种子/` 给用户挑。种子在调用 main_reflow.py 前用 `torch.manual_seed` 设定，做法同 `diction.py cand`。
- `run13.sh`：旬夏、菲比 13 首的和声都左右声道分开转换（2026-10-25，8 万步，26 条），只转换，混音在本地用 `covers/remix.sh` 做，输出到 `covers/best/`。原唱和声在中间的歌（左右相关 0.7 以上）改用单声道转换放在正中，名单是 remix.sh 里的 `CENTER_BACKING`。
