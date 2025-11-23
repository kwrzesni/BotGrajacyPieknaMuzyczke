#!/bin/bash
echo $(ps -aux | grep python | grep 'BotGrajacyPieknaMuzyczke.py' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')
