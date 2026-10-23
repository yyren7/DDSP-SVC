#!/bin/bash
# The GPU is shared with ComfyUI batches: run each round whenever NEED MiB are free, and when a round dies
# (out of memory as a batch starts), wait for the next free window and run it again; finished files are kept.
cd /root/autodl-tmp/covers
NEED=8000
SONGS2="akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo rokutousei brave kimishira togetsukyo"
SONGS3="akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo"
wait_gpu() {
    while true; do
        free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
        [ "$free" -ge "$NEED" ] && return
        sleep 20
    done
}
try() {  # name log command...
    local name=$1 log=$2; shift 2
    for k in $(seq 40); do
        wait_gpu
        echo "=== $name try $k with ${free} MiB free $(date +%T)"
        if "$@" >> "$log" 2>&1; then echo "=== $name done $(date +%T)"; return 0; fi
        echo "=== $name failed $(date +%T): $(grep -h -o -E '[A-Za-z]*Error[^.]*' "$log" | tail -1 | cut -c1-120)"
        sleep 30
    done
    return 1
}
try round2 run2b.log ./run2.sh $SONGS2 && try round3 run3.log ./run3.sh $SONGS3
echo "=== all done $(date +%T)"
