#!/bin/bash
bot_pid=$(~/pid_bot.sh)
lavalink_pid=$(~/pid_lavalink.sh)
if [[ -z $bot_pid ]] && [[ ! -z $lavalink_pid ]]; then
	kill $lavalink_pid
fi

if [[ -z $bot_pid ]]; then
        python ~/BotGrajacyPieknaMuzyczke.py > logs.txt 2> errors.txt &
fi
