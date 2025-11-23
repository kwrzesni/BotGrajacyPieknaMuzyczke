#!/bin/bash
echo "bot: $(ps -aux | grep python | grep 'BotGrajacyPieknaMuzyczke.py' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')"
echo "lavalink: $(ps -aux | grep java | grep 'Lavalink.jar' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')"
