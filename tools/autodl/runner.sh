#!/bin/bash
# Keeps AutoDL in sync with GitHub so jobs can be fixed while they run.
#   - pulls $BRANCH every $INTERVAL seconds
#   - starts / restarts the jobs named in tools/autodl/plan.txt when JOB, RUN_ID or SPEAKER changes;
#     JOB may be a comma separated chain (e.g. uvr,features,train), run in order until one fails
#   - shuts the instance down after IDLE_SHUTDOWN_MIN minutes (with a GPU) or IDLE_SHUTDOWN_MIN_NOGPU
#     minutes (no-GPU mode) with no job running and nobody using the review page (stops billing)
#   - starts itself again after every power-on (see AUTOSTART below)
#   - keeps the review web page running (restarted after every code update)
#   - publishes status, log tails and review feedback to the $LOG_BRANCH branch
# Usage (inside tmux):  bash tools/autodl/runner.sh
# The GitHub token is read from $GITHUB_TOKEN, or from .autodl/token after the first run.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

INTERVAL="${INTERVAL:-60}"
TOKEN_FILE="$STATE_DIR/token"
if [ -n "${GITHUB_TOKEN:-}" ]; then
    (umask 077; echo "$GITHUB_TOKEN" > "$TOKEN_FILE")
fi
[ -s "$TOKEN_FILE" ] || { echo "set GITHUB_TOKEN for the first run"; exit 1; }
PUSH_URL="${PUSH_URL:-https://x-access-token:$(cat "$TOKEN_FILE")@github.com/$GITHUB_REPO.git}"

