#!/data/data/com.termux/files/usr/bin/bash
# One-shot setup: turns a fresh Termux into a Pi-like dev box.
set -euo pipefail

if [ -z "${PREFIX:-}" ] || [ ! -d "$PREFIX" ]; then
  echo "This script is meant to run inside Termux on the phone." >&2
  exit 1
fi

echo "==> Updating packages"
pkg update -y
pkg upgrade -y

echo "==> Installing tools"
pkg install -y \
  python git openssh termux-api \
  curl wget nano vim htop tmux \
  iproute2 nmap jq

echo "==> Storage access (tap Allow on the phone)"
termux-setup-storage || true

echo "==> SSH server"
if [ ! -f "$PREFIX/etc/ssh/.pixel_to_pi_pw" ]; then
  echo "Set a password for SSH logins:"
  passwd
  touch "$PREFIX/etc/ssh/.pixel_to_pi_pw"
fi
pgrep -x sshd >/dev/null || sshd

echo "==> Checking Termux:API"
if timeout 10 termux-battery-status >/dev/null 2>&1; then
  echo "Termux:API works."
else
  echo "Termux:API didn't answer. Install the Termux:API app from the same source as Termux."
fi

IP=$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{sub(/\/.*/,"",$2); print $2}' || true)
cat <<EOF

All set.
  SSH from a laptop:  ssh -p 8022 $(whoami)@${IP:-<phone-ip>}
  Dashboard:          cd projects/dashboard && python server.py
                      then open http://localhost:8000 (or http://${IP:-<phone-ip>}:8000)
EOF
