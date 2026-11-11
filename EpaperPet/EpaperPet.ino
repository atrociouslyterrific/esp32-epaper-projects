// EpaperPet — a little digital pet for the Waveshare ESP32-S3-ePaper-1.54
//
// Controls:
//   BOOT button -> move to the next menu option (FEED / PLAY / SLEEP)
//   PWR  button -> do the selected option (any button wakes a sleeping pet)
//
// The pet gets hungry, bored and tired over time. Keep its bars up!
// Its stats are saved, so it remembers everything after you unplug it.
// (Time is paused while the board is off.)
//
// Needs the GxEPD2 library (already installed for EpaperHello).

#include <SPI.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <GxEPD2_BW.h>

// ---- Wi-Fi (type your own details here in the Arduino IDE) ----
// Your network must be 2.4 GHz (the ESP32 can't join 5 GHz-only networks).
// Don't paste your real password back into GitHub.
const char *WIFI_NAME     = "your-wifi-name";
const char *WIFI_PASSWORD = "your-wifi-password";
const char *WEB_NAME      = "pip";  // phone address becomes http://pip.local

// ---- Board pins (from Waveshare's example code) ----
const int EPD_PWR  = 6;   // screen power (LOW = on)
const int EPD_BUSY = 8;
const int EPD_RST  = 9;
const int EPD_DC   = 10;
const int EPD_CS   = 11;
const int EPD_SCK  = 12;
const int EPD_MOSI = 13;
const int VBAT_PWR = 17;  // keep board on when on battery (HIGH = stay on)
const int BTN_BOOT = 0;   // pressed = LOW
const int BTN_PWR  = 18;  // pressed = LOW

// ---- Things you can change ----
const char *PET_NAME = "Pip";
const unsigned long TICK_MS = 60UL * 1000;  // stats change once a minute

GxEPD2_BW<GxEPD2_154_D67, GxEPD2_154_D67::HEIGHT>
    display(GxEPD2_154_D67(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));
Preferences prefs;

// ---- Pet state ----
int food   = 80;   // 0..100
int fun    = 80;   // 0..100
int energy = 80;   // 0..100
bool asleep = false;
unsigned long ageMinutes = 0;

enum Mood { HAPPY, OKAY, SAD, SLEEPING };
enum Action { FEED, PLAY, SLEEP, ACTION_COUNT };
const char *ACTION_NAMES[ACTION_COUNT] = {"FEED", "PLAY", "SLEEP"};
int selected = FEED;

char message[32] = "Hi! I'm new here.";
int frame = 0;               // makes the pet bounce a little each update
int redrawCount = 0;
unsigned long lastTick = 0;

int clampStat(int v) { return v < 0 ? 0 : (v > 100 ? 100 : v); }

// ---------- Saving ----------
void saveState() {
  prefs.putInt("food", food);
  prefs.putInt("fun", fun);
  prefs.putInt("energy", energy);
  prefs.putBool("asleep", asleep);
  prefs.putULong("age", ageMinutes);
}

void loadState() {
  food       = prefs.getInt("food", food);
  fun        = prefs.getInt("fun", fun);
  energy     = prefs.getInt("energy", energy);
  asleep     = prefs.getBool("asleep", false);
  ageMinutes = prefs.getULong("age", 0);
  if (ageMinutes > 0) snprintf(message, sizeof(message), "Welcome back!");
}

// ---------- Mood ----------
Mood currentMood() {
  if (asleep) return SLEEPING;
  int lowest = min(food, min(fun, energy));
  if (lowest < 25) return SAD;
  if (lowest < 55) return OKAY;
  return HAPPY;
}

// ---------- Drawing ----------
// Draw a curved mouth. curve > 0 = smile, curve < 0 = frown, 0 = flat.
void drawMouth(int cx, int cy, int halfWidth, int curve) {
  for (int t = 0; t <= 2; t++) {  // 3 pixels thick
    int prevX = cx - halfWidth;
    int prevY = cy + t;
    for (int x = -halfWidth + 1; x <= halfWidth; x++) {
      float k = 1.0f - (float)(x * x) / (halfWidth * halfWidth);  // 0 at ends, 1 in middle
      int y = cy + t + (int)(curve * k);
      display.drawLine(prevX, prevY, cx + x, y, GxEPD_BLACK);
      prevX = cx + x;
      prevY = y;
    }
  }
}

