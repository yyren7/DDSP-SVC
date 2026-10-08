# AutoDL 边跑边修

AutoDL 上常驻一个 runner 脚本，通过 GitHub 和 Claude 交换代码与日志：

- **runner**：每分钟拉一次代码，按 `tools/autodl/plan.txt` 启动或重启任务，并把状态、日志尾部和你的试听反馈推到 `autodl-logs` 分支。
- **Claude**：读 `autodl-logs` 分支上的日志，修好代码后推到 `claude/amazing-sagan-49ux44` 分支，runner 会自动拉取。
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
git clone -b claude/amazing-sagan-49ux44 https://github.com/yyren7/DDSP-SVC.git
cd DDSP-SVC
tmux new -s runner                   # 用 tmux 运行，关掉网页终端也不会中断
GITHUB_TOKEN=粘贴你的token bash tools/autodl/runner.sh
```

- runner 启动时会打印**试听密钥**，记下来。
- 按 `Ctrl+B` 再按 `D` 可以离开 tmux，runner 继续在后台运行。
- 实例关机重开后，进入仓库目录执行 `tmux new -s runner` 和 `bash tools/autodl/runner.sh` 即可，第二次起不用再给 token。

### 4. 上传音频

用 JupyterLab 左侧的上传按钮，或 AutoDL 网盘：

- 训练用的歌曲放进 `raw_songs/`
- 想用来试转换效果的歌曲放进 `test_songs/`

### 5. 打开试听网页

AutoDL 控制台 → 实例的「自定义服务」→ 打开 6008 端口对应的链接，然后在网址末尾加上 `?key=试听密钥`。之后浏览器会记住密钥。

网页里可以：
- 按歌曲对比原曲、分离人声、去和声、去混响、去噪的效果
- 按阶段浏览切片、训练集、转换结果
- 在每段音频下面或页面顶部写反馈

## 之后的流程

做完上面几步后在对话里告诉 Claude。之后由 Claude 修改 `plan.txt` 来推进任务：

| JOB | 内容 |
|---|---|
| `setup` | 建 conda 环境（ddsp、uvr），下载 ContentVec、NSF-HiFiGAN、RMVPE |
| `uvr` | `raw_songs/` 依次分离人声、去和声、去混响、去噪，再切片，输出到 `data/` |
| `features` | DDSP-SVC 特征预处理（`preprocess.py`） |
| `train` | 训练。重启任务时会从最近保存的 checkpoint 继续 |
| `infer` | 用最新的 checkpoint 转换 `test_songs/` 里的歌曲，结果在网页的「转换结果」里 |
| `idle` | 停止当前任务 |

改 `JOB`，或者把 `RUN_ID` 加 1，都会让 runner 停掉当前任务并按新计划启动。

`JOB` 可以写成用逗号连接的任务链，比如 `JOB=uvr,features,train`。runner 会按顺序执行，前一个成功才启动下一个，遇到失败就停下。

## 自动关机

没有任务在跑的状态持续 `IDLE_SHUTDOWN_MIN` 分钟（默认 30）后，runner 会在日志分支记一笔，然后执行 `shutdown` 关机，停止计费。设为 `0` 表示不自动关机。

重新开机后，在 JupyterLab 终端执行：

```bash
cd /root/autodl-tmp/DDSP-SVC && tmux new -s runner
bash tools/autodl/runner.sh
```

只是上传文件的话，可以用 AutoDL 的「无卡模式」开机，更便宜。

## 注意

- runner 每次拉代码都会用 GitHub 上的版本覆盖仓库里被 git 跟踪的文件。想改配置（比如 `configs/reflow.yaml`）请告诉 Claude，不要直接在 AutoDL 上改。音频、数据、模型和实验目录不受影响。
- TensorBoard 可以照常用 6006 端口：`tensorboard --logdir exp --port 6006`。
- 想自己看日志：`tail -f .autodl/job_<任务名>.log`。
- runner 访问 GitHub 时先直连，失败再走学术加速，因为学术加速访问 GitHub 有时会返回 503。
