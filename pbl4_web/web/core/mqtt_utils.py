# import sys
# import os

# print("=== MQTT UTILS DEBUG ===")
# print("Python path:", sys.executable)
# print("Working directory:", os.getcwd())
# print("MQTT_BROKER:", "127.0.0.1")
# print("MQTT_PORT:", 1883)

# IS_RUNSERVER = "runserver" in sys.argv
# print("Is runserver:", IS_RUNSERVER)
# print("=========================")

# import json
# import logging
# import time
# from typing import Callable
# import paho.mqtt.client as mqtt

# logger = logging.getLogger(__name__)

# # ====================================
# # MQTT CONFIG - FIXED
# # ====================================
# MQTT_BROKER = "127.0.0.1"  # ĐẢM BẢO ĐÂY LÀ 127.0.0.1
# MQTT_PORT = 1883
# MQTT_USERNAME = ""
# MQTT_PASSWORD = ""
# MQTT_KEEPALIVE = 60

# # ====================================
# # MQTT TOPICS - CHUẨN HÓA THEO NODE-RED
# # ====================================
# TOPICS = {
#     # === ESP32 GỬI LÊN (Django Subscribe) ===
#     'ESP32_SENSORS': 'pccc/esp32/sensors',
#     'ESP32_STATUS': 'pccc/esp32/status',
    
#     # === AI GỬI LÊN (Django Subscribe) ===
#     'AI_DETECTION': 'pccc/ai/detection',
    
#     # === DJANGO GỬI ĐẾN ESP32 (Django Publish) ===
#     'CMD_SERVO': 'pccc/esp32/servo',
#     'CMD_RELAY': 'pccc/esp32/relay',
    
#     # === DJANGO GỬI ĐẾN NODE-RED (Django Publish) ===
#     'DJANGO_COMMAND': 'pccc/django/command',
#     'DJANGO_AI_RESULT': 'pccc/django/ai',
    
#     # === NODE-RED GỬI VỀ DJANGO (Django Subscribe) ===
#     'NODERED_ALERT': 'pccc/nodered/alert',
#     'NODERED_STATUS': 'pccc/nodered/status',
    
#     # === SYSTEM ===
#     'SYSTEM_STATUS': 'pccc/system/status',
#     'ALERT': 'pccc/alert',                      # Alert từ AI

# }

# # ====================================
# # STATE VARIABLES
# # ====================================
# _mqtt_client = None
# _is_connected = False
# _connection_attempts = 0
# MAX_RECONNECT_ATTEMPTS = 5

# _message_callbacks = {}

# # Cache dữ liệu sensor gần nhất
# _latest_sensor_data = {
#     'gas': 0,
#     'smoke': 0,
#     'relay1_state': False,  # ✅ Đèn + Còi
#     'relay2_state': False,  # ✅ Bơm
#     'servo_angle': 0,       # ✅ CHỈ 1 SERVO - góc hiện tại
#     'last_update': None,
#     'esp32_online': False,
#     'ai_detection': {
#         'detected': False,
#         'type': None,
#         'confidence': 0,
#         'position': {'x': 0, 'y': 0},
#         'last_detection_time': None
#     }
# }

# # ====================================
# # CALLBACKS - IMPROVED
# # ====================================

# def _on_connect(client, userdata, flags, rc):
#     """Khi kết nối MQTT thành công"""
#     global _is_connected, _connection_attempts

#     print(f"🔄 MQTT on_connect called with rc={rc}")

#     if rc == 0:
#         _is_connected = True
#         _connection_attempts = 0
#         print(f"✅ MQTT connected → {MQTT_BROKER}:{MQTT_PORT}")

#         # Subscribe tất cả topics cần thiết
#         subscribe_topics = [
#             TOPICS['ESP32_SENSORS'],
#             TOPICS['ESP32_STATUS'], 
#             TOPICS['AI_DETECTION'],
#             TOPICS['NODERED_ALERT'],
#             TOPICS['NODERED_STATUS'],
#         ]
        
#         for topic in subscribe_topics:
#             try:
#                 client.subscribe(topic, qos=1)
#                 print(f"📌 Subscribed: {topic}")
#             except Exception as e:
#                 print(f"❌ Subscribe failed for {topic}: {e}")

#         # Publish Django online status
#         try:
#             client.publish(TOPICS['SYSTEM_STATUS'], json.dumps({
#                 "source": "django",
#                 "status": "online",
#                 "timestamp": time.time()
#             }), qos=1, retain=True)
#             print("✅ Published online status")
#         except Exception as e:
#             print(f"❌ Publish status failed: {e}")

#     else:
#         _is_connected = False
#         error_messages = {
#             1: "Connection refused - incorrect protocol version",
#             2: "Connection refused - invalid client identifier", 
#             3: "Connection refused - server unavailable",
#             4: "Connection refused - bad username or password",
#             5: "Connection refused - not authorised",
#             7: "Connection refused - broker not available"
#         }
#         error_msg = error_messages.get(rc, f"Unknown error {rc}")
#         print(f"❌ MQTT connection failed: {error_msg}")
        
#         # Tự động reconnect sau delay
#         if _connection_attempts < MAX_RECONNECT_ATTEMPTS:
#             _reconnect_client(client)

# def _on_disconnect(client, userdata, rc):
#     """Khi mất kết nối"""
#     global _is_connected
#     _is_connected = False
    
#     print(f"🔌 MQTT disconnected rc={rc}")
    
#     if rc == 0:
#         print("🔌 MQTT disconnected normally")
#     else:
#         print(f"🔌 MQTT disconnected unexpectedly (rc={rc})")
#         # Tự động reconnect cho unexpected disconnects
#         if _connection_attempts < MAX_RECONNECT_ATTEMPTS:
#             _reconnect_client(client)

# def _on_message(client, userdata, message):
#     """Khi nhận MQTT message"""
#     try:
#         topic = message.topic
#         payload = message.payload.decode("utf-8")

#         print(f"📥 MQTT [{topic}]: {payload[:100]}...")

#         # Parse JSON payload
#         try:
#             data = json.loads(payload)
#         except json.JSONDecodeError:
#             data = payload

#         # === XỬ LÝ TỪ ESP32 ===
#         if topic == TOPICS["ESP32_SENSORS"]:
#             _handle_esp32_sensors(data)
        
#         elif topic == TOPICS["ESP32_STATUS"]:
#             _handle_esp32_status(data)
        
#         # === XỬ LÝ TỪ AI ===
#         elif topic == TOPICS["AI_DETECTION"]:
#             _handle_ai_detection(data)
        
#         # === XỬ LÝ TỪ NODE-RED ===
#         elif topic == TOPICS["NODERED_ALERT"]:
#             _handle_nodered_alert(data)
        
#         elif topic == TOPICS["NODERED_STATUS"]:
#             _handle_nodered_status(data)

#         # === CALLBACKS TÙY CHỈNH ===
#         if topic in _message_callbacks:
#             for cb in _message_callbacks[topic]:
#                 try:
#                     cb(topic, data)
#                 except Exception as e:
#                     print(f"❌ Callback error for {topic}: {e}")

#     except Exception as e:
#         print(f"❌ Message handling error: {e}")

# def _on_publish(client, userdata, mid):
#     """Khi publish thành công"""
#     print(f"📤 Published (mid={mid})")

# # ====================================
# # RECONNECT LOGIC
# # ====================================

# def _reconnect_client(client):
#     """Tự động reconnect với exponential backoff"""
#     global _connection_attempts
    
#     if _connection_attempts >= MAX_RECONNECT_ATTEMPTS:
#         print("❌ Max reconnect attempts reached")
#         return False

#     _connection_attempts += 1
#     delay = min(2 ** _connection_attempts, 30)
    
#     print(f"⏳ Reconnecting in {delay}s... (attempt {_connection_attempts})")
#     time.sleep(delay)

#     try:
#         client.reconnect()
#         return True
#     except Exception as e:
#         print(f"❌ Reconnect failed: {e}")
#         return False

# # ====================================
# # MESSAGE HANDLERS (giữ nguyên)
# # ====================================

# # def _handle_esp32_sensors(data):
# #     """Xử lý dữ liệu sensor từ ESP32"""
    
# #     try:
# #         _latest_sensor_data['gas'] = data.get('gas', 0)
# #         _latest_sensor_data['smoke'] = data.get('smoke', 0)
# #         _latest_sensor_data['relay1_state'] = bool(data.get('relay1', 0))

