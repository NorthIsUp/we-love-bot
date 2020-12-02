#!/usr/bin/env bash
case "$@" in
run)
    python3 app.py
    ;;
*)
    echo "'$@' is not a valid command"
    ;;
esac
