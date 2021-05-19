#!/usr/bin/env bash
set -x
case "$@" in
run)
    python3 northisbot
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