# #         _latest_sensor_data['relay2_state'] = bool(data.get('relay2', 0))
# #         _latest_sensor_data['last_update'] = time.time()
# #         _latest_sensor_data['esp32_online'] = True
# #         _latest_sensor_data['servo_pan'] = data.get('servo_pan', 90)
# #         # _latest_sensor_data['servo_tilt'] = data.get('servo_tilt', 90)
        
# #         print(f"📊 Sensors - Gas: {data.get('gas', 0)}, Smoke: {data.get('smoke', 0)}, "
# #                     f"Relay1: {data.get('relay1', 0)}, Relay2: {data.get('relay2', 0)}")        
# #     except Exception as e:
# #         print(f"❌ Handle ESP32 sensors error: {e}")

# def _handle_esp32_sensors(data):
#     """Xử lý dữ liệu sensor từ ESP32"""
#     try:
#         _latest_sensor_data['gas'] = data.get('gas', 0)
#         _latest_sensor_data['smoke'] = data.get('smoke', 0)
#         _latest_sensor_data['relay1_state'] = bool(data.get('relay1', 0))
#         _latest_sensor_data['relay2_state'] = bool(data.get('relay2', 0))
        
#         # ✅ CHỈ LẤY servo_pan (KHÔNG CÓ servo_tilt)
#         _latest_sensor_data['servo_angle'] = data.get('servo_pan', 0)
        
#         _latest_sensor_data['last_update'] = time.time()
#         _latest_sensor_data['esp32_online'] = True
        
#         print(f"📊 Sensors - Gas: {data.get('gas', 0)}, Smoke: {data.get('smoke', 0)}, "
#               f"Relay1: {data.get('relay1', 0)}, Relay2: {data.get('relay2', 0)}, "
#               f"Servo: {data.get('servo_pan', 0)}°")
        
#         # ✅ KIỂM TRA: Nếu relay2 = 0 (bơm tắt) thì servo phải về 0 độ
#         if not _latest_sensor_data['relay2_state'] and _latest_sensor_data['servo_angle'] != 0:
#             print(f"⚠️  Warning: Pump is OFF but servo angle is {_latest_sensor_data['servo_angle']}°")
            
#     except Exception as e:
#         print(f"❌ Handle ESP32 sensors error: {e}")

# # ====================================
# # CONTROL COMMANDS (FIXED - CHỈ 1 SERVO)
# # ====================================

# def control_servo(angle, action='move'):
#     """
#     Điều khiển servo duy nhất
#     angle: 0-180 độ
#     action: 'move' (mặc định) hoặc 'home' (về 0 độ)
#     """
#     if action == 'home':
#         angle = 0
    
#     angle = max(0, min(180, int(angle)))
    
#     payload = {
#         "servo_pan": angle,  # ✅ CHỈ GỬI servo_pan
#         "action": action,
#         "timestamp": time.time()
#     }
    
#     print(f"🔄 Control servo to {angle}° (action: {action})")
    
#     # Cập nhật cache
#     _latest_sensor_data['servo_angle'] = angle
    
#     return publish(TOPICS["CMD_SERVO"], payload, qos=1)

# def control_pump(action, duration=None):
#     """
#     Điều khiển máy bơm + tự động điều khiển servo
#     action: 'ON'/'OFF' hoặc True/False
#     """
#     if action in ['ON', 'on', 1, '1', True]:
#         relay_state = 1
#         print(f"💧 Web Control: Pump ON (relay2=1)")
#     else:
#         relay_state = 0
#         print(f"💧 Web Control: Pump OFF (relay2=0)")
    
#     payload = {
#         "relay2": relay_state,
#         "timestamp": time.time(),
#         "source": "web_control"
#     }
    
#     if duration is not None:
#         payload["duration"] = int(duration)

#     # Cập nhật cache
#     _latest_sensor_data['relay2_state'] = bool(relay_state)
    
#     # ✅ Nếu tắt bơm, tự động gửi lệnh servo về 0 độ
#     if relay_state == 0:
#         print("🔄 Pump OFF → Auto reset servo to 0°")
#         # Gửi lệnh servo về 0 độ
#         servo_payload = {
#             "servo_pan": 0,
#             "action": "home",
#             "timestamp": time.time()
#         }
#         publish(TOPICS["CMD_SERVO"], servo_payload, qos=1)
    
#     return publish(TOPICS["CMD_RELAY"], payload, qos=1)

# # ====================================
# # AI FIRE DETECTION CONTROL (NEW)
# # ====================================

# def ai_control_fire_detection(x_position, confidence, fire_type="fire"):
#     """
#     Điều khiển tự động khi AI phát hiện lửa
#     x_position: vị trí ngang của lửa (0-100)
#     confidence: độ tin cậy (0-100)
#     """
#     try:
#         # 1. Chuyển vị trí ngang sang góc servo (0-180)
#         angle = int((x_position / 100) * 180)
#         angle = max(0, min(180, angle))
        
#         print(f"🔥 AI Fire Detection: {fire_type} at x={x_position}% → angle={angle}° (conf: {confidence}%)")
        
#         # 2. Gửi lệnh quay servo đến vị trí lửa
#         servo_success = control_servo(angle, action="aim_fire")
        
#         # 3. BẬT BƠM (relay2)
#         if servo_success:
#             print(f"💧 AI: Turning ON pump for fire extinguishing")
#             pump_success = control_pump(True)
            
#             # 4. BẬT ĐÈN + CÒI (relay1)
#             light_success = control_light_buzzer(True)
            
#             return {
#                 "servo_angle": angle,
#                 "pump_on": pump_success,
#                 "light_buzzer_on": light_success,
#                 "ai_confidence": confidence
#             }
#         else:
#             print("❌ AI: Failed to control servo")
#             return None
            
#     except Exception as e:
#         print(f"❌ AI control error: {e}")
#         return None

# def ai_control_safe():
#     """
#     Khi AI báo an toàn (không còn lửa)
#     """
#     print("✅ AI Safe Detection: Turning OFF system")
    
#     # 1. TẮT BƠM
#     pump_success = control_pump(False)
    
#     # 2. TẮT ĐÈN + CÒI
#     light_success = control_light_buzzer(False)
    
#     # 3. SERVO VỀ 0 ĐỘ (sẽ tự động gọi trong control_pump)
#     # Hoặc gọi thêm để chắc chắn
#     servo_success = control_servo(0, action="home")
    
#     return {
#         "pump_off": pump_success,
#         "light_buzzer_off": light_success,
#         "servo_home": servo_success
#     }

# # ====================================
# # RELAY CONTROL (UPDATED)
# # ====================================

# def control_relay1(action=True, duration=None):
#     """Điều khiển Relay 1 (Đèn + Còi)"""
#     state = 1 if action else 0
    
#     payload = {
#         "relay1": state,
#         "timestamp": time.time()
#     }
    
#     if duration is not None:
#         payload["duration"] = int(duration)
    
#     print(f"💡🔊 Control Relay1 (Light+Buzzer): {'ON' if state else 'OFF'}")
#     _latest_sensor_data['relay1_state'] = bool(state)
    
#     return publish(TOPICS['CMD_RELAY'], payload, qos=1)

# def control_relay2(action=True, duration=None):
#     """
#     Điều khiển Relay 2 (Bơm) với tự động servo
#     Khi tắt bơm → servo về 0 độ
#     """
#     state = 1 if action else 0
    
#     payload = {
#         "relay2": state,
#         "timestamp": time.time()
#     }
    
#     if duration is not None:
#         payload["duration"] = int(duration)
    
#     print(f"💧 Control Relay2 (Pump): {'ON' if state else 'OFF'}")
#     _latest_sensor_data['relay2_state'] = bool(state)
    
#     # ✅ Nếu tắt bơm, gửi lệnh servo về 0 độ
#     if state == 0:
#         print("🔄 Pump OFF → Auto reset servo to 0°")
#         servo_payload = {
#             "servo_pan": 0,
#             "action": "home",
#             "timestamp": time.time()
#         }
#         publish(TOPICS["CMD_SERVO"], servo_payload, qos=1)
    
#     return publish(TOPICS['CMD_RELAY'], payload, qos=1)

# # ====================================
# # MANUAL FIRE CONTROL (cho web interface)
# # ====================================

