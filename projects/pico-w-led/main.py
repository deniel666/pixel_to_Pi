# MicroPython for Raspberry Pi Pico W: a tiny HTTP server the phone can call.
#   GET /led?on=1   -> LED on
#   GET /led?on=0   -> LED off
#   GET /           -> {"on": true|false}
# Copy to the Pico as main.py (Thonny: File > Save as > Raspberry Pi Pico).
import network
import socket
import time
from machine import Pin

WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

# "LED" is the Pico W's onboard LED. For an external LED, use Pin(15, Pin.OUT)
# and wire GP15 -> 330Ω resistor -> LED long leg, LED short leg -> GND.
led = Pin("LED", Pin.OUT)


def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(30):
        if wlan.isconnected():
            break
        led.toggle()  # blink while connecting
        time.sleep(0.5)
    if not wlan.isconnected():
        raise RuntimeError("Wi-Fi connect failed; check SSID/password (2.4 GHz only)")
    led.off()
    ip = wlan.ifconfig()[0]
    print("Pico W ready at http://%s" % ip)
    return ip


def serve():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(2)
    while True:
        conn, _ = s.accept()
        try:
            request = conn.recv(1024).decode()
            path = request.split(" ")[1] if " " in request else "/"
            if path.startswith("/led"):
                if "on=1" in path:
                    led.on()
                elif "on=0" in path:
                    led.off()
            body = '{"on": %s}' % ("true" if led.value() else "false")
            conn.send("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + body)
        except OSError:
            pass
        finally:
            conn.close()


connect()
serve()
