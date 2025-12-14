import cv2
import os
import time
import base64
import requests
import math
import threading
from ultralytics import YOLO

# ======================================================
# IMPORT MQTT BUZZER
# ======================================================
from mqtt_sender import buzzer_on, buzzer_off


# ======================================================
# KONFIGURASI
# ======================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VEHICLE_MODEL_PATH = os.path.join(BASE_DIR, "YOLO-model", "yolov8n.pt")
HELMET_MODEL_PATH  = os.path.join(BASE_DIR, "YOLO-model", "best.pt")

RTSP_URL = r"D:\Traffic_eye\SensorObjek\video\test3.mp4"
# RTSP_URL = "rtsp://user:pass@ip:554/live"

DJANGO_SEND_DATA_URL    = "http://127.0.0.1:8000/api/yolo-test/"
DJANGO_UPLOAD_IMAGE_URL = "http://127.0.0.1:8000/api/save-violation/"

# ✅ TAMBAHAN: endpoint update total harian
DJANGO_DAILY_URL        = "http://127.0.0.1:8000/api/update-traffic-harian/"

DEBUG_SHOW = True
LINE_Y = 540  # posisi garis hitung kendaraan (di resolusi 1280x720)

CONF_VEHICLE = 0.30
CONF_HELMET  = 0.40

MIN_HEAD_SIZE   = 120    # tinggi min bbox kepala (di resolusi 1280x720)
STABLE_FRAMES   = 10
NOHELM_TTL      = 120
TRACK_TTL       = 25
SEND_INTERVAL   = 1.0    # kirim data realtime ke Django tiap 1 detik

# resolusi tampilan & resolusi deteksi (lebih kecil supaya enteng)
VIEW_W, VIEW_H = 1280, 720
DET_W, DET_H   = 640, 360    # YOLO dipanggil di ukuran ini
SCALE_X = VIEW_W / DET_W
SCALE_Y = VIEW_H / DET_H


# ======================================================
# LOAD YOLO MODELS
# ======================================================

vehicle_model = YOLO(VEHICLE_MODEL_PATH)
helmet_model  = YOLO(HELMET_MODEL_PATH)

vehicle_names = vehicle_model.names
helmet_names  = helmet_model.names

print("[INFO] Model kendaraan:", vehicle_names)
print("[INFO] Model helmet   :", helmet_names)


# ======================================================
# CLASS ID NO HELMET
# ======================================================

NOHELM_ID = None
HELMET_ID = None

for cid, name in helmet_names.items():
    n = name.lower()
    if "no" in n:
        NOHELM_ID = cid
    elif "helmet" in n:
        HELMET_ID = cid

print("NO_HELMET ID =", NOHELM_ID)


# ======================================================
# FOLDER VIOLATIONS
# ======================================================

VIOL_DIR = os.path.join(BASE_DIR, "violations")
os.makedirs(VIOL_DIR, exist_ok=True)


# ======================================================
# BANTUAN
# ======================================================

def center(b):
    x1, y1, x2, y2 = b
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def crop(frame, box, pad=20):
    x1, y1, x2, y2 = box
    h, w = frame.shape[:2]
    return frame[max(0, y1 - pad):min(h, y2 + pad),
                 max(0, x1 - pad):min(w, x2 + pad)]


# ======================================================
# POST ASYNC (UTILITY)
# ======================================================

def post_async(url, payload, timeout=1):
    def task():
        try:
            requests.post(url, json=payload, timeout=timeout)
        except Exception:
            pass
    threading.Thread(target=task, daemon=True).start()


# ======================================================
# ASYNC SAVE + UPLOAD (ANTI FREEZE)
# ======================================================

