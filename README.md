# Hệ thống PCCC thông minh

Hệ thống phòng cháy chữa cháy (PCCC) tích hợp IoT, AI nhận diện lửa/khói và giao diện web quản trị. Dự án gồm backend Django, luồng Node-RED, firmware ESP32 và mô hình YOLO.

**Repository GitHub:** [https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh](https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh.git)

---

## Mục lục

1. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
2. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
3. [Cài đặt](#cài-đặt)
4. [Cấu hình](#cấu-hình)
5. [Chạy hệ thống](#chạy-hệ-thống)
6. [Đẩy project lên GitHub](#đẩy-project-lên-github)
7. [Xử lý lỗi thường gặp](#xử-lý-lỗi-thường-gặp)

---

## Cấu trúc thư mục

```
.
├── web/                 # Ứng dụng Django (dashboard, API, AI)
│   ├── manage.py
│   ├── ffsys/           # Cấu hình project Django
│   └── core/            # App chính: views, MQTT, detector
├── node-red/
│   └── flows.json       # Luồng Node-RED (MQTT, điều khiển thiết bị)
└── Code IoT/
    └── CODEFinal.ino    # Firmware ESP32 (cảm biến, relay, servo)
```

---

## Yêu cầu hệ thống

| Thành phần | Phiên bản gợi ý |
|------------|-----------------|
| Python | 3.10 trở lên |
| Django | 4.2 |
| MySQL | 8.x (hoặc MariaDB) |
| MQTT Broker | Mosquitto (cổng `1883`) |
| Node.js | 18+ (cho Node-RED) |
| Node-RED | Cài global: `npm install -g node-red` |
| FFmpeg | Dùng cho stream camera RTSP |
| Arduino IDE | Nạp firmware ESP32 |

**Thư viện Python chính:**

```bash
pip install django==4.2 mysqlclient paho-mqtt opencv-python numpy ultralytics
```

> Trên Windows, nếu `mysqlclient` lỗi, có thể dùng: `pip install pymysql` và thêm vào `web/ffsys/__init__.py`:
> `import pymysql; pymysql.install_as_MySQLdb()`

**Phần cứng / mạng:**

- ESP32 (cảm biến khói/khí, relay, servo)
- Camera IP hỗ trợ RTSP (tùy chọn, cho AI)
- File mô hình YOLO: `best2.pt` (đặt trong thư mục `web/`)

---

## Cài đặt

### 1. Clone hoặc tải mã nguồn

```bash
git clone https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh.git
cd H-th-ng-pccc-th-ng-minh
```

Nếu bạn đang có sẵn thư mục project trên máy, mở terminal tại thư mục chứa `web/`, `node-red/`, `Code IoT/`.

### 2. Tạo môi trường ảo Python

**Windows (PowerShell):**

```powershell
cd web
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install django==4.2 mysqlclient paho-mqtt opencv-python numpy ultralytics
```

**Linux / macOS:**

```bash
cd web
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install django==4.2 mysqlclient paho-mqtt opencv-python numpy ultralytics
```

### 3. Cài đặt MySQL

1. Cài [MySQL Community Server](https://dev.mysql.com/downloads/mysql/).
2. Tạo database:

```sql
CREATE DATABASE pbl4_b CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

3. (Tùy chọn) Tạo user riêng thay vì dùng `root`.

### 4. Cài MQTT Broker (Mosquitto)

**Windows:** tải từ [Eclipse Mosquitto](https://mosquitto.org/download/) và chạy service.

**Ubuntu:**

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

Kiểm tra:

```bash
mosquitto_sub -h localhost -t test -v
```

### 5. Cài Node-RED

```bash
npm install -g node-red
```

Sau khi chạy Node-RED, vào **Menu → Import** và chọn file `node-red/flows.json`, rồi **Deploy**.

### 6. Cài FFmpeg

- Windows: tải từ [ffmpeg.org](https://ffmpeg.org/download.html), thêm `ffmpeg` vào `PATH`.
- Ubuntu: `sudo apt install ffmpeg`

### 7. Nạp firmware ESP32

1. Mở `Code IoT/CODEFinal.ino` bằng Arduino IDE.
2. Cài thư viện: **WiFi**, **PubSubClient**, **ArduinoJson**, **ESP32Servo**.
3. Sửa `ssid`, `password`, `mqtt_server` cho đúng mạng và IP máy chạy Mosquitto.
4. Chọn board **ESP32** và nạp code.

---

## Cấu hình

### Database – `web/ffsys/settings.py`

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'pbl4_b',
        'USER': 'root',           # đổi nếu cần
        'PASSWORD': '',           # mật khẩu MySQL của bạn
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

### MQTT – `web/ffsys/settings.py`

```python
MQTT_CONFIG = {
    'HOST': 'localhost',
    'PORT': 1883,
    'KEEPALIVE': 60,
    'CLIENT_ID': 'Django_PCCC_System',
}
```

### Camera & AI – `web/core/detector.py`

- Cập nhật `RTSP_URL` theo camera của bạn.
- Đặt file `best2.pt` vào thư mục `web/` (hoặc chỉnh `AI_MODEL_PATH` trong settings).

### ESP32 – `Code IoT/CODEFinal.ino`

- `mqtt_server`: IP máy tính chạy Mosquitto (cùng mạng WiFi với ESP32).
- Topic MQTT chuẩn: `pccc/esp32/sensors`, `pccc/esp32/relay`, ...

> **Lưu ý bảo mật:** Không commit mật khẩu WiFi, RTSP, `SECRET_KEY` production lên GitHub. Nên dùng biến môi trường hoặc file `.env` (không đưa vào git).

---

## Chạy hệ thống

Thứ tự khuyến nghị:

### Bước 1 – Mosquitto

Đảm bảo broker MQTT đang chạy trên cổng `1883`.

### Bước 2 – Node-RED

```bash
node-red
```

Truy cập: [http://127.0.0.1:1880](http://127.0.0.1:1880) → Import `node-red/flows.json` → **Deploy**.

### Bước 3 – Django

```bash
cd web
# Kích hoạt venv (xem mục Cài đặt)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Truy cập web: [http://127.0.0.1:8000](http://127.0.0.1:8000)

- Đăng nhập: `/login/`
- Dashboard: `/`
- Admin Django: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

### Bước 4 – ESP32 & camera

- Bật ESP32 (kết nối WiFi + MQTT).
- Bật camera RTSP nếu dùng nhận diện AI.

---

## Đẩy project lên GitHub

Repository đích: **https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh.git**

### Lần đầu đẩy code (chưa có git trong project)

Tại thư mục gốc project (có `web/`, `node-red/`, `Code IoT/`):

**1. Tạo file `.gitignore`** (khuyến nghị):

```gitignore
# Python
web/venv/
__pycache__/
*.py[cod]
*.egg-info/
.env

# Django
web/db.sqlite3
web/media/
web/staticfiles/

# AI model (file lớn – có thể dùng Git LFS hoặc tải riêng)
web/best2.pt

# IDE / OS
.vscode/
.idea/
*.log
Thumbs.db
```

**2. Khởi tạo git và commit:**

```bash
git init
git add .
git commit -m "Initial commit: Hệ thống PCCC thông minh"
git branch -M main
git remote add origin https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh.git
git push -u origin main
```

Khi được hỏi đăng nhập GitHub:

- Dùng **Personal Access Token** (Settings → Developer settings → Tokens) thay cho mật khẩu, hoặc
- Cài [GitHub CLI](https://cli.github.com/) và chạy `gh auth login`.

### Đã có repository trên GitHub (chỉ cập nhật code)

```bash
git add .
git commit -m "Mô tả thay đổi của bạn"
git push origin main
```

### Clone về máy khác

```bash
git clone https://github.com/quoc2075/H-th-ng-pccc-th-ng-minh.git
cd H-th-ng-pccc-th-ng-minh
```

Sau đó làm lại các bước trong mục [Cài đặt](#cài-đặt) và [Chạy hệ thống](#chạy-hệ-thống).

### Lưu ý khi push

| Không nên commit | Lý do |
|------------------|--------|
| `web/venv/` | Môi trường ảo, tạo lại bằng `pip install` |
| Mật khẩu WiFi / RTSP trong code | Bảo mật |
| `best2.pt` (nếu quá lớn) | Dùng Git LFS hoặc hướng dẫn tải riêng trong README |

---

## Xử lý lỗi thường gặp

| Triệu chứng | Hướng xử lý |
|-------------|-------------|
| `Can't connect to MySQL` | Kiểm tra MySQL đã chạy, tên DB `pbl4_b`, user/password trong `settings.py` |
| MQTT không nhận dữ liệu | Kiểm tra Mosquitto, firewall cổng 1883, IP `mqtt_server` trên ESP32 |
| AI không chạy | `pip install ultralytics opencv-python`, có file `best2.pt`, RTSP đúng |
| Camera không hiển thị | Cài FFmpeg, kiểm tra URL RTSP và mạng |
| `mysqlclient` lỗi trên Windows | Dùng `pymysql` như ghi chú ở mục Yêu cầu hệ thống |
| Push GitHub bị từ chối | Kiểm tra quyền repo, dùng token, hoặc `git pull origin main --rebase` trước khi push |

---

## Tính năng chính

- Dashboard web (admin / user): theo dõi cảm biến, cảnh báo, điều khiển relay, bơm, còi, đèn.
- Nhận diện lửa/khói bằng YOLO (Ultralytics).
- Giao tiếp MQTT giữa Django, Node-RED và ESP32.
- Xuất log sự kiện CSV, cảnh báo real-time (SSE).

---

## Nhóm phát triển

Dự án PBL4 – Hệ thống PCCC thông minh.

Nếu gặp lỗi khi cài đặt, mở **Issue** trên GitHub hoặc liên hệ nhóm phát triển.
