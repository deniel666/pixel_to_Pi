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

Report the lines the dashboard prints (take a screenshot with
`adb exec-out screencap -p > termux.png` if that's easier). Then do Task 1.
Skip Tasks 2 and 3 while this foreground dashboard is running: they'd start a
second copy on the same port.

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

## Task 4: sensors through the phone's browser

This Termux is the Google Play build, which has no working Termux:API for
sensors, so the phone's Chrome sends the motion sensor instead. The dashboard
is running in the Termux foreground:

```sh
ssh -p 8022 localhost 'cd ~/pixel_to_Pi && git pull && git log --oneline -1'
adb shell input keycombination 113 31   # Ctrl+C: stop the dashboard (Termux must be in front)
t "python server.py"
adb shell am start -a android.intent.action.VIEW -d http://localhost:8000/sensors.html
open http://localhost:8000
```

Then the user taps **Start** on the phone page. Its status should read
`Sending ✓ (N)` with N growing, and tilting the phone moves the bubble on the
Mac dashboard. Keep that Chrome tab on the phone screen. Report the status line.

## Task 5: GPT-Live voice assistant

The phone's dashboard server brokers GPT-Live sessions, so the OpenAI key
stays on the phone. The user gives you their OpenAI API key. Write it **without
putting it on a command line or in chat**:

```sh
pbpaste | ssh -p 8022 localhost 'umask 077; cat > ~/.openai_key'   # after the user copies the key
ssh -p 8022 localhost 'wc -c < ~/.openai_key'                      # just the length, never the key
```

Then update and restart, as in Task 4:

```sh
ssh -p 8022 localhost 'cd ~/pixel_to_Pi && git pull && git log --oneline -1'
adb shell input keycombination 113 31   # Ctrl+C in Termux (Termux in front)
t "python server.py"
adb shell am start -a android.intent.action.VIEW -d http://localhost:8000/voice.html
```

The user taps **👂 Wake word** once (allow the microphone), then says
**«Привет, Пиксель»** (rising chime = starting, ding = ready) and talks.
**«Пока, Пиксель»** or 45 s of silence ends the call (falling chime).
A low buzz means an error. Transcripts appear
on the Mac dashboard. **Report back**: the status and red error text on the
phone page (if any), the "Event types seen" list (expand it at the bottom),
and any `GPT-Live session ...` lines the dashboard printed in Termux.

If you lose the connection (cable unplugged or adb restarted), re-run the two
`adb forward` lines.
