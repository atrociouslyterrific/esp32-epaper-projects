# ESP32-S3 e-paper projects

Sketches for the Waveshare ESP32-S3-ePaper-1.54 (200×200 black/white e-paper).

GitHub compiles every sketch on each push (see the **Actions** tab), so errors show up before you upload.

## Sketches

- **EpaperHello**: shows "Hello!" plus the temperature and humidity from the onboard sensor, updating every 30 seconds.
- **EpaperPet**: a digital pet named Pip. BOOT moves between FEED / PLAY / SLEEP, PWR picks one. Keep its food, fun and energy bars up; its stats are saved when unplugged.

## Arduino IDE settings

- Board: **ESP32S3 Dev Module** (esp32 by Espressif, 3.3.0 or newer)
- USB CDC On Boot: **Enabled**
- Library: **GxEPD2** (install with Adafruit GFX when asked)

## Board pins (from Waveshare's example code)

| Function | GPIO |
|---|---|
| Screen power (LOW = on) | 6 |
| Screen BUSY / RST / DC / CS | 8 / 9 / 10 / 11 |
| Screen SCK / MOSI | 12 / 13 |
| Battery power hold (HIGH = stay on) | 17 |
| PWR button / BOOT button | 18 / 0 |
| I2C SDA / SCL (RTC 0x51, SHTC3 0x70) | 47 / 48 |
