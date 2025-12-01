from ultralytics import YOLO
import cv2
import os
import time
import requests

# ======================================================
# KONFIGURASI MODEL DAN STREAM
# ======================================================
MODEL_PATH = r"D:\Traffic_eye\SensorObjek\YOLO-model\best.pt"
RTSP_URL = "rtsp://admin:BSUFGS@192.168.18.89:554/h264/ch2/main/av_stream"           # ganti RTSP / video path kalau perlu
DJANGO_URL = "http://127.0.0.1:8000/api/yolo-test/"

RECONNECT_DELAY = 3
MAX_EMPTY_FRAMES = 50
SEND_INTERVAL = 1.0
LINE_Y = 550
TOLERANCE = 45

# ==================== THRESHOLD PER KELAS ======================
# motor harus CONF paling tinggi → biar mobil nggak kebaca motor
CONF_MOTOR = 0.60
CONF_CAR = 0.40
CONF_HELMET = 0.35
CONF_NO_HELMET = 0.40

# RULE UKURAN & BENTUK (disesuaikan CCTV 1280x720-an)
# semua dalam bentuk rasio terhadap ukuran frame
MOTOR_MAX_AREA = 0.030   # kalau motor lebih besar dari ini → kemungkinan mobil
CAR_MIN_AREA = 0.010     # kalau car lebih kecil dari ini → kemungkinan motor
ASPECT_WIDE = 2.2        # kalau sangat lebar → cenderung mobil
ASPECT_TALL = 1.0        # kalau tinggi (portrait) & kecil → cenderung motor

# berapa frame sebelum track dianggap hilang
TRACK_TTL = 25


model = YOLO(MODEL_PATH)
os.makedirs("violations", exist_ok=True)


# ======================================================
# KIRIM DATA KE DJANGO
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
        r = requests.post(DJANGO_URL, json=payload, timeout=1)
        print(f"[Django] {r.status_code}:", r.text)
    except Exception as e:
        print("⚠️ Tidak bisa kirim ke Django:", e)


# ======================================================
# BANTUAN GEOMETRI
# ======================================================
def overlap(box1, box2):
    x1, y1, x2, y2 = box1
    a1, b1, a2, b2 = box2
    return not (x2 < a1 or a2 < x1 or y2 < b1 or b2 < y1)


def refine_vehicle_label(label, area, w, h, frame_w, frame_h):
    """
    Koreksi label antara 'motor' dan 'car' berdasarkan:
    - luas relatif (area / (W*H))
    - aspek rasio (w/h)
    """
    frame_area = frame_w * frame_h
    if frame_area <= 0:
        return label

    norm_area = area / frame_area
    aspect = w / max(h, 1)

    # motor terlalu besar / sangat lebar → kemungkinan mobil
    if label == "motor":
        if norm_area > MOTOR_MAX_AREA or aspect > ASPECT_WIDE:
            return "car"

    # mobil sangat kecil & cukup tinggi → kemungkinan motor
    if label == "car":
        if norm_area < CAR_MIN_AREA and aspect < ASPECT_WIDE and h > w * ASPECT_TALL:
            return "motor"

    return label


# ======================================================
# TRACKING SEDERHANA (BY CENTROID)
# ======================================================
class Track:
    def __init__(self, tid, cls_name, cx, cy, frame_id):
        self.id = tid
        self.cls = cls_name     # 'motor' / 'car'
        self.cx = cx
        self.cy = cy
        self.last_cx = cx
        self.last_cy = cy
        self.last_seen = frame_id
        self.counted = False