void drawPet(int cx, int cy, Mood mood) {
  const int r = 34;

  // Feet
  display.fillRoundRect(cx - 24, cy + r - 6, 16, 12, 5, GxEPD_BLACK);
  display.fillRoundRect(cx + 8,  cy + r - 6, 16, 12, 5, GxEPD_BLACK);

  // Body (thick outline)
  display.fillCircle(cx, cy, r, GxEPD_BLACK);
  display.fillCircle(cx, cy, r - 3, GxEPD_WHITE);

  // Little antenna sprout on top
  display.drawLine(cx, cy - r, cx + 4, cy - r - 12, GxEPD_BLACK);
  display.drawLine(cx + 1, cy - r, cx + 5, cy - r - 12, GxEPD_BLACK);
  display.fillCircle(cx + 6, cy - r - 14, 4, GxEPD_BLACK);

  int eyeY = cy - 6;
  int eyeL = cx - 12, eyeR = cx + 12;

  switch (mood) {
    case HAPPY:
      display.fillCircle(eyeL, eyeY, 6, GxEPD_BLACK);
      display.fillCircle(eyeR, eyeY, 6, GxEPD_BLACK);
      display.fillCircle(eyeL + 2, eyeY - 2, 2, GxEPD_WHITE);  // sparkle
      display.fillCircle(eyeR + 2, eyeY - 2, 2, GxEPD_WHITE);
      drawMouth(cx, cy + 10, 12, 7);
      // Blush
      display.drawCircle(cx - 24, cy + 8, 3, GxEPD_BLACK);
      display.drawCircle(cx + 24, cy + 8, 3, GxEPD_BLACK);
      break;

    case OKAY:
      display.fillCircle(eyeL, eyeY, 5, GxEPD_BLACK);
      display.fillCircle(eyeR, eyeY, 5, GxEPD_BLACK);
      drawMouth(cx, cy + 12, 9, 0);
      break;

    case SAD:
      display.fillCircle(eyeL, eyeY, 5, GxEPD_BLACK);
      display.fillCircle(eyeR, eyeY, 5, GxEPD_BLACK);
      // Worried eyebrows
      display.drawLine(eyeL - 7, eyeY - 12, eyeL + 5, eyeY - 8, GxEPD_BLACK);
      display.drawLine(eyeR + 7, eyeY - 12, eyeR - 5, eyeY - 8, GxEPD_BLACK);
      drawMouth(cx, cy + 18, 10, -6);
      // Tear
      display.fillTriangle(eyeR + 4, eyeY + 6, eyeR + 1, eyeY + 13, eyeR + 7, eyeY + 13, GxEPD_BLACK);
      display.fillCircle(eyeR + 4, eyeY + 14, 3, GxEPD_BLACK);
      break;

    case SLEEPING:
      // Closed eyes
      drawMouth(eyeL, eyeY, 6, 3);
      drawMouth(eyeR, eyeY, 6, 3);
      display.fillCircle(cx, cy + 14, 3, GxEPD_BLACK);  // small "o" mouth
      // Zzz
      display.setFont();
      display.setTextColor(GxEPD_BLACK);
      display.setTextSize(1);
      display.setCursor(cx + r + 2, cy - r + 6);  display.print("z");
      display.setTextSize(2);
      display.setCursor(cx + r + 8, cy - r - 12); display.print("Z");
      break;
  }
}

void drawMenu() {
  const int w = 200 / ACTION_COUNT;
  display.setFont();
  display.setTextSize(2);
  for (int i = 0; i < ACTION_COUNT; i++) {
    int x = i * w;
    bool isSel = (i == selected);
    if (isSel) display.fillRect(x + 1, 0, w - 2, 22, GxEPD_BLACK);
    else       display.drawRect(x + 1, 0, w - 2, 22, GxEPD_BLACK);
    display.setTextColor(isSel ? GxEPD_WHITE : GxEPD_BLACK);
    int textW = strlen(ACTION_NAMES[i]) * 12;
    display.setCursor(x + (w - textW) / 2, 4);
    display.print(ACTION_NAMES[i]);
  }
}

void drawBar(int y, const char *label, int value) {
  display.setFont();
  display.setTextSize(1);
  display.setTextColor(GxEPD_BLACK);
  display.setCursor(6, y + 1);
  display.print(label);
  const int bx = 56, bw = 136, bh = 10;
  display.drawRect(bx, y, bw, bh, GxEPD_BLACK);
  display.fillRect(bx + 2, y + 2, (bw - 4) * value / 100, bh - 4, GxEPD_BLACK);
}

void drawCenteredSmall(const char *text, int y) {
  display.setFont();
  display.setTextSize(1);
  display.setTextColor(GxEPD_BLACK);
  int w = strlen(text) * 6;
  display.setCursor((200 - w) / 2, y);
  display.print(text);
}

