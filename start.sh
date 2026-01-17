#!/bin/bash
bot_pid=$(~/pid_bot.sh)
lavalink_pid=$(~/pid_lavalink.sh)
if [[ -z $bot_pid ]] && [[ ! -z $lavalink_pid ]]; then
	kill $lavalink_pid
fi

if [[ -z $bot_pid ]]; then
        python ~/bot_grajacy_piekna_muzyczke.py &> /dev/null &
fi
