# ESP32-S3 e-paper projects

Sketches for the Waveshare ESP32-S3-ePaper-1.54 (200×200 black/white e-paper).

GitHub compiles every sketch on each push (see the **Actions** tab) and puts the finished program files on the **latest** release page, so nothing needs compiling on your Mac.

## Putting a program on the board (no Arduino IDE needed)

1. Download `EpaperPet.bin` (or `EpaperHello.bin`) from the repo's **Releases → latest** page.
2. In **Chrome**, open https://espressif.github.io/esptool-js/
3. Plug in the board, click **Connect**, and pick the `usbmodem` port.
4. Set **Flash Address** to `0x0`, choose the `.bin` file, click **Program**.
5. When it says it's done, unplug and replug the board.

## Sketches

- **EpaperHello**: shows "Hello!" plus the temperature and humidity from the onboard sensor, updating every 30 seconds.
- **EpaperPet**: a digital pet named Pip. BOOT moves between FEED / PLAY / SLEEP, PWR picks one. Keep its food, fun and energy bars up; its stats are saved when unplugged. First start: join the **Pip-Setup** Wi-Fi with your phone and pick your home network. Then open http://pip.local on your phone to play. Hold BOOT 5 s to forget Wi-Fi.

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
