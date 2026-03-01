/**
 * VRC Facial Tracker - WiFi Manager Implementation
 *
 * Uses Preferences (NVS) to persist WiFi credentials.
 * Falls back to a captive-portal AP if no stored/compiled creds work.
 */

#include "wifi_manager.h"
#include "config.h"

// Only compile when in STREAM mode (AP portal makes most sense here,
// but it's useful for every mode).
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <DNSServer.h>

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------
static Preferences s_prefs;
static WebServer  *s_portal = nullptr;
static DNSServer  *s_dns    = nullptr;

static bool s_portal_active   = false;
static bool s_connected       = false;
static bool s_credentials_set = false;

static String s_ssid;
static String s_pass;
static String s_ip_str;

static unsigned long s_reconnect_ts = 0;
static const unsigned long RECONNECT_INTERVAL_MS = 15000;

static unsigned long s_last_led_toggle = 0;
static bool s_led_state = false;

// AP settings
static const char *AP_PREFIX = "VRC-Tracker-";
static const int   AP_CHANNEL = 6;
static const IPAddress AP_IP(192, 168, 4, 1);
static const IPAddress AP_GW(192, 168, 4, 1);
static const IPAddress AP_MASK(255, 255, 255, 0);

// ---------------------------------------------------------------------------
// LED helpers
// ---------------------------------------------------------------------------
static void led_on()  { digitalWrite(WIFI_STATUS_LED_PIN, HIGH); }
static void led_off() { digitalWrite(WIFI_STATUS_LED_PIN, LOW); }

static void led_blink_fast() {
    unsigned long now = millis();
    if (now - s_last_led_toggle >= 150) {
        s_last_led_toggle = now;
        s_led_state = !s_led_state;
        digitalWrite(WIFI_STATUS_LED_PIN, s_led_state ? HIGH : LOW);
    }
}

static void led_blink_slow() {
    unsigned long now = millis();
    if (now - s_last_led_toggle >= WIFI_LED_BLINK_INTERVAL_MS) {
        s_last_led_toggle = now;
        s_led_state = !s_led_state;
        digitalWrite(WIFI_STATUS_LED_PIN, s_led_state ? HIGH : LOW);
    }
}

// ---------------------------------------------------------------------------
// NVS credential storage
// ---------------------------------------------------------------------------
static void save_credentials(const String &ssid, const String &pass) {
    s_prefs.begin("wifi", false);
    s_prefs.putString("ssid", ssid);
    s_prefs.putString("pass", pass);
    s_prefs.end();
    Serial.printf("[WiFi] Credentials saved (SSID: %s)\n", ssid.c_str());
}

static bool load_credentials(String &ssid, String &pass) {
    s_prefs.begin("wifi", true);
    ssid = s_prefs.getString("ssid", "");
    pass = s_prefs.getString("pass", "");
    s_prefs.end();
    return ssid.length() > 0;
}

// ---------------------------------------------------------------------------
// Try connecting to STA mode
// ---------------------------------------------------------------------------
static bool try_connect(const String &ssid, const String &pass,
                        int timeout_s = 15) {
    if (ssid.length() == 0) return false;

    Serial.printf("[WiFi] Connecting to '%s' ...", ssid.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), pass.c_str());

    for (int i = 0; i < timeout_s * 2; i++) {
        led_blink_slow();
        delay(500);
        Serial.print(".");
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println(" OK");
            s_ip_str = WiFi.localIP().toString();
            Serial.printf("[WiFi] IP: %s\n", s_ip_str.c_str());
            led_on();
            return true;
        }
    }
    Serial.println(" FAILED");
    WiFi.disconnect();
    return false;
}

