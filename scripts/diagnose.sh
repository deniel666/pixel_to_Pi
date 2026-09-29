#!/data/data/com.termux/files/usr/bin/bash
# Collect everything needed to debug the voice assistant. Prints no secrets.
# Usage (from the Mac): ssh -p 8022 localhost 'bash ~/pixel_to_Pi/scripts/diagnose.sh'
cd "$(dirname "$0")/.." || exit 1
echo "=== code:      $(git log --oneline -1)"
echo "=== server:    $(python scripts/stop_dashboard.py --list 2>/dev/null | head -1)"
echo "=== voice API: $(curl -s -m 5 -XPOST localhost:8000/api/live -d '{}' || echo 'no answer')"
echo "=== tools:     $(curl -s -m 5 localhost:8000/api/tools || echo 'no answer')"
if [ -s ~/.openai_key ]; then
  code=$(curl -s -m 15 -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models \
         -H "Authorization: Bearer $(cat ~/.openai_key)")
  echo "=== OpenAI key: HTTP $code (200 = valid, 401 = bad key, 429 = quota/billing)"
else
  echo "=== OpenAI key: MISSING (~/.openai_key)"
fi
python ~/pixel_to_Pi/scripts/set_secret.py --show 2>/dev/null | sed 's/^/=== config: /'
echo "=== last 40 lines of server.log:"
tail -n 40 projects/dashboard/server.log 2>/dev/null || echo "(no log)"
