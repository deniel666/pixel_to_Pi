#!/data/data/com.termux/files/usr/bin/bash
# Stop any running dashboard and start the current code in the background.
# Usage (from the Mac): ssh -p 8022 localhost 'bash ~/pixel_to_Pi/scripts/restart-dashboard.sh'
cd "$(dirname "$0")/../projects/dashboard" || exit 1

pkill -f "^python3? server.py" && sleep 1
if pgrep -f "^python3? server.py" >/dev/null; then
  pkill -9 -f "^python3? server.py"
  sleep 1
fi

termux-wake-lock 2>/dev/null
nohup python server.py > server.log 2>&1 &
sleep 3
echo "--- commit: $(git log --oneline -1)"
echo "--- server.log:"
cat server.log
if curl -s -XPOST localhost:8000/api/live -d '{}' | grep -q "missing sdp"; then
  echo "--- OK: voice API is live"
else
  echo "--- PROBLEM: /api/live not answering. Old server still on port 8000?"
fi
