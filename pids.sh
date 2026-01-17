#!/bin/bash
echo "bot: $(ps -ux | grep python | grep 'bot_grajacy_piekna_muzyczke.py' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')"
echo "lavalink: $(ps -ux | grep java | grep 'Lavalink.jar' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')"
