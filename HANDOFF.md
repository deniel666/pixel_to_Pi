# Handoff: Pixel 7 Pro "Pi" setup (for a local agent on the Mac)

You are taking over from a cloud session that could not reach the user's
devices. You run **on the user's Mac**, so you can execute commands yourself.
The user prefers chatting in **Russian**. Do the typing for them; only ask them
to act on the phone when something truly needs a tap (permission dialogs, PIN).

## Goal

Use the Pixel 7 Pro as a Raspberry Pi-style tinker computer: Linux shell
(Termux), shown on the big monitor, running the projects in this repo. Start
with the live sensor dashboard, then maybe the Pico W LED project. Background
reading: `TINKER.md` (guide), `README.md` (longer-term voice assistant / LED
panel brief).

## Hardware and state (2026-09-25, ~10:15 local)

| Item | State |
|---|---|
| Phone | Pixel 7 Pro, **Android 17**, build CP3A.260905.009 |
| Video out | Pixel 7 Pro has **no USB-C video out**. The monitor is connected to the **Mac** (USB-C to HDMI), and the phone is mirrored with scrcpy |
| USB link | Phone to Mac by USB. Developer options on, USB debugging on, Mac **authorized** (`adb devices` shows `device`) |
| Mac tools | Homebrew, `scrcpy` 4.1, `android-platform-tools` (adb) installed |
| scrcpy | Running in one Terminal tab. **Don't Ctrl+C that tab**; open new tabs |
| Termux | Installed on phone. Repo cloned at `~/pixel_to_Pi` on branch `claude/affectionate-bardeen-molo5d` (**stale**, needs `git pull`) |
| setup script | `scripts/setup-termux.sh` installed packages (python, openssh, git, vim, clang…), then **exited at the SSH password step** (passwords didn't match). So `sshd` was never started and no SSH password is set |
| Termux:API | Package installed. The **Termux:API app** is probably missing or not responding (`termux-sensor -l` returned non-JSON) |
| Dashboard | Ran once and crashed its sensor thread on that non-JSON. **Fixed in commit e413ef7**: now it falls back to demo mode with a hint. Phone copy needs `git pull` |

Repo: https://github.com/deniel666/pixel_to_Pi, PR #1 (branch
`claude/affectionate-bardeen-molo5d`, not merged yet).

## Next steps

### 1. One-time manual step on the phone (the user types it in Termux)

Without SSH you can't run commands inside Termux. `adb shell` runs as a
different user and can't reach Termux's files. So the user must type this once
in the Termux window (click the scrcpy window first):

```sh
passwd      # same password twice; typing is invisible
sshd
```

Pasting tip: in the scrcpy window, **Cmd+Shift+V** types the Mac clipboard as
keystrokes. Plain paste often fails in Termux.

### 2. Connect over USB (you do this on the Mac)

```sh
adb forward tcp:8022 tcp:8022   # Termux sshd
adb forward tcp:8000 tcp:8000   # dashboard
ssh -p 8022 localhost           # user enters the password once
```

Then set up key login so you can run commands non-interactively:

```sh
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
ssh-copy-id -p 8022 localhost
ssh -p 8022 localhost 'echo ok'   # should print ok with no password
```

The Termux username doesn't matter for sshd. Forwards are lost when the cable is
unplugged or adb restarts, so re-run the two `adb forward` lines then.

### 3. Update the repo and finish the setup

```sh
ssh -p 8022 localhost 'cd ~/pixel_to_Pi && git pull'
```

`setup-termux.sh` now re-prompts on a password mismatch. It doesn't need
re-running, since packages are already installed and the password was set in
step 1.

### 4. Termux:API for real sensors

The user installs **Termux:API** from **F-Droid** (the same store Termux came
from; mixing F-Droid and Play Store builds breaks it) and **opens it once**.
Verify:

```sh
ssh -p 8022 localhost 'termux-battery-status'   # expect JSON with "percentage"
ssh -p 8022 localhost 'termux-sensor -l'        # expect {"sensors": [...]}
```

If these hang or print errors, check the app's permissions in Android settings.
The dashboard still works without it, in demo mode.

### 5. Run the dashboard and show it on the monitor

```sh
ssh -p 8022 localhost 'termux-wake-lock; cd ~/pixel_to_Pi/projects/dashboard && nohup python server.py > server.log 2>&1 &'
sleep 3; curl -s localhost:8000/api/stats | head -c 300
open http://localhost:8000
```

Put the browser full-screen on the monitor (Cmd+Ctrl+F). Startup log is in
`~/pixel_to_Pi/projects/dashboard/server.log` on the phone: expect
`[live Termux:API]` or `[DEMO mode: ...]`.

**Done when:** the dashboard is full-screen on the monitor with real battery
data, and tilting the phone moves the bubble.

## Gotchas already hit

- The first Developer options screen the user found was **TalkBack's**
  developer settings ("Enable node tree debugging"). The system one is under
  Settings → System (after tapping Build number 7 times).
- Commands typed into the Mac Terminal tab running scrcpy don't execute until
  scrcpy exits.
- The user speaks Russian and uses voice dictation, so expect transcription
  errors in folder and command names.

## Ideas after the dashboard works

Listed in `TINKER.md`: Pico W LED over Wi-Fi (`projects/pico-w-led`), time-lapse
camera with `termux-camera-photo`, knock detector with `termux-tts-speak`,
Termux:X11 desktop, MQTT broker. The longer-term plan in `README.md` is a voice
assistant plus an LED panel over Wi-Fi.
