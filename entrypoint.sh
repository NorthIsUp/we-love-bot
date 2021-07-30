#!/usr/bin/env bash
set -x
echo "$1 -- ${@:2}"
case "$1" in
run)
    shift
    python3 welovebot $@
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