def match_tracks(tracks, detections, frame_id, max_dist=60):
    """
    detections: list[(cls_name, (x1,y1,x2,y2))]
    Update tracks berdasarkan centroid terdekat.
    Return: updated_tracks, list_of_new_tracks
    """
    new_tracks = []
    used_det = set()

    # update tracks yang sudah ada
    for tr in tracks:
        best_idx = -1
        best_dist = 1e9
        for i, (cls_name, box) in enumerate(detections):
            if i in used_det:
                continue
            if cls_name != tr.cls:   # hanya cocokkan kelas yang sama
                continue
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dist = ((cx - tr.cx) ** 2 + (cy - tr.cy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx >= 0 and best_dist < max_dist:
            # update track dengan detection baru
            cls_name, box = detections[best_idx]
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            tr.last_cx, tr.last_cy = tr.cx, tr.cy
            tr.cx, tr.cy = cx, cy
            tr.last_seen = frame_id
            used_det.add(best_idx)

    # buat track baru untuk detection yang belum terpakai
    next_id = (max([t.id for t in tracks]) + 1) if tracks else 1
    for i, (cls_name, box) in enumerate(detections):
        if i in used_det:
            continue
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        new_tracks.append(Track(next_id, cls_name, cx, cy, frame_id))
        next_id += 1

    # gabungkan list lama + baru
    tracks.extend(new_tracks)

    # buang track yang sudah lama nggak kelihatan
    tracks = [t for t in tracks if frame_id - t.last_seen <= TRACK_TTL]

    return tracks


# ======================================================
# FUNGSI BUKA STREAM
# ======================================================
def open_stream():
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        print("❌ Tidak bisa membuka kamera/RTSP")
    return cap


# ======================================================
# MAIN LOOP
# ======================================================
def main():

    motor_count = 0
    mobil_count = 0
    pelanggar_count = 0

    frame_id = 0
    last_send = time.time()
    tracks = []

    cap = open_stream()
    empty_frame = 0

    try:
        while True:

            # ================= HANDLE STREAM PUTUS =================
            if not cap or not cap.isOpened():
                print("🔄 Reconnecting...")
                send_to_django(motor_count, mobil_count, pelanggar_count,
                               motor_count + mobil_count, False)
                time.sleep(RECONNECT_DELAY)
                cap = open_stream()
                empty_frame = 0
                continue

            ret, frame = cap.read()
            if not ret:
                empty_frame += 1
                if empty_frame >= MAX_EMPTY_FRAMES:
                    cap.release()
                    cap = None
                continue

            empty_frame = 0
            frame_id += 1
            h_frame, w_frame = frame.shape[:2]

            # ======================================================
            # YOLO PREDICT
            # ======================================================
            results = model(frame, stream=True)

            motors, cars, helmets, no_helmets = [], [], [], []

            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = model.names[cls]

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    w = x2 - x1
                    h = y2 - y1
                    area = w * h
                    if w <= 0 or h <= 0:
                        continue

                    # ---------------- THRESHOLD PER KELAS ----------------
                    if label == "motor" and conf < CONF_MOTOR:
                        continue
                    if label == "car" and conf < CONF_CAR:
                        continue
                    if label == "helmet" and conf < CONF_HELMET:
                        continue
                    if label == "no_helmet" and conf < CONF_NO_HELMET:
                        continue

                    # ---------------- KOREKSI MOTOR vs CAR ----------------
                    if label in ("motor", "car"):
                        label = refine_vehicle_label(label, area, w, h,
                                                     w_frame, h_frame)

                    # ---------------- MASUK LIST ----------------
                    if label == "motor":
                        motors.append((x1, y1, x2, y2))
                    elif label == "car":
                        cars.append((x1, y1, x2, y2))
                    elif label == "helmet":
                        helmets.append((x1, y1, x2, y2))
                    elif label == "no_helmet":
                        no_helmets.append((x1, y1, x2, y2))

            # ---------------- BUANG MOTOR YANG NEMPEL MOBIL ----------------
            motors_filtered = []
            for m in motors:
                if all(not overlap(m, c) for c in cars):
                    motors_filtered.append(m)
            motors = motors_filtered

            # ======================================================
            # HITUNG PELANGGARAN (NO_HELMET)
            # ======================================================
            for (x1, y1, x2, y2) in no_helmets:
                pelanggar_count += 1

                # simpan crop kepala/area pelanggaran
                y1c = max(0, y1 - 20)
                y2c = min(h_frame, y2 + 20)
                x1c = max(0, x1 - 20)
                x2c = min(w_frame, x2 + 20)
                crop = frame[y1c:y2c, x1c:x2c]

                save_path = f"violations/pelanggar_{frame_id}.jpg"
                cv2.imwrite(save_path, crop)

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, "NO HELMET", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

            # ======================================================
            # TRACKING + COUNTING LINE
            # ======================================================
            detections_for_track = [("motor", m) for m in motors] + \
                                   [("car", c) for c in cars]

            tracks = match_tracks(tracks, detections_for_track, frame_id)

            for tr in tracks:
                # gambar titik track
                color = (255, 0, 0) if tr.cls == "motor" else (0, 255, 0)
                cv2.circle(frame, (int(tr.cx), int(tr.cy)), 4, color, -1)

                # cek crossing line (sekali saja per track)
                if not tr.counted:
                    # crossing dari atas ke bawah (atau sebaliknya)
                    if (tr.last_cy < LINE_Y <= tr.cy) or (tr.last_cy > LINE_Y >= tr.cy):
                        if tr.cls == "motor":
                            motor_count += 1
                        elif tr.cls == "car":
                            mobil_count += 1
                        tr.counted = True

            # ======================================================
            # KIRIM DATA REALTIME KE DJANGO
            # ======================================================
            if time.time() - last_send >= SEND_INTERVAL:
                total = motor_count + mobil_count
                send_to_django(motor_count, mobil_count,
                               pelanggar_count, total, True)
                last_send = time.time()

            # ======================================================
            # TAMPILKAN FRAME
            # ======================================================
            cv2.line(frame, (0, LINE_Y),
                     (w_frame, LINE_Y), (0, 255, 255), 4)

            cv2.putText(frame, f"Motor: {motor_count}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 200, 255), 2)
            cv2.putText(frame, f"Mobil: {mobil_count}",
                        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 200, 255), 2)

            cv2.imshow("YOLO NEW (MAX ACCURACY)", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        send_to_django(motor_count, mobil_count,
                       pelanggar_count, motor_count + mobil_count, False)
        print("Program berhenti.")


if __name__ == "__main__":
    main()
