#!/usr/bin/env bash
set -x
[[ ${#@} == 3 ]] && set - $3

echo "$1 -- ${@:2}" >&2
python3 --version

case "$1" in
run)
    shift
    exec python3 welovebot $@
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
