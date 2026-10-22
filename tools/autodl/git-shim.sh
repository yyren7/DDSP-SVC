#!/bin/bash
# git with the instance-wide GitHub rule: fetch, pull, push, clone and ls-remote go through ghnet
# (the way to GitHub that works, retries, token header, log), every other command straight to git.
# Installed as /usr/local/bin/git by DDSP-SVC/tools/autodl/runner.sh from tools/autodl/git-shim.sh.
REAL=/usr/bin/git
[ -z "${GHNET_INNER:-}" ] && command -v ghnet >/dev/null 2>&1 || exec "$REAL" "$@"
sub=""; skip=0
for a in "$@"; do
    [ "$skip" = 1 ] && { skip=0; continue; }
    case "$a" in
        -C|-c|--git-dir|--work-tree|--namespace|--super-prefix|--config-env) skip=1 ;;  # option with its own argument
        -*) ;;                                                                        # --git-dir=x, --bare, -p, ...
        *) sub="$a"; break ;;
    esac
done
case "$sub" in
    fetch|pull|push|clone|ls-remote) exec ghnet "$REAL" "$@" ;;
    *) exec "$REAL" "$@" ;;
esac
