import cv2
import os
import time
import base64
import requests
from ultralytics import YOLO

# =============================
# MODEL
# =============================
MODEL_VEHICLE = YOLO("yolov8l.pt")   # untuk mobil & motor (sangat akurat)
MODEL_HELMET = YOLO(r"D:\Traffic_eye\SensorObjek\YOLO-model\best.pt")  # model custom kamu

RTSP_URL = r"D:\Traffic_eye\SensorObjek\video\test2.mp4"

DJANGO_SEND_DATA_URL = "http://127.0.0.1:8000/api/yolo-test/"
DJANGO_UPLOAD_IMAGE_URL = "http://127.0.0.1:8000/api/save-violation/"

LINE_Y = 550
TOLERANCE = 45

SEND_INTERVAL = 1.0
RECONNECT_DELAY = 3
MAX_EMPTY_FRAMES = 50

os.makedirs("violations", exist_ok=True)


# ===========================================
# KIRIM GAMBAR PELANGGAR
# ===========================================
def send_violation_image(image_path):
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    payload = {
        "image": f"data:image/jpeg;base64,{encoded}",
        "lokasi": "Gerbang Kampus Uniba",
    }

    try:
        r = requests.post(DJANGO_UPLOAD_IMAGE_URL, json=payload, timeout=2)
        print("[UPLOAD VIOLATION]", r.text)
    except:
        print("⚠ Gagal upload pelanggaran")


# ===========================================
# KIRIM COUNTER KE DJANGO
# ===========================================
def send_to_django(motor, mobil, pelanggar, total, stream_active=True):
    payload = {
        "motor": motor,
        "mobil": mobil,
        "pelanggar": pelanggar,
        "total": total,
        "stream_active": stream_active,
    }
    try:
        requests.post(DJANGO_SEND_DATA_URL, json=payload, timeout=2)
    except:
        pass


# ===========================================
# BUKA STREAM
# ===========================================
def open_stream():
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("❌ Tidak bisa membuka video/RTSP")
    return cap


# ===========================================
# MAIN PROGRAM
# ===========================================
def main():

    motor_count = 0
    mobil_count = 0
    pelanggar_count = 0

    last_send = time.time()
    frame_id = 0

    cap = open_stream()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_id += 1
            h, w = frame.shape[:2]

            # =================================================
            # DETEKSI KENDARAAN DENGAN YOLOv8l (COCO)
            # =================================================
            veh = MODEL_VEHICLE(frame)[0]

            motors = []
            cars = []

            for b in veh.boxes:
                cls = int(b.cls[0])
                conf = float(b.conf[0])
                x1, y1, x2, y2 = map(int, b.xyxy[0])

                if cls == 2:  # car
                    cars.append((x1, y1, x2, y2))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0,255,0), 2)

                if cls == 3:  # motorcycle
                    motors.append((x1, y1, x2, y2))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255,0,0), 2)

            # =================================================
            # DETEKSI HELM
            # =================================================
            helm = MODEL_HELMET(frame)[0]

            nohelm = []

            for b in helm.boxes:
                label = MODEL_HELMET.names[int(b.cls[0])]
                if label == "no_helmet":
                    x1, y1, x2, y2 = map(int, b.xyxy[0])
                    nohelm.append((x1, y1, x2, y2))

                    # simpan + kirim
                    fname = f"pelanggar_{frame_id}.jpg"
                    path = os.path.join("violations", fname)
                    cv2.imwrite(path, frame)
                    send_violation_image(path)

                    cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 3)
                    pelanggar_count += 1

            # =================================================
            # COUNTING (garis)
            # =================================================
            for (x1,y1,x2,y2) in cars:
                cy = (y1 + y2)//2
                if LINE_Y - TOLERANCE < cy < LINE_Y + TOLERANCE:
                    mobil_count += 1

            for (x1,y1,x2,y2) in motors:
                cy = (y1 + y2)//2
                if LINE_Y - TOLERANCE < cy < LINE_Y + TOLERANCE:
                    motor_count += 1

            # =================================================
            # KIRIM KE DJANGO (per 1 detik)
            # =================================================
            if time.time() - last_send >= SEND_INTERVAL:
                send_to_django(motor_count, mobil_count,
                               pelanggar_count, motor_count+mobil_count)
                last_send = time.time()

            # =================================================
            # TAMPILKAN HASIL
            # =================================================
            cv2.line(frame, (0, LINE_Y), (w, LINE_Y), (0,255,255), 3)
            cv2.putText(frame, f"Motor: {motor_count}", (20,40), 0, 1, (255,255,0), 2)
            cv2.putText(frame, f"Mobil: {mobil_count}", (20,80), 0, 1, (0,255,0), 2)
            cv2.putText(frame, f"Pelanggar: {pelanggar_count}", (20,120), 0, 1, (0,0,255), 2)

            cv2.imshow("HYBRID YOLO (MAX ACCURACY)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Program berhenti.")


if __name__ == "__main__":
    main()