# def manual_fire_control(angle):
#     """
#     Điều khiển thủ công từ web:
#     - Quay servo đến góc chỉ định
#     - Bật bơm
#     - Bật đèn + còi
#     """
#     print(f"👨‍🚒 Manual Fire Control: Angle={angle}°")
    
#     results = {}
    
#     # 1. Quay servo
#     results['servo'] = control_servo(angle)
    
#     # 2. Bật bơm
#     results['pump'] = control_relay2(True)
    
#     # 3. Bật đèn + còi
#     results['light_buzzer'] = control_relay1(True)
    
#     return results

# def manual_safe_control():
#     """
#     Tắt hệ thống thủ công từ web:
#     - Tắt bơm (sẽ tự động reset servo về 0)
#     - Tắt đèn + còi
#     """
#     print("👨‍🚒 Manual Safe Control: Turning OFF system")
    
#     results = {}
    
#     # 1. Tắt bơm (sẽ tự động reset servo)
#     results['pump'] = control_relay2(False)
    
#     # 2. Tắt đèn + còi
#     results['light_buzzer'] = control_relay1(False)
    
#     return results

# # ====================================
# # UTILITY FUNCTIONS (UPDATED)
# # ====================================

# def get_latest_sensor_data():
#     """Lấy dữ liệu sensor mới nhất"""
#     return _latest_sensor_data.copy()

# def get_sensor_readings():
#     """Lấy readings sensor đơn giản cho dashboard"""
#     data = _latest_sensor_data
#     return {
#         "gas": data.get('gas', 0),
#         "smoke": data.get('smoke', 0),
#         "relay1_state": data.get('relay1_state', False),
#         "relay2_state": data.get('relay2_state', False),
#         "servo_angle": data.get('servo_angle', 0),
#         "esp32_online": data.get('esp32_online', False),
#         "last_update": data.get('last_update'),
#         "ai_detected": data.get('ai_detection', {}).get('detected', False),
#         "ai_type": data.get('ai_detection', {}).get('type'),
#         "ai_confidence": data.get('ai_detection', {}).get('confidence', 0)
#     }

# def get_system_status():
#     """Lấy trạng thái hệ thống"""
#     return {
#         "mqtt_connected": _is_connected,
#         "connection_attempts": _connection_attempts,
#         "esp32_online": _latest_sensor_data['esp32_online'],
#         "last_update": _latest_sensor_data['last_update'],
#         "relay1_state": _latest_sensor_data['relay1_state'],
#         "relay2_state": _latest_sensor_data['relay2_state'],
#         "servo_angle": _latest_sensor_data['servo_angle'],
#         "ai_detection": _latest_sensor_data['ai_detection']
#     }

# # ====================================
# # TEST FUNCTIONS
# # ====================================

# def test_servo_sweep():
#     """Test servo quét từ 0-180 độ"""
#     print("🧪 Testing servo sweep 0 → 180 → 0")
    
#     # Quay từ 0 đến 180
#     for angle in range(0, 181, 10):
#         control_servo(angle)
#         time.sleep(0.5)
    
#     # Quay về 0
#     control_servo(0, action="home")
#     print("✅ Servo test completed")



# def _handle_esp32_status(data):
#     """Xử lý heartbeat/status từ ESP32"""
#     try:
#         _latest_sensor_data['esp32_online'] = (data.get('status') == 'online')
#         print(f"💓 ESP32 Status: {data}")
#     except Exception as e:
#         print(f"❌ Handle ESP32 status error: {e}")

# def _handle_ai_detection(data):
#     """Xử lý AI detection"""
#     try:
#         ai_data = _latest_sensor_data['ai_detection']
#         ai_data['detected'] = data.get('detected', False)
#         ai_data['type'] = data.get('type')
#         ai_data['confidence'] = data.get('confidence', 0)
#         ai_data['position'] = data.get('position', {'x': 0, 'y': 0})
#         ai_data['last_detection_time'] = time.time()
        
#         if data.get('detected'):
#             print(f"🔥 AI Detection: {data.get('type')} (conf: {data.get('confidence', 0)})")
    
#     except Exception as e:
#         print(f"❌ Handle AI detection error: {e}")

# def _handle_nodered_alert(data):
#     """Xử lý alert từ Node-RED"""
#     try:
#         print(f"🚨 Node-RED Alert: {data}")
#     except Exception as e:
#         print(f"❌ Handle Node-RED alert error: {e}")

# def _handle_nodered_status(data):
#     """Xử lý status từ Node-RED"""
#     try:
#         print(f"📊 Node-RED Status: {data}")
#     except Exception as e:
#         print(f"❌ Handle Node-RED status error: {e}")

# # ====================================
# # BUILD CLIENT - IMPROVED
# # ====================================

# def _build_client():
#     """Tạo MQTT client với debug chi tiết"""
#     global _connection_attempts
    
#     print(f"🔄 MQTT: Building client for {MQTT_BROKER}:{MQTT_PORT}")
    
#     try:
#         client_id = f"Django_PCCC_{int(time.time())}"
#         print(f"🔄 MQTT: Client ID: {client_id}")
        
#         client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
#         print("✅ MQTT: Client object created")

#         client.on_connect = _on_connect
#         client.on_disconnect = _on_disconnect
#         client.on_message = _on_message
#         client.on_publish = _on_publish
#         print("✅ MQTT: Callbacks set")

#         # Last will message
#         client.will_set(
#             TOPICS["SYSTEM_STATUS"],
#             json.dumps({
#                 "source": "django",
#                 "status": "offline",
#                 "timestamp": time.time()
#             }),
#             qos=1, retain=True
#         )
#         print("✅ MQTT: Last will set")

#         print(f"🔄 MQTT: Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        
#         try:
#             client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
#             print("✅ MQTT: Connect method called")
#         except Exception as e:
#             print(f"❌ MQTT: Connect failed: {e}")
#             return None
        
#         client.loop_start()
#         print("✅ MQTT: Loop started")
        
#         # Chờ kết nối thành công
#         print("🔄 MQTT: Waiting for connection...")
#         for i in range(10):
#             if _is_connected:
#                 print("✅ MQTT: Connected successfully!")
#                 return client
#             time.sleep(0.5)
#             print(f"🔄 MQTT: Waiting... {i+1}/10")
        
#         print("⚠️ MQTT: Connection timeout - may still connect later")
#         return client

#     except Exception as e:
#         print(f"❌ MQTT: Build client failed: {e}")
#         return None

# # ====================================
# # PUBLIC APIs
# # ====================================

# def get_client():
#     """Lấy MQTT client instance"""
#     global _mqtt_client
#     if _mqtt_client is None:
#         print("🔄 MQTT: Creating new client...")
#         _mqtt_client = _build_client()
#     else:
#         print("✅ MQTT: Using existing client")
#     return _mqtt_client

# def is_connected():
#     """Kiểm tra kết nối MQTT"""
#     return _is_connected

# def publish(topic, payload, qos=1, retain=False):
#     """Publish message lên MQTT"""
#     print(f"📤 MQTT: Attempting to publish to {topic}")
    
#     client = get_client()
#     if client is None:
#         print("❌ MQTT: Client not available")
#         return False

#     if not _is_connected:
#         print("❌ MQTT: Not connected, cannot publish")
#         return False

#     try:
#         if isinstance(payload, dict):
#             payload = json.dumps(payload, ensure_ascii=False)

#         result = client.publish(topic, payload, qos=qos, retain=retain)
        
#         if result.rc == mqtt.MQTT_ERR_SUCCESS:
#             print(f"✅ MQTT: Published to {topic}: {payload[:50]}...")
#             return True
#         else:
#             print(f"❌ MQTT: Publish failed with rc={result.rc}")
#             return False

#     except Exception as e:
#         print(f"❌ MQTT: Publish error: {e}")
#         return False

# # ====================================
# # CONTROL COMMANDS
# # ====================================

# # def control_relay1(action=True, duration=None):
# #     """
# #     Điều khiển Relay 1 (Đèn + Còi)
# #     action: True / False
# #     duration: giây (tự động tắt)
# #     """
# #     state = 1 if action else 0

# #     payload = {
# #         "relay1": state,
# #         "timestamp": time.time()
# #     }

# #     if duration is not None:
# #         payload["duration"] = int(duration)

# #     print(f"💡🔊 Control Relay1 (Light+Buzzer): {'ON' if state else 'OFF'}")

