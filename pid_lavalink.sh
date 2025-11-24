#!/bin/bash
echo $(ps -ux | grep java | grep 'Lavalink.jar' | tr -s ' ' | cut -d ' ' -f 2 | tr '\n' ' ')
