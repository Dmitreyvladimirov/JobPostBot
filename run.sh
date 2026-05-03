#!/bin/bash
set -a
source /Users/DimaKu/Documents/Coding/JobPostBot.nosync/.env
set +a

exec /opt/homebrew/bin/python3 /Users/DimaKu/Documents/Coding/JobPostBot.nosync/bot.py
