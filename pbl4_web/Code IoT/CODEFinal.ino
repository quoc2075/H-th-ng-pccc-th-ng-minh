#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>  
#include <ESP32Servo.h>

// ---------- Cấu hình ----------
// WiFi
const char* ssid = "Không cho";
const char* password = "27052705";

bool wasFireActive = false ;

unsigned long lastFireTime = 0;
const unsigned long FIRE_TIMEOUT =5000;
// MQTT
 const char* mqtt_server = "172.20.10.7";
 const int mqtt_port = 1883;
 const char* mqtt_user = "";
 const char* mqtt_pass = "";
// MQTT TOPICS - CHUẨN HÓA THEO NODE-RED
// ====================================
// ESP32 GỬI LÊN (Publish)
const char* TOPIC_SENSORS = "pccc/esp32/sensors";   // Gửi JSON: {smoke, gas, relay1,relay2, timestamp}
const char* TOPIC_STATUS = "pccc/esp32/status";     // Gửi heartbeat

// ESP32 NHẬN VỀ (Subscribe)
const char* TOPIC_SERVO = "pccc/esp32/servo";       // Nhận: {servo_pan, servo_tilt, action}
const char* TOPIC_RELAY = "pccc/esp32/relay";  

     // Nhận: {relay2, duration}


// Chân kết nối
const int gasPin    = 32;
const int smokePin  = 33;
const int relayPin1 = 23; // Còi + đèn
const int relayPin2 = 22; // Bơm
const int buttonPin = 13; // Nút dừng khẩn cấp
const int PIN_SERVO_PAN  = 21; // pan khoogn tilt

// Ngưỡng
const int gas_threshold   = 1500;
const int smoke_threshold = 1500;

// ---------- Biến toàn cục ----------
WiFiClient espClient;
PubSubClient client(espClient);
Servo servoPan;
int servoPanAngle = 0;
int servoCurrentAngle = 0;
const int SERVO_HOME_ANGLE = 90;
int servoTargetAngle = 0;
bool servoLocked = false; // SON MOI THEM
// bool fireActive = false; 
const int SERVO_OFFSET = 0;           // ESP tự hiểu đang cháy hay không


// Timer biến (dùng millis thay cho delay)
unsigned long lastPublish = 0;
unsigned long lastReconnectAttempt = 0;
const unsigned long publishInterval = 1000; // 1 giây gửi 1 lần
const unsigned long reconnectInterval = 5000; // 5 giây thử kết nối lại 1 lần

bool relay2_remote_state = false;
bool relay1_remote_state = false; // Lưu trạng thái lệnh từ server
// relay1 có 2 chế độ: AUTO theo cảm biến hoặc MANUAL theo server
enum RelayMode { AUTO_MODE, MANUAL_MODE };
RelayMode relay1_mode = AUTO_MODE;

// ---------- Functions ----------

void setup_wifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  // Chỉ bắt đầu kết nối, không dùng while chờ đợi để tránh treo code
  WiFi.begin(ssid, password);
  // Serial.println("Dang ket noi Wifi...");
}

void updateServo() {
  static unsigned long lastServoUpdate = 0;
  const unsigned long servoInterval = 20; // 20ms mỗi bước
  
  unsigned long now = millis();
  if (now - lastServoUpdate < servoInterval) return;
  lastServoUpdate = now;
  
  // Nếu chưa đến góc mục tiêu
  if (servoCurrentAngle != servoTargetAngle) {
    // Di chuyển từ từ (1 độ mỗi bước)
    if (servoCurrentAngle < servoTargetAngle) {
      servoCurrentAngle++;
    } else {
      servoCurrentAngle--;
    }
servoPan.write(servoCurrentAngle);
// Debug mỗi 10 độ
    if (servoCurrentAngle % 10 == 0) {
      Serial.print("[SERVO] Moving to ");
      Serial.print(servoTargetAngle);
      Serial.print("°, current: ");
      Serial.println(servoCurrentAngle);
    }
  }
}

