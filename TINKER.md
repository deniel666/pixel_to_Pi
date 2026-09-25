# Pixel → Pi: Friday-night tinker kit

Turn a Pixel 7 Pro into a Raspberry Pi–style tinker box: Linux shell, SSH,
Python, a big screen, a keyboard, sensors, and real blinking LEDs.

It's a Friday-night project. Plan on roughly 30 minutes to reach a working shell on the big screen.

---

## 0. Things to know first

| Pi thing | Pixel 7 Pro equivalent |
|---|---|
| Raspberry Pi OS | **Termux** (Linux userland, no root), or Android's built-in **Linux Terminal** (a Debian VM) |
| HDMI out | ⚠️ **No wired video out** (see below). Use DisplayLink, casting, or scrcpy |
| GPIO pins | None. Use a **Pico W / ESP32** as the "GPIO board" over Wi-Fi (project included) |
| Onboard sensors | Many more than a Pi: accelerometer, gyro, light, pressure, GPS, camera, mic |
| USB ports | One USB-C port. Use a **powered USB-C hub** for keyboard, mouse, and drives |

### The monitor catch

The Pixel 7 / 7 Pro **doesn't support DisplayPort-over-USB-C**. Wired video out
first appeared on the Pixel 8. A plain USB-C→HDMI cable shows nothing. Options,
from best to worst:

1. **DisplayLink adapter or dock** plus the free *DisplayLink Presenter* app
   from the Play Store. It streams the screen over USB data, so the
   Pixel 7 doesn't need alt-mode. Most of these docks also have USB ports for a
   keyboard and mouse.
2. **Chromecast, Google TV, or a Miracast dongle** on the monitor. Use Quick
   Settings → *Screen cast*. Setup is easy, but there's some lag.
3. **scrcpy** from a laptop connected to the monitor. You get a mirror with
   full mouse and keyboard control, and very little lag.

If your monitor already shows the phone, you've done one of these. Carry on.

Tip: turn the phone sideways and enable **Settings → Display → Auto-rotate**. A
Bluetooth keyboard and mouse make it feel like a desktop.

---

## 1. Get a Linux shell

### Option A: Termux (recommended; it can reach the phone's sensors)

1. Install **Termux** and **Termux:API** from [F-Droid](https://f-droid.org/packages/com.termux/)
   (the Play Store builds are outdated). Get both from the *same* source.
2. Open Termux and run:

   ```sh
   pkg install -y git
   git clone https://github.com/deniel666/pixel_to_Pi.git
   cd pixel_to_Pi
   bash scripts/setup-termux.sh
   ```

The script installs Python, SSH, handy tools, and Termux:API bindings. It also
prints your IP and SSH port so you can work from a laptop.

### Option B: Android's built-in Linux Terminal (a real Debian VM)

On Android 16: **Settings → System → Developer options → Linux development
environment** → enable, then open the *Terminal* app. It's a full Debian with
`apt`, which is closer to a real Pi, but it can't reach phone sensors. Use it for
servers, compilers, and general Linux fun.

---

## 2. SSH in from a laptop (optional but comfy)

```sh
ssh -p 8022 <anything>@<phone-ip>   # the Termux password you set in setup
```

---

## 3. Projects

### 🖥️ Live sensor dashboard (`projects/dashboard`)

Serves a full-screen page with battery, temperature, light level, a live
accelerometer "bubble level", and memory. Open it on the big monitor.

```sh
cd projects/dashboard
python server.py            # then open http://localhost:8000 in Chrome, full-screen
```

- It runs anywhere. Without Termux:API it switches to **demo mode** with fake data.
- Open `http://<phone-ip>:8000` on any device on the same Wi-Fi.
- Tilt the phone and watch the bubble move.

### 💡 Real GPIO: blink an LED from the phone (`projects/pico-w-led`)

The Pixel has no pins, so a **Raspberry Pi Pico W** (about $6) does that job.
Flash it with MicroPython, copy `main.py` over with Thonny, and put your Wi-Fi
details in it. Then start the dashboard pointed at it:

```sh
PICO_URL=http://<pico-ip> python server.py
```

The dashboard gets an **LED on/off** button, and a
**"light follows the room"** mode that turns the LED on when the phone's light
sensor sees darkness. Wiring and details are in the project's README.

### More ideas for tonight

- `termux-camera-photo` + a cron job gives you a **time-lapse camera**.
- `termux-sensor -s accelerometer` can drive a **knock detector** that runs
  `termux-tts-speak "who's there?"`.
- `pkg install nodejs` → run a **home-lab web server**, reachable on your
  LAN at `http://<phone-ip>:<port>`.
- `pkg install x11-repo termux-x11-nightly xfce4` + the Termux:X11 app gives you
  a **Linux desktop** on the monitor.
- `pkg install mosquitto` → the phone becomes an **MQTT broker** for ESP32 gadgets.
- USB-C hub + USB drive → use `termux-setup-storage` as a pocket **file server**
  (`python -m http.server`).

---

## Safety and battery

- Keep the phone on a charger in a ventilated spot. Enable **Settings → Battery →
  Adaptive charging / Charging optimization** so it doesn't sit at 100% all night.
- Run `termux-wake-lock` for long jobs so Android doesn't kill Termux.
  Run `termux-wake-unlock` when you're done.
