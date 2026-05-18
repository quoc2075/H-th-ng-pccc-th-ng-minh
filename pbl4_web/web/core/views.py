from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib import messages

import cv2
import numpy as np
import csv
from datetime import datetime
import json
import logging
import time
import threading
import queue

from .models import User, Alert, Device, EventLog
from .mqtt_utils import publish as mqtt_publish
from .detector import RTSP_URL, get_ai_overall_status, start_detector, set_state_change_callback

from .mqtt_utils import control_relay1, control_relay2, control_servo
logger = logging.getLogger(__name__)

# ===========================
# SSE STATE MANAGEMENT - ULTRA OPTIMIZED
# ===========================
_sse_state_queue = queue.Queue()
_current_sse_state = "safe"
_sse_lock = threading.Lock()

# 🔥 THÊM: Event để đánh thức SSE clients ngay lập tức
_sse_event = threading.Event()

_last_fire_state = False
_fire_start_time = 0
_safe_start_time = 0
SAFE_TIMEOUT = 5  # 5 giây an toàn mới tắt hệ thống

def _detector_state_callback(state_dict):
    """
    Callback từ AI detector - Tự động điều khiển thiết bị
    """
    global _current_sse_state, _last_fire_state, _fire_start_time, _safe_start_time
    
    try:
        is_fire = state_dict.get('state', False)
        event_type = "fire" if is_fire else "safe"
        
        # === XỬ LÝ FIRE STATE ===
        if is_fire:
            # Reset safe timer
            _safe_start_time = 0
            
            # Nếu mới chuyển từ safe → fire
            if not _last_fire_state:
                print(f"🔥 FIRE DETECTED: Auto-activating system")
                _fire_start_time = time.time()
                
                # 🔥 TỰ ĐỘNG BẬT HỆ THỐNG
                control_relay1(True)  # Bật còi + đèn
                control_relay2(True)  # Bật bơm
                
                # Servo sẽ được điều khiển bởi mqtt_utils._handle_ai_detection
                
            _last_fire_state = True
        
        # === XỬ LÝ SAFE STATE ===
        else:
            # Nếu mới chuyển từ fire → safe
            if _last_fire_state:
                print(f"✅ SAFE DETECTED: Starting safe timeout ({SAFE_TIMEOUT}s)")
                _safe_start_time = time.time()
            
            # Kiểm tra timeout
            if _safe_start_time > 0:
                safe_duration = time.time() - _safe_start_time
                
                if safe_duration >= SAFE_TIMEOUT:
                    print(f"🔄 AUTO SHUTDOWN: {SAFE_TIMEOUT}s safe → Turning OFF system")
                    
                    # 🔥 TỰ ĐỘNG TẮT HỆ THỐNG
                    control_relay2(False)  # Tắt bơm (servo sẽ tự động reset trong mqtt_utils)
                    control_relay1(False)  # Tắt còi + đèn
                    control_servo(0, action="home")  # Chắc chắn servo về 0
                    
                    # Reset states
                    _last_fire_state = False
                    _fire_start_time = 0
                    _safe_start_time = 0
        
        # === CẬP NHẬT SSE STATE ===
        with _sse_lock:
            old_state = _current_sse_state
            _current_sse_state = event_type
        
        if old_state != event_type:
            _sse_state_queue.put(event_type)
            _sse_event.set()
            print(f"⚡ SSE: State changed {old_state} → {event_type}")
        
    except Exception as e:
        print(f"❌ Callback error: {e}")
        import traceback
        traceback.print_exc()
        
# Đăng ký callback khi module load
set_state_change_callback(_detector_state_callback)
print("✅ SSE callback registered with detector")

