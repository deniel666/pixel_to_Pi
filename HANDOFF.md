# Handoff: short tasks for the local agent on the Mac

A cloud Claude session is doing the planning and code for this repo but can't
reach the user's devices. **Your job is only to run these commands on the Mac
and report the output back.** Don't redesign anything and don't edit code. If
something fails, stop and paste the error.

Setup: Pixel 7 Pro (Android 17) is connected to the Mac by USB, and
`adb devices` shows it as `device`. scrcpy is running in a Terminal tab, so
don't touch that tab. Termux on the phone has this repo at `~/pixel_to_Pi`.

## Before you start (the user does this on the phone, in Termux)

```sh
passwd   # same password twice
sshd
```

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
