#!/data/data/com.termux/files/usr/bin/bash
# Stop any running dashboard and start the current code in the background.
# Usage (from the Mac): ssh -p 8022 localhost 'bash ~/pixel_to_Pi/scripts/restart-dashboard.sh'
cd "$(dirname "$0")/../projects/dashboard" || exit 1

if ! python ../../scripts/stop_dashboard.py; then
  echo "--- PROBLEM: could not free port 8000; not starting a second server."
  exit 1
fi

termux-wake-lock 2>/dev/null
nohup python server.py > server.log 2>&1 &
sleep 3
echo "--- commit: $(git log --oneline -1)"
echo "--- server.log:"
cat server.log
# /api/tools only exists in the current version, so an old server can't pass this.
if curl -s -m 5 localhost:8000/api/tools | grep -q '"enabled"'; then
  echo "--- OK: current server is running. Tools: $(curl -s -m 5 localhost:8000/api/tools)"
else
  echo "--- PROBLEM: the current server is not the one answering on port 8000."
  exit 1
fi
