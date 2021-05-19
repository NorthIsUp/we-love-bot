#!/usr/bin/env bash
set -x
case "$@" in
run)
    python3 welovebot
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