# #     _latest_sensor_data['relay1_state'] = bool(state)

# #     return publish(TOPICS['CMD_RELAY'], payload, qos=1)


# # def control_relay2(action=True, duration=None):
# #     """
# #     Điều khiển Relay 2 (Máy bơm)
# #     action: True / False
# #     duration: giây (tự động tắt)
# #     """
# #     state = 1 if action else 0

# #     payload = {
# #         "relay2": state,
# #         "timestamp": time.time()
# #     }

# #     if duration is not None:
# #         payload["duration"] = int(duration)

# #     print(f"💧 Control Relay2 (Pump): {'ON' if state else 'OFF'}")

# #     _latest_sensor_data['relay2_state'] = bool(state)

# #     return publish(TOPICS['CMD_RELAY'], payload, qos=1)

# # def control_servo(pan_angle, tilt_angle=None, action='move'):
# #     """Điều khiển servo"""
# #     pan_angle = max(0, min(180, int(pan_angle)))
    
# #     payload = {
# #         "servo_pan": pan_angle,
# #         "action": action,
# #         "timestamp": time.time()
# #     }
    
# #     if tilt_angle is not None:
# #         tilt_angle = max(0, min(180, int(tilt_angle)))
# #         payload["servo_tilt"] = tilt_angle
    
# #     print(f"🔄 Control servo: pan={pan_angle}°")
# #     return publish(TOPICS["CMD_SERVO"], payload, qos=1)

# # def control_pump(action, duration=None):
# #     """Điều khiển máy bơm"""
# #     if action in ['ON', 'on', 1, '1', True]:
# #         relay_state = 1
# #     else:
# #         relay_state = 0
    
# #     payload = {
# #         "relay2": relay_state,
# #         "timestamp": time.time(),
# #         "source": "web_control"
# #     }
    
# #     if duration is not None:
# #         payload["duration"] = int(duration)

# #     print(f"💧 Web Control: Pump {'ON' if relay_state else 'OFF'} (relay2={relay_state})")
# #     _latest_sensor_data['relay2_state'] = bool(relay_state)
    
# #     return publish(TOPICS["CMD_RELAY"], payload, qos=1)

# # ====================================
# # INIT WHEN DJANGO RUNSERVER
# # ====================================

# if IS_RUNSERVER:
#     print("🔥 MQTT: Initializing for Django runserver...")
#     # Khởi tạo client nhưng không block
#     import threading
#     def init_mqtt_async():
#         time.sleep(3)  # Chờ Django khởi động xong
#         print("🔄 MQTT: Starting async initialization...")
#         get_client()
    
#     thread = threading.Thread(target=init_mqtt_async, daemon=True)
#     thread.start()

# # ====================================
# # UTILITY FUNCTIONS
# # ====================================

# def get_system_status():
#     """Lấy trạng thái hệ thống"""
#     return {
#         "mqtt_connected": _is_connected,
#         "connection_attempts": _connection_attempts,
#         "esp32_online": _latest_sensor_data['esp32_online'],
#         "last_update": _latest_sensor_data['last_update'],
#     }

# def disconnect():
#     """Ngắt kết nối MQTT"""
#     global _mqtt_client, _is_connected
#     if _mqtt_client:
#         _mqtt_client.loop_stop()
#         _mqtt_client.disconnect()
#         _mqtt_client = None
#         _is_connected = False
#         print("👋 MQTT disconnected")
        
# # ====================================
# # PUBLIC APIs - THÊM CÁC HÀM NÀY
# # ====================================

# def get_latest_sensor_data():
#     """Lấy dữ liệu sensor mới nhất (dùng cho dashboard)"""
#     return _latest_sensor_data.copy()

# def get_system_status():
#     """Lấy trạng thái hệ thống"""
#     return {
#         "mqtt_connected": _is_connected,
#         "connection_attempts": _connection_attempts,
#         "esp32_online": _latest_sensor_data['esp32_online'],
#         "last_update": _latest_sensor_data['last_update'],
#         "relay1_state": _latest_sensor_data['relay1_state'],
#         "relay2_state": _latest_sensor_data['relay2_state'],
#         "ai_detection": _latest_sensor_data['ai_detection']
#     }

# def get_sensor_readings():
#     """Lấy readings sensor đơn giản cho dashboard"""
#     data = _latest_sensor_data
#     return {
#         "gas": data.get('gas', 0),
#         "smoke": data.get('smoke', 0),
#         "relay1_state": data.get('relay1_state', False),
#         "relay2_state": data.get('relay2_state', False),
#         "esp32_online": data.get('esp32_online', False),
#         "last_update": data.get('last_update'),
#         "ai_detected": data.get('ai_detection', {}).get('detected', False),
#         "ai_type": data.get('ai_detection', {}).get('type'),
#         "ai_confidence": data.get('ai_detection', {}).get('confidence', 0)
#     }
    
# # ====================================
# # LIGHT / BUZZER CONTROL (NEW)
# # ====================================

# # ====================================
# # LIGHT / BUZZER CONTROL (RELAY 1 - CHUNG)
# # ====================================

# def control_light_buzzer(action=True, duration=None):
#     """
#     Điều khiển đèn + còi qua Relay 1 (bật/tắt cùng lúc)
#     action: True / False
#     duration: giây (optional) - tự động tắt sau X giây
#     """
#     state = 1 if action else 0

#     payload = {
#         "relay1": state,
#         "timestamp": time.time(),
#         "source": "web_control"
#     }

#     if duration is not None:
#         payload["duration"] = int(duration)

#     print(f"💡🔊 Web Control: Light+Buzzer {'ON' if state else 'OFF'} (relay1={state})")
#     _latest_sensor_data['light_state'] = bool(state)
#     _latest_sensor_data['buzzer_state'] = bool(state)

#     return publish(TOPICS['CMD_RELAY'], payload, qos=1)


# # ✅ Giữ lại 2 hàm riêng để tương thích code cũ
# def control_light(action=True):
#     """Wrapper - điều khiển Relay 1 (đèn+còi)"""
#     return control_light_buzzer(action)


# def control_buzzer(action=True, duration=None):
#     """Wrapper - điều khiển Relay 1 (đèn+còi)"""
#     return control_light_buzzer(action, duration)








import sys
import os

print("=== MQTT UTILS DEBUG ===")
print("Python path:", sys.executable)
print("Working directory:", os.getcwd())
print("MQTT_BROKER:", "127.0.0.1")
print("MQTT_PORT:", 1883)

IS_RUNSERVER = "runserver" in sys.argv
print("Is runserver:", IS_RUNSERVER)
print("=========================")

import json
import logging
import time
from typing import Callable
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ====================================
# MQTT CONFIG - FIXED
# ====================================
MQTT_BROKER = "127.0.0.1"  # ĐẢM BẢO ĐÂY LÀ 127.0.0.1
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
MQTT_KEEPALIVE = 60

# ====================================
# MQTT TOPICS - CHUẨN HÓA THEO NODE-RED
# ====================================
TOPICS = {
    # === ESP32 GỬI LÊN (Django Subscribe) ===
    'ESP32_SENSORS': 'pccc/esp32/sensors',
    'ESP32_STATUS': 'pccc/esp32/status',
    
    # === AI GỬI LÊN (Django Subscribe) ===
    'AI_DETECTION': 'pccc/ai/alert',
    
    # === DJANGO GỬI ĐẾN ESP32 (Django Publish) ===
    'CMD_SERVO': 'pccc/esp32/servo',
    'CMD_RELAY': 'pccc/esp32/relay',
    
    # === DJANGO GỬI ĐẾN NODE-RED (Django Publish) ===
    'DJANGO_COMMAND': 'pccc/django/command',
    'DJANGO_AI_RESULT': 'pccc/django/ai',
    
    # === NODE-RED GỬI VỀ DJANGO (Django Subscribe) ===
    'NODERED_ALERT': 'pccc/nodered/alert',
    'NODERED_STATUS': 'pccc/nodered/status',
    
    # === SYSTEM ===
    'SYSTEM_STATUS': 'pccc/system/status',
    'ALERT': 'pccc/alert',                      # Alert từ AI

}

# ====================================
# STATE VARIABLES
# ====================================
_mqtt_client = None
_is_connected = False
_connection_attempts = 0
MAX_RECONNECT_ATTEMPTS = 5

_message_callbacks = {}

