import threading
import time
import logging
import json
import os

from django.conf import settings
from django.db import close_old_connections

# ===========================
# MQTT IMPORT
# ===========================
try:
    from core.mqtt_utils import publish as mqtt_publish
    MQTT_AVAILABLE = True
    print("✅ MQTT imported successfully")
except Exception as e:
    print(f"❌ MQTT import failed: {e}")
    MQTT_AVAILABLE = False
    def mqtt_publish(topic, payload):
        print(f"📤 MQTT DUMMY: Would publish to {topic}: {payload}")
        return True

logger = logging.getLogger(__name__)

# ===========================
# AI IMPORTS
# ===========================
try:
    from ultralytics import YOLO
    import cv2
    AI_DEPS_AVAILABLE = True
    print("✅ AI dependencies loaded")
except Exception as exc:
    YOLO = None
    cv2 = None
    AI_DEPS_AVAILABLE = False
    logger.error("❌ AI dependencies missing: %s", exc)

# ===========================
# CAMERA CONFIGURATION
# ===========================
RTSP_URL = "rtsp://Bong2625:06062005@172.20.10.5:554/stream2"

RTSP_FALLBACKS = [
    "rtsp://Bong2625:06062005@172.20.10.5:554/stream2",
    "rtsp://Bong2625:06062005@172.20.10.5:554/stream1",
]

_model = None
_thread = None
_stop_event = threading.Event()

# ===========================
# 🔥 STATE MANAGEMENT - OPTIMIZED
# ===========================
_last_state = False  # False = safe, True = fire
_last_alert_ts = 0.0
_last_box = None
_camera_retry_count = 0
_max_camera_retries = 10
_current_servo_angle = 90  # ✅ THÊM: Góc hiện tại của servo, mặc định 90°
_last_fire_activation_time = 0


# 🔥 Consecutive detection counter
_consecutive_fire_frames = 0
_consecutive_safe_frames = 0
_fire_confirmation_threshold = 3   # 3 frames = ~150ms
_safe_confirmation_threshold = 1   # 1 frame = ~50ms (nhanh chóng tắt)

poll_interval = 0.02  # 50 FPS

# STATE CALLBACK
_state_change_callback = None

def set_state_change_callback(callback_func):
    """Đăng ký callback nhận thông báo state thay đổi"""
    global _state_change_callback
    _state_change_callback = callback_func
    print("✅ State change callback registered")

def _notify_state_change(is_fire, detection_type=None, confidence=0.0):
    """Gọi callback khi state thay đổi"""
    global _state_change_callback
    if _state_change_callback:
        try:
            state_dict = {
                'state': is_fire,
                'type': detection_type,
                'confidence': confidence,
                'timestamp': time.time()
            }
            _state_change_callback(state_dict)
            print(f"⚡ Callback sent: {state_dict}")
        except Exception as e:
            print(f"⚠️ Callback error: {e}")
            import traceback
            traceback.print_exc()

# ===========================
# LOAD YOLO MODEL
# ===========================
def _load_model():
    global _model
    if _model is not None:
        return _model

    model_path = getattr(settings, "AI_MODEL_PATH", "best2.pt")
    try:
        if not os.path.exists(model_path):
            print(f"❌ Model file not found: {model_path}")
            return None
            
        model = YOLO(model_path)
        model.fuse()
        _model = model
        print("✅ YOLO model loaded successfully")
        print(f"   Model classes: {model.names}")
        return model
    except Exception as exc:
        print(f"❌ Load YOLO failed: {exc}")
        return None

# ===========================
# CAMERA UTILITIES
# ===========================
def _create_capture_with_options(rtsp_url):
    print(f"🔄 Attempting camera connection: {rtsp_url}")
    
    cap = cv2.VideoCapture()
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 30000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
    
    try:
        if not cap.open(rtsp_url):
            print(f"❌ Cannot open stream: {rtsp_url}")
            return None
            
        for i in range(5):
            success, frame = cap.read()
            if success and frame is not None:
                h, w = frame.shape[:2]
                print(f"✅ Camera connected: {w}x{h}")
                return cap
            time.sleep(0.2)
            
        print("❌ Camera connected but no frames")
        cap.release()
        return None
        
    except Exception as e:
        print(f"❌ Camera connection error: {e}")
        if cap.isOpened():
            cap.release()
        return None

