# AutoDL 边跑边修

当前进展见 [PROGRESS.md](PROGRESS.md)。

AutoDL 上常驻一个 runner 脚本，通过 GitHub 和 Claude 交换代码与日志：

- **runner**：每分钟拉一次代码，按 `tools/autodl/plan.txt` 启动或重启任务，并把状态、日志和你的试听反馈推到 `autodl-logs` 分支。
- **Claude**：读 `autodl-logs` 分支上的日志，修好代码后推到 `master` 分支，runner 会自动拉取。
- **试听网页**：runner 同时在 6008 端口开一个网页。你可以在浏览器里在线听各阶段的音频（边下边播，不占本地硬盘），并直接写反馈。

## 第一次使用（只做一次）

### 1. 准备 GitHub token

GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token：

- Repository access：**Only select repositories** → `yyren7/DDSP-SVC`
- Permissions → Repository permissions → **Contents: Read and write**

生成后先复制保存好。token 只保存在 AutoDL 的 `.autodl/token` 里，不会提交到仓库。

### 2. 租 AutoDL 实例

镜像选带 Miniconda 的基础镜像（例如 PyTorch 或 Miniconda）。实例开机后，打开 JupyterLab 的终端。

### 3. 克隆仓库并启动 runner

```bash
source /etc/network_turbo            # 开启 AutoDL 学术加速，访问 GitHub、HuggingFace
cd /root/autodl-tmp                  # 数据盘，空间大
git clone -b master https://github.com/yyren7/DDSP-SVC.git
cd DDSP-SVC
tmux new -s runner                   # 用 tmux 运行，关掉网页终端也不会中断
GITHUB_TOKEN=粘贴你的token bash tools/autodl/runner.sh
```

- runner 启动时会打印**试听密钥**，记下来。
- 按 `Ctrl+B` 再按 `D` 可以离开 tmux，runner 继续在后台运行。
- 实例关机重开后，进入仓库目录执行 `tmux new -s runner` 和 `bash tools/autodl/runner.sh` 即可，第二次起不用再给 token。

### 4. 上传音频

用 JupyterLab 左侧的上传按钮，或 AutoDL 网盘，放进当前说话人的目录（见下面的「多个说话人」）：

- 训练用的歌曲放进 `/root/autodl-tmp/speakers/<说话人>/raw_songs/`
- 想用来试转换效果的歌曲放进 `/root/autodl-tmp/speakers/<说话人>/test_songs/`

### 5. 打开试听网页

AutoDL 控制台 → 实例的「自定义服务」→ 打开 6008 端口对应的链接，然后在网址末尾加上 `?key=试听密钥`。之后浏览器会记住密钥。

网页里可以：
- 在顶部切换说话人，默认打开 `plan.txt` 里的 `SPEAKER`
- 按歌曲对比原曲、分离人声、去混响、去和声的效果
- 在「模型对比」里听同一段歌用不同模型和步骤处理的结果
- 按阶段浏览切片、训练集、转换结果
- 按场次试听 `songsplit` 切好的歌回歌曲，每首标出它在原录像里的位置
- 在每段音频下面或页面顶部写反馈

## 多个说话人

每个人的数据、模型和转换结果都放在数据盘上自己的目录里，一人一个模型，互不影响：

```
/root/autodl-tmp/speakers/<说话人>/
├── downloads/    download 下载的原始录像、视频（冷存储）
├── songs/        songsplit 切好的歌，每首一个文件
├── raw_songs/    挑出来做训练集的歌
├── work/         uvr 各阶段的中间结果（1_vocals … 4_slices）
├── data/         训练集 train/audio、验证集 val/audio，以及 features 的特征
├── exp/          训练出的模型和训练日志
├── reflow.yaml   这个人的训练配置（每次 features/train/infer 时自动生成，不要手改）
├── test_songs/   想试转换效果的歌
├── work_test/    测试歌曲的干声
└── infer_out/    转换结果
```

- `plan.txt` 里的 `SPEAKER` 决定任务处理谁，只能用字母、数字、`_` 和 `-`，例如 `SPEAKER=sakura_shunka`。改 `SPEAKER` 也会重启任务。
- 任务启动时就定下了说话人，任务跑到一半改 `SPEAKER` 不会把文件写到别人的目录里。
- 训练配置以 `configs/reflow.yaml` 为底，只替换数据和模型目录。想给某个人单独调参，就新建 `configs/speakers/<说话人>.yaml`（完整的一份配置），有这个文件时用它代替 `configs/reflow.yaml`。
- 加新人：把 `SPEAKER` 改成新名字，再跑 `download` 或者直接往 `raw_songs/` 放歌，目录会自动建好。

## 之后的流程

做完上面几步后在对话里告诉 Claude。之后由 Claude 修改 `plan.txt` 来推进任务：

