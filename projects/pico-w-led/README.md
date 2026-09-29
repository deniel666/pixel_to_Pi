# Pico W: the phone's GPIO board

The Pixel has no header pins, so a Raspberry Pi Pico W handles them. The phone
talks to it over Wi-Fi.

## You need

- Raspberry Pi Pico W (the **W** matters, since it has the Wi-Fi)
- Micro-USB cable
- Optional: LED + 330Ω resistor + breadboard (the onboard LED works fine)

## Steps

1. Hold **BOOTSEL** while plugging the Pico into a computer. It shows up as a drive.
   Drag the MicroPython `.uf2` for Pico W onto it
   (from <https://micropython.org/download/RPI_PICO_W/>).
2. Open **Thonny**, choose interpreter *MicroPython (Raspberry Pi Pico)*.
3. Open `main.py`, set `WIFI_SSID` / `WIFI_PASSWORD` (2.4 GHz network), and
   save it to the Pico as `main.py`.
4. Press Stop/Restart. The shell prints `Pico W ready at http://192.168.x.y`.
5. On the phone (Termux):

   ```sh
   curl "http://192.168.x.y/led?on=1"      # LED on!
   cd projects/dashboard
   PICO_URL=http://192.168.x.y python server.py
   ```

After that, the Pico can run from any USB charger, and even from the phone
itself through a USB-C to micro-USB OTG cable.

## Wiring an external LED

```
GP15 ──[330Ω]──▶|── GND
             (long leg)
```

Then change `led = Pin("LED", Pin.OUT)` to `led = Pin(15, Pin.OUT)`.

## Next steps

- Swap the LED for a relay module to switch a real lamp. Stick to low-voltage
  or pre-built smart relays unless you know mains wiring.
- Add a `/temp` route that returns the Pico's internal temperature
  (`machine.ADC(4)`), and graph it on the dashboard.
- Use the phone's accelerometer to drive a servo on the Pico, so that
  tilting the phone steers it.
