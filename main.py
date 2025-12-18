import cv2
import mediapipe as mp
import time
import sqlite3
import numpy as np
import os
import json
import pygame
import threading
from tensorflow.keras.models import load_model

# Paths and constants
DB_PATH = "drivers.db"
ACTIVE_FILE = "current_driver.json"
RECORDS_DIR = "records"
ALERT_SOUND = "alert.wav"
MODEL_PATH = "model.h5"

last_alert_time = 0
ALERT_COOLDOWN = 10  # seconds
alert_count = 0
MAX_VOLUME = 1.0
MIN_VOLUME = 0.2
RESET_THRESHOLD = 30  # seconds of silence to reset alert count
EYE_AR_THRESH = 0.21
EYE_AR_CONSEC_FRAMES = 20
MAR_THRESH = 0.6
COUNTER = 0

os.makedirs(RECORDS_DIR, exist_ok=True)

def get_active_driver_id():
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("driver_id")
    return None

def db():
    return sqlite3.connect(DB_PATH)

pygame.mixer.init()

def play_alert_sound(volume=1.0, duration=3):
    try:
        sound = pygame.mixer.Sound(ALERT_SOUND)
        sound.set_volume(volume)
        channel = sound.play()

        def stop_sound():
            time.sleep(duration)
            if channel.get_busy():
                channel.stop()

        threading.Thread(target=stop_sound, daemon=True).start()
    except Exception as e:
        print(f"[ERROR] Could not play sound: {e}")

def eye_aspect_ratio(landmarks, eye_indices):
    A = np.linalg.norm(landmarks[eye_indices[1]] - landmarks[eye_indices[5]])
    B = np.linalg.norm(landmarks[eye_indices[2]] - landmarks[eye_indices[4]])
    C = np.linalg.norm(landmarks[eye_indices[0]] - landmarks[eye_indices[3]])
    return (A + B) / (2.0 * C)

def mouth_aspect_ratio(landmarks):
    vertical = np.linalg.norm(landmarks[13] - landmarks[14])
    horizontal = np.linalg.norm(landmarks[78] - landmarks[308])
    return vertical / horizontal

# Load trained model
model = load_model(MODEL_PATH)

# Initialize MediaPipe
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, min_detection_confidence=0.5)

print("Starting camera...")
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            h, w, _ = frame.shape
            landmarks = np.array([[lm.x * w, lm.y * h] for lm in face_landmarks.landmark])

            left_eye_indices = [33, 160, 158, 133, 153, 144]
            right_eye_indices = [362, 385, 387, 263, 373, 380]
            mouth_indices = [13, 14, 78, 308]

            leftEAR = eye_aspect_ratio(landmarks, left_eye_indices)
            rightEAR = eye_aspect_ratio(landmarks, right_eye_indices)
            ear = (leftEAR + rightEAR) / 2.0
            mar = mouth_aspect_ratio(landmarks)

            for idx in left_eye_indices + right_eye_indices + mouth_indices:
                cv2.circle(frame, (int(landmarks[idx][0]), int(landmarks[idx][1])), 2, (0, 255, 0), -1)

            print(f"EAR: {ear:.3f}, MAR: {mar:.3f}")

            alert_type = None

            # Primary EAR logic
            if ear < EYE_AR_THRESH:
                COUNTER += 1
                if COUNTER >= EYE_AR_CONSEC_FRAMES:
                    # Use model to confirm drowsiness
                    x_coords = landmarks[:, 0]
                    y_coords = landmarks[:, 1]
                    x1, y1 = int(np.min(x_coords)), int(np.min(y_coords))
                    x2, y2 = int(np.max(x_coords)), int(np.max(y_coords))

                    pad = 20
                    x1 = max(x1 - pad, 0)
                    y1 = max(y1 - pad, 0)
                    x2 = min(x2 + pad, w)
                    y2 = min(y2 + pad, h)

                    face_crop = frame[y1:y2, x1:x2]
                    if face_crop.size != 0:
                        try:
                            face_resized = cv2.resize(face_crop, (224, 224))
                            face_input = face_resized / 255.0
                            face_input = np.expand_dims(face_input, axis=0)
                            prediction = model.predict(face_input)[0][0]
                            print(f"Model Confidence: {prediction:.2f}")
                            if prediction > 0.7:
                                alert_type = "drowsiness"
                        except Exception as e:
                            print(f"[ERROR] Model prediction failed: {e}")
                    COUNTER = 0
            else:
                COUNTER = 0

            # MAR logic for yawning
            if mar > MAR_THRESH:
                alert_type = "yawning"

            if alert_type:
                current_time = time.time()
                if current_time - last_alert_time > ALERT_COOLDOWN:
                    if current_time - last_alert_time > RESET_THRESHOLD:
                        alert_count = 0

                    alert_count += 1
                    volume = min(MIN_VOLUME + 0.2 * alert_count, MAX_VOLUME)
                    print(f"[ALERT] {alert_type.capitalize()} Detected! Volume: {volume:.2f}")
                    play_alert_sound(volume)
                    last_alert_time = current_time

                    driver_id = get_active_driver_id()
                    if driver_id:
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_dir = os.path.join(RECORDS_DIR, str(driver_id))
                        os.makedirs(save_dir, exist_ok=True)
                        filename = f"event_{int(current_time)}.jpg"
                        img_path = os.path.join(save_dir, filename)
                        cv2.imwrite(img_path, frame)
                        db_image_path = f"{RECORDS_DIR}/{driver_id}/{filename}"

                        conn = db()
                        c = conn.cursor()
                        c.execute("""CREATE TABLE IF NOT EXISTS events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            driver_id TEXT,
                            event_type TEXT,
                            ts TEXT,
                            image_path TEXT
                        )""")
                        c.execute("INSERT INTO events(driver_id, event_type, ts, image_path) VALUES (?,?,?,?)",
                                  (driver_id, alert_type, ts, db_image_path))
                        conn.commit()
                        conn.close()

    cv2.imshow("Drowsiness Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()