def _connect_to_camera():
    global _camera_retry_count
    
    for i, rtsp_url in enumerate(RTSP_FALLBACKS):
        print(f"📡 Trying camera {i+1}/{len(RTSP_FALLBACKS)}: {rtsp_url}")
        cap = _create_capture_with_options(rtsp_url)
        if cap is not None:
            _camera_retry_count = 0
            return cap
        time.sleep(1)
    
    _camera_retry_count += 1
    print(f"⚠️ All camera connections failed (retry {_camera_retry_count}/{_max_camera_retries})")
    return None

def _get_frame(cap):
    if not cap or not cap.isOpened():
        return None, False

    try:
        success, frame = cap.read()
        
        if not success or frame is None:
            return None, False
        
        h, w = frame.shape[:2]
        if w > 1280:
            frame = cv2.resize(frame, (1280, 720))
        
        return frame, True
        
    except Exception as e:
        print(f"⚠️ Error reading frame: {e}")
        return None, False

# ===========================
# YOLO DETECT
# ===========================
def _run_yolo(model, frame):
    global _last_box

    try:
        results = model(
            frame, 
            verbose=False, 
            conf=getattr(settings, "AI_CONF_THRESHOLD", 0.25),
            imgsz=640
        )

        best_conf = 0.0
        best_cls = None
        best_box = None

        for r in results:
            if not hasattr(r, "boxes") or r.boxes is None:
                continue

            for b in r.boxes:
                cls_id = int(b.cls)
                cls_name = model.names[cls_id]
                conf = float(b.conf)

                if cls_name not in ("fire", "smoke"):
                    continue

                if conf > best_conf:
                    best_conf = conf
                    best_cls = cls_name
                    best_box = b.xyxy[0].tolist()

        if best_cls is None:
            _last_box = None
            return False, None, 0.0

        _last_box = best_box
        return True, best_cls, best_conf
        
    except Exception as e:
        print(f"❌ YOLO detection error: {e}")
        return False, None, 0.0

# ===========================
# 🔥 DEVICE CONTROL - FIXED
# ===========================


# ===========================
# 🔥 DEVICE CONTROL - FIXED
# ===========================