void drawScreen() {
  redrawCount++;
  // Full (flashing) refresh now and then to clean up ghosting.
  if (redrawCount % 15 == 1) display.setFullWindow();
  else display.setPartialWindow(0, 0, display.width(), display.height());

  Mood mood = currentMood();
  int bounce = (mood == SLEEPING) ? 0 : ((frame % 2) ? -3 : 3);

  char header[32];
  unsigned long days = ageMinutes / (60 * 24);
  unsigned long hours = (ageMinutes / 60) % 24;
  snprintf(header, sizeof(header), "%s  age %lud %luh", PET_NAME, days, hours);

  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    drawMenu();
    drawCenteredSmall(header, 27);
    drawPet(100 + bounce, 88, mood);
    drawCenteredSmall(message, 140);
    drawBar(156, "FOOD", food);
    drawBar(171, "FUN", fun);
    drawBar(186, "ENERGY", energy);
  } while (display.nextPage());

  display.hibernate();
  Serial.printf("food %d fun %d energy %d asleep %d | %s\n", food, fun, energy, asleep, message);
}

// ---------- Game logic ----------
void doAction(int action) {
  switch (action) {
    case FEED:
      if (food >= 95) {
        snprintf(message, sizeof(message), "I'm too full!");
        fun = clampStat(fun - 5);
      } else {
        food = clampStat(food + 25);
        snprintf(message, sizeof(message), "Yum! Thank you!");
      }
      break;

    case PLAY:
      if (energy < 15) {
        snprintf(message, sizeof(message), "Too tired to play...");
      } else {
        fun = clampStat(fun + 20);
        energy = clampStat(energy - 10);
        food = clampStat(food - 5);
        snprintf(message, sizeof(message), "Wheee! That was fun!");
      }
      break;

    case SLEEP:
      asleep = true;
      snprintf(message, sizeof(message), "Goodnight...");
      break;
  }
  saveState();
}

// Called once a minute.
void tick() {
  ageMinutes++;
  if (asleep) {
    energy = clampStat(energy + 4);
    food = clampStat(food - 1);
    if (energy >= 100) {
      asleep = false;
      snprintf(message, sizeof(message), "Good morning!");
    }
  } else {
    food = clampStat(food - 2);
    fun = clampStat(fun - 2);
    energy = clampStat(energy - 1);
    if (food < 25)        snprintf(message, sizeof(message), "I'm hungry!");
    else if (fun < 25)    snprintf(message, sizeof(message), "I'm bored...");
    else if (energy < 25) snprintf(message, sizeof(message), "I'm sleepy...");
  }
  saveState();
}

// ---------- Phone web page ----------
WebServer server(80);
bool needRedraw = false;
bool wifiWasConnected = false;
unsigned long lastWifiAttempt = 0;

