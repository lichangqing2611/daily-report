#!/bin/bash

today=`date +%Y-%m-%d`

cd /Users/Charles/Documents/AI/daily-report && DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d'=' -f2) python3 run.py --date $today --all