// ---------------------------------------------------------------------------
// Portal HTML
// ---------------------------------------------------------------------------
static const char PORTAL_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VRC Tracker WiFi Setup</title>
<style>
  body{font-family:system-ui,sans-serif;background:#111;color:#eee;
       display:flex;justify-content:center;padding:2em}
  .card{background:#1a1a2e;border-radius:12px;padding:2em;max-width:360px;width:100%}
  h1{margin:0 0 .5em;font-size:1.4em;color:#4af}
  p{color:#aaa;font-size:0.9em}
  label{display:block;margin:1em 0 .3em;font-size:0.85em;color:#ccc}
  input{width:100%;padding:.6em;border:1px solid #333;border-radius:6px;
        background:#222;color:#eee;box-sizing:border-box;font-size:1em}
  button{width:100%;padding:.7em;margin-top:1.5em;border:none;border-radius:6px;
         background:#4af;color:#111;font-size:1em;font-weight:600;cursor:pointer}
  button:hover{background:#5bf}
  .info{margin-top:1em;font-size:0.8em;color:#888}
  #msg{color:#f44;margin-top:.5em;font-size:0.85em}
  #scan{margin:1em 0;max-height:120px;overflow-y:auto}
  .net{padding:4px 8px;cursor:pointer;border-radius:4px}
  .net:hover{background:#333}
</style>
</head>
<body>
<div class="card">
  <h1>&#128225; VRC Facial Tracker</h1>
  <p>WiFi Setup — Enter your network credentials.</p>
  <div id="scan"></div>
  <form method="POST" action="/save">
    <label for="ssid">WiFi SSID</label>
    <input id="ssid" name="ssid" required autofocus>
    <label for="pass">Password</label>
    <input id="pass" name="pass" type="password">
    <button type="submit">Connect</button>
  </form>
  <div id="msg"></div>
  <p class="info">After connecting, the tracker will reboot and join your network.
     The stream URL will be printed on the Serial monitor.</p>
</div>
<script>
fetch('/scan').then(r=>r.json()).then(nets=>{
  let h='<p style="font-size:0.8em;color:#888">Available networks:</p>';
  nets.forEach(n=>{
    h+='<div class="net" onclick="document.getElementById(\'ssid\').value=\''+n.s+'\'">'+
       n.s+' ('+n.r+'dBm)</div>';
  });
  document.getElementById('scan').innerHTML=h;
}).catch(()=>{});
</script>
</body>
</html>
)rawliteral";

// ---------------------------------------------------------------------------
// Portal handlers
// ---------------------------------------------------------------------------
static void handle_portal_root() {
    s_portal->send(200, "text/html", PORTAL_HTML);
}

static void handle_portal_scan() {
    int n = WiFi.scanNetworks();
    String json = "[";
    for (int i = 0; i < n && i < 15; i++) {
        if (i) json += ",";
        json += "{\"s\":\"" + WiFi.SSID(i) + "\",\"r\":" + String(WiFi.RSSI(i)) + "}";
    }
    json += "]";
    WiFi.scanDelete();
    s_portal->send(200, "application/json", json);
}

static void handle_portal_save() {
    String ssid = s_portal->arg("ssid");
    String pass = s_portal->arg("pass");

    if (ssid.length() == 0) {
        s_portal->send(400, "text/html",
            "<html><body style='background:#111;color:#f44;padding:2em'>"
            "<h2>SSID is required.</h2>"
            "<a href='/' style='color:#4af'>Back</a></body></html>");
        return;
    }

    save_credentials(ssid, pass);

    s_portal->send(200, "text/html",
        "<html><body style='background:#111;color:#4af;padding:2em;font-family:system-ui'>"
        "<h2>&#10004; Saved!</h2>"
        "<p>Rebooting to connect to <b>" + ssid + "</b>...</p>"
        "<p>Check Serial monitor for the new IP address.</p>"
        "</body></html>");

    delay(2000);
    ESP.restart();
}

// Called for any URL not matched — redirect to portal (captive portal)
static void handle_portal_not_found() {
    s_portal->sendHeader("Location", "http://192.168.4.1/", true);
    s_portal->send(302, "text/plain", "");
}

// ---------------------------------------------------------------------------
// Start AP + captive portal
// ---------------------------------------------------------------------------
static void start_portal() {
    // Generate unique AP name from MAC
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char ap_name[32];
    snprintf(ap_name, sizeof(ap_name), "%s%02X%02X", AP_PREFIX, mac[4], mac[5]);

    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(AP_IP, AP_GW, AP_MASK);
    WiFi.softAP(ap_name, nullptr, AP_CHANNEL); // open network

    s_ip_str = WiFi.softAPIP().toString();
    Serial.printf("[WiFi] AP mode: SSID=%s  IP=%s\n", ap_name, s_ip_str.c_str());
    Serial.println("[WiFi] Connect to this AP and open http://192.168.4.1");

    // DNS server — redirect all DNS queries to us (captive portal)
    s_dns = new DNSServer();
    s_dns->start(53, "*", AP_IP);

    // Web server
    s_portal = new WebServer(80);
    s_portal->on("/",     HTTP_GET,  handle_portal_root);
    s_portal->on("/scan", HTTP_GET,  handle_portal_scan);
    s_portal->on("/save", HTTP_POST, handle_portal_save);
    s_portal->onNotFound(handle_portal_not_found);
    s_portal->begin();

    s_portal_active = true;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
bool wifi_manager_init() {
    pinMode(WIFI_STATUS_LED_PIN, OUTPUT);
    led_off();

    // 1) Try stored credentials
    String stored_ssid, stored_pass;
    if (load_credentials(stored_ssid, stored_pass)) {
        Serial.println("[WiFi] Found stored credentials");
        if (try_connect(stored_ssid, stored_pass)) {
            s_ssid = stored_ssid;
            s_pass = stored_pass;
            s_connected = true;
            return true;
        }
    }

    // 2) Try compile-time credentials (if set)
    String compile_ssid = WIFI_SSID;
    String compile_pass = WIFI_PASSWORD;
    if (compile_ssid.length() > 0 &&
        compile_ssid != "YOUR_WIFI_SSID") {
        Serial.println("[WiFi] Trying compile-time credentials");
        if (try_connect(compile_ssid, compile_pass)) {
            save_credentials(compile_ssid, compile_pass);
            s_ssid = compile_ssid;
            s_pass = compile_pass;
            s_connected = true;
            return true;
        }
    }

    // 3) No working credentials — start AP portal
    Serial.println("[WiFi] No working credentials. Starting AP portal...");
    start_portal();
    return false;
}

void wifi_manager_loop() {
    if (s_portal_active) {
        // Handle portal requests
        s_dns->processNextRequest();
        s_portal->handleClient();
        led_blink_fast();   // fast blink = AP mode
        return;
    }

    // STA mode: reconnect if dropped
    if (WiFi.status() != WL_CONNECTED) {
        led_blink_slow();
        unsigned long now = millis();
        if (now - s_reconnect_ts > RECONNECT_INTERVAL_MS) {
            s_reconnect_ts = now;
            Serial.println("[WiFi] Reconnecting...");
            WiFi.disconnect();
            WiFi.begin(s_ssid.c_str(), s_pass.c_str());
        }
        s_connected = false;
    } else {
        if (!s_connected) {
            s_ip_str = WiFi.localIP().toString();
            Serial.printf("[WiFi] Reconnected! IP: %s\n", s_ip_str.c_str());
            s_connected = true;
        }
        led_on();
    }
}

void wifi_manager_reset() {
    s_prefs.begin("wifi", false);
    s_prefs.clear();
    s_prefs.end();
    Serial.println("[WiFi] Stored credentials cleared.");
}

bool wifi_manager_is_portal_active() {
    return s_portal_active;
}

const char* wifi_manager_get_ip() {
    static char buf[16];
    s_ip_str.toCharArray(buf, sizeof(buf));
    return buf;
}