# Cache dữ liệu sensor gần nhất - CHỈ 1 SERVO
_latest_sensor_data = {
    'gas': 0,
    'smoke': 0,
    'relay1_state': False,      # ✅ Đèn + Còi
    'relay2_state': False,      # ✅ Bơm
    'servo_angle': 0,           # ✅ CHỈ 1 SERVO - góc hiện tại (0-180 độ)
    'servo_target': 0,          # ✅ Góc mục tiêu
    'last_update': None,
    'esp32_online': False,
    'ai_detection': {
        'detected': False,
        'type': None,
        'confidence': 0,
        'position': {'x': 0, 'y': 0},
        'last_detection_time': None
    },
    'system_status': 'safe',    # 'safe' hoặc 'fire'
    'fire_position': 0,         # Vị trí lửa phát hiện (0-100)
}

# ====================================
# CALLBACKS - IMPROVED
# ====================================

def _on_connect(client, userdata, flags, rc):
    """Khi kết nối MQTT thành công"""
    global _is_connected, _connection_attempts

    print(f"🔄 MQTT on_connect called with rc={rc}")

    if rc == 0:
        _is_connected = True
        _connection_attempts = 0
        print(f"✅ MQTT connected → {MQTT_BROKER}:{MQTT_PORT}")

        # Subscribe tất cả topics cần thiết
        subscribe_topics = [
            TOPICS['ESP32_SENSORS'],
            TOPICS['ESP32_STATUS'], 
            TOPICS['AI_DETECTION'],
            TOPICS['NODERED_ALERT'],
            TOPICS['NODERED_STATUS'],
        ]
        
        for topic in subscribe_topics:
            try:
                client.subscribe(topic, qos=1)
                print(f"📌 Subscribed: {topic}")
            except Exception as e:
                print(f"❌ Subscribe failed for {topic}: {e}")

        # Publish Django online status
        try:
            client.publish(TOPICS['SYSTEM_STATUS'], json.dumps({
                "source": "django",
                "status": "online",
                "timestamp": time.time()
            }), qos=1, retain=True)
            print("✅ Published online status")
        except Exception as e:
            print(f"❌ Publish status failed: {e}")

    else:
        _is_connected = False
        error_messages = {
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier", 
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorised",
            7: "Connection refused - broker not available"
        }
        error_msg = error_messages.get(rc, f"Unknown error {rc}")
        print(f"❌ MQTT connection failed: {error_msg}")
        
        # Tự động reconnect sau delay
        if _connection_attempts < MAX_RECONNECT_ATTEMPTS:
            _reconnect_client(client)

def _on_disconnect(client, userdata, rc):
    """Khi mất kết nối"""
    global _is_connected
    _is_connected = False
    
    print(f"🔌 MQTT disconnected rc={rc}")
    
    if rc == 0:
        print("🔌 MQTT disconnected normally")
    else:
        print(f"🔌 MQTT disconnected unexpectedly (rc={rc})")
        # Tự động reconnect cho unexpected disconnects
        if _connection_attempts < MAX_RECONNECT_ATTEMPTS:
            _reconnect_client(client)

def _on_message(client, userdata, message):
    """Khi nhận MQTT message"""
    try:
        topic = message.topic
        payload = message.payload.decode("utf-8")

        print(f"📥 MQTT [{topic}]: {payload[:100]}...")

        # Parse JSON payload
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = payload

        # === XỬ LÝ TỪ ESP32 ===
        if topic == TOPICS["ESP32_SENSORS"]:
            _handle_esp32_sensors(data)
        
        elif topic == TOPICS["ESP32_STATUS"]:
            _handle_esp32_status(data)
        
        # === XỬ LÝ TỪ AI ===
        elif topic == TOPICS["AI_DETECTION"]:
            _handle_ai_detection(data)
        
        # === XỬ LÝ TỪ NODE-RED ===
        elif topic == TOPICS["NODERED_ALERT"]:
            _handle_nodered_alert(data)
        
        elif topic == TOPICS["NODERED_STATUS"]:
            _handle_nodered_status(data)

        # === CALLBACKS TÙY CHỈNH ===
        if topic in _message_callbacks:
            for cb in _message_callbacks[topic]:
                try:
                    cb(topic, data)
                except Exception as e:
                    print(f"❌ Callback error for {topic}: {e}")

    except Exception as e:
        print(f"❌ Message handling error: {e}")

def _on_publish(client, userdata, mid):
    """Khi publish thành công"""
    print(f"📤 Published (mid={mid})")

# ====================================
# RECONNECT LOGIC
# ====================================

def _reconnect_client(client):
    """Tự động reconnect với exponential backoff"""
    global _connection_attempts
    
    if _connection_attempts >= MAX_RECONNECT_ATTEMPTS:
        print("❌ Max reconnect attempts reached")
        return False

    _connection_attempts += 1
    delay = min(2 ** _connection_attempts, 30)
    
    print(f"⏳ Reconnecting in {delay}s... (attempt {_connection_attempts})")
    time.sleep(delay)

    try:
        client.reconnect()
        return True
    except Exception as e:
        print(f"❌ Reconnect failed: {e}")
        return False

# ====================================
# MESSAGE HANDLERS (FIXED - CHỈ 1 SERVO)
# ====================================

def _handle_esp32_sensors(data):
    """Xử lý dữ liệu sensor từ ESP32 - CHỈ 1 SERVO"""
    try:
        # Cập nhật sensor values
        _latest_sensor_data['gas'] = data.get('gas', 0)
        _latest_sensor_data['smoke'] = data.get('smoke', 0)
        _latest_sensor_data['relay1_state'] = bool(data.get('relay1', 0))
        _latest_sensor_data['relay2_state'] = bool(data.get('relay2', 0))
        
        # ✅ CHỈ LẤY servo_pan (KHÔNG CÓ servo_tilt)
        servo_angle = data.get('servo_pan', 0)
        _latest_sensor_data['servo_angle'] = servo_angle
        
        _latest_sensor_data['last_update'] = time.time()
        _latest_sensor_data['esp32_online'] = True
        
        print(f"📊 Sensors - Gas: {data.get('gas', 0)}, Smoke: {data.get('smoke', 0)}, "
              f"Relay1: {data.get('relay1', 0)}, Relay2: {data.get('relay2', 0)}, "
              f"Servo: {servo_angle}°")
        
        # ✅ KIỂM TRA AN TOÀN: Nếu relay2 = 0 (bơm tắt) nhưng servo khác 0
        if not _latest_sensor_data['relay2_state'] and servo_angle != 0:
            print(f"⚠️  Safety Check: Pump is OFF but servo angle is {servo_angle}°")
            # Tự động reset servo về 0 độ
            if _latest_sensor_data['system_status'] == 'safe':
                print("🔄 Auto-resetting servo to 0° (safety)")
                control_servo(0, action="home")
                
    except Exception as e:
        print(f"❌ Handle ESP32 sensors error: {e}")

def _handle_esp32_status(data):
    """Xử lý heartbeat/status từ ESP32"""
    try:
        _latest_sensor_data['esp32_online'] = (data.get('status') == 'online')
        print(f"💓 ESP32 Status: {data}")
    except Exception as e:
        print(f"❌ Handle ESP32 status error: {e}")

