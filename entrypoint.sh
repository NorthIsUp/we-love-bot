#!/usr/bin/env bash
set -x
case "$1" in
run)
    shift
    python3 welovebot $@
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
