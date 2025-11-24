#!/bin/bash
echo $(ps -ux | grep python | grep 'BotGrajacyPieknaMuzyczke.py' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')
