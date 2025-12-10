import cv2
import os
import time
import math
import serial
import requests
import base64  # <--- WAJIB ADA
from ultralytics import YOLO
from flask import Flask, Response

# 1. PAKSA TCP (Stabil)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# =============================
# KONFIGURASI
# =============================
SERIAL_PORT = 'COM7' 
BAUD_RATE = 115200

# Link CCTV
RTSP_URL = r"D:\Traffic_eye\SensorObjek\video\test3.mp4"

# URL API
DJANGO_SEND_DATA_URL = "http://127.0.0.1:8000/api/yolo-test/"
DJANGO_UPLOAD_URL = "http://127.0.0.1:8000/api/save-violation/" # <--- INI PENTING

# =============================
# SETUP
# =============================
app = Flask(__name__)
MODEL_VEHICLE = YOLO("yolov8n.pt") 
MODEL_HELMET = YOLO("YOLO-model/best.pt")

try:
    esp32 = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"✅ ESP32 Terhubung di {SERIAL_PORT}")
except:
    esp32 = None
    print(f"⚠ ESP32 Gagal (Mode Simulasi)")

# =============================
# FUNGSI KIRIM FOTO KE DJANGO
# =============================
def lapor_pelanggaran(frame, lokasi="Gerbang Utama"):
    """Mengirim foto bukti pelanggaran ke Database Django agar jadi Notifikasi"""
    try:
        # 1. Encode gambar ke Base64
        _, buffer = cv2.imencode('.jpg', frame)
        img_str = base64.b64encode(buffer).decode('utf-8')
        img_base64 = "data:image/jpeg;base64," + img_str

        # 2. Kirim ke API
        payload = {
            "image": img_base64,
            "lokasi": lokasi
        }
        # Kirim di background (timeout kecil biar gak bikin lag video)
        try:
            requests.post(DJANGO_UPLOAD_URL, json=payload, timeout=0.5)
            print("📨 Laporan Terkirim ke Website!") 
        except: 
            pass # Kalau gagal kirim, biarin aja biar video gak macet
            
    except Exception as e:
        print(f"Gagal Upload: {e}")

# =============================
# GENERATOR VIDEO
# =============================
def generate_frames():
    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Database ID
    counted_ids_pelanggar = set()
    counted_ids_motor = set()
    counted_ids_mobil = set()

    # Memory Anti-Hantu
    recent_violations = [] 
    
    # KONFIGURASI ANTI-DOBEL
    DIST_THRESHOLD = 500  
    TIME_THRESHOLD = 5.0  
    
    pelanggar_count = 0
    motor_count = 0
    mobil_count = 0

    CY_LINE = 500 
    OFFSET = 15   
    
    last_send = time.time()
    SEND_INTERVAL = 1.0

    print("🚀 Streaming + NOTIFIKASI AKTIF Berjalan...")

    while True:
        success, frame = cap.read()
        if not success:
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        frame = cv2.resize(frame, (1280, 720))
        current_time = time.time()
        
        # Bersihkan memori lama
        recent_violations = [v for v in recent_violations if current_time - v['time'] < TIME_THRESHOLD]

        trigger_buzzer_now = False 

        # ---------------------------------------------------------
        # A. DETEKSI KENDARAAN
        # ---------------------------------------------------------
        try:
            results_veh = MODEL_VEHICLE.track(frame, persist=True, verbose=False)[0]
            for box in results_veh.boxes:
                if box.id is not None:
                    track_id = int(box.id[0])
                    cls = int(box.cls[0])
                    coords = list(map(int, box.xyxy[0]))
                    cy = coords[3]

                    color = (0, 255, 0) if cls == 2 else (255, 0, 0)
                    cv2.rectangle(frame, (coords[0], coords[1]), (coords[2], coords[3]), color, 2)

                    if (CY_LINE - OFFSET) < cy < (CY_LINE + OFFSET):
                        if cls == 2 and track_id not in counted_ids_mobil:
                            counted_ids_mobil.add(track_id)
                            mobil_count += 1
                        elif cls == 3 and track_id not in counted_ids_motor:
                            counted_ids_motor.add(track_id)
                            motor_count += 1
        except: pass

        # ---------------------------------------------------------
        # B. DETEKSI HELM + LAPOR POLISI
        # ---------------------------------------------------------
        try:
            results_helm = MODEL_HELMET.track(frame, persist=True, verbose=False)[0]
            for box in results_helm.boxes:
                if box.id is not None:
                    track_id = int(box.id[0])
                    cls = int(box.cls[0])
                    label = MODEL_HELMET.names[cls]
                    coords = list(map(int, box.xyxy[0]))
                    
                    cx = int((coords[0] + coords[2]) / 2)
                    cy = int((coords[1] + coords[3]) / 2) 

                    if label == "no_helmet":
                        
                        # SYARAT 1: WAJIB DI GARIS
                        if (CY_LINE - OFFSET) < cy < (CY_LINE + OFFSET):
                            
                            # SYARAT 2: ID BELUM TERCATAT
                            if track_id in counted_ids_pelanggar:
                                continue 

                            # SYARAT 3: CEK JARAK (ANTI-HANTU)
                            is_duplicate_person = False
                            for v in recent_violations:
                                distance = math.sqrt((cx - v['x'])**2 + (cy - v['y'])**2)
                                if distance < DIST_THRESHOLD:
                                    is_duplicate_person = True
                                    counted_ids_pelanggar.add(track_id) 
                                    break
                            
                            if is_duplicate_person:
                                continue 

                            # === VALID PELANGGAR BARU ===
                            counted_ids_pelanggar.add(track_id)
                            recent_violations.append({'x': cx, 'y': cy, 'time': current_time})
                            
                            pelanggar_count += 1
                            trigger_buzzer_now = True 
                            
                            # 📸 VISUALISASI
                            cv2.rectangle(frame, (coords[0], coords[1]), (coords[2], coords[3]), (0, 0, 255), 3)
                            cv2.putText(frame, "PELANGGAR!", (coords[0], coords[1]-10), 0, 0.6, (0,0,255), 2)
                            
                            # 📨 KIRIM LAPORAN KE WEBSITE (INI YANG BIKIN NOTIF MUNCUL)
                            # Kita crop gambar pas momen pelanggaran
                            lapor_pelanggaran(frame, lokasi="Gerbang Depan")

        except: pass
        
        # C. UPDATE BUZZER
        if esp32:
            try:
                esp32.write(b'1' if trigger_buzzer_now else b'0')
            except: pass

        # D. KIRIM DATA ANGKA KE DJANGO
        if time.time() - last_send >= SEND_INTERVAL:
            payload = {
                "motor": motor_count, "mobil": mobil_count, 
                "pelanggar": pelanggar_count, 
                "total": motor_count + mobil_count, "stream_active": True
            }
            try:
                requests.post(DJANGO_SEND_DATA_URL, json=payload, timeout=0.1)
            except: pass
            last_send = time.time()

        # UI
        cv2.line(frame, (0, CY_LINE), (1280, CY_LINE), (0, 255, 255), 2)
        cv2.putText(frame, f"Pelanggar: {pelanggar_count}", (10, 30), 0, 0.6, (0,0,255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True)