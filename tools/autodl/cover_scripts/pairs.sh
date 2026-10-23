#!/bin/bash
# Download candidate on/off vocal pairs and measure how cleanly they cancel.
# lines: song bvid orig_page inst_page [inst2_page]   (inst2: a second off vocal, e.g. the one with the chorus)
set -uo pipefail
C=/root/autodl-tmp/covers; R=/root/autodl-tmp/DDSP-SVC; E=/root/autodl-tmp/conda_envs
CK=(--cookies "$R/.autodl/bilibili_cookies.txt")
dl() {  # bvid page out
    [ -s "$3" ] && return 0
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY "$E/uvr/bin/yt-dlp" "${CK[@]}" -q --no-warnings \
        -f ba --no-playlist -o "$3.%(ext)s" "https://www.bilibili.com/video/$1?p=$2" < /dev/null && mv "$3".* "$3" 2>/dev/null; [ -s "$3" ]
}
cd "$R"
while read -r song bv po pi pi2; do
    [ -z "$song" ] || [[ "$song" == \#* ]] && continue
    d="$C/$song/pairs/$bv"; mkdir -p "$d"
    dl "$bv" "$po" "$d/orig.m4a" && dl "$bv" "$pi" "$d/inst.m4a" || { echo "$song $bv: download failed"; continue; }
    [ -n "${pi2:-}" ] && dl "$bv" "$pi2" "$d/inst2.m4a"
    for i in inst inst2; do
        [ -s "$d/$i.m4a" ] || continue
        [ -f "$d/$i/offvocal.json" ] || "$E/ddsp/bin/python" tools/offvocal.py "$d/orig.m4a" "$d/$i.m4a" -o "$d/$i" < /dev/null > "$d/$i.log" 2>&1
        r=$(grep -h -E '"depth_best3s_db"|"depth_p10_db"|"verdict"|"cutoff' "$d/$i/offvocal.json" 2>/dev/null | tr -d '\n ' | cut -c1-200)
        echo "$song $bv $i: ${r:-$(tail -1 "$d/$i.log")}"
    done
done < "${1:-/dev/stdin}"
