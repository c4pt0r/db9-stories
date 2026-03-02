#!/bin/bash
cd /home/pi/db9-stories

# db9 config
export DB9_API_URL="https://staging.db9.ai/api"
export DB9_ID="rkwkfa6enstb"
export DB9_TOKEN="$(cat ~/.db9/credentials | grep token | cut -d'"' -f2)"

# Start server
uvicorn main:app --host 0.0.0.0 --port 3458 --reload