void reconnect_mqtt() {
  // Nếu đã kết nối rồi thì thoát ngay
  if (client.connected()) return;

  // Chỉ thử kết nối lại mỗi 5 giây (Non-blocking)
  unsigned long now = millis();
  if (now - lastReconnectAttempt > reconnectInterval) {
    lastReconnectAttempt = now;
    
    // Tạo ID ngẫu nhiên để tránh xung đột với ESP cũ
    String clientId = "ESP32_Client_";
    clientId += String(random(0xffff), HEX);

    if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
      // Serial.println("MQTT Connected!");
      client.subscribe(TOPIC_RELAY);
      client.subscribe(TOPIC_SERVO);
    } else {
      // Serial.print("MQTT failed, rc=");
      // Serial.println(client.state());
    }
  }
}
void checkAutoReset() {
  unsigned long now = millis();
  
  int gasValue = analogRead(gasPin);
  int smokeValue = analogRead(smokePin);
  bool currentFire = (gasValue >= gas_threshold || smokeValue >= smoke_threshold);

  // Nếu đang/đã có lửa và bơm đang tắt
  if (wasFireActive && !relay2_remote_state && !currentFire) {
    // Kiểm tra timeout (5 giây không có lửa)
    if (now - lastFireTime > FIRE_TIMEOUT) {
      // Tự động reset servo về 0 độ
      if (servoTargetAngle != SERVO_HOME_ANGLE && !servoLocked) {
        Serial.println("[AUTO-RESET] Fire timeout → Servo return home");
        servoTargetAngle = SERVO_HOME_ANGLE;
        servoLocked = true;
      }
      wasFireActive = false;  // Reset flag
    }
  }
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  String topicStr(topic);

  // =========================
  // RELAY
  // =========================
  if (topicStr == TOPIC_RELAY) {
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    String cmd2 = "", cmd1 = "";
    if (!error) {
      if (doc.containsKey("relay2")) {
        if (doc["relay2"].is<const char*>()) cmd2 = String(doc["relay2"].as<const char*>());
        else if (doc["relay2"].is<bool>())   cmd2 = doc["relay2"].as<bool>() ? "1" : "0";
        else if (doc["relay2"].is<int>())    cmd2 = String(doc["relay2"].as<int>());
      }
      if (doc.containsKey("relay1")) {
        if (doc["relay1"].is<const char*>()) cmd1 = String(doc["relay1"].as<const char*>());
        else if (doc["relay1"].is<bool>())   cmd1 = doc["relay1"].as<bool>() ? "1" : "0";
        else if (doc["relay1"].is<int>())    cmd1 = String(doc["relay1"].as<int>());
      }
    } else {
      for (unsigned int i = 0; i < length; i++) cmd2 += (char)payload[i];
    }

    cmd2.trim(); cmd2.toLowerCase();
    cmd1.trim(); cmd1.toLowerCase();

    if (cmd2.length() > 0) {
if (cmd2 == "fire" || cmd2 == "true" || cmd2 == "1" || cmd2 == "on") {
        relay2_remote_state = true;
        lastFireTime = millis();
        wasFireActive = true;
      } else if (cmd2 == "safe" || cmd2 == "false" || cmd2 == "0" || cmd2 == "off") {
        relay2_remote_state = false;
      }
      Serial.printf("[MQTT][RELAY2] %s\n", relay2_remote_state ? "ON" : "OFF");
    }

    if (cmd1.length() > 0) {
      if (cmd1 == "auto") {
        relay1_mode = AUTO_MODE;
        Serial.println("[MQTT][RELAY1] mode=AUTO");
      } else if (cmd1 == "true" || cmd1 == "1" || cmd1 == "on") {
        relay1_mode = MANUAL_MODE;
        relay1_remote_state = true;
        Serial.println("[MQTT][RELAY1] mode=MANUAL state=ON");
      } else if (cmd1 == "false" || cmd1 == "0" || cmd1 == "off") {
        relay1_mode = MANUAL_MODE;
        relay1_remote_state = false;
        Serial.println("[MQTT][RELAY1] mode=MANUAL state=OFF");
      }
    }
    return;
  }

  // =========================
  // SERVO
  // =========================
  if (topicStr == TOPIC_SERVO) {
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, payload, length)) return;

    if (doc.containsKey("servo_pan")) {
      int rawAngle = doc["servo_pan"];
      rawAngle = constrain(rawAngle, 0, 180);

      servoTargetAngle = rawAngle;     // offset = 0 rồi
      servoLocked = false;

      // lastFireTime = millis();
      // wasFireActive = true;

      Serial.printf("[SERVO] Target=%d\n", servoTargetAngle);
    }

    if (doc.containsKey("action")) {
      String action = doc["action"].as<String>();
      action.toLowerCase();

      if (action == "home" || action == "reset" || action == "return_home" || action == "return_to_default") {
        servoTargetAngle = SERVO_HOME_ANGLE;   // 90
        servoLocked = false;
        Serial.println("[SERVO] Action: return home(90)");
      }
    }
    return;
  }
}


// ---------- Setup ----------
void setup() {
  // Serial.begin(115200); // Bật lên để debug nếu cần


  Serial.begin(115200);
  delay(200);
servoPan.attach(PIN_SERVO_PAN);
  // Đồng bộ biến với vị trí home = 90
servoCurrentAngle = SERVO_HOME_ANGLE;
servoTargetAngle  = SERVO_HOME_ANGLE;

servoPan.write(servoCurrentAngle);

  pinMode(relayPin1, OUTPUT);
  pinMode(relayPin2, OUTPUT);
  
  // QUAN TRỌNG: Nút nhấn kích mức HIGH -> Dùng điện trở kéo xuống (PULLDOWN)
  // Trạng thái bình thường (không nhấn) = LOW. Nhấn = HIGH (3.3V)
  pinMode(buttonPin, INPUT_PULLDOWN); 

  // Trạng thái ban đầu: TẮT HẾT
  digitalWrite(relayPin1, LOW);
  digitalWrite(relayPin2, LOW);
  
  analogReadResolution(12);

  setup_wifi(); // Gọi lần đầu
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqtt_callback);

  randomSeed((uint32_t)ESP.getEfuseMac());

}

// ---------- Loop ----------
void loop() {
  // 1. QUẢN LÝ KẾT NỐI (Không chặn code chính)
if (WiFi.status() != WL_CONNECTED) {
// Nếu mất Wifi, thử kết nối lại (nhưng không dừng chương trình)
      static unsigned long lastWifiCheck = 0;
      if (millis() - lastWifiCheck > 5000) {
         lastWifiCheck = millis();
         WiFi.reconnect();
      }
  } else {
      // Có Wifi thì lo vụ MQTT
      reconnect_mqtt();
      client.loop();
  }

  // 2. ĐỌC CẢM BIẾN & NÚT NHẤN
  int gasValue = analogRead(gasPin);
  int smokeValue = analogRead(smokePin);
  int buttonState = digitalRead(buttonPin);
  bool currentFire = (gasValue >= gas_threshold || smokeValue >= smoke_threshold);
  if (currentFire || relay2_remote_state) {
  lastFireTime = millis();
  wasFireActive = true;
  }

  // BẬT TẮT RELAY 2//
  if (relay2_remote_state) {
    digitalWrite(relayPin2, HIGH);
  } else {
    digitalWrite(relayPin2, LOW);
  }

  // if (!relay2_remote_state && servoTargetAngle != 0 && !servoLocked) {
  // Serial.println("[SAFETY] Pump OFF → Servo reset to 0°");
  // servoTargetAngle = 0;
  // }

// Cập nhật servo
updateServo();
checkAutoReset();


  // 3. XỬ LÝ LOGIC ĐIỀU KHIỂN (Ưu tiên an toàn số 1)
  
  if (buttonState == HIGH) {
  // Emergency ưu tiên cao nhất: tắt relay1 bất kể mode gì
  digitalWrite(relayPin1, LOW);
} else {
  // Không emergency
  if (relay1_mode == MANUAL_MODE) {
    // server điều khiển
    digitalWrite(relayPin1, relay1_remote_state ? HIGH : LOW);
  } else {
    // AUTO theo cảm biến
    bool isDanger = (gasValue >= gas_threshold || smokeValue >= smoke_threshold);
    digitalWrite(relayPin1, isDanger ? HIGH : LOW);
  }
}


 
  // 4. GỬI DỮ LIỆU MQTT (Mỗi 1 giây)
unsigned long now = millis();
if (now - lastPublish >= publishInterval) {
    lastPublish = now;

    // Chỉ gửi khi có kết nối
    if (client.connected()) {
        // Tạo JSON gộp tất cả dữ liệu
        StaticJsonDocument<128> doc;
        doc["gas"] = gasValue;
        doc["smoke"] = smokeValue;
        doc["relay1"] = (digitalRead(relayPin1) == HIGH) ? 1 : 0;
        doc["relay1_mode"] = (relay1_mode == MANUAL_MODE) ? "manual" : "auto";

        doc["relay2"] = relay2_remote_state ? 1 : 0;
doc["servo_pan"] = servoCurrentAngle;
        doc["timestamp"] = now;

        char buffer[128];
        serializeJson(doc, buffer);

        client.publish(TOPIC_SENSORS, buffer);

        Serial.println("[MQTT] → " + String(buffer)); // Debug
    }
}

}