REVIEW_KEY_FILE="$STATE_DIR/review_key"
[ -s "$REVIEW_KEY_FILE" ] || (umask 077; head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$REVIEW_KEY_FILE")

PUB="$STATE_DIR/publish"
# Every job run gets its own log, .autodl/runs/<start time>_<job>.log, and job_<job>.log links to the
# job's latest run. The newest runs are kept up to LOG_KEEP_MB in all (the latest run of every job is
# always kept). The log branch gets the newest LOG_PUBLISH_RUNS runs; a run longer than
# LOG_HEAD + LOG_TAIL lines is published as its first LOG_HEAD and last LOG_TAIL lines.
RUNS_DIR="$STATE_DIR/runs"
LOG_KEEP_MB="${LOG_KEEP_MB:-2048}"
LOG_PUBLISH_RUNS="${LOG_PUBLISH_RUNS:-60}"
LOG_HEAD="${LOG_HEAD:-300}"
LOG_TAIL="${LOG_TAIL:-1700}"
mkdir -p "$RUNS_DIR"
JOB_PID=""; JOB_KEY=""; JOB_NAME=""; JOB_IDX=0; REVIEW_PID=""
RESUME=1   # first loop pass after a (re)start: rerun a job that did not finish cleanly
IDLE_SINCE=$(date +%s)

stop_group() {  # pid
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null || return 0
    kill -TERM -- "-$1" 2>/dev/null
    for _ in $(seq 30); do kill -0 "$1" 2>/dev/null || return 0; sleep 1; done
    kill -KILL -- "-$1" 2>/dev/null
}

# GitHub through AutoDL's academic proxy sometimes answers 503, so try a direct
# connection first and fall back to the proxy. Every call has a timeout.
net() {
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
        timeout 90 "$@" && return 0
    [ -f /etc/network_turbo ] || return 1
    (source /etc/network_turbo >/dev/null 2>&1; timeout 90 "$@")
}

job_exit_code() {  # job -> exit code of its last finished run, empty while it has not finished
    tail -n 1 "$STATE_DIR/job_$1.log" 2>/dev/null | sed -n 's/^=== .* exit \([0-9]*\)$/\1/p'
}

start_job() {  # chain item: job[@speaker][:dataset], speaker if not SPEAKER in plan.txt, dataset see config.sh
    local item="$1" job speaker dataset="" now log
    if [[ "$item" == *:* ]]; then dataset="${item#*:}"; item="${item%%:*}"; fi
    job="${item%%@*}"
    speaker="$(plan_value SPEAKER)"; [ "$item" != "$job" ] && speaker="${item#*@}"
    now="$(date '+%F %T')"; log="${now/ /_}"; log="$RUNS_DIR/${log//:/}_$job.log"
    split_job_log "$job"
    ln -sfn "runs/$(basename "$log")" "$STATE_DIR/job_$job.log"
    echo "=== $now start $job at $(git rev-parse --short HEAD)" >> "$log"
    # The speaker is fixed when the job starts, so editing plan.txt never moves a running job's files.
    SPEAKER="$speaker" DATASET="$dataset" MAX_STEPS="$(plan_value MAX_STEPS)" LINE_FEATURES="$(plan_value LINE_FEATURES)" \
    UVR_ARGS="$(plan_value UVR_ARGS)" KEY="$(plan_value KEY)" SPK_ID="$(plan_value SPK_ID)" \
    WORKERS="$(plan_value WORKERS)" \
    DL_URL="$(plan_value DL_URL)" DL_MATCH="$(plan_value DL_MATCH)" DL_MAX="$(plan_value DL_MAX)" DL_FILTER="$(plan_value DL_FILTER)" SPLIT_ARGS="$(plan_value SPLIT_ARGS)" \
        setsid bash -c "bash tools/autodl/jobs.sh $job >> '$log' 2>&1; rc=\$?; echo \"=== \$(date '+%F %T') exit \$rc\" >> '$log'" &
    JOB_PID=$!; JOB_NAME="$job"
    save_job_state
}

# An empty JOB_PID must never reach `kill -0`: `kill -0 0` checks our own process group and succeeds.
job_running() { [ -n "$JOB_PID" ] && kill -0 "$JOB_PID" 2>/dev/null; }

# Remember the running job so a restarted runner adopts it instead of starting a second copy.
save_job_state() { echo "$JOB_PID|$JOB_KEY|$JOB_NAME|$JOB_IDX" > "$STATE_DIR/job.state"; }
load_job_state() {
    [ -f "$STATE_DIR/job.state" ] || return 0
    local pid key name idx
    IFS='|' read -r pid key name idx < "$STATE_DIR/job.state"
    JOB_NAME="$name"; JOB_KEY="$key"; JOB_IDX="${idx:-0}"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        JOB_PID="$pid"; echo "adopted running job $name (pid $pid)"
    fi
}

# python3 is not on PATH when the runner is started over plain ssh; conda's base python always exists.
PYTHON3="$(command -v python3 || echo "$CONDA_BASE/bin/python3")"

start_review() {
    stop_group "$REVIEW_PID"
    REVIEW_KEY="$(cat "$REVIEW_KEY_FILE")" setsid "$PYTHON3" tools/autodl/review_server.py --port "$REVIEW_PORT" \
        >> "$STATE_DIR/review_server.log" 2>&1 &
    REVIEW_PID=$!
}

# The review server logs every request, so a fresh log means someone is listening right now.
review_active() { [ -n "$(find "$STATE_DIR/review_server.log" -mmin -2 2>/dev/null)" ]; }

# No-GPU mode keeps an nvidia-smi that lists nothing, so look for an actual GPU.
has_gpu() { nvidia-smi -L 2>/dev/null | grep -q '^GPU '; }

# AutoDL's boot script (PID 1) sources /etc/profile, and /etc/profile.d lives on the system disk, so
# this snippet brings the runner back after every power-on. In login shells it does nothing while
# the runner is up.
AUTOSTART=/etc/profile.d/zz-ddsp-runner.sh
cat > "$AUTOSTART.tmp" <<EOF
# Written by $REPO_DIR/tools/autodl/runner.sh: start the runner when AutoDL boots the instance.
if [ -f "$REPO_DIR/tools/autodl/runner.sh" ] && command -v tmux >/dev/null 2>&1 && ! tmux has-session -t runner 2>/dev/null; then
    (cd "$REPO_DIR" && tmux new -d -s runner "bash tools/autodl/runner.sh 2>&1 | tee -a .autodl/runner_console.log")
fi
EOF
mv "$AUTOSTART.tmp" "$AUTOSTART" 2>/dev/null || echo "could not install $AUTOSTART"

# Until 2026-10-18 every run of a job was appended to one job_<job>.log; split such a file into runs/.
# Not while the job is running, because it still writes to that file.
split_job_log() {  # job
    local log="$STATE_DIR/job_$1.log" last
    [ -f "$log" ] && [ ! -L "$log" ] || return 0
    job_running && [ "$1" = "$JOB_NAME" ] && return 0
    last="$(awk -v dir="$RUNS_DIR" -v job="$1" '
        /^=== [0-9-]+ [0-9:]+ start / { t = $3; gsub(/:/, "", t); if (out) close(out); out = dir "/" $2 "_" t "_" job ".log" }
        !out { out = dir "/0000-00-00_000000_" job ".log" }
        { print > out }
        END { print out }' "$log")"
    [ -n "$last" ] && rm -f "$log" && ln -s "runs/$(basename "$last")" "$log"
}

# Delete the oldest runs beyond LOG_KEEP_MB, except a run that is still some job's latest.
prune_runs() {
    find "$RUNS_DIR" -maxdepth 1 -name '*.log' -printf '%f %s\n' | sort -r |
        awk -v max=$((LOG_KEEP_MB << 20)) '{ total += $2 } total > max { print $1 }' |
        while read -r f; do
            [ "$(readlink "$STATE_DIR/job_${f#*_*_}")" = "runs/$f" ] || rm -f "$RUNS_DIR/$f"
        done
}

# The log branch is public, so the review key and the GitHub token are masked in everything published,
# and so is every key the runner ever printed at startup (the console log outlives a new key).
sed_escape() { printf '%s' "$1" | sed 's/[]\/$*.^[]/\\&/g'; }
REDACT="s/$(sed_escape "$(cat "$REVIEW_KEY_FILE")")/***/g; s/$(sed_escape "$(cat "$TOKEN_FILE")")/***/g"
REDACT="$REDACT; s/\(review key: \)[^ ]*/\1***/g"

# A log as a terminal shows it: a progress bar redrawn with \r keeps only its last frame.
render() { awk '{ sub(/\r+$/, ""); n = split($0, p, "\r"); if (p[n] ~ /[^ \t]/) print p[n] }' | sed "$REDACT"; }

publish_log() {  # log, published copy
    local size n tmp="$STATE_DIR/render.tmp"
    size=$(stat -L -c %s "$1")
    if [ "$size" -gt $((8 << 20)) ]; then
        # A long training run: render only its two ends instead of the whole file every minute.
        { head -c $((1 << 20)) "$1" | render | head -n "$LOG_HEAD"
          echo "... $((size >> 20)) MB in all, the middle is left out ..."
          tail -c $((4 << 20)) "$1" | tail -n +2 | render | tail -n "$LOG_TAIL"; } > "$2"
        return 0
    fi
    render < "$1" > "$tmp"
    n=$(wc -l < "$tmp")
    if [ "$n" -gt $((LOG_HEAD + LOG_TAIL)) ]; then
        { head -n "$LOG_HEAD" "$tmp"; echo "... $((n - LOG_HEAD - LOG_TAIL)) lines left out ..."
          tail -n "$LOG_TAIL" "$tmp"; } > "$2"
        rm -f "$tmp"
    else
        mv "$tmp" "$2"
    fi
}

# Logs only grow, so a log is rendered again only when it is another file (inode) or got longer.
declare -A PUBLISHED   # published copy -> "inode size" of the log it was rendered from
publish_changed() {  # log, published copy
    local sig; sig="$(stat -L -c '%i %s' "$1" 2>/dev/null)" || return 0
    [ "${PUBLISHED[$2]:-}" = "$sig" ] && [ -f "$2" ] && return 0
    publish_log "$1" "$2" && PUBLISHED[$2]="$sig"
}

publish() {
    mkdir -p "$PUB"
    [ -d "$PUB/.git" ] || git -C "$PUB" init -q
    # a new SPEAKER gets the folders you upload into right away
    use_speaker "$(plan_value SPEAKER)" && mkdir -p "$RAW_DIR" "$TEST_DIR"
    {
        echo "time:     $(date '+%F %T %Z')"
        echo "code:     $(git rev-parse --short HEAD) $(git log -1 --format=%s)"
        echo "plan:     JOB=$(plan_value JOB) RUN_ID=$(plan_value RUN_ID) SPEAKER=${SPEAKER:-(missing or invalid)}"
        echo "speakers: $(cd "$SPEAKERS_DIR" 2>/dev/null && ls -d -- */ 2>/dev/null | tr -d / | xargs)"
        if job_running; then
            echo "job:      $JOB_NAME running (pid $JOB_PID)"
        else
            echo "job:      ${JOB_NAME:-none} not running; $(grep '=== .* exit' "$STATE_DIR/job_${JOB_NAME:-none}.log" 2>/dev/null | tail -1)"
        fi
        echo "review:   port $REVIEW_PORT (key is in .autodl/review_key, not published)"
        echo "logs:     job_<job>.log latest run of each job, runs/ last $LOG_PUBLISH_RUNS runs, runner.log runner console"
        echo "mode:     $(has_gpu && echo "GPU, idle shutdown after $(plan_value IDLE_SHUTDOWN_MIN) min" \
                                   || echo "no GPU, idle shutdown after $(plan_value IDLE_SHUTDOWN_MIN_NOGPU) min")"
        echo; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv 2>/dev/null
        echo; df -h "$REPO_DIR" 2>/dev/null | tail -1
        echo; for d in "$DL_DIR" "$SONG_DIR" "$RAW_DIR" "$WORK_DIR"/* "$DATA_DIR"/train/audio "$DATA_DIR"/val/audio \
                       "$TEST_DIR" "$INFER_DIR"/*; do
            [ -n "$SPK_DIR" ] && [ -d "$d" ] && echo "$(find "$d" -type f | wc -l) files  ${d#$SPEAKERS_DIR/}"
        done
    } > "$PUB/status.txt" 2>&1
    local l f keep
    for l in "$STATE_DIR"/job_*.log; do
        [ -L "$l" ] || { l="${l##*/job_}"; split_job_log "${l%.log}"; }
    done
    prune_runs
    mkdir -p "$PUB/runs"
    keep="$(ls "$RUNS_DIR" | sort | tail -n "$LOG_PUBLISH_RUNS")"
    for f in $keep; do publish_changed "$RUNS_DIR/$f" "$PUB/runs/$f"; done
    for f in $(ls "$PUB/runs"); do grep -qxF "$f" <<< "$keep" || rm -f "$PUB/runs/$f"; done
    for l in "$STATE_DIR"/job_*.log; do
        [ -e "$l" ] && publish_changed "$l" "$PUB/$(basename "$l")"
    done
    [ -f "$STATE_DIR/runner_console.log" ] && tail -n 3000 "$STATE_DIR/runner_console.log" | render | tail -n 500 > "$PUB/runner.log"
    tail -n 3000 "$STATE_DIR/review_server.log" 2>/dev/null | render | tail -n 300 > "$PUB/review_server.log"
    if [ -f "$EXP_DIR/log_info.txt" ]; then
        tail -n 200 "$EXP_DIR/log_info.txt" > "$PUB/train_log_info.txt"
    else
        rm -f "$PUB/train_log_info.txt"  # do not show another speaker's training log
    fi
    [ -f "$STATE_DIR/feedback.jsonl" ] && cp "$STATE_DIR/feedback.jsonl" "$PUB/feedback.jsonl"
    [ -f "$STATE_DIR/shutdown.log" ] && tail -n 200 "$STATE_DIR/shutdown.log" | render > "$PUB/shutdown.log"
    # One squashed commit, force-pushed, so the log branch never grows.
    git -C "$PUB" add -A
    git -C "$PUB" -c user.name=autodl-runner -c user.email=runner@autodl commit -q --amend -m "status $(date '+%F %T')" 2>/dev/null \
        || git -C "$PUB" -c user.name=autodl-runner -c user.email=runner@autodl commit -q -m "status $(date '+%F %T')"
    net git -C "$PUB" push -q -f "$PUSH_URL" "HEAD:refs/heads/$LOG_BRANCH" 2>&1 | sed "s#$PUSH_URL#<repo>#" | tail -2
    # Every amend leaves the replaced commit behind; drop those once they pile up.
    if [ "$(git -C "$PUB" count-objects | cut -d' ' -f1)" -gt 3000 ]; then
        git -C "$PUB" reflog expire --expire=now --all && git -C "$PUB" gc -q --prune=now
    fi
}

# AutoDL's `shutdown` works from an interactive terminal, so it may be an alias or function from
# .bashrc that a plain script does not see. Try an interactive shell first, record what `shutdown`
# resolves to and what it printed, and give it two minutes to take the machine down.
power_off() {
    local log="$STATE_DIR/shutdown.log"
    {
        echo "=== $(date '+%F %T') shutdown attempt"
        echo "-- type -a shutdown (script):"; type -a shutdown 2>&1
        echo "-- type -a shutdown (interactive):"; bash -ic 'type -a shutdown' 2>&1
    } >> "$log"
    if [ -n "${SHUTDOWN_CMD:-}" ]; then
        $SHUTDOWN_CMD >> "$log" 2>&1
    else
        echo "-- bash -ic shutdown:" >> "$log"
        bash -ic 'shutdown' >> "$log" 2>&1 || { echo "-- shutdown:" >> "$log"; shutdown >> "$log" 2>&1; }
    fi
    echo "-- exit $?" >> "$log"
    sleep "${SHUTDOWN_WAIT:-120}"
}

# Ctrl+C stops the runner and its jobs.
cleanup() { stop_group "$JOB_PID"; stop_group "$REVIEW_PID"; rm -f "$STATE_DIR/job.state"; exit 0; }
trap cleanup INT

echo "runner started; review key: $(cat "$REVIEW_KEY_FILE")"
load_job_state
pkill -f "python3 tools/autodl/review_server.py --port $REVIEW_PORT" 2>/dev/null
start_review
while true; do
    # With the token: GitHub turns anonymous fetches from AutoDL's shared address away for long spells
    # ("Authentication failed", 2026-10-20 21:53-22:45 without one update).
    if net git fetch -q "$PUSH_URL" "$BRANCH" 2>/dev/null && [ "$(git rev-parse HEAD)" != "$(git rev-parse FETCH_HEAD)" ]; then
        old_runner="$(git rev-parse HEAD:tools/autodl/runner.sh)"
        git reset -q --hard FETCH_HEAD
        echo "$(date '+%F %T') updated to $(git rev-parse --short HEAD)"
        if [ "$old_runner" != "$(git rev-parse HEAD:tools/autodl/runner.sh)" ]; then
            echo "$(date '+%F %T') runner.sh changed, restarting runner (jobs keep running)"
            stop_group "$REVIEW_PID"
            exec bash tools/autodl/runner.sh
        fi
        start_review
    fi

    want_chain="$(plan_value JOB)"; want_key="$want_chain:$(plan_value RUN_ID):$(plan_value SPEAKER)"
    IFS=',' read -r -a chain <<< "${want_chain// /}"
    if [ "$want_key" != "$JOB_KEY" ]; then
        # New plan: stop whatever runs and start the chain from the beginning.
        stop_group "$JOB_PID"; JOB_PID=""
        JOB_KEY="$want_key"; JOB_NAME=""; JOB_IDX=0; save_job_state
        if [ "${#chain[@]}" -gt 0 ] && [ "${chain[0]}" != "idle" ]; then
            echo "$(date '+%F %T') starting job ${chain[0]}"
            start_job "${chain[0]}"
        fi
    elif [ -n "$JOB_NAME" ] && ! job_running; then
        # Current job finished: move on to the next one in the chain if it succeeded.
        rc="$(job_exit_code "$JOB_NAME")"
        if [ "$rc" = "0" ] && [ $((JOB_IDX + 1)) -lt "${#chain[@]}" ]; then
            JOB_IDX=$((JOB_IDX + 1))
            echo "$(date '+%F %T') $JOB_NAME done, starting job ${chain[$JOB_IDX]}"
            start_job "${chain[$JOB_IDX]}"
        elif [ "$rc" != "0" ] && [ -n "$RESUME" ]; then
            # Right after (re)start: a job that failed or was cut off by a shutdown runs again, so
            # booting with a GPU resumes uvr/training without touching plan.txt.
            echo "$(date '+%F %T') resuming $JOB_NAME (last run: $([ -n "$rc" ] && echo "exit $rc" || echo interrupted))"
            start_job "${chain[$JOB_IDX]:-$JOB_NAME}"  # the chain item keeps its @speaker
        fi
    fi
    RESUME=""

    kill -0 "$REVIEW_PID" 2>/dev/null || start_review
    publish

    # Nothing running and nobody listening for IDLE_SHUTDOWN_MIN minutes -> power off so the instance
    # stops billing.
    if job_running || review_active; then
        IDLE_SINCE=$(date +%s)
    else
        if has_gpu; then
            limit="$(plan_value IDLE_SHUTDOWN_MIN)"; limit="${limit:-30}"
        else  # no-GPU mode costs little; keep it up for listening and small jobs
            limit="$(plan_value IDLE_SHUTDOWN_MIN_NOGPU)"; limit="${limit:-1440}"
        fi
        if [ "$limit" -gt 0 ] 2>/dev/null && [ $(( $(date +%s) - IDLE_SINCE )) -ge $((limit * 60)) ]; then
            echo "$(date '+%F %T') idle for $limit min, shutting down"
            echo "shutdown: idle for $limit min at $(date '+%F %T %Z')" >> "$PUB/status.txt"
            git -C "$PUB" add -A && git -C "$PUB" -c user.name=autodl-runner -c user.email=runner@autodl commit -q --amend -m "shutdown $(date '+%F %T')"
            net git -C "$PUB" push -q -f "$PUSH_URL" "HEAD:refs/heads/$LOG_BRANCH" 2>&1 | sed "s#$PUSH_URL#<repo>#" | tail -2
            power_off
            # Still here, so the shutdown did not take effect: report it and try again next window.
            echo "$(date '+%F %T') shutdown did not take effect, see .autodl/shutdown.log"
            echo "shutdown FAILED at $(date '+%F %T %Z'), see shutdown.log" >> "$STATE_DIR/shutdown.log"
            IDLE_SINCE=$(date +%s)
        fi
    fi
    sleep "$INTERVAL"
done