# ===========================
# SSE ENDPOINT - ULTRA FAST RESPONSE
# ===========================
def sse_alerts(request):
    """
    SSE endpoint - Tối ưu hóa độ trễ xuống < 100ms
    🔥 KEY CHANGES:
    - Dùng threading.Event thay vì sleep cố định
    - Timeout queue.get() = 0.1s thay vì non-blocking
    - Bỏ polling backup (không cần thiết nếu callback hoạt động)
    """
    def event_stream():
        print("🔥 SSE: Client connected")
        
        # Gửi initial state
        with _sse_lock:
            initial_state = _current_sse_state
        yield f"data: {initial_state}\n\n"
        print(f"📡 SSE: Sent initial state = {initial_state}")
        
        last_sent_state = initial_state
        heartbeat_counter = 0
        
        while True:
            try:
                # 🔥 WAIT FOR EVENT WITH TIMEOUT
                # Thay vì sleep cố định 0.5s, chờ event hoặc timeout 0.5s
                _sse_event.wait(timeout=0.5)
                _sse_event.clear()  # Reset event
                
                # 1. Check queue với timeout ngắn
                try:
                    new_state = _sse_state_queue.get(timeout=0.1)
                    if new_state != last_sent_state:
                        yield f"data: {new_state}\n\n"
                        print(f"⚡ SSE: State change sent → {new_state} (instant)")
                        last_sent_state = new_state
                        heartbeat_counter = 0  # Reset heartbeat
                        continue  # Gửi ngay, không đợi
                except queue.Empty:
                    pass
                
                # 2. Heartbeat mỗi 10 lần (~5s)
                heartbeat_counter += 1
                if heartbeat_counter >= 10:
                    yield f": heartbeat\n\n"
                    heartbeat_counter = 0
                    
                    # Safety check: Đồng bộ với detector state
                    current_detector_state = get_ai_overall_status()
                    current_state_str = "fire" if current_detector_state else "safe"
                    
                    if current_state_str != last_sent_state:
                        yield f"data: {current_state_str}\n\n"
                        print(f"⚠️ SSE: Sync correction → {current_state_str}")
                        last_sent_state = current_state_str
                
            except GeneratorExit:
                print("🔌 SSE: Client disconnected")
                break
            except Exception as e:
                print(f"⚠️ SSE error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    
    return response

# ==========================
# ĐĂNG KÝ
# ==========================
#def register_view(request):
#    if request.method == "POST":
#        username = request.POST.get("username", "").strip()
#        password = request.POST.get("password", "").strip()

#        if not username or not password:
  #          return render(request, "register.html", {"error": "Thiếu username hoặc password"})

 #       if User.objects.filter(username=username).exists():
 #           return render(request, "register.html", {"error": "Tài khoản đã tồn tại"})

#        User.objects.create_user(username=username, password=password, role="user")
 #       return redirect("login")

#    return render(request, "register.html")

# ==========================
# ĐĂNG NHẬP / ĐĂNG XUẤT
# ==========================
def login_view(request):
    if request.method == "POST":
        u = request.POST.get("username")
        p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            try:
                start_detector()
            except Exception as e:
                print(f"⚠️ AI detector start failed: {e}")
            return redirect("dashboard")
        return render(request, "login.html", {"error": "Sai tài khoản hoặc mật khẩu"})

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")

# ==========================
# DASHBOARD
# ==========================
@login_required
def dashboard_view(request):
    alerts = Alert.objects.order_by("-created_at")
    ai_status = "danger" if get_ai_overall_status() else "safe"
    
    from .mqtt_utils import get_latest_sensor_data
    sensor_data = get_latest_sensor_data()

    if request.user.role == "admin":
        devices = Device.objects.all()
        users = User.objects.all().order_by("id")
        return render(request, "dashboard_admin.html", {
            "alerts": alerts,
            "devices": devices,
            "users": users,
            "ai_status": ai_status,
            "sensor_data": sensor_data,
        })

    return render(request, "dashboard_user.html", {
        "alerts": alerts,
        "ai_status": ai_status,
        "sensor_data": sensor_data,
    })

def crop_left_black(frame, threshold=10):
    """
    Tự động cắt vùng đen bên trái của frame
    threshold: độ sáng (0–255), < threshold coi là đen
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    cut_x = 0
    for x in range(w):
        col_mean = gray[:, x].mean()
        if col_mean > threshold:   # gặp ảnh thật
            cut_x = x
            break

    if cut_x > 0:
        frame = frame[:, cut_x:w]

    return frame


# ==========================
# STREAM CAMERA
# ==========================
@login_required
def opencv_mjpeg_stream(request):
    if not request.user.can_view_cam:
        return HttpResponse("⛔ Bạn không có quyền xem camera", status=403)

    # ==========================================
    # 🔥 CROP THEO VÙNG ẢNH THẬT (CHUẨN NHẤT)
    # ==========================================
    def crop_valid_region(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Threshold để tách nền tối / padding
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)

        # Morphology để gộp vùng ảnh
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Tìm contour lớn nhất (vùng ảnh thật)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return frame

        # Contour lớn nhất
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)

        # Tránh crop quá nhỏ / sai
        if w < frame.shape[1] * 0.5:
            return frame

        return frame[y:y+h, x:x+w]

    def generate():
        cap = None
        retry_count = 0
        max_retries = 3
        frame_count = 0

        while retry_count < max_retries:
            try:
                cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

                if not cap.isOpened():
                    print("❌ OpenCV cannot open RTSP stream")
                    retry_count += 1
                    time.sleep(2)
                    continue

                print("✅ OpenCV MJPEG stream started")

                while True:
                    success, frame = cap.read()
                    if not success:
                        print("⚠️ OpenCV frame read failed")
                        break

                    frame_count += 1

                    if frame_count % 30 == 0:
                        h, w, _ = frame.shape
                        print(f"📹 RAW FRAME: {w} x {h}")

                    # 🔥 FIX LỆCH KHUNG (CROP THEO ẢNH THẬT)
                    frame = crop_valid_region(frame)

                    # Resize sau khi crop
                    frame = cv2.resize(frame, (1280, 720))

                    ok, jpeg = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 70]
                    )

                    if not ok:
                        yield get_error_frame_bytes("Encode Error")
                        continue

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + jpeg.tobytes() +
                        b"\r\n"
                    )

                    time.sleep(0.03)

            except Exception as e:
                print(f"❌ OpenCV stream error: {e}")
                yield get_error_frame_bytes("Camera Error")
                retry_count += 1
                time.sleep(2)

            finally:
                if cap and cap.isOpened():
                    cap.release()

        yield get_error_frame_bytes("Stream disconnected")

    return StreamingHttpResponse(
        generate(),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )

def get_error_frame_bytes(message="Camera Error"):
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(img, message, (50, 150), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, "RTSP: 172.20.10.5", (30, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    success, jpeg = cv2.imencode('.jpg', img)
    return b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + (jpeg.tobytes() if success else b'') + b'\r\n'

# ==========================
# THIẾT BỊ — MQTT
# ==========================
@login_required
def device_command(request, device_id):
    if request.method != "POST":
        return HttpResponse(status=405)

    if request.user.role != "admin":
        return HttpResponse("🚫 Không có quyền điều khiển", status=403)

    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return HttpResponse("Thiết bị không tồn tại", status=404)

    action = request.POST.get("action")
    payload_map = {
        "pump_on": "PUMP_ON",
        "pump_off": "PUMP_OFF",
        "left": "ROTATE_LEFT",
        "right": "ROTATE_RIGHT",
        "stop": "ROTATE_STOP",
        "light_on": json.dumps({"light": 1}),
        "light_off": json.dumps({"light": 0}),
        "speaker_on": json.dumps({"speaker": 1}),
        "speaker_off": json.dumps({"speaker": 0}),
        
    }
    payload = payload_map.get(action)
    if not payload:
        return HttpResponse("Tham số action không hợp lệ", status=400)
    if action.startswith("light"):
        ok = mqtt_publish("pccc/esp32/light", payload)
    elif action.startswith("speaker"):
        ok = mqtt_publish("pccc/esp32/speaker", payload)
    else:
        ok = mqtt_publish(device.mqtt_topic_cmd, payload)


    ok = mqtt_publish(device.mqtt_topic_cmd, payload)
    EventLog.objects.create(
        category="device_cmd",
        message=f"{request.user.username} -> {device.name}: {payload}",
        meta={"device_id": device.id, "action": action, "ok": ok},
    )
    return redirect("dashboard")

@login_required
def device_set_mode(request, device_id):
    if request.method != "POST":
        return HttpResponse(status=405)
    if request.user.role != "admin":
        return HttpResponse("🚫 Không có quyền điều khiển", status=403)
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return HttpResponse("Thiết bị không tồn tại", status=404)

    mode = request.POST.get("mode")
    if mode not in ("auto", "manual"):
        return HttpResponse("Tham số mode không hợp lệ", status=400)

    device.mode_auto = (mode == "auto")
    device.save(update_fields=["mode_auto"])
    ok = mqtt_publish(device.mqtt_topic_cmd, "MODE_AUTO" if device.mode_auto else "MODE_MANUAL")
    EventLog.objects.create(
        category="device_mode",
        message=f"{request.user.username} đặt {device.name} -> {mode}",
        meta={"device_id": device.id, "mode": mode, "ok": ok},
    )
    return redirect("dashboard")

# ==========================
# API ENDPOINTS
# ==========================
@csrf_exempt
def api_pccc_data(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body)
        print(f"📊 Sensor Data: {payload}")
        return JsonResponse({"status": "success", "received": True})
    except Exception as e:
        print(f"❌ API data error: {e}")
        return JsonResponse({"error": "Invalid data"}, status=400)

@csrf_exempt
def api_pccc_alert(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body)
        print(f"🚨 Alert Received: {payload}")
        
        alert_type = payload.get('type', 'unknown')
        message = f"Alert: {alert_type}"
        
        Alert.objects.create(
            cls=alert_type,
            confidence=payload.get('conf', 0),
            message=message
        )
        
        return JsonResponse({"status": "alert_processed"})
    except Exception as e:
        print(f"❌ API alert error: {e}")
        return JsonResponse({"error": "Invalid alert data"}, status=400)

# ==========================
# ADMIN USER MANAGEMENT
# ==========================
@login_required
def admin_user_add(request):
    if request.user.role != "admin":
        return HttpResponse("Forbidden", status=403)

    if request.method == "POST":
        try:
            User.objects.create_user(
                username=request.POST["username"],
                password=request.POST["password"],
                email=request.POST.get("email", ""),
                role=request.POST.get("role", "user")
            )
            messages.success(request, "Tạo tài khoản thành công!")
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, f"Lỗi tạo tài khoản: {e}")
            return redirect("dashboard")
    
    return HttpResponse("Method not allowed", status=405)
@login_required
def admin_user_edit(request, uid):
    if request.user.role != "admin":
        return HttpResponse("Forbidden", status=403)

    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    try:
        user = User.objects.get(id=uid)

        # Cập nhật email, role
        user.email = request.POST.get("email", user.email)
        user.role = request.POST.get("role", user.role)

        user.can_view_cam = bool(request.POST.get("can_view_cam"))

        # Nếu có password mới thì cập nhật
        new_password = request.POST.get("password", "").strip()
        if new_password:
            user.set_password(new_password)

        user.save()
        messages.success(request, "Cập nhật tài khoản thành công!")
    except Exception as e:
        messages.error(request, f"Lỗi cập nhật: {e}")

    return redirect("dashboard")


@login_required
def admin_user_delete(request, uid):
    if request.user.role != "admin":
        return HttpResponse("Forbidden", status=403)

    try:
        user = User.objects.get(id=uid)
        if user == request.user:
            messages.error(request, "Không thể xóa tài khoản của chính mình!")
        else:
            user.delete()
            messages.success(request, "Xóa tài khoản thành công!")
    except Exception as e:
        messages.error(request, f"Lỗi xóa tài khoản: {e}")
    
    return redirect("dashboard")

# ==========================
# EXPORT UTILITIES
# ==========================
@login_required
def export_events_csv(request):
    if request.user.role != "admin":
        return HttpResponse("Forbidden", status=403)

    start_str = request.GET.get("start")
    end_str = request.GET.get("end")
    qs = EventLog.objects.all().order_by("-created_at")

    def parse_dt(s: str):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    if start_str:
        dt = parse_dt(start_str)
        if dt:
            qs = qs.filter(created_at__gte=dt)
    if end_str:
        dt = parse_dt(end_str)
        if dt:
            qs = qs.filter(created_at__lte=dt)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="event_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(["Time", "Category", "Message", "Meta Data"])
    
    for e in qs.iterator():
        writer.writerow([
            timezone.localtime(e.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            e.category,
            e.message,
            e.meta,
        ])
    
    return response

# ==========================
# SYSTEM STATUS API
# ==========================
@login_required
def system_status_api(request):
    from .mqtt_utils import get_system_status, get_latest_sensor_data
    
    status = {
        "ai_detector": get_ai_overall_status(),
        "mqtt": get_system_status(),
        "sensors": get_latest_sensor_data(),
        "alerts_count": Alert.objects.count(),
        "timestamp": timezone.now().isoformat()
    }
    
    return JsonResponse(status)

@login_required
def light_on(request):
    """Bật đèn + còi qua Relay 1"""
    from .mqtt_utils import control_light_buzzer
    control_light_buzzer(True)
    return JsonResponse({"device": "light+buzzer", "state": "ON", "relay": "relay1"})

@login_required
def light_off(request):
    """Tắt đèn + còi qua Relay 1"""
    from .mqtt_utils import control_light_buzzer
    control_light_buzzer(False)
    return JsonResponse({"device": "light+buzzer", "state": "OFF", "relay": "relay1"})

@login_required
def buzzer_on(request):
    """Bật đèn + còi qua Relay 1 (có thời gian tự động tắt)"""
    from .mqtt_utils import control_light_buzzer
    duration = request.GET.get("duration")
    if duration:
        control_light_buzzer(True, int(duration))
    else:
        control_light_buzzer(True)
    return JsonResponse({"device": "light+buzzer", "state": "ON", "relay": "relay1", "duration": duration})

@login_required
def buzzer_off(request):
    """Tắt đèn + còi qua Relay 1"""
    from .mqtt_utils import control_light_buzzer
    control_light_buzzer(False)
    return JsonResponse({"device": "light+buzzer", "state": "OFF", "relay": "relay1"})

@login_required
def api_control_pump_on(request):
    """API bật máy bơm"""
    from .mqtt_utils import control_pump
    success = control_pump(True)
    return JsonResponse({
        "device": "pump",
        "state": "ON",
        "success": success,
        "timestamp": time.time()
    })

@login_required
def api_control_pump_off(request):
    """API tắt máy bơm"""
    from .mqtt_utils import control_pump
    success = control_pump(False)
    return JsonResponse({
        "device": "pump",
        "state": "OFF",
        "success": success,
        "timestamp": time.time()
    })
    
    
@login_required
def emergency_stop(request):
    """Dừng khẩn cấp tất cả thiết bị"""
    from .mqtt_utils import emergency_stop as mqtt_emergency_stop
    
    result = mqtt_emergency_stop()
    
    return JsonResponse({
        "status": "emergency_stop",
        "message": "Hệ thống đã dừng khẩn cấp",
        "result": result,
        "timestamp": time.time()
    })    