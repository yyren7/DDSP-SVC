#!/bin/bash
# A cover script (run9.sh, run10.sh ...) on the GPU once it has had NEED MiB free at two checks a minute apart,
# so that the other jobs sharing it (Seed-VC fine-tuning; Blender, whose own loop starts a batch at 8000 MiB free
# and takes its memory only after loading the scene) keep their headroom; a run squeezed out all the same waits
# again, at most TRIES times (the scripts skip what is done). Free memory logged when it changes by over 500 MiB.
#   nohup ./gpu_wait.sh ./run10.sh > run10.log 2>&1 &
set -uo pipefail
NEED=${NEED:-5000}; TRIES=${TRIES:-10}
cd /root/autodl-tmp/covers
last=-1000; ok=0
for try in $(seq "$TRIES"); do
    while :; do
        free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
        if [ "$free" -ge "$NEED" ]; then ok=$((ok + 1)); else ok=0; fi
        [ "$ok" -ge 2 ] && break
        if [ $((free - last)) -gt 500 ] || [ $((last - free)) -gt 500 ]; then echo "$(date +%T) free $free MiB, waiting for $NEED"; last=$free; fi
        sleep 60
    done
    echo "$(date +%T) free $free MiB twice, try $try on the GPU: $*"
    DEV=cuda "$@" && exit 0
    echo "$(date +%T) try $try failed"; ok=0; last=-1000
done
exit 1
