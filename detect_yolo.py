import cv2
import os
import time
import base64
import requests
import numpy as np
from ultralytics import YOLO

# ======================================================
# KONFIGURASI MODEL & STREAM
# ======================================================

# SESUAIKAN DENGAN LOKASI FILE DI KOMPUTER KAMU
VEHICLE_MODEL_PATH = r"D:\Traffic_eye\SensorObjek\YOLO-model\yolov8n.pt"  # YOLO ORIGINAL (COCO)
HELMET_MODEL_PATH  = r"D:\Traffic_eye\SensorObjek\YOLO-model\best.pt"     # model custom (helmet/no_helmet)
RTSP_URL           = r"D:\Traffic_eye\SensorObjek\video\no_helmet_test.mp4"        # atau RTSP CCTV kamu

# Endpoint Django (sudah sesuai dengan projekmu)
DJANGO_SEND_DATA_URL    = "http://127.0.0.1:8000/api/yolo-test/"
DJANGO_UPLOAD_IMAGE_URL = "http://127.0.0.1:8000/api/save-violation/"

# Garis hitung & interval kirim data
LINE_Y          = 540
TOLERANCE       = 45
SEND_INTERVAL   = 1.0
RECONNECT_DELAY = 2
MAX_EMPTY_FRAMES = 50

# Threshold confidence
CONF_VEHICLE   = 0.30
CONF_NO_HELMET = 0.35

# Tracking
TRACK_TTL     = 25      # berapa frame track disimpan
NO_HELMET_TTL = 150     # berapa lama ingat 1 pelanggar supaya tidak dihitung ulang


# ======================================================
# LOAD MODEL
# ======================================================

print("[INFO] Load YOLO vehicle model...")
vehicle_model = YOLO(VEHICLE_MODEL_PATH)

print("[INFO] Load YOLO helmet model...")
helmet_model = YOLO(HELMET_MODEL_PATH)

# class nama dari masing2 model
vehicle_names = vehicle_model.names
helmet_names  = helmet_model.names

# mapping kelas dari COCO yang dianggap motor / mobil
MOTOR_LABELS = {"motorcycle"}                    # bisa tambah "bicycle" kalau mau
CAR_LABELS   = {"car", "truck", "bus"}          # semua ini dihitung sebagai "mobil"

# index kelas no_helmet di model custom
NO_HELMET_CLASS_ID = None
for cid, name in helmet_names.items():
    if name.lower() == "no_helmet":
        NO_HELMET_CLASS_ID = cid
        break

if NO_HELMET_CLASS_ID is None:
    print("⚠ Peringatan: Kelas 'no_helmet' tidak ditemukan di best.pt. Deteksi pelanggaran helm TIDAK AKTIF.")

# buat folder penyimpanan pelanggar
os.makedirs("violations", exist_ok=True)


# ======================================================
# FUNGSI BANTUAN: KIRIM GAMBAR PELANGGAR KE DJANGO
# ======================================================
def send_violation_image(image_path, lokasi="Gerbang Kampus Uniba"):
    """
    Kirim 1 foto pelanggar ke endpoint /api/save-violation/
    dalam bentuk base64 (sesuai API_data_pelanggar).
    """
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        payload = {
            "image": f"data:image/jpeg;base64,{encoded}",
            "lokasi": lokasi,
        }

        r = requests.post(DJANGO_UPLOAD_IMAGE_URL, json=payload, timeout=3)
        print(f"[UPLOAD VIOLATION] {r.status_code}: {r.text}")

    except Exception as e:
        print(f"❌ Gagal upload gambar pelanggar: {e}")


# ======================================================
# FUNGSI BANTUAN: KIRIM COUNTER KE DJANGO
# ======================================================
def send_to_django(motor, mobil, pelanggar, total, stream_active=True):
    payload = {
        "motor": motor,
        "mobil": mobil,
        "pelanggar": pelanggar,
        "total": total,
        "stream_active": stream_active,
    }
    try:
        r = requests.post(DJANGO_SEND_DATA_URL, json=payload, timeout=2)
        print("[Django Data]", r.status_code, r.text)
    except Exception as e:
        print("⚠ Tidak bisa kirim data YOLO ke Django:", e)


