import cv2
import os
import time
import serial
import requests
from ultralytics import YOLO
from flask import Flask, Response

# =============================
# PAKSA TCP UNTUK RTSP (Stabil)
# =============================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# =============================
# KONFIGURASI SISTEM
# =============================
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200

RTSP_URL = "rtsp://admin:BSUFGS@192.168.18.89:554/h264/ch2/main/av_stream"
DJANGO_SEND_DATA_URL = "http://127.0.0.1:8000/api/yolo-test/"

# =============================
# FLASK & MODEL YOLO
# =============================
app = Flask(__name__)

MODEL_VEHICLE = YOLO("yolov8n.pt") 
MODEL_HELMET = YOLO("YOLO-model/best.pt")

print("DAFTAR LABEL MODEL HELMET:", MODEL_HELMET.names)


os.makedirs("violations", exist_ok=True)

# =============================
# INISIALISASI SERIAL ESP32
# =============================
try:
    esp32 = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"✅ ESP32 Terhubung di {SERIAL_PORT}")
except:
    esp32 = None
    print("⚠ ESP32 Gagal (Mode Simulasi)")


# =============================
# GENERATOR VIDEO STREAM
# =============================
def generate_frames():

    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Tracking ID agar tidak double count
    counted_motor = set()
    counted_mobil = set()

    motor_count = 0
    mobil_count = 0
    pelanggar_count = 0

    CY_LINE = 250
    OFFSET = 8

    last_send = time.time()
    SEND_INTERVAL = 1

    frame_count = 0
    SKIP_FRAMES = 3  # AI mikir 1x tiap 3 frame

    cache_veh = []
    cache_helm = []
    buzzer_active = False

    print("🚀 Streaming OPTIMIZED MODE Berjalan...")

    while True:
        success, frame = cap.read()
        if not success:
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        # Resize untuk memperingan YOLO
        frame = cv2.resize(frame, (640, 360))
        frame_count += 1

        # ======================================================
        # YOLO AKTIF HANYA PADA FRAME TERTENTU (SKIPPING)
        # ======================================================
        if frame_count % SKIP_FRAMES == 0:

            cache_veh = []
            cache_helm = []
            buzzer_active = False  # reset tiap frame analisa

            # ============================
            # DETEKSI KENDARAAN (TRACK)
            # ============================
            try:
                results_v = MODEL_VEHICLE.track(frame, persist=True, verbose=False)[0]

                for box in results_v.boxes:
                    if box.id is None:
                        continue
                    
                    coords = list(map(int, box.xyxy[0]))
                    track_id = int(box.id[0])
                    cls = int(box.cls[0])

                    cache_veh.append((coords, track_id, cls))

                    cy = coords[3]  # titik tengah bawah

                    # Mobil
                    if cls == 2:
                        if (CY_LINE - OFFSET) < cy < (CY_LINE + OFFSET):
                            if track_id not in counted_mobil:
                                counted_mobil.add(track_id)
                                mobil_count += 1

                    # Motor
                    if cls == 3:
                        if (CY_LINE - OFFSET) < cy < (CY_LINE + OFFSET):
                            if track_id not in counted_motor:
                                counted_motor.add(track_id)
                                motor_count += 1

            except:
                pass

            # ============================
            # DETEKSI HELM (TANPA TRACK)
            # ============================
            try:
                results_h = MODEL_HELMET(frame, verbose=False)[0]

                for box in results_h.boxes:

                    cls = int(box.cls[0])

                    # Abaikan deteksi motor dan mobil (class 2 dan 3)
                    if cls not in [0, 1]:
                        continue

                    coords = list(map(int, box.xyxy[0]))
                    label = MODEL_HELMET.names[cls]

                    cache_helm.append((coords, label))

                    # Jika no_helmet → pelanggar
                    if label == "no_helmet":
                        buzzer_active = True
                        pelanggar_count += 1

            except Exception as e:
                print("Error HELMET:", e)

            # ============================
            # BUZZER UPDATE
            # ============================
            if esp32:
                try:
                    esp32.write(b'1' if buzzer_active else b'0')
                except:
                    pass

            # ============================
            # KIRIM DATA KE DJANGO
            # ============================
            if time.time() - last_send >= SEND_INTERVAL:
                payload = {
                    "motor": motor_count,
                    "mobil": mobil_count,
                    "pelanggar": pelanggar_count,
                    "total": motor_count + mobil_count,
                    "stream_active": True,
                }

                try:
                    requests.post(DJANGO_SEND_DATA_URL, json=payload, timeout=0.2)
                except:
                    pass

                last_send = time.time()

        # ======================================================
        # GAMBAR CACHE (VISUALISASI)
        # ======================================================

        for (coords, track_id, cls) in cache_veh:
            color = (0, 255, 0) if cls == 2 else (255, 0, 0)
            cv2.rectangle(frame, (coords[0], coords[1]), (coords[2], coords[3]), color, 2)

        for (coords, label) in cache_helm:
            if label == "no_helmet":
                cv2.rectangle(frame, (coords[0], coords[1]), (coords[2], coords[3]), (0, 0, 255), 3)
                cv2.putText(frame, "NO HELMET", (coords[0], coords[1] - 10), 0, 0.6, (0, 0, 255), 2)

        cv2.line(frame, (0, CY_LINE), (640, CY_LINE), (0, 255, 255), 2)
        cv2.putText(frame, f"Pelanggar: {pelanggar_count}", (10, 30), 0, 0.6, (0,0,255), 2)

        # Output MJPEG ke Flask
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )


# =============================
# ROUTE STREAM FLASK
# =============================
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
