#!/bin/bash
bot_pid=$(~/pid_bot.sh)
lavalink_pid=$(~/pid_lavalink.sh)

if [[ ! -z $bot_pid ]]; then
        kill $bot_pid
fi

if [[ ! -z $lavalink_pid ]]; then
        kill $lavalink_pid
fi

