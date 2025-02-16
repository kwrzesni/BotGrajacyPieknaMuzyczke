#!/bin/bash

cd /root/BotGrajacyPieknaMuzyczke/LavaLink
lavalink_pid=$(ps -eo pid,command | grep java | grep Lavalink.jar | cut -d ' ' -f 1)
if [[ -z "$lavalink_pid" ]]; then
    java -jar Lavalink.jar &> /dev/null &
    echo Lavalink started
fi
cd ..
python_pid=$(ps -eo pid,command | grep python | grep BotGrajacyPieknaMuzyczke.py | cut -d ' ' -f 1)
if [[ -z "$python_pid" ]]; then
    source SrodowiskoMuzyczne/bin/activate
    python BotGrajacyPieknaMuzyczke.py &> /dev/null &
    echo BotGrajacyPieknaMuzyczke started
fi