def save_and_upload_async(frame, box, sid):
    """
    Simpan gambar pelanggar & upload ke Django
    dijalankan di THREAD terpisah (tidak mengganggu FPS).
    """
    frame_copy = frame.copy()
    box_copy   = tuple(box)

    def task():
        try:
            crop_img = crop(frame_copy, box_copy)
            fname = f"pel_{sid}_{int(time.time())}.jpg"
            fpath = os.path.join(VIOL_DIR, fname)
            cv2.imwrite(fpath, crop_img)

            with open(fpath, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()

            payload = {
                "image": f"data:image/jpeg;base64,{encoded}",
                "lokasi": "Gerbang masuk Polibatam"
            }
            requests.post(DJANGO_UPLOAD_IMAGE_URL, json=payload, timeout=2)

        except Exception as e:
            print("UPLOAD ERROR:", e)

    threading.Thread(target=task, daemon=True).start()


# ======================================================
# MEMORY DETEKSI PELANGGAR
# ======================================================

stable_mem = {}
viol_count = 0
unique_id = 1


def register_candidate(box, frame_id):
    """
    Pelanggar dihitung hanya jika:
    - stabil (≥ STABLE_FRAMES)
    - belum disimpan sebelumnya
    """
    global stable_mem, unique_id, viol_count

    cx, cy = center(box)

    found_id = None
    for sid, data in stable_mem.items():
        if dist((cx, cy), (data["cx"], data["cy"])) < 80:
            found_id = sid
            break

    if found_id is None:
        stable_mem[unique_id] = {
            "cx": cx,
            "cy": cy,
            "seen": 1,
            "last": frame_id,
            "saved": False
        }
        unique_id += 1
        return None

    stable_mem[found_id]["cx"] = cx
    stable_mem[found_id]["cy"] = cy
    stable_mem[found_id]["seen"] += 1
    stable_mem[found_id]["last"] = frame_id

    if stable_mem[found_id]["seen"] < STABLE_FRAMES:
        return None

    if stable_mem[found_id]["saved"]:
        return None

    stable_mem[found_id]["saved"] = True
    viol_count += 1
    return found_id


def clean_memory(frame_id):
    remove = []
    for sid, data in stable_mem.items():
        if frame_id - data["last"] > NOHELM_TTL:
            remove.append(sid)
    for sid in remove:
        del stable_mem[sid]


# ======================================================
# TRACKING KENDARAAN
# ======================================================

class Track:
    def __init__(self, tid, cls, cx, cy, frame_id):
        self.id = tid
        self.cls = cls
        self.cx = cx
        self.cy = cy
        self.last_cx = cx
        self.last_cy = cy
        self.last_seen = frame_id
        self.counted = False


def match_tracks(tracks, detections, frame_id, max_dist=60):
    used = set()

    for tr in tracks:
        best_idx = -1
        best_dist = 999999

        for i, (cls, box) in enumerate(detections):
            if i in used or cls != tr.cls:
                continue

            cx, cy = center(box)
            d = dist((cx, cy), (tr.cx, tr.cy))

            if d < best_dist:
                best_dist = d
                best_idx = i

        if best_idx != -1 and best_dist < max_dist:
            x1, y1, x2, y2 = detections[best_idx][1]
            tr.last_cx, tr.last_cy = tr.cx, tr.cy
            tr.cx = (x1 + x2) // 2
            tr.cy = (y1 + y2) // 2
            tr.last_seen = frame_id
            used.add(best_idx)

    next_id = max([t.id for t in tracks], default=0) + 1

    for i, (cls, box) in enumerate(detections):
        if i not in used:
            cx, cy = center(box)
            tracks.append(Track(next_id, cls, cx, cy, frame_id))
            next_id += 1

    return [t for t in tracks if frame_id - t.last_seen <= TRACK_TTL]


# ======================================================
# KIRIM DATA REALTIME KE DJANGO (ASYNC)
# ======================================================

def send_counts_to_django_async(motor, mobil, pelanggar, stream_active=True):
    payload = {
        "motor": motor,
        "mobil": mobil,
        "pelanggar": pelanggar,
        "total": motor + mobil,
        "stream_active": stream_active,
    }
    post_async(DJANGO_SEND_DATA_URL, payload, timeout=1)


# ======================================================
# MAIN PROGRAM
# ======================================================

def main():
    global viol_count

    motor_count = 0
    car_count   = 0

    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("❌ Video/RTSP gagal dibuka!")
        return

    frame_id = 0
    tracks = []
    last_send = time.time()

    while True:
        ok, frame_raw = cap.read()
        if not ok:
            break

        # frame tampilan besar
        frame = cv2.resize(frame_raw, (VIEW_W, VIEW_H))
        frame_id += 1

        # frame untuk YOLO (lebih kecil → anti lag)
        det_frame = cv2.resize(frame, (DET_W, DET_H))

        # ---------------- DETEKSI KENDARAAN (DI FRAME KECIL) ----------------
        vres = vehicle_model(det_frame, conf=CONF_VEHICLE)[0]
        motors, cars = [], []

        for b in vres.boxes:
            cls = vehicle_names[int(b.cls[0])]
            x1, y1, x2, y2 = map(int, b.xyxy[0])

            # skala koordinat ke frame tampilan 1280x720
            x1 = int(x1 * SCALE_X)
            x2 = int(x2 * SCALE_X)
            y1 = int(y1 * SCALE_Y)
            y2 = int(y2 * SCALE_Y)

            if cls == "motorcycle":
                motors.append((x1, y1, x2, y2))
            elif cls in ["car", "truck", "bus"]:
                cars.append((x1, y1, x2, y2))

        detections = [("motor", m) for m in motors] + \
                     [("car", c) for c in cars]

        tracks = match_tracks(tracks, detections, frame_id)

        # ---------------- HITUNG KENDARAAN SAAT MELEWATI GARIS ----------------
        for tr in tracks:
            if (not tr.counted and
               ((tr.last_cy < LINE_Y <= tr.cy) or (tr.last_cy > LINE_Y >= tr.cy))):

                tr.counted = True

                # ✅ UPDATE TOTAL HARIAN (DB) - 1 kendaraan = 1 increment
                daily_payload = {
                    "motor": 1 if tr.cls == "motor" else 0,
                    "mobil": 1 if tr.cls == "car" else 0,
                    "pelanggar": 0
                }
                post_async(DJANGO_DAILY_URL, daily_payload, timeout=1)

                # realtime counter (tetap)
                if tr.cls == "motor":
                    motor_count += 1
                elif tr.cls == "car":
                    car_count += 1

        # ---------------- DETEKSI NO HELMET (DI FRAME KECIL) ----------------
        hres = helmet_model(det_frame, conf=CONF_HELMET)[0]
        nohelm_boxes = []

        for b in hres.boxes:
            cid = int(b.cls[0])
            x1, y1, x2, y2 = map(int, b.xyxy[0])

            # skala ke 1280x720
            x1 = int(x1 * SCALE_X)
            x2 = int(x2 * SCALE_X)
            y1 = int(y1 * SCALE_Y)
            y2 = int(y2 * SCALE_Y)

            # tinggi bbox di resolusi besar
            if (y2 - y1) < MIN_HEAD_SIZE:
                continue

            if cid == NOHELM_ID:
                nohelm_boxes.append((x1, y1, x2, y2))

        # ---------------- REGISTER + BUZZER + SAVE (ASYNC) ----------------
        for box in nohelm_boxes:
            sid = register_candidate(box, frame_id)

            if sid is not None:
                # MQTT BUZZER (TIDAK BLOKIR)
                buzzer_on()
                threading.Timer(0.7, buzzer_off).start()

                # SAVE + UPLOAD (ASYNC)
                save_and_upload_async(frame, box, sid)

                # ✅ UPDATE TOTAL PELANGGAR HARIAN (DB)
                post_async(DJANGO_DAILY_URL, {"motor": 0, "mobil": 0, "pelanggar": 1}, timeout=1)

        clean_memory(frame_id)

        # ---------------- KIRIM DATA DASHBOARD REALTIME (ASYNC) ----------------
        if time.time() - last_send >= SEND_INTERVAL:
            send_counts_to_django_async(motor_count, car_count, viol_count)
            last_send = time.time()

        # ---------------- VISUALISASI ----------------
        if DEBUG_SHOW:
            cv2.line(frame, (0, LINE_Y), (VIEW_W, LINE_Y), (0, 255, 255), 3)

            for m in motors:
                cv2.rectangle(frame, m[:2], m[2:], (0, 255, 255), 2)
            for c in cars:
                cv2.rectangle(frame, c[:2], c[2:], (0, 255, 0), 2)
            for nh in nohelm_boxes:
                cv2.rectangle(frame, nh[:2], nh[2:], (0, 0, 255), 3)

            cv2.putText(frame, f"Motor: {motor_count}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(frame, f"Mobil: {car_count}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Pelanggar: {viol_count}", (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            cv2.imshow("YOLO FINAL", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    # saat stop
    send_counts_to_django_async(motor_count, car_count, viol_count, stream_active=False)
    cap.release()
    cv2.destroyAllWindows()
    print("Program berhenti.")


# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    main()