def _activate_fire_response(cls_name, confidence):
    """
    Kích hoạt hệ thống khi phát hiện lửa
    ✅ UPDATED: Góc mặc định 90°, quay đến vị trí lửa với camera 105°
    FIXED: Đã sửa lỗi mapping góc servo
    """
    try:
        from django.utils.timezone import now
        
        now_ts = time.time()
        log_time = now().strftime("%H:%M:%S.%f")[:-3]
        
        print(f"\n{'='*60}")
        print(f"🚨 [{log_time}] FIRE RESPONSE ACTIVATED")
        print(f"   Type: {cls_name}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"{'='*60}")
        
        # ===========================================
        # 1. CALCULATE SERVO ANGLE FROM FIRE POSITION
        # ===========================================
        default_angle = 90  # ✅ GÓC MẶC ĐỊNH LÀ 90° (giữa)
        target_angle = default_angle
        fire_position = 0
        
        if _last_box:
            x1, y1, x2, y2 = _last_box
            center_x = int((x1 + x2) / 2)
            frame_width = 1280  # Giả sử frame width cố định
            
            # Tính vị trí lửa (0-100%)
            fire_position = int((center_x / frame_width) * 100)
            fire_position = max(0, min(100, fire_position))
            
            # ===========================================
            # TÍNH TOÁN GÓC SERVO CHO CAMERA 105° - ĐÃ FIX
            # ===========================================
            # Camera: 105° (52.5° mỗi bên từ vị trí giữa)
            # Servo: 180° (0-180°)
            # Logic đúng:
            # - Lửa ở TRÁI (0%) → Servo quay PHẢI (142.5°)
            # - Lửa ở GIỮA (50%) → Servo quay GIỮA (90°)
            # - Lửa ở PHẢI (100%) → Servo quay TRÁI (37.5°)
            # ===========================================
            
            # Tính tỉ lệ vị trí lửa (0.0 đến 1.0)
            ratio = center_x / frame_width
            
            # Vì camera và servo ngược hướng:
            # Camera thấy TRÁI thì servo phải quay PHẢI
            inverted_ratio = 1.0 - ratio
            
            # Chuyển đổi sang góc nhìn camera (-52.5° đến +52.5°)
            # Nhưng đảo ngược cho đúng servo
            camera_angle = (inverted_ratio - 0.5) * 105  # -52.5° đến +52.5°
            
            # Chuyển đổi sang góc servo (37.5° đến 142.5°)
            target_angle = 90 + camera_angle
            
            # Đảm bảo góc trong phạm vi 37.5° - 142.5°
            target_angle = max(37.5, min(142.5, target_angle))
            target_angle = int(target_angle)  # Chuyển thành số nguyên
            
            # Thông tin debug
            print(f"   🔥 Fire Position: X={center_x}px ({fire_position}%)")
            print(f"   🔄 Ratio: {ratio:.2f} → Inverted: {inverted_ratio:.2f}")
            print(f"   📐 Camera Angle: {camera_angle:.1f}°")
            print(f"   🎯 Servo Target: {target_angle}° (Range: 37.5°-142.5°)")
            print(f"   📷 Camera FOV: 105° (Center: 90°)")
            
            # Hiển thị mapping trực quan
            print(f"   📍 Mapping:")
            if ratio <= 0.2:
                print(f"      Fire: LEFT   ({fire_position}%) → Servo: RIGHT  ({target_angle}°)")
            elif ratio >= 0.8:
                print(f"      Fire: RIGHT  ({fire_position}%) → Servo: LEFT   ({target_angle}°)")
            else:
                print(f"      Fire: CENTER ({fire_position}%) → Servo: CENTER ({target_angle}°)")
                
        else:
            print(f"   🎯 Servo Target: {target_angle}° (Default position)")
        
        # ===========================================
        # 2. ACTIVATE RELAY 1 (LIGHT + BUZZER)
        # ===========================================
        print("   ⚡ Sending Relay1 ON command...")
        
        relay1_payload = {
            "relay1": 1,  # ✅ INT value, not string
            "timestamp": now_ts,
            "source": "ai_fire",
            "fire_type": cls_name,
            "camera_fov": 105  # Thêm thông tin góc nhìn camera
        }
        
        relay1_success = mqtt_publish("pccc/esp32/relay", json.dumps(relay1_payload))
        
        if relay1_success:
            print("   ✅ 💡🔊 Relay1 ON (Light+Buzzer)")
        else:
            print("   ❌ Relay1 command failed!")
        
        # ===========================================
        # 3. ACTIVATE RELAY 2 (PUMP) 
        # ===========================================
        print("   ⚡ Sending Relay2 ON command...")
        
        relay2_payload = {
            "relay2": 1,
            "timestamp": now_ts,
            "source": "ai_fire",
            "fire_position": fire_position,
            "servo_target_angle": target_angle,
            "servo_direction": "right" if target_angle > 90 else "left" if target_angle < 90 else "center"
        }
        
        relay2_success = mqtt_publish("pccc/esp32/relay", json.dumps(relay2_payload))
        
        if relay2_success:
            print("   ✅ 💧 Relay2 ON (Pump)")
        else:
            print("   ❌ Relay2 command failed!")
        
        # ===========================================
        # 4. CONTROL SERVO TO FIRE POSITION
        # ===========================================
        print(f"   ⚡ Sending Servo command: {target_angle}°...")
        
        servo_payload = {
            "servo_pan": target_angle,
            "action": "aim_fire",
            "timestamp": now_ts,
            "fire_position": fire_position,
            "confidence": round(confidence, 2),
            "default_position": default_angle,
            "camera_fov": 105,
            "servo_range": "37.5-142.5",  # Phạm vi thực tế cho camera 105°
            "direction": "right" if target_angle > 90 else "left" if target_angle < 90 else "center"
        }
        
        servo_success = mqtt_publish("pccc/esp32/servo", json.dumps(servo_payload))
        
        if servo_success:
            print(f"   ✅ 🎯 Servo: {target_angle}° (Aiming fire)")
            print(f"   📊 Servo Range: 37.5° (left) ← 90° (center) → 142.5° (right)")
            print(f"   🔄 Note: Camera sees OPPOSITE direction (mirrored)")
        else:
            print("   ❌ Servo command failed!")
        
        # ===========================================
        # 5. UPDATE GLOBAL STATE
        # ===========================================
        global _last_fire_activation_time, _current_servo_angle
        _last_fire_activation_time = now_ts
        _current_servo_angle = target_angle  # Lưu góc hiện tại
        
        # ===========================================
        # 6. SEND AI ALERT TO DASHBOARD
        # ===========================================
        print("   ⚡ Sending alert to dashboard...")
        
        alert_payload = {
            "type": cls_name,
            "conf": round(confidence, 2),
            "state": "fire",
            "timestamp": now_ts,
            "fire_position": fire_position,
            "servo_angle": target_angle,
            "default_angle": default_angle,
            "source": "ai_detector",
            "camera_fov": 105,
            "servo_range_min": 37.5,
            "servo_range_max": 142.5,
            "servo_direction": "right" if target_angle > 90 else "left" if target_angle < 90 else "center"
        }
        
        alert_success = mqtt_publish("pccc/alert", json.dumps(alert_payload))
        
        if alert_success:
            print("   ✅ 📡 Alert sent to dashboard")
        else:
            print("   ❌ Alert sending failed!")
        
        # ===========================================
        # 7. LOG TO DATABASE
        # ===========================================
        try:
            from core.models import EventLog
            
            EventLog.objects.create(
                category="ai_fire_activated",
                message=f"AI activated fire response: {cls_name} ({confidence:.2f})",
                meta={
                    "fire_type": cls_name,
                    "confidence": confidence,
                    "fire_position": fire_position,
                    "servo_angle": target_angle,
                    "default_angle": default_angle,
                    "camera_fov": 105,
                    "servo_range": "37.5-142.5",
                    "servo_direction": "right" if target_angle > 90 else "left" if target_angle < 90 else "center",
                    "relay1_success": relay1_success,
                    "relay2_success": relay2_success,
                    "servo_success": servo_success
                }
            )
            print("   ✅ 📝 Event logged to database")
            
        except Exception as db_error:
            print(f"   ⚠️  Database log error: {db_error}")
        
        # ===========================================
        # 8. SUMMARY
        # ===========================================
        print(f"\n   📊 ACTIVATION SUMMARY:")
        print(f"      • Fire Type: {cls_name}")
        print(f"      • Confidence: {confidence:.2f}")
        print(f"      • Fire Position: {fire_position}%")
        print(f"      • Servo Angle: {target_angle}°")
        print(f"      • Servo Direction: {'RIGHT' if target_angle > 90 else 'LEFT' if target_angle < 90 else 'CENTER'}")
        print(f"      • Camera FOV: 105°")
        print(f"      • Relay1: {'ON' if relay1_success else 'FAILED'}")
        print(f"      • Relay2: {'ON' if relay2_success else 'FAILED'}")
        print(f"      • Servo: {'OK' if servo_success else 'FAILED'}")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "relay1": relay1_success,
            "relay2": relay2_success,
            "servo": servo_success,
            "servo_angle": target_angle,
            "default_angle": default_angle,
            "fire_position": fire_position,
            "camera_fov": 105,
            "servo_range_min": 37.5,
            "servo_range_max": 142.5,
            "servo_direction": "right" if target_angle > 90 else "left" if target_angle < 90 else "center",
            "timestamp": now_ts
        }
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in fire response activation: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }
def _deactivate_fire_response():
    """
    Tắt hệ thống khi an toàn
    ✅ UPDATED: Reset servo về vị trí mặc định 90° (không phải 0°)
    """
    try:
        print(f"\n{'='*60}")
        print(f"🔄 DEACTIVATING FIRE RESPONSE")
        print(f"{'='*60}")
        
        now_ts = time.time()
        default_angle = 90  # ✅ VỊ TRÍ MẶC ĐỊNH LÀ 90°
        
        # 1. ✅ TẮT RELAY 2 (MÁY BƠM) - TRƯỚC
        print("   ⚡ Tắt máy bơm...")
        mqtt_publish("pccc/esp32/relay", json.dumps({
            "relay2": 0,
            "timestamp": now_ts,
            "action": "pump_off_safe"
        }))
        print("✅ 💧 Relay2 OFF (Pump)")
        
        # 2. ✅ RESET SERVO VỀ VỊ TRÍ MẶC ĐỊNH 90° SAU KHI TẮT BƠM
        print(f"   ⚡ Đưa servo về vị trí mặc định {default_angle}°...")
        mqtt_publish("pccc/esp32/servo", json.dumps({
            "servo_pan": default_angle,  # ✅ Reset về 90° như yêu cầu
            "action": "return_to_default",
            "timestamp": now_ts,
            "default_position": True
        }))
        print(f"✅ 🎯 Servo: Reset to default position ({default_angle}°)")
        
        # 3. ✅ TẮT RELAY 1 (ĐÈN + CÒI) - SAU KHI SERVO ĐÃ VỀ VỊ TRÍ
        print("   ⚡ Tắt đèn và còi...")
        mqtt_publish("pccc/esp32/relay", json.dumps({
            "relay1": 0,
            "timestamp": now_ts,
            "action": "lights_off_safe"
        }))
        print("✅ 💡🔊 Relay1 OFF (Light+Buzzer)")
        
        # 4. ✅ UPDATE GLOBAL STATE
        global _current_servo_angle
        _current_servo_angle = default_angle
        
        # 5. ✅ GỬI SAFE ALERT
        mqtt_publish("pccc/alert", json.dumps({
            "type": "safe",
            "state": "safe",
            "timestamp": now_ts,
            "servo_returned_to_default": True,
            "default_angle": default_angle
        }))
        print("✅ 📡 Safe alert sent")
        
        # 6. ✅ LOG TO DATABASE
        try:
            from core.models import EventLog
            
            EventLog.objects.create(
                category="ai_safe_activated",
                message=f"System returned to safe state - Servo at {default_angle}°",
                meta={
                    "default_angle": default_angle,
                    "action": "system_safe"
                }
            )
            print("   ✅ 📝 Event logged to database")
            
        except Exception as db_error:
            print(f"   ⚠️  Database log error: {db_error}")
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error deactivating: {e}")
        import traceback
        traceback.print_exc()
        

