#!/bin/bash
# ghnet: run a command that talks to GitHub by the way out of AutoDL that works right now.
#   ghnet git pull      ghnet git clone https://github.com/...      ghnet curl -fsSL https://github.com/...
# The git on PATH (/usr/local/bin/git, from git-shim.sh) sends fetch, pull, push, clone and ls-remote
# through here by itself, so every project on this instance gets the rule without doing anything.
#
# There are two ways out, both shared with every other user of the host and both bad at times: the
# direct connection stalls for minutes to hours when the link abroad is bad, and the academic proxy
# (a Squid at 172.26.1.26 that opens the TLS connections itself) answers 503 or turns a valid token
# away for a while. The way that worked last time is tried first, then the other, and both again
# after a pause, as long as the failure looks like the network; a failure of the command itself (a
# merge conflict, a wrong path) is reported at once. For git: the token in $GHNET_STATE/token goes
# to github.com in an Authorization header on every request, so no request is anonymous (GitHub
# throttles the shared addresses' anonymous requests first) and the token stays out of `ps`; a
# token GitHub refuses is dropped for one more anonymous try; HTTP/1.1 is used because HTTP/2
# streams to GitHub break now and then; a transfer below 1 kB/s for 30 s is given up. Every failed
# attempt is logged with its reason in $GHNET_STATE/net.log, the way that worked in $GHNET_STATE/way,
# the last success (time, command, way) in $GHNET_STATE/last_ok.
# Installed by DDSP-SVC/tools/autodl/runner.sh from tools/autodl/ghnet.sh.
set -uo pipefail
STATE="${GHNET_STATE:-/root/.ghnet}"
TIMEOUT="${GHNET_TIMEOUT:-300}"   # hard cap per attempt; a stall is caught sooner by the low speed limit
PROXY_FILE="${GHNET_PROXY_FILE:-/etc/network_turbo}"   # sets http(s)_proxy; overridable for tests
mkdir -p "$STATE"
export GHNET_INNER=1              # the git shim passes commands straight through from here on
[ $# -gt 0 ] || { echo "usage: ghnet command [args...]" >&2; exit 2; }

TOKEN_B64=""
[ -s "$STATE/token" ] && TOKEN_B64="$(printf 'x-access-token:%s' "$(cat "$STATE/token")" | base64 -w0)"
cfg=(http.version=HTTP/1.1 http.lowSpeedLimit=1000 http.lowSpeedTime=30)
git_env() {  # token|anon -> GIT_ENV: GIT_CONFIG_* for cfg, plus the token header unless anon
    local -a c=("${cfg[@]}"); local i
    [ "$1" = anon ] || [ -z "$TOKEN_B64" ] || c+=("http.https://github.com/.extraheader=Authorization: Basic $TOKEN_B64")
    GIT_ENV=(GIT_TERMINAL_PROMPT=0 "GIT_CONFIG_COUNT=${#c[@]}")
    for i in "${!c[@]}"; do GIT_ENV+=("GIT_CONFIG_KEY_$i=${c[$i]%%=*}" "GIT_CONFIG_VALUE_$i=${c[$i]#*=}"); done
}

via() {  # direct|proxy token|anon command...
    local way="$1"; git_env "$2"; shift 2
    if [ "$way" = direct ]; then
        env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
            "${GIT_ENV[@]}" timeout -k 10 "$TIMEOUT" "$@"
    else
        [ -f "$PROXY_FILE" ] || { echo "no $PROXY_FILE" >&2; return 1; }
        (source "$PROXY_FILE" >/dev/null 2>&1; env "${GIT_ENV[@]}" timeout -k 10 "$TIMEOUT" "$@")
    fi
}

# What the log calls this command: "git pull", "curl", ... (git's global options are skipped).
subcommand() {
    local skip=0 a
    for a in "$@"; do
        [ "$skip" = 1 ] && { skip=0; continue; }
        case "$a" in
            -C|-c|--git-dir|--work-tree|--namespace|--super-prefix|--config-env) skip=1 ;;
            -*) ;;
            *) echo "$a"; return ;;
        esac
    done
}
what="${1##*/}"; [ "$what" = git ] && what="git $(subcommand "${@:2}")"

log() { echo "$(date '+%F %T') $*" | tee -a "$STATE/net.log" >&2; }
[ -f "$STATE/net.log" ] && [ "$(wc -l < "$STATE/net.log")" -gt 3000 ] && { tail -n 2000 "$STATE/net.log" > "$STATE/net.log.tmp" && mv "$STATE/net.log.tmp" "$STATE/net.log"; }

network_error() {  # exit code, stderr file -> true when the failure looks like the way, not the command
    [ "$1" = 124 ] && return 0
    grep -q -i -E 'unable to access|could not resolve|connection (refused|reset|closed)|timed out|too slow|early eof|hung up|rpc failed|empty reply|http/?2|returned error: (5[0-9][0-9]|429)|could not read username|authentication failed|unexpected disconnect|ssl|tls|network is unreachable|no answer|network_turbo' "$2"
}

err="$(mktemp "${TMPDIR:-/tmp}/ghnet.XXXXXX")"; trap 'rm -f "$err"' EXIT
first="$(cat "$STATE/way" 2>/dev/null)"
[ "$first" = direct ] || [ "$first" = proxy ] || { [ -f "$PROXY_FILE" ] && first=proxy || first=direct; }
[ "$first" = direct ] && other=proxy || other=direct
rc=1
for round in 1 2; do
    [ "$round" = 1 ] || sleep 10
    for way in "$first" "$other"; do
        for auth in token anon; do
            via "$way" "$auth" "$@" 2>"$err"; rc=$?
            [ -t 2 ] && cat "$err" >&2   # a person at a terminal sees what the command said
            if [ "$rc" = 0 ]; then
                echo "$way" > "$STATE/way"
                echo "$(date '+%F %T') $what via $way" > "$STATE/last_ok"
                [ "$auth" = anon ] && note=" without the token" || note=""
                [ "$round$way$auth" = "1${first}token" ] || log "$what ok via $way$note after retrying"
                exit 0
            fi
            reason="$(grep -v '^$' "$err" | tail -1)"; [ "$rc" = 124 ] && reason="no answer in $TIMEOUT s"
            if [[ "$reason" == *"could not read Username"* ]]; then   # how git reports a 401 with prompts off
                if [ "$auth" = anon ]; then reason="refused without the token too (401)"
                elif [ -n "$TOKEN_B64" ]; then reason="token refused (401)"
                else reason="refused, no token (401)"; fi
            fi
            # the command's own failure (a merge conflict, a wrong path): no retry, not the log's business
            network_error "$rc" "$err" || { [ -t 2 ] || cat "$err" >&2; exit "$rc"; }
            log "$what via $way failed: $reason"
            [ "$reason" = "token refused (401)" ] || break   # the anonymous try only follows a refused token
        done
    done
done
[ -t 2 ] || cat "$err" >&2
exit "$rc"
