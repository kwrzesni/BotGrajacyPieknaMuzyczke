#!/bin/bash

lavalink_pid=$(ps -eo pid,command | grep java | grep Lavalink.jar | cut -d ' ' -f 1)
if [[ -n "$lavalink_pid" ]]; then
    kill $lavalink_pid
    echo Lavalink stopped
fi
python_pid=$(ps -eo pid,command | grep python | grep BotGrajacyPieknaMuzyczke.py | cut -d ' ' -f 1)
if [[ -n "$python_pid" ]]; then
    kill $python_pid
    echo BotGrajacyPieknaMuzyczke stopped
fi