def _handle_ai_detection(data):
    """Xử lý AI detection - TỰ ĐỘNG ĐIỀU KHIỂN"""
    try:
        detected = data.get('detected', False)
        fire_type = data.get('type', 'fire')
        confidence = data.get('confidence', 0)
        
        # Cập nhật cache
        ai_data = _latest_sensor_data['ai_detection']
        ai_data['detected'] = detected
        ai_data['type'] = fire_type
        ai_data['confidence'] = confidence
        ai_data['position'] = data.get('position', {'x': 0, 'y': 0})
        ai_data['last_detection_time'] = time.time()
        
        if detected:
            print(f"🔥 AI Detection: {fire_type} (conf: {confidence}%)")
            
            # Lấy vị trí lửa
            position = data.get('position', {'x': 0, 'y': 0})
            x_position = position.get('x', 0)
            
            # Lưu vị trí lửa
            _latest_sensor_data['fire_position'] = x_position
            _latest_sensor_data['system_status'] = 'fire'
            
            # 🔥 TỰ ĐỘNG XỬ LÝ: Tính góc và điều khiển
            if confidence > 50:  # Chỉ xử lý khi độ tin cậy > 50%
                # Chuyển vị trí ngang (0-100) sang góc (0-180)
                angle = int((x_position / 100) * 180)
                angle = max(0, min(180, angle))
                
                # Gửi lệnh điều khiển
                print(f"🎯 Auto Control: Fire at x={x_position}% → angle={angle}°")
                
                # 1. Quay servo đến vị trí lửa
                control_servo(angle, action="aim_fire")
                
                # 2. Bật bơm
                control_relay2(True)
                
                # 3. Bật đèn + còi
                control_relay1(True)
                
        else:
            # AI báo an toàn
            print("✅ AI Safe: No fire detected")
            _latest_sensor_data['system_status'] = 'safe'
            
            # 🔥 TỰ ĐỘNG TẮT HỆ THỐNG Nếu đang ở trạng thái cháy
            if _latest_sensor_data.get('last_fire_time'):
                fire_time_ago = time.time() - _latest_sensor_data['last_fire_time']
                if fire_time_ago > 5:  # Sau 5 giây không có lửa
                    print("🔄 Auto Safe Control: Turning OFF system")
                    
                    # 1. Tắt bơm (sẽ tự động reset servo)
                    control_relay2(False)
                    
                    # 2. Tắt đèn + còi
                    control_relay1(False)
                    
                    # 3. Reset servo về 0 (chắc chắn)
                    control_servo(0, action="home")
    
    except Exception as e:
        print(f"❌ Handle AI detection error: {e}")

def _handle_nodered_alert(data):
    """Xử lý alert từ Node-RED"""
    try:
        print(f"🚨 Node-RED Alert: {data}")
    except Exception as e:
        print(f"❌ Handle Node-RED alert error: {e}")

def _handle_nodered_status(data):
    """Xử lý status từ Node-RED"""
    try:
        print(f"📊 Node-RED Status: {data}")
    except Exception as e:
        print(f"❌ Handle Node-RED status error: {e}")

# ====================================
# BUILD CLIENT - IMPROVED
# ====================================

def _build_client():
    """Tạo MQTT client với debug chi tiết"""
    global _connection_attempts
    
    print(f"🔄 MQTT: Building client for {MQTT_BROKER}:{MQTT_PORT}")
    
    try:
        client_id = f"Django_PCCC_{int(time.time())}"
        print(f"🔄 MQTT: Client ID: {client_id}")
        
        client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        print("✅ MQTT: Client object created")

        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message
        client.on_publish = _on_publish
        print("✅ MQTT: Callbacks set")

        # Last will message
        client.will_set(
            TOPICS["SYSTEM_STATUS"],
            json.dumps({
                "source": "django",
                "status": "offline",
                "timestamp": time.time()
            }),
            qos=1, retain=True
        )
        print("✅ MQTT: Last will set")

        print(f"🔄 MQTT: Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            print("✅ MQTT: Connect method called")
        except Exception as e:
            print(f"❌ MQTT: Connect failed: {e}")
            return None
        
        client.loop_start()
        print("✅ MQTT: Loop started")
        
        # Chờ kết nối thành công
        print("🔄 MQTT: Waiting for connection...")
        for i in range(10):
            if _is_connected:
                print("✅ MQTT: Connected successfully!")
                return client
            time.sleep(0.5)
            print(f"🔄 MQTT: Waiting... {i+1}/10")
        
        print("⚠️ MQTT: Connection timeout - may still connect later")
        return client

    except Exception as e:
        print(f"❌ MQTT: Build client failed: {e}")
        return None

# ====================================
# PUBLIC APIs
# ====================================

def get_client():
    """Lấy MQTT client instance"""
    global _mqtt_client
    if _mqtt_client is None:
        print("🔄 MQTT: Creating new client...")
        _mqtt_client = _build_client()
    else:
        print("✅ MQTT: Using existing client")
    return _mqtt_client

def is_connected():
    """Kiểm tra kết nối MQTT"""
    return _is_connected

def publish(topic, payload, qos=1, retain=False):
    """Publish message lên MQTT"""
    print(f"📤 MQTT: Attempting to publish to {topic}")
    
    client = get_client()
    if client is None:
        print("❌ MQTT: Client not available")
        return False

    if not _is_connected:
        print("❌ MQTT: Not connected, cannot publish")
        return False

    try:
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)

        result = client.publish(topic, payload, qos=qos, retain=retain)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"✅ MQTT: Published to {topic}: {payload[:50]}...")
            return True
        else:
            print(f"❌ MQTT: Publish failed with rc={result.rc}")
            return False

    except Exception as e:
        print(f"❌ MQTT: Publish error: {e}")
        return False

# ====================================
# SERVO CONTROL (CHỈ 1 SERVO)
# ====================================

def control_servo(angle, action='move'):
    """
    Điều khiển servo duy nhất
    angle: 0-180 độ
    action: 'move' (mặc định), 'home' (về 90°), 'aim_fire' (nhắm lửa), 'return_to_default' (về 90°)
    """
    if action in ['home', 'return_to_default', 'shutdown_reset']:
        angle = 90  # ✅ VỊ TRÍ MẶC ĐỊNH LÀ 90°
    
    angle = max(0, min(180, int(angle)))
    
    payload = {
        "servo_pan": angle,  # ✅ CHỈ GỮI servo_pan
        "action": action,
        "timestamp": time.time(),
        "default_position": (action in ['home', 'return_to_default', 'shutdown_reset'])
    }
    
    # Cập nhật cache
    _latest_sensor_data['servo_angle'] = angle
    _latest_sensor_data['servo_target'] = angle
    
    action_desc = {
        'move': 'Di chuyển đến',
        'home': 'Về vị trí mặc định',
        'aim_fire': 'Nhắm lửa',
        'return_to_default': 'Về vị trí mặc định',
        'safety_reset': 'Reset an toàn',
        'safety_correct': 'Hiệu chỉnh an toàn',
        'shutdown_reset': 'Reset khi shutdown'
    }
    
    print(f"🔄 {action_desc.get(action, 'Điều khiển')} servo đến {angle}°")
    
    return publish(TOPICS["CMD_SERVO"], payload, qos=1)

# ====================================
# RELAY CONTROL (WITH AUTO SERVO RESET)
# ====================================

def control_relay1(action=True, duration=None):
    """
    Điều khiển Relay 1 (Đèn + Còi)
    action: True / False
    duration: giây (tự động tắt)
    """
    state = 1 if action else 0
    
    payload = {
        "relay1": state,
        "timestamp": time.time()
    }
    
    if duration is not None:
        payload["duration"] = int(duration)
    
    print(f"💡🔊 Control Relay1 (Light+Buzzer): {'ON' if state else 'OFF'}")
    _latest_sensor_data['relay1_state'] = bool(state)
    
    return publish(TOPICS['CMD_RELAY'], payload, qos=1)

