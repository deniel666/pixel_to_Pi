# Handoff: short tasks for the local agent on the Mac

A cloud Claude session is doing the planning and code for this repo but can't
reach the user's devices. **Your job is only to run these commands on the Mac
and report the output back.** Don't redesign anything and don't edit code. If
something fails, stop and paste the error.

Setup: Pixel 7 Pro (Android 17) is connected to the Mac by USB, and
`adb devices` shows it as `device`. scrcpy is running in a Terminal tab, so
don't touch that tab. Termux on the phone has this repo at `~/pixel_to_Pi`.

## Task 0: type into Termux for the user (no SSH needed)

`adb shell input text` types into whatever app is on screen, so keep **Termux
open and in front** on the phone. Define this helper in your Mac shell. Avoid
`&`, `;`, `|`, `$` and quotes in the typed text:

```sh
t() { adb shell "input text '$(printf %s "$1" | sed 's/ /%s/g')'"; adb shell input keyevent 66; sleep 1; }
```

First stop the old dashboard (Ctrl+C in Termux), then set the SSH password.
Pick a simple letters-and-digits password, tell the user what it is, and type
the **same** value both times:

```sh
adb shell input keycombination 113 31   # Ctrl+C
t "passwd"
t "PICKED_PASSWORD"
t "PICKED_PASSWORD"
t "sshd"
```

Also pull the latest code and restart the dashboard in the foreground. The new
version logs what `termux-sensor` actually prints instead of crashing:

```sh
t "cd ~/pixel_to_Pi"
t "git pull"
t "cd projects/dashboard"
t "python server.py"
```

Tasks 2 and 3 below then just confirm this over SSH.

## Task 1: connect to the phone over USB

```sh
adb forward tcp:8022 tcp:8022
adb forward tcp:8000 tcp:8000
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
ssh-copy-id -p 8022 localhost     # the user enters the Termux password once
ssh -p 8022 localhost 'echo ok'   # must print: ok
```

## Task 2: update the code on the phone

```sh
ssh -p 8022 localhost 'cd ~/pixel_to_Pi && git pull && git log --oneline -1'
```

## Task 3: start the dashboard and open it

```sh
ssh -p 8022 localhost 'termux-wake-lock; cd ~/pixel_to_Pi/projects/dashboard && nohup python server.py > server.log 2>&1 &'
sleep 5
ssh -p 8022 localhost 'cat ~/pixel_to_Pi/projects/dashboard/server.log'
open http://localhost:8000
```

**Report back** the output of `server.log`. It shows either
`[live Termux:API]` or `[DEMO mode ...]`.

If you lose the connection (cable unplugged or adb restarted), re-run the two
`adb forward` lines.
