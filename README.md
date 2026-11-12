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

- **PipAI** keeps improving: GitHub retrains its brain and voice every night from where it left off (keeping a new version only if it tests better), Pip also learns on the board from its own life, and it downloads new versions over Wi-Fi by itself once a day. Tap BOOT to drop a snack, PWR to pet it. With a microSD card it keeps a diary (/pip/diary.csv).
- **PipAI and Bloop**: put Pip's board next to Bloop's (the pet from [esp32-s3-touch-lcd-3.5c](https://github.com/atrociouslyterrific/esp32-s3-touch-lcd-3.5c)) and they visit each other, one room at a time: Pip leaves its room and appears in Bloop's on Bloop's screen, then they both come over to Pip's room here, taking turns. While Pip is in Bloop's room it feels what happens there (the room being shaken or tipped, bumps, zero-g, lights out, playing with Bloop's toy): its real feelings change according to its personality. They talk to each other while they're together: what Bloop says shows in a bubble over Bloop, and Pip answers in its own voice. Move the boards apart and they go home. They find each other by radio (ESP-NOW), no setup needed.
- **PipAI**: an autonomous pet with a real neural-network brain. Every 3 minutes it senses temperature, humidity, time, battery and your pats, and its network (trained with reinforcement learning on GitHub) picks what to do. Each Pip is born with a random personality. Watch it at http://pip.local. See `training/` and `training/personality_report.md`.

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