def control_relay2(action=True, duration=None, source="web_control", reason=None):
    """
    Điều khiển Relay 2 (Bơm) với safety check và auto servo reset
    ✅ AN TOÀN: Khi tắt bơm → servo tự động về 0°
    
    Args:
        action: True/False hoặc "ON"/"OFF"
        duration: thời gian chạy (giây), tự động tắt sau
        source: nguồn điều khiển (ai, web, manual, emergency)
        reason: lý do điều khiển (debug)
    """
    try:
        # ===========================================
        # 1. PARSE ACTION INPUT
        # ===========================================
        if isinstance(action, str):
            action = action.upper().strip()
            if action in ['ON', '1', 'TRUE', 'YES']:
                state = 1
            else:
                state = 0
        else:
            state = 1 if action else 0
        
        now_ts = time.time()
        current_angle = _latest_sensor_data.get('servo_angle', 0)
        current_pump_state = _latest_sensor_data.get('relay2_state', False)
        
        print(f"\n{'='*60}")
        print(f"💧 RELAY2 CONTROL - {time.strftime('%H:%M:%S', time.localtime(now_ts))}")
        print(f"{'='*60}")
        print(f"   📝 Command: {'ON' if state else 'OFF'}")
        print(f"   📍 Source: {source}")
        if reason:
            print(f"   🎯 Reason: {reason}")
        print(f"   📊 Current State: {'ON' if current_pump_state else 'OFF'}")
        print(f"   🎯 Servo Angle: {current_angle}°")
        
        # ===========================================
        # 2. SAFETY CHECK: PUMP OFF -> SERVO MUST BE 0°
        # ===========================================
        safety_violation = False
        
        if state == 0:  # Turning pump OFF
            print("   🔒 Safety Check: Pump OFF command detected")
            
            # ✅ THAY ĐỔI: KHÔNG reset servo về 0° khi tắt bơm
            # Servo sẽ được reset bởi detector khi hệ thống an toàn
            print("   ✅ Safety OK: Pump can be turned OFF, servo maintains position")
        
        elif state == 1:  # Turning pump ON
            print("   🔒 Safety Check: Pump ON command detected")
            
            # Check if servo angle is valid (0-180°)
            current_angle = _latest_sensor_data.get('servo_angle', 90)
            if current_angle < 0 or current_angle > 180:
                print(f"   ⚠️  SAFETY VIOLATION: Invalid servo angle {current_angle}°")
                print(f"   🛠️  Auto-correcting: Setting servo to 90°...")
                
                # Auto correct servo to default position (90°)
                servo_payload = {
                    "servo_pan": 90,
                    "action": "safety_correct",
                    "timestamp": now_ts,
                    "reason": f"Invalid angle {current_angle}° when pump ON",
                    "source": source
                }
                
                servo_success = publish(TOPICS["CMD_SERVO"], servo_payload, qos=1)
                
                if servo_success:
                    print("   ✅ Servo corrected to 90° (safety)")
                    _latest_sensor_data['servo_angle'] = 90
                    _latest_sensor_data['servo_target'] = 90
                else:
                    print("   ❌ Servo correction FAILED!")
                    safety_violation = True
            else:
                print(f"   ✅ Safety OK: Servo angle {current_angle}° is valid")
        
        # ===========================================
        # 3. SAFETY CHECK: PUMP ON -> SERVO POSITION VALIDATION
        # ===========================================
        elif state == 1:  # Turning pump ON
            print("   🔒 Safety Check: Pump ON command detected")
            
            # Check if servo angle is valid (0-180°)
            if current_angle < 0 or current_angle > 180:
                print(f"   ⚠️  SAFETY VIOLATION: Invalid servo angle {current_angle}°")
                print(f"   🛠️  Auto-correcting: Setting servo to 90°...")
                
                # Auto correct servo to middle position
                servo_payload = {
                    "servo_pan": 90,
                    "action": "safety_correct",
                    "timestamp": now_ts,
                    "reason": f"Invalid angle {current_angle}° when pump ON",
                    "source": source
                }
                
                servo_success = publish(TOPICS["CMD_SERVO"], servo_payload, qos=1)
                
                if servo_success:
                    print("   ✅ Servo corrected to 90° (safety)")
                    _latest_sensor_data['servo_angle'] = 90
                    _latest_sensor_data['servo_target'] = 90
                else:
                    print("   ❌ Servo correction FAILED!")
                    safety_violation = True
            else:
                print(f"   ✅ Safety OK: Servo angle {current_angle}° is valid")
        
        # ===========================================
        # 4. PREPARE RELAY PAYLOAD
        # ===========================================
        payload = {
            "relay2": state,
            "timestamp": now_ts,
            "source": source,
            "safety_check": not safety_violation,
            "current_servo_angle": current_angle,
            "system_status": _latest_sensor_data.get('system_status', 'unknown')
        }
        
        if reason:
            payload["reason"] = reason
            
        if duration is not None:
            payload["duration"] = int(duration)
            print(f"   ⏱️  Duration: {duration}s (auto-off)")
        
        # ===========================================
        # 5. UPDATE CACHE STATE
        # ===========================================
        _latest_sensor_data['relay2_state'] = bool(state)
        
        if state == 1:
            _latest_sensor_data['system_status'] = 'active'
            print(f"   📈 System Status: ACTIVE (pump ON)")
        else:
            _latest_sensor_data['system_status'] = 'safe'
            print(f"   📈 System Status: SAFE (pump OFF)")
        
        # ===========================================
        # 6. SEND MQTT COMMAND
        # ===========================================
        print(f"   📤 Sending MQTT command...")
        
        mqtt_success = publish(TOPICS['CMD_RELAY'], payload, qos=1)
        
        if mqtt_success:
            print(f"   ✅ MQTT command sent successfully")
        else:
            print(f"   ❌ MQTT command FAILED!")
            # Revert cache if failed
            _latest_sensor_data['relay2_state'] = current_pump_state
        
        # ===========================================
        # 7. LOG THE ACTION
        # ===========================================
        try:
            from core.models import EventLog
            
            EventLog.objects.create(
                category="relay2_control",
                message=f"Relay2 {'ON' if state else 'OFF'} from {source}",
                meta={
                    "state": "ON" if state else "OFF",
                    "source": source,
                    "reason": reason,
                    "duration": duration,
                    "safety_violation": safety_violation,
                    "servo_angle": current_angle,
                    "mqtt_success": mqtt_success,
                    "timestamp": now_ts
                }
            )
            print(f"   ✅ 📝 Event logged to database")
            
        except Exception as db_error:
            print(f"   ⚠️  Database log error: {db_error}")
        
        # ===========================================
        # 8. RETURN RESULT
        # ===========================================
        result = {
            "success": mqtt_success and not safety_violation,
            "state": "ON" if state else "OFF",
            "safety_violation": safety_violation,
            "servo_angle_before": current_angle,
            "servo_angle_after": _latest_sensor_data['servo_angle'],
            "timestamp": now_ts,
            "source": source
        }
        
        print(f"\n   📊 RESULT:")
        print(f"      • Command: {'ON' if state else 'OFF'}")
        print(f"      • MQTT Success: {'Yes' if mqtt_success else 'No'}")
        print(f"      • Safety Violation: {'Yes' if safety_violation else 'No'}")
        print(f"      • Servo Angle: {current_angle}° → {_latest_sensor_data['servo_angle']}°")
        print(f"      • System Status: {_latest_sensor_data.get('system_status', 'unknown')}")
        print(f"{'='*60}\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in control_relay2: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to send emergency stop
        try:
            emergency_payload = {
                "relay2": 0,
                "timestamp": time.time(),
                "emergency": True,
                "error": str(e),
                "source": "error_recovery"
            }
            publish(TOPICS['CMD_RELAY'], emergency_payload, qos=1)
            print("   🚨 Emergency stop sent due to error")
        except Exception as emergency_error:
            print(f"   ❌ Emergency stop also failed: {emergency_error}")
        
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

# ====================================
# LIGHT / BUZZER CONTROL (RELAY 1)
# ====================================

def control_light_buzzer(action=True, duration=None):
    """
    Điều khiển đèn + còi qua Relay 1 (bật/tắt cùng lúc)
    action: True / False
    duration: giây (optional) - tự động tắt sau X giây
    """
    state = 1 if action else 0

    payload = {
        "relay1": state,
        "timestamp": time.time(),
        "source": "web_control"
    }

    if duration is not None:
        payload["duration"] = int(duration)

    print(f"💡🔊 Web Control: Light+Buzzer {'ON' if state else 'OFF'} (relay1={state})")
    _latest_sensor_data['relay1_state'] = bool(state)

    return publish(TOPICS['CMD_RELAY'], payload, qos=1)

# ====================================
# PUMP CONTROL (WITH SAFETY)
# ====================================

def control_pump(action, duration=None):
    """
    Điều khiển máy bơm (alias của control_relay2)
    Khi tắt bơm → servo tự động về 0 độ
    """
    if action in ['ON', 'on', 1, '1', True]:
        return control_relay2(True, duration)
    else:
        return control_relay2(False, duration)

# ====================================
# AI FIRE CONTROL (AUTOMATIC)
# ====================================

def ai_control_fire_detection(x_position, confidence, fire_type="fire"):
    """
    Điều khiển tự động khi AI phát hiện lửa
    x_position: vị trí ngang của lửa (0-100)
    confidence: độ tin cậy (0-100)
    """
    try:
        # Chuyển vị trí ngang sang góc servo (0-180)
        angle = int((x_position / 100) * 180)
        angle = max(0, min(180, angle))
        
        print(f"🔥 AI Fire Detection: {fire_type} at x={x_position}% → angle={angle}° (conf: {confidence}%)")
        
        # Cập nhật cache
        _latest_sensor_data['system_status'] = 'fire'
        _latest_sensor_data['fire_position'] = x_position
        _latest_sensor_data['last_fire_time'] = time.time()
        
        # 1. Quay servo đến vị trí lửa
        servo_success = control_servo(angle, action="aim_fire")
        
        # 2. BẬT BƠM
        pump_success = control_relay2(True)
        
        # 3. BẬT ĐÈN + CÒI
        light_success = control_relay1(True)
        
        return {
            "servo_angle": angle,
            "pump_on": pump_success,
            "light_buzzer_on": light_success,
            "ai_confidence": confidence,
            "fire_position": x_position
        }
            
    except Exception as e:
        print(f"❌ AI control error: {e}")
        return None

def ai_control_safe():
    """
    Khi AI báo an toàn (không còn lửa)
    """
    print("✅ AI Safe Detection: Turning OFF system")
    
    # Cập nhật trạng thái
    _latest_sensor_data['system_status'] = 'safe'
    
    # 1. TẮT BƠM (sẽ tự động reset servo về 0)
    pump_success = control_relay2(False)
    
    # 2. TẮT ĐÈN + CÒI
    light_success = control_relay1(False)
    
    # 3. SERVO VỀ 0 ĐỘ (chắc chắn)
    servo_success = control_servo(0, action="home")
    
    return {
        "pump_off": pump_success,
        "light_buzzer_off": light_success,
        "servo_home": servo_success
    }

# ====================================
# MANUAL CONTROL (FOR WEB INTERFACE)
# ====================================

def manual_fire_control(angle, auto_pump=True):
    """
    Điều khiển thủ công từ web:
    - Quay servo đến góc chỉ định
    - Bật bơm (nếu auto_pump=True)
    - Bật đèn + còi
    """
    angle = max(0, min(180, angle))
    
    print(f"👨‍🚒 Manual Fire Control: Angle={angle}°, Auto Pump: {auto_pump}")
    
    results = {}
    
    # 1. Quay servo
    results['servo'] = control_servo(angle)
    
    # 2. Bật bơm (nếu được yêu cầu)
    if auto_pump:
        results['pump'] = control_relay2(True)
    
    # 3. Bật đèn + còi
    results['light_buzzer'] = control_relay1(True)
    
    # Cập nhật trạng thái
    _latest_sensor_data['system_status'] = 'fire'
    
    return results

def manual_safe_control():
    """
    Tắt hệ thống thủ công từ web:
    - Tắt bơm (sẽ tự động reset servo về 0)
    - Tắt đèn + còi
    """
    print("👨‍🚒 Manual Safe Control: Turning OFF system")
    
    results = {}
    
    # 1. Tắt bơm (sẽ tự động reset servo)
    results['pump'] = control_relay2(False)
    
    # 2. Tắt đèn + còi
    results['light_buzzer'] = control_relay1(False)
    
    # 3. Cập nhật trạng thái
    _latest_sensor_data['system_status'] = 'safe'
    
    return results

# ====================================
# SYSTEM CONTROL
# ====================================

def emergency_stop():
    """
    Dừng khẩn cấp: Tắt mọi thứ và đưa servo về 90°
    """
    print("🚨 EMERGENCY STOP: Turning OFF everything!")
    
    results = {}
    
    # 1. Tắt bơm
    results['pump'] = control_relay2(False)
    
    # 2. Tắt đèn + còi
    results['light_buzzer'] = control_relay1(False)
    
    # 3. Servo về 90° (vị trí mặc định)
    results['servo'] = control_servo(90, action="emergency_reset")
    
    # 4. Cập nhật trạng thái
    _latest_sensor_data['system_status'] = 'safe'
    
    # 5. Gửi alert
    publish(TOPICS['ALERT'], {
        "type": "emergency_stop",
        "timestamp": time.time(),
        "message": "Emergency stop activated - Servo at 90°"
    })
    
    return results

def reset_system():
    """
    Reset hệ thống về trạng thái ban đầu
    """
    print("🔄 System Reset: Returning to initial state")
    
    results = manual_safe_control()
    
    # Reset AI detection
    _latest_sensor_data['ai_detection'] = {
        'detected': False,
        'type': None,
        'confidence': 0,
        'position': {'x': 0, 'y': 0},
        'last_detection_time': None
    }
    
    return results

# ====================================
# UTILITY FUNCTIONS
# ====================================

def get_latest_sensor_data():
    """Lấy dữ liệu sensor mới nhất"""
    return _latest_sensor_data.copy()

def get_sensor_readings():
    """Lấy readings sensor đơn giản cho dashboard"""
    data = _latest_sensor_data
    ai_data = data.get('ai_detection', {})
    
    return {
        "gas": data.get('gas', 0),
        "smoke": data.get('smoke', 0),
        "relay1_state": data.get('relay1_state', False),
        "relay2_state": data.get('relay2_state', False),
        "servo_angle": data.get('servo_angle', 0),
        "servo_target": data.get('servo_target', 0),
        "esp32_online": data.get('esp32_online', False),
        "last_update": data.get('last_update'),
        "system_status": data.get('system_status', 'safe'),
        "fire_position": data.get('fire_position', 0),
        "ai_detected": ai_data.get('detected', False),
        "ai_type": ai_data.get('type'),
        "ai_confidence": ai_data.get('confidence', 0),
        "ai_position_x": ai_data.get('position', {}).get('x', 0),
        "ai_position_y": ai_data.get('position', {}).get('y', 0)
    }

def get_system_status():
    """Lấy trạng thái hệ thống"""
    return {
        "mqtt_connected": _is_connected,
        "connection_attempts": _connection_attempts,
        "esp32_online": _latest_sensor_data['esp32_online'],
        "last_update": _latest_sensor_data['last_update'],
        "relay1_state": _latest_sensor_data['relay1_state'],
        "relay2_state": _latest_sensor_data['relay2_state'],
        "servo_angle": _latest_sensor_data['servo_angle'],
        "system_status": _latest_sensor_data['system_status'],
        "ai_detection": _latest_sensor_data['ai_detection']
    }

# ====================================
# COMPATIBILITY WRAPPERS
# ====================================

def control_light(action=True):
    """Wrapper - điều khiển Relay 1 (đèn+còi)"""
    return control_light_buzzer(action)

def control_buzzer(action=True, duration=None):
    """Wrapper - điều khiển Relay 1 (đèn+còi)"""
    return control_light_buzzer(action, duration)

# ====================================
# TEST FUNCTIONS
# ====================================

def test_servo_sweep():
    """Test servo quét từ 0-180 độ"""
    print("🧪 Testing servo sweep 0 → 180 → 0")
    
    # Quay từ 0 đến 180
    for angle in range(0, 181, 20):
        control_servo(angle)
        time.sleep(0.3)
    
    # Quay về 0
    control_servo(0, action="home")
    time.sleep(0.5)
    
    print("✅ Servo test completed")

def test_fire_scenario():
    """Test kịch bản cháy"""
    print("🧪 Testing fire scenario")
    
    # Phát hiện lửa ở vị trí 60%
    result = ai_control_fire_detection(60, 85, "test_fire")
    print(f"Fire control result: {result}")
    
    time.sleep(3)
    
    # An toàn
    result = ai_control_safe()
    print(f"Safe control result: {result}")

# ====================================
# INIT WHEN DJANGO RUNSERVER
# ====================================

if IS_RUNSERVER:
    print("🔥 MQTT: Initializing for Django runserver...")
    # Khởi tạo client nhưng không block
    import threading
    def init_mqtt_async():
        time.sleep(3)  # Chờ Django khởi động xong
        print("🔄 MQTT: Starting async initialization...")
        get_client()
    
    thread = threading.Thread(target=init_mqtt_async, daemon=True)
    thread.start()

# ====================================
# DISCONNECT
# ====================================

def disconnect():
    """Ngắt kết nối MQTT"""
    global _mqtt_client, _is_connected
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
        _is_connected = False
        print("👋 MQTT disconnected")

# ====================================
# CALLBACK REGISTRATION
# ====================================

def register_callback(topic, callback):
    """Đăng ký callback cho topic cụ thể"""
    if topic not in _message_callbacks:
        _message_callbacks[topic] = []
    _message_callbacks[topic].append(callback)
    print(f"📝 Registered callback for {topic}")

def unregister_callback(topic, callback):
    """Hủy đăng ký callback"""
    if topic in _message_callbacks:
        if callback in _message_callbacks[topic]:
            _message_callbacks[topic].remove(callback)
            print(f"📝 Unregistered callback for {topic}")