# ======================================================
# TRACKER SEDERHANA UNTUK MOTOR & MOBIL
# ======================================================
class Track:
    def __init__(self, tid, cls_name, cx, cy, frame_id):
        self.id = tid
        self.cls = cls_name      # 'motor' atau 'car'
        self.cx = cx
        self.cy = cy
        self.last_cx = cx
        self.last_cy = cy
        self.last_seen = frame_id
        self.counted = False     # sudah melewati garis atau belum


def match_tracks(tracks, detections, frame_id, max_dist=60):
    """
    detections: list[(cls_name, (x1,y1,x2,y2))]
    Update tracks pakai centroid paling dekat.
    """
    new_tracks = []
    used_det = set()

    # update track lama
    for tr in tracks:
        best_idx = -1
        best_dist = 1e9
        for i, (cls_name, box) in enumerate(detections):
            if i in used_det or cls_name != tr.cls:
                continue
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((cx - tr.cx) ** 2 + (cy - tr.cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx != -1 and best_dist < max_dist:
            cls_name, box = detections[best_idx]
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            tr.last_cx, tr.last_cy = tr.cx, tr.cy
            tr.cx, tr.cy = cx, cy
            tr.last_seen = frame_id
            used_det.add(best_idx)

    # buat track baru
    next_id = (max([t.id for t in tracks]) + 1) if tracks else 1
    for i, (cls_name, box) in enumerate(detections):
        if i in used_det:
            continue
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        new_tracks.append(Track(next_id, cls_name, cx, cy, frame_id))
        next_id += 1

    tracks.extend(new_tracks)
    # buang track yang sudah lama hilang
    tracks = [t for t in tracks if frame_id - t.last_seen <= TRACK_TTL]
    return tracks


# ======================================================
# MEMORY PELANGGAR (NO_HELMET) AGAR TIDAK DOBEL
# ======================================================
def register_no_helmet(memory, cx, cy, frame_id, max_dist=40):
    """
    memory: list dict {cx, cy, last_seen}
    Kalau centroid dekat dengan yg lama -> dianggap pelanggar yang sama.
    Kalau tidak ada yg dekat -> pelanggar baru -> return True.
    """
    found = False
    for m in memory:
        dist = ((cx - m["cx"]) ** 2 + (cy - m["cy"]) ** 2) ** 0.5
        if dist < max_dist:
            m["last_seen"] = frame_id
            found = True
            break

    if not found:
        memory.append({"cx": cx, "cy": cy, "last_seen": frame_id})
        return True  # pelanggar baru

    # bersihkan memory yang kadaluarsa
    memory[:] = [m for m in memory if frame_id - m["last_seen"] <= NO_HELMET_TTL]
    return False


# ======================================================
# FUNGSI BUKA STREAM
# ======================================================
def open_stream():
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("❌ Tidak bisa membuka kamera/video")
    else:
        print("[INFO] Stream berhasil dibuka.")
    return cap


# ======================================================
# MAIN LOOP
# ======================================================
def main():
    motor_count = 0
    mobil_count = 0
    pelanggar_count = 0

    tracks = []
    no_helmet_memory = []

    frame_id = 0
    last_send = time.time()

    cap = open_stream()
    empty_frame = 0

    try:
        while True:
            # ================= RECONNECT STREAM =================
            if not cap or not cap.isOpened():
                print("🔄 Reconnecting stream...")
                send_to_django(motor_count, mobil_count,
                               pelanggar_count, motor_count + mobil_count,
                               stream_active=False)
                time.sleep(RECONNECT_DELAY)
                cap = open_stream()
                empty_frame = 0
                continue

            ret, frame = cap.read()
            if not ret:
                empty_frame += 1
                print(f"⚠ No frame #{empty_frame}")
                if empty_frame >= MAX_EMPTY_FRAMES:
                    cap.release()
                    cap = None
                continue

            empty_frame = 0
            frame_id += 1
            h_frame, w_frame = frame.shape[:2]

            # ==================================================
            # 1) DETEKSI KENDARAAN DENGAN YOLO ORIGINAL
            # ==================================================
            results_vehicle = vehicle_model(frame, imgsz=640, conf=CONF_VEHICLE)[0]

            motors, cars = [], []

            for box in results_vehicle.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = vehicle_names[cls_id]

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                if x2 <= x1 or y2 <= y1:
                    continue

                # kelompokkan ke motor / mobil
                if label in MOTOR_LABELS:
                    motors.append((x1, y1, x2, y2))
                elif label in CAR_LABELS:
                    cars.append((x1, y1, x2, y2))

            # ==================================================
            # 2) DETEKSI NO HELMET DENGAN MODEL CUSTOM
            # ==================================================
            nohelmets = []
            if NO_HELMET_CLASS_ID is not None:
                results_helmet = helmet_model(frame, imgsz=640, conf=CONF_NO_HELMET)[0]
                for box in results_helmet.boxes:
                    cls_id = int(box.cls[0])
                    if cls_id != NO_HELMET_CLASS_ID:
                        continue

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    if x2 <= x1 or y2 <= y1:
                        continue

                    nohelmets.append((x1, y1, x2, y2))

            # ==================================================
            # 3) PROSES PELANGGAR (NO_HELMET)
            # ==================================================
            for (x1, y1, x2, y2) in nohelmets:
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                is_new_violation = register_no_helmet(
                    no_helmet_memory, cx, cy, frame_id
                )

                if is_new_violation:
                    pelanggar_count += 1

                    pad = 20
                    x1c = max(0, x1 - pad)
                    y1c = max(0, y1 - pad)
                    x2c = min(w_frame, x2 + pad)
                    y2c = min(h_frame, y2 + pad)
                    crop = frame[y1c:y2c, x1c:x2c]

                    filename = f"pelanggar_{int(time.time())}_{frame_id}.jpg"
                    save_path = os.path.join("violations", filename)
                    cv2.imwrite(save_path, crop)

                    send_violation_image(save_path)

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, "NO HELMET", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # ==================================================
            # 4) TRACKING + COUNTING KENDARAAN
            # ==================================================
            detections = [("motor", m) for m in motors] + \
                         [("car", c) for c in cars]
            tracks = match_tracks(tracks, detections, frame_id)

            for tr in tracks:
                color = (255, 0, 0) if tr.cls == "motor" else (0, 255, 0)
                cv2.circle(frame, (int(tr.cx), int(tr.cy)), 4, color, -1)

                if not tr.counted:
                    if (tr.last_cy < LINE_Y <= tr.cy) or (tr.last_cy > LINE_Y >= tr.cy):
                        if tr.cls == "motor":
                            motor_count += 1
                        elif tr.cls == "car":
                            mobil_count += 1
                        tr.counted = True

            # ==================================================
            # 5) KIRIM DATA KE DJANGO
            # ==================================================
            if time.time() - last_send >= SEND_INTERVAL:
                total = motor_count + mobil_count
                send_to_django(motor_count, mobil_count,
                               pelanggar_count, total, stream_active=True)
                last_send = time.time()

            # ==================================================
            # 6) TAMPILKAN FRAME
            # ==================================================
            cv2.line(frame, (0, LINE_Y), (w_frame, LINE_Y), (0, 255, 255), 4)

            cv2.putText(frame, f"Motor: {motor_count}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 200, 255), 2)
            cv2.putText(frame, f"Mobil: {mobil_count}",
                        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 200, 255), 2)
            cv2.putText(frame, f"Pelanggar: {pelanggar_count}",
                        (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 0, 255), 2)

            cv2.imshow("YOLO DETECT FINAL", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        send_to_django(motor_count, mobil_count,
                       pelanggar_count, motor_count + mobil_count,
                       stream_active=False)
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        print("Program berhenti.")


if __name__ == "__main__":
    main()