const char PAGE_HTML[] PROGMEM = R"rawliteral(<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pet</title>
<style>
  body{font-family:-apple-system,system-ui,sans-serif;max-width:420px;margin:0 auto;padding:16px;background:#f4f1ea;color:#222}
  h1{margin:4px 0;font-size:28px;text-align:center}
  #msg{text-align:center;min-height:1.4em;margin:8px 0 16px;font-style:italic}
  .row{display:flex;align-items:center;gap:10px;margin:10px 0}
  .row span{width:70px;font-weight:600}
  .bar{flex:1;height:18px;border:2px solid #222;border-radius:6px;overflow:hidden;background:#fff}
  .fill{height:100%;background:#222;transition:width .4s}
  .btns{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}
  button{font-size:20px;padding:16px;border:2px solid #222;border-radius:12px;background:#fff}
  button:active{background:#222;color:#fff}
  #face{font-size:56px;text-align:center}
  #age{text-align:center;color:#666}
</style></head><body>
<div id="face">( o_o )</div>
<h1 id="name">...</h1>
<div id="age"></div>
<div id="msg"></div>
<div class="row"><span>Food</span><div class="bar"><div class="fill" id="food"></div></div></div>
<div class="row"><span>Fun</span><div class="bar"><div class="fill" id="fun"></div></div></div>
<div class="row"><span>Energy</span><div class="bar"><div class="fill" id="energy"></div></div></div>
<div class="btns">
  <button onclick="act('feed')">Feed</button>
  <button onclick="act('play')">Play</button>
  <button onclick="act('sleep')">Sleep</button>
  <button onclick="act('wake')">Wake</button>
</div>
<script>
const faces={happy:'( ^o^ )',okay:'( o_o )',sad:'( T_T )',sleeping:'( -_- ) zZ'};
function show(s){
  document.getElementById('name').textContent=s.name;
  document.getElementById('age').textContent='age '+s.days+'d '+s.hours+'h';
  document.getElementById('msg').textContent=s.message;
  document.getElementById('face').textContent=faces[s.mood]||'';
  for(const k of ['food','fun','energy'])document.getElementById(k).style.width=s[k]+'%';
}
function load(){fetch('/state').then(r=>r.json()).then(show).catch(()=>{});}
function act(a){fetch('/do?a='+a).then(r=>r.json()).then(show);}
load();setInterval(load,5000);
</script></body></html>)rawliteral";

const char *moodName(Mood m) {
  switch (m) {
    case HAPPY: return "happy";
    case OKAY:  return "okay";
    case SAD:   return "sad";
    default:    return "sleeping";
  }
}

void sendState() {
  char json[256];
  snprintf(json, sizeof(json),
           "{\"name\":\"%s\",\"food\":%d,\"fun\":%d,\"energy\":%d,\"asleep\":%s,"
           "\"mood\":\"%s\",\"message\":\"%s\",\"days\":%lu,\"hours\":%lu}",
           PET_NAME, food, fun, energy, asleep ? "true" : "false",
           moodName(currentMood()), message,
           ageMinutes / (60 * 24), (ageMinutes / 60) % 24);
  server.send(200, "application/json", json);
}

void handleAction() {
  String a = server.arg("a");
  if (a == "wake") {
    if (asleep) {
      asleep = false;
      snprintf(message, sizeof(message), "Huh? I'm awake!");
      saveState();
    }
  } else {
    if (asleep) {  // any action wakes the pet first, same as the buttons
      asleep = false;
      snprintf(message, sizeof(message), "Huh? I'm awake!");
      saveState();
    } else if (a == "feed")  doAction(FEED);
    else if (a == "play")    doAction(PLAY);
    else if (a == "sleep")   doAction(SLEEP);
  }
  needRedraw = true;  // the screen updates right after we reply to the phone
  sendState();
}

void startWifi() {
  if (strcmp(WIFI_NAME, "your-wifi-name") == 0) {
    Serial.println("Wi-Fi not set up: edit WIFI_NAME and WIFI_PASSWORD at the top.");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(WEB_NAME);
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
  lastWifiAttempt = millis();
  Serial.printf("Connecting to Wi-Fi \"%s\"...\n", WIFI_NAME);

  server.on("/", []() { server.send_P(200, "text/html", PAGE_HTML); });
  server.on("/state", sendState);
  server.on("/do", handleAction);
  server.begin();
}

// Notice when Wi-Fi connects or drops, and retry if needed.
void checkWifi() {
  if (strcmp(WIFI_NAME, "your-wifi-name") == 0) return;
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wifiWasConnected) {
    MDNS.begin(WEB_NAME);
    MDNS.addService("http", "tcp", 80);
    String ip = WiFi.localIP().toString();
    Serial.printf("Wi-Fi connected! Open http://%s.local or http://%s\n", WEB_NAME, ip.c_str());
    snprintf(message, sizeof(message), "WiFi: %s", ip.c_str());
    needRedraw = true;
  } else if (!connected && wifiWasConnected) {
    Serial.println("Wi-Fi lost, reconnecting...");
    MDNS.end();
  }
  if (!connected && millis() - lastWifiAttempt > 30000) {
    WiFi.reconnect();
    lastWifiAttempt = millis();
  }
  wifiWasConnected = connected;
}

// Returns true once per press (on the moment it goes down).
bool pressed(int pin, bool &wasDown) {
  bool down = digitalRead(pin) == LOW;
  bool justPressed = down && !wasDown;
  wasDown = down;
  return justPressed;
}

// ---------- Setup & loop ----------
void setup() {
  pinMode(VBAT_PWR, OUTPUT);
  digitalWrite(VBAT_PWR, HIGH);
  pinMode(EPD_PWR, OUTPUT);
  digitalWrite(EPD_PWR, LOW);
  pinMode(BTN_BOOT, INPUT_PULLUP);
  pinMode(BTN_PWR, INPUT_PULLUP);
  delay(100);

  Serial.begin(115200);
  delay(300);
  Serial.println("EpaperPet starting");

  prefs.begin("pet", false);
  loadState();

  SPI.begin(EPD_SCK, -1, EPD_MOSI, EPD_CS);
  display.init(115200, true, 2, false);
  display.setRotation(0);

  drawScreen();
  lastTick = millis();

  startWifi();
}

bool bootWasDown = true;  // start "down" so a held button at power-on is ignored
bool pwrWasDown = true;

void loop() {
  bool changed = false;

  if (pressed(BTN_BOOT, bootWasDown)) {
    if (asleep) {
      asleep = false;
      snprintf(message, sizeof(message), "Huh? I'm awake!");
      saveState();
    } else {
      selected = (selected + 1) % ACTION_COUNT;
    }
    changed = true;
  }

  if (pressed(BTN_PWR, pwrWasDown)) {
    if (asleep) {
      asleep = false;
      snprintf(message, sizeof(message), "Huh? I'm awake!");
      saveState();
    } else {
      doAction(selected);
    }
    changed = true;
  }

  if (millis() - lastTick >= TICK_MS) {
    lastTick += TICK_MS;
    tick();
    frame++;
    changed = true;
  }

  server.handleClient();
  checkWifi();
  if (needRedraw) {
    needRedraw = false;
    changed = true;
  }

  if (changed) drawScreen();
  delay(20);  // simple debounce
}