| JOB | 内容 |
|---|---|
| `setup` | 建 conda 环境（ddsp、uvr），下载 ContentVec、NSF-HiFiGAN、RMVPE |
| `download` | 按 `DL_URL` 下载 B 站空间里标题匹配 `DL_MATCH` 的视频音频（`DL_URL` 也可以是仓库里的链接清单，比如 `tools/autodl/lists/` 下的文件），存到 `downloads/`（冷存储）。`DL_MAX` 限制每次最多下载几个新视频（空间按新到旧排，多 P 视频每个 P 算一个）。`DL_FILTER` 追加 yt-dlp 的过滤条件，比如 `duration>=120 & duration<=480`。需要登录时把 cookies 放到 `.autodl/bilibili_cookies.txt` |
| `songsplit` | 把 `downloads/` 里的歌回录像按歌曲切开，去掉聊天，每首歌一个文件存到 `songs/`。歌名取自评论里的道标；切分结果列在 `songs/_songs.tsv`。每个人的切歌参数写在 `tools/autodl/split/<说话人>.args`，`SPLIT_ARGS` 加在它后面，用来临时试参数（见 `python tools/split_songs.py -h`） |
| `uvr` | `raw_songs/` 依次分离人声、去混响、去和声，再切片，输出到 `data/`。模型见 `tools/prepare_dataset.py` 的 `DEFAULT_MODELS`，换了模型的阶段会自动重做 |
| `compare` | 从几首歌各截 40 秒，用几套模型和步骤分别去伴奏，在试听网页的「模型对比」里并排听（`tools/autodl/compare_uvr.py`） |
| `features` | DDSP-SVC 特征预处理（`preprocess.py`） |
| `train` | 训练。重启任务时会从最近保存的 checkpoint 继续 |
| `infer` | 用最新的 checkpoint 转换 `test_songs/` 里的歌曲，结果在网页的「转换结果」里 |
| `migrate` | 一次性任务：把旧的单人目录（仓库里的 `raw_songs/`、`preprocess_work/`、`data/` 等，以及数据盘上的 `<名字>_raw_songs/`、`<名字>_songs/`）搬进 `speakers/`。目标目录里已经有文件时会停下，不覆盖 |
| `idle` | 停止当前任务 |

表格里的目录都在当前说话人的目录 `speakers/<SPEAKER>/` 下。

改 `JOB`、`SPEAKER`，或者把 `RUN_ID` 加 1，都会让 runner 停掉当前任务并按新计划启动。

`JOB` 可以写成用逗号连接的任务链，比如 `JOB=uvr,features,train`。runner 会按顺序执行，前一个成功才启动下一个，遇到失败就停下。

## 自动关机

没有任务在跑、试听网页也没人用的状态持续一段时间后：有卡模式 `IDLE_SHUTDOWN_MIN` 分钟（默认 30），无卡模式 `IDLE_SHUTDOWN_MIN_NOGPU` 分钟（默认 1440，即 24 小时），runner 会在日志分支记一笔，然后执行 `shutdown` 关机，停止计费。设为 `0` 表示不自动关机。

runner 会把自己写进 `/etc/profile.d/zz-ddsp-runner.sh`，之后每次开机自动启动，不用再手动执行。如果没有自动启动，在 JupyterLab 终端执行：

```bash
cd /root/autodl-tmp/DDSP-SVC && tmux new -s runner
bash tools/autodl/runner.sh
```

只是上传文件的话，可以用 AutoDL 的「无卡模式」开机，更便宜。

## 注意

- runner 每次拉代码都会用 GitHub 上的版本覆盖仓库里被 git 跟踪的文件。想改配置（比如 `configs/reflow.yaml`）请告诉 Claude，不要直接在 AutoDL 上改。音频、数据、模型和实验目录不受影响。
- TensorBoard 可以照常用 6006 端口：`tensorboard --logdir /root/autodl-tmp/speakers --port 6006`，所有人的训练曲线都能看到。
- 日志：任务每运行一次单独记一个文件 `.autodl/runs/<开始时间>_<任务名>.log`，`.autodl/job_<任务名>.log` 指向这个任务最近一次运行的日志。想自己看：`tail -F .autodl/job_<任务名>.log`。实例上从新到旧保留 2G 日志，每个任务最近一次运行的日志总会保留。`autodl-logs` 分支上有最近 60 次运行的日志：进度条只留最后一帧，超过 2000 行的只留开头 300 行和最后 1700 行。runner 自己的输出在分支上的 `runner.log`。
- 系统盘只有约 30G，所以 conda 环境（`/root/autodl-tmp/conda_envs/`）、pip/conda/HuggingFace 缓存（`/root/autodl-tmp/.cache/`）都放在数据盘上。两个环境里的 torch 都锁定为 2.9.1（见 `torch-constraints.txt`），防止依赖把它换成另一套 CUDA 版本。
- runner 访问 GitHub 时先直连，失败再走学术加速，因为学术加速访问 GitHub 有时会返回 503。