# ===========================
# 🔥 MAIN LOOP - ULTRA FAST & CLEAN
# ===========================
def _loop():
    global _last_state, _last_alert_ts, _camera_retry_count
    global _consecutive_fire_frames, _consecutive_safe_frames

    if not AI_DEPS_AVAILABLE:
        print("❌ AI disabled: missing dependencies")
        return

    model = _load_model()
    if model is None:
        print("❌ AI model failed to load")
        return

    cap = _connect_to_camera()
    if cap is None:
        print("❌ Cannot connect to camera")
        return

    print("🔥 AI detector started - ULTRA FAST mode")
    print("⚡ Fire: 3 frames | Safe: 1 frame | Servo reset: 0°")
    
    db_cooldown = 1.0
    last_successful_frame_time = time.time()
    consecutive_failures = 0
    frame_count = 0
    
    # 🔥 TRACKING: Đã gửi lệnh hay chưa (tránh spam)
    fire_activated = False
    last_activation_time = 0
    ACTIVATION_COOLDOWN = 2.0  # 2 giây giữa các lần gửi lệnh

    while not _stop_event.is_set():
        try:
            if frame_count % 30 == 0:
                close_old_connections()

            frame, success = _get_frame(cap)
            
            if success:
                last_successful_frame_time = time.time()
                consecutive_failures = 0
                frame_count += 1
                
                if frame_count % 100 == 0:
                    status = "🔥 FIRE" if _last_state else "🟢 SAFE"
                    activated = "ACTIVE" if fire_activated else "IDLE"
                    print(f"📊 Frame {frame_count} | {status} | System: {activated}")
                
                detected, cls_name, conf = _run_yolo(model, frame)
                now_ts = time.time()

                # ===========================
                # 🔥 FIRE DETECTION
                # ===========================
                if detected:
                    _consecutive_fire_frames += 1
                    _consecutive_safe_frames = 0

                    # ✅ XÁC NHẬN FIRE - 3 FRAMES
                    if _consecutive_fire_frames >= _fire_confirmation_threshold:
                        
                        # State change: safe → fire
                        if not _last_state:
                            _last_state = True
                            print(f"\n⚡⚡⚡ FIRE DETECTED: {cls_name} ({conf:.2f}) ⚡⚡⚡")
                            _notify_state_change(True, cls_name, conf)
                        
                        # ✅ GỬI LỆNH ĐIỀU KHIỂN (CHỈ 1 LẦN)
                        if not fire_activated or (now_ts - last_activation_time > ACTIVATION_COOLDOWN):
                            _activate_fire_response(cls_name, conf)
                            fire_activated = True
                            last_activation_time = now_ts
                        
                        # LƯU DB (với cooldown)
                        if now_ts - _last_alert_ts >= db_cooldown:
                            try:
                                from core.models import Alert, EventLog
                                
                                if _last_box:
                                    x1, y1, x2, y2 = _last_box
                                    
                                    Alert.objects.create(
                                        cls=cls_name,
                                        confidence=conf,
                                        x1=x1, y1=y1, x2=x2, y2=y2,
                                    )

                                    EventLog.objects.create(
                                        category="ai_fire",
                                        message=f"FIRE: {cls_name} ({conf:.2f})",
                                        meta={"activated": fire_activated},
                                    )

                                _last_alert_ts = now_ts

                            except Exception as e:
                                print(f"⚠️ DB error: {e}")
                
                # ===========================
                # 🔥 SAFE DETECTION
                # ===========================
                else:
                    _consecutive_safe_frames += 1
                    _consecutive_fire_frames = 0
                    
                    # ✅ XÁC NHẬN SAFE - 1 FRAME
                    if _consecutive_safe_frames >= _safe_confirmation_threshold:
                        
                        # State change: fire → safe
                        if _last_state:
                            print(f"\n⚡⚡⚡ SYSTEM SAFE - No fire ⚡⚡⚡")
                            _last_state = False
                            _notify_state_change(False, None, 0.0)
                            
                            # ✅ TẮT HỆ THỐNG (CHỈ 1 LẦN)
                            if fire_activated or (now_ts - last_activation_time > ACTIVATION_COOLDOWN):
                                _deactivate_fire_response()
                                fire_activated = False
                                last_activation_time = now_ts
                
            else:
                # ===========================
                # CAMERA ERROR HANDLING
                # ===========================
                consecutive_failures += 1
                current_time = time.time()
                
                if (current_time - last_successful_frame_time > 15.0 or 
                    consecutive_failures > 10):
                    print("⚠️ Camera reconnecting...")
                    if cap.isOpened():
                        cap.release()
                    time.sleep(2)
                    
                    cap = _connect_to_camera()
                    if cap:
                        last_successful_frame_time = time.time()
                        consecutive_failures = 0
                        print("✅ Camera OK")
                    else:
                        if _camera_retry_count >= _max_camera_retries:
                            print("🚫 Max retries")
                            break
            
            time.sleep(poll_interval)
            
        except Exception as e:
            print(f"❌ Loop error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)
    
    # ===========================
    # CLEANUP ON EXIT
    # ===========================
    print("\n🛑 Stopping detector...")
    try:
        # Đưa servo về vị trí mặc định 90° trước khi tắt
        mqtt_publish("pccc/esp32/servo", json.dumps({
            "servo_pan": 90,  # ✅ Reset về 90° khi shutdown
            "action": "shutdown_reset"
        }))
        time.sleep(0.5)
        
        # Tắt tất cả thiết bị
        mqtt_publish("pccc/esp32/relay", json.dumps({
            "relay1": 0,
            "relay2": 0,
            "shutdown": True
        }))
        print("✅ All devices OFF, Servo at 90°")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")
    
    if cap and cap.isOpened():
        cap.release()
    print("🎯 Detector stopped")

# ===========================
# PUBLIC API
# ===========================
def start_detector():
    global _thread, _stop_event
    if _thread is not None and _thread.is_alive():
        print("✅ AI detector already running")
        return True

    if not AI_DEPS_AVAILABLE:
        print("❌ AI not started (missing deps)")
        return False

    if _load_model() is None:
        return False

    _stop_event.clear()
    _current_servo_angle = 90  # ✅ Reset góc về mặc định khi start
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    print("✅ AI detector thread started")
    return True

def stop_detector():
    global _stop_event
    _stop_event.set()
    print("🛑 Stopping AI detector...")

def get_ai_overall_status():
    """Trả về state hiện tại: True=fire, False=safe"""
    return bool(_last_state)

def get_camera_status():
    return _camera_retry_count < _max_camera_retries

# ===========================
# AUTO-START
# ===========================
def auto_start_detector():
    try:
        time.sleep(3)
        
        if AI_DEPS_AVAILABLE:
            print("🚀 Auto-starting AI detector...")
            start_detector()
        else:
            print("⚠️ AI dependencies not available")
    except Exception as e:
        print(f"⚠️ Auto-start failed: {e}")


def get_ai_servo_angle():
    """Trả về góc servo hiện tại"""
    return _current_servo_angle

def get_ai_overall_status():
    """Trả về state hiện tại: True=fire, False=safe"""
    return bool(_last_state)

auto_start_thread = threading.Thread(target=auto_start_detector, daemon=True)
auto_start_thread.start()