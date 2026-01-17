#!/bin/bash
echo $(ps -ux | grep python | grep 'bot_grajacy_piekna_muzyczke.py' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')
