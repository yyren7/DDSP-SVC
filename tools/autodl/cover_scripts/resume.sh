#!/bin/bash
# Waits until the GPU (shared with ComfyUI) has NEED MiB free, then finishes round 2 (run2.sh skips what is
# done) and runs round 3. Progress in resume.log.
cd /root/autodl-tmp/covers
E=/root/autodl-tmp/conda_envs
NEED=8000
idle_since=""
while true; do
    free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    [ "$free" -ge "$NEED" ] && break
    q=$(curl -s -m 5 http://127.0.0.1:8188/queue | "$E/ddsp/bin/python" -c 'import sys, json; d = json.load(sys.stdin); print(len(d.get("queue_running", [])) + len(d.get("queue_pending", [])))' 2>/dev/null || echo "?")
    if [ "$q" = "0" ]; then
        [ -z "$idle_since" ] && idle_since=$(date +%s)
        echo "$(date +%T) free ${free} MiB, ComfyUI idle for $(( $(date +%s) - idle_since )) s"
    else
        idle_since=""
        echo "$(date +%T) free ${free} MiB, ComfyUI busy ($q jobs)"
    fi
    sleep 30
done
echo "=== GPU free: ${free} MiB $(date +%T)"
if ./run2.sh akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo rokutousei brave kimishira togetsukyo > run2b.log 2>&1; then
    echo "=== round 2 done $(date +%T)"
    if ./run3.sh akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo > run3.log 2>&1; then
        echo "=== round 3 done $(date +%T)"
    else
        echo "=== round 3 stopped $(date +%T)"
    fi
else
    echo "=== round 2 stopped $(date +%T)"
fi
echo "=== all done $(date +%T)"
