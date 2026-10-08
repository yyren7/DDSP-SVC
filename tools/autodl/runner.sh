#!/bin/bash
# Keeps AutoDL in sync with GitHub so jobs can be fixed while they run.
#   - pulls $BRANCH every $INTERVAL seconds
#   - starts / restarts the job named in tools/autodl/plan.txt when JOB or RUN_ID changes
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
JOB_PID=""; JOB_KEY=""; JOB_NAME=""; REVIEW_PID=""

plan_value() {  # key -> value from plan.txt (plain KEY=VALUE lines, never executed)
    grep -E "^$1=" tools/autodl/plan.txt 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}

stop_group() {  # pid
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null || return 0
    kill -TERM -- "-$1" 2>/dev/null
    for _ in $(seq 30); do kill -0 "$1" 2>/dev/null || return 0; sleep 1; done
    kill -KILL -- "-$1" 2>/dev/null
}

start_job() {
    local job="$1" log="$STATE_DIR/job_$1.log"
    echo "=== $(date '+%F %T') start $job at $(git rev-parse --short HEAD)" >> "$log"
    UVR_ARGS="$(plan_value UVR_ARGS)" KEY="$(plan_value KEY)" SPK_ID="$(plan_value SPK_ID)" \
    WORKERS="$(plan_value WORKERS)" \
        setsid bash -c "bash tools/autodl/jobs.sh $job >> '$log' 2>&1; rc=\$?; echo \"=== \$(date '+%F %T') exit \$rc\" >> '$log'" &
    JOB_PID=$!; JOB_NAME="$job"
    save_job_state
}

# Remember the running job so a restarted runner adopts it instead of starting a second copy.
save_job_state() { echo "$JOB_PID|$JOB_KEY|$JOB_NAME" > "$STATE_DIR/job.state"; }
load_job_state() {
    [ -f "$STATE_DIR/job.state" ] || return 0
    local pid key name
    IFS='|' read -r pid key name < "$STATE_DIR/job.state"
    JOB_NAME="$name"; JOB_KEY="$key"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        JOB_PID="$pid"; echo "adopted running job $name (pid $pid)"
    fi
}

start_review() {
    stop_group "$REVIEW_PID"
    REVIEW_KEY="$(cat "$REVIEW_KEY_FILE")" setsid python3 tools/autodl/review_server.py --port "$REVIEW_PORT" \
        >> "$STATE_DIR/review_server.log" 2>&1 &
    REVIEW_PID=$!
}

tail_clean() {  # file lines: turn progress-bar carriage returns into lines, keep the end
    [ -f "$1" ] && tr '\r' '\n' < "$1" | grep -v '^\s*$' | tail -n "$2"
}

publish() {
    mkdir -p "$PUB"
    [ -d "$PUB/.git" ] || git -C "$PUB" init -q
    {
        echo "time:     $(date '+%F %T %Z')"
        echo "code:     $(git rev-parse --short HEAD) $(git log -1 --format=%s)"
        echo "plan:     JOB=$(plan_value JOB) RUN_ID=$(plan_value RUN_ID)"
        if [ -n "$JOB_PID" ] && kill -0 "$JOB_PID" 2>/dev/null; then
            echo "job:      $JOB_NAME running (pid $JOB_PID)"
        else
            echo "job:      ${JOB_NAME:-none} not running; $(grep '=== .* exit' "$STATE_DIR/job_${JOB_NAME:-none}.log" 2>/dev/null | tail -1)"
        fi
        echo "review:   port $REVIEW_PORT (key is in .autodl/review_key, not published)"
        echo; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv 2>/dev/null
        echo; df -h "$REPO_DIR" 2>/dev/null | tail -1
        echo; for d in "$RAW_DIR" "$WORK_DIR"/* data/train/audio data/val/audio "$TEST_DIR" "$INFER_DIR"/*; do
            [ -d "$d" ] && echo "$(find "$d" -type f -not -name '.gitignore' | wc -l) files  ${d#$REPO_DIR/}"
        done
    } > "$PUB/status.txt" 2>&1
    for f in "$STATE_DIR"/job_*.log; do
        [ -f "$f" ] && tail_clean "$f" 400 > "$PUB/$(basename "$f")"
    done
    tail_clean "$STATE_DIR/review_server.log" 100 > "$PUB/review_server.log"
    local exp; exp=$(grep -E '^\s*expdir:' "$CONFIG" | head -1 | awk '{print $2}')
    [ -f "$exp/log_info.txt" ] && tail -n 200 "$exp/log_info.txt" > "$PUB/train_log_info.txt"
    [ -f "$STATE_DIR/feedback.jsonl" ] && cp "$STATE_DIR/feedback.jsonl" "$PUB/feedback.jsonl"
    # One squashed commit, force-pushed, so the log branch never grows.
    git -C "$PUB" add -A
    git -C "$PUB" -c user.name=autodl-runner -c user.email=runner@autodl commit -q --amend -m "status $(date '+%F %T')" 2>/dev/null \
        || git -C "$PUB" -c user.name=autodl-runner -c user.email=runner@autodl commit -q -m "status $(date '+%F %T')"
    # Network calls get a timeout so a stalled connection can never freeze the loop.
    timeout 120 git -C "$PUB" push -q -f "$PUSH_URL" "HEAD:refs/heads/$LOG_BRANCH" 2>&1 | sed "s#$PUSH_URL#<repo>#" | tail -2
}

# Ctrl+C stops the runner and its jobs.
cleanup() { stop_group "$JOB_PID"; stop_group "$REVIEW_PID"; rm -f "$STATE_DIR/job.state"; exit 0; }
trap cleanup INT

echo "runner started; review key: $(cat "$REVIEW_KEY_FILE")"
load_job_state
pkill -f "^python3 tools/autodl/review_server.py --port $REVIEW_PORT" 2>/dev/null
start_review
while true; do
    [ -f /etc/network_turbo ] && source /etc/network_turbo >/dev/null 2>&1
    if timeout 60 git fetch -q origin "$BRANCH" 2>/dev/null && [ "$(git rev-parse HEAD)" != "$(git rev-parse FETCH_HEAD)" ]; then
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
    want_job="$(plan_value JOB)"; want_key="$want_job:$(plan_value RUN_ID)"
    if [ "$want_key" != "$JOB_KEY" ]; then
        stop_group "$JOB_PID"; JOB_PID=""
        JOB_KEY="$want_key"; JOB_NAME=""; save_job_state
        if [ -n "$want_job" ] && [ "$want_job" != "idle" ]; then
            echo "$(date '+%F %T') starting job $want_job"
            start_job "$want_job"
        fi
    fi
    kill -0 "$REVIEW_PID" 2>/dev/null || start_review
    publish
    sleep "$INTERVAL"
done
