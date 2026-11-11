// EpaperHello — first screen sketch for the Waveshare ESP32-S3-ePaper-1.54
//
// Shows a big "Hello!" plus the room temperature and humidity from the
// onboard SHTC3 sensor. Updates every 30 seconds.
//
// Needs one library: GxEPD2 (by Jean-Marc Zingg). Install it from
// Tools -> Manage Libraries; say "Install All" so Adafruit GFX comes too.
//
// Pin numbers come from Waveshare's own example code (user_config.h).

#include <SPI.h>
#include <Wire.h>
#include <GxEPD2_BW.h>
#include <Fonts/FreeSansBold24pt7b.h>
#include <Fonts/FreeSans12pt7b.h>

// ---- Board pins ----
const int EPD_PWR  = 6;   // screen power switch (LOW = on)
const int EPD_BUSY = 8;
const int EPD_RST  = 9;
const int EPD_DC   = 10;
const int EPD_CS   = 11;
const int EPD_SCK  = 12;
const int EPD_MOSI = 13;
const int VBAT_PWR = 17;  // keeps the board on when running from battery (HIGH = stay on)
const int I2C_SDA  = 47;
const int I2C_SCL  = 48;
const uint8_t SHTC3_ADDR = 0x70;

// ---- Text you can change ----
const char *GREETING = "Hello!";
const unsigned long UPDATE_EVERY_MS = 30 * 1000;  // 30 seconds

// 1.54" 200x200 black/white panel (SSD1681 controller)
GxEPD2_BW<GxEPD2_154_D67, GxEPD2_154_D67::HEIGHT>
    display(GxEPD2_154_D67(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

int updateCount = 0;

// Write a 16-bit command to the SHTC3 sensor.
bool shtc3Command(uint16_t cmd) {
  Wire.beginTransmission(SHTC3_ADDR);
  Wire.write(cmd >> 8);
  Wire.write(cmd & 0xFF);
  return Wire.endTransmission() == 0;
}

// Read temperature (°C) and humidity (%). Returns false if the sensor didn't answer.
bool readSHTC3(float &tempC, float &humidity) {
  if (!shtc3Command(0x3517)) return false;  // wake up
  delay(1);
  if (!shtc3Command(0x7866)) return false;  // measure, temperature first
  delay(20);
  if (Wire.requestFrom(SHTC3_ADDR, (uint8_t)6) != 6) return false;
  uint16_t rawT = (Wire.read() << 8) | Wire.read(); Wire.read();  // skip checksum
  uint16_t rawH = (Wire.read() << 8) | Wire.read(); Wire.read();
  shtc3Command(0xB098);                     // back to sleep
  tempC    = -45.0f + 175.0f * rawT / 65536.0f;
  humidity = 100.0f * rawH / 65536.0f;
  return true;
}

// Print text centred horizontally at height y.
void printCentered(const char *text, int y) {
  int16_t x1, y1;
  uint16_t w, h;
  display.getTextBounds(text, 0, y, &x1, &y1, &w, &h);
  display.setCursor((display.width() - w) / 2 - x1, y);
  display.print(text);
}

void drawScreen() {
  float tempC = 0, humidity = 0;
  bool ok = readSHTC3(tempC, humidity);

  char line1[24], line2[24], line3[24];
  if (ok) {
    snprintf(line1, sizeof(line1), "%.1f C", tempC);
    snprintf(line2, sizeof(line2), "%.0f %% humidity", humidity);
  } else {
    snprintf(line1, sizeof(line1), "no sensor");
    snprintf(line2, sizeof(line2), " ");
  }
  snprintf(line3, sizeof(line3), "update #%d", ++updateCount);

  Serial.printf("Update %d: %s, %s\n", updateCount, line1, line2);

  // Do a full (flashing) refresh every 10th time to clear ghosting,
  // and a quick partial refresh the rest of the time.
  if (updateCount % 10 == 1) {
    display.setFullWindow();
  } else {
    display.setPartialWindow(0, 0, display.width(), display.height());
  }

  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    display.setFont(&FreeSansBold24pt7b);
    printCentered(GREETING, 60);

    display.drawLine(20, 80, 180, 80, GxEPD_BLACK);

    display.setFont(&FreeSans12pt7b);
    printCentered(line1, 115);
    printCentered(line2, 145);
    printCentered(line3, 185);
  } while (display.nextPage());

  display.hibernate();  // screen keeps the picture with no power
}

void setup() {
  // Keep the board powered on battery, and switch the screen's power on.
  pinMode(VBAT_PWR, OUTPUT);
  digitalWrite(VBAT_PWR, HIGH);
  pinMode(EPD_PWR, OUTPUT);
  digitalWrite(EPD_PWR, LOW);
  delay(100);

  Serial.begin(115200);
  delay(500);
  Serial.println("EpaperHello starting");

  Wire.begin(I2C_SDA, I2C_SCL);

  SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
  display.init(115200, true, 2, false);
  display.setRotation(0);  // try 1, 2 or 3 if the text is sideways or upside down

  drawScreen();
}

void loop() {
  delay(UPDATE_EVERY_MS);
  drawScreen();
}
