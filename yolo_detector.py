from ultralytics import YOLO
import cv2

# Load model
MODEL_PATH = "YOLO_model/best.pt"
model = YOLO(MODEL_PATH)

CLASS_NAMES = {
    0: "helmet",
    1: "no_helmet",
    2: "motor",
    3: "car"
}

def detect_objects(frame):
    """
    Mendeteksi objek pada 1 frame gambar.
    frame: numpy array (OpenCV)
    return: dict jumlah helmet / no_helmet / motor / car
    """

    results = model(frame)[0]

    counts = {
        "helmet": 0,
        "no_helmet": 0,
        "motor": 0,
        "car": 0,
    }

    for box in results.boxes:
        cls_id = int(box.cls)
        label = CLASS_NAMES.get(cls_id, None)

        if label in counts:
            counts[label] += 1

    return counts
