#!/bin/bash
# CloudVision CRM — double-click launcher (macOS)
cd "$(dirname "$0")"

echo "Installing dependencies (first run only)..."
python3 -m pip install -r requirements.txt --quiet 2>/dev/null || pip3 install -r requirements.txt --quiet

echo "Starting CloudVision CRM at http://localhost:5050 ..."
( sleep 2 && open "http://localhost:5050" ) &
python3 app.py
