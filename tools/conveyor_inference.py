import os
import sys
import time
import json
import sqlite3
import cv2
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FT_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "best.pt")
BASE_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
DB_PATH = os.path.join(PROJECT_ROOT, "database", "smartwaste.db")

def get_model_path():
    if os.path.exists(FT_MODEL_PATH):
        return FT_MODEL_PATH
    return BASE_MODEL_PATH

def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS waste_batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_name TEXT DEFAULT 'Conveyor Area A',
        latitude REAL DEFAULT 12.9716,
        longitude REAL DEFAULT 77.5946,
        camera_id TEXT DEFAULT 'CONVEYOR_CAM_01',
        capture_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_waste_kg REAL DEFAULT 0.0,
        organic_kg REAL DEFAULT 0.0,
        plastic_kg REAL DEFAULT 0.0,
        paper_kg REAL DEFAULT 0.0,
        cardboard_kg REAL DEFAULT 0.0,
        glass_kg REAL DEFAULT 0.0,
        metal_kg REAL DEFAULT 0.0,
        other_kg REAL DEFAULT 0.0,
        organic_percentage REAL DEFAULT 0.0,
        recyclable_percentage REAL DEFAULT 0.0,
        dry_percentage REAL DEFAULT 0.0,
        moisture_percentage REAL DEFAULT 0.0,
        waste_quality_index REAL DEFAULT 75.0,
        lhv_mj_kg REAL DEFAULT 15.0,
        energy_potential_kwh REAL DEFAULT 100.0,
        dumping_detected INTEGER DEFAULT 0,
        dumping_severity TEXT DEFAULT 'Low',
        recommended_plant TEXT DEFAULT 'Biogas Plant Alpha',
        plant_type TEXT DEFAULT 'Anaerobic Digestion',
        plant_distance_km REAL DEFAULT 5.2,
        plant_capacity_available_kg REAL DEFAULT 5000.0,
        transport_cost REAL DEFAULT 150.0,
        carbon_offset_kg REAL DEFAULT 45.0,
        suitability_score REAL DEFAULT 88.0,
        optimization_method REAL DEFAULT 1.0,
        optimization_status TEXT DEFAULT 'COMPLETED',
        processing_status TEXT DEFAULT 'PENDING',
        primary_waste_type TEXT,
        detected_items_summary TEXT,
        processed_at TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS waste_detections (
        detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        object_id INTEGER,
        camera_id TEXT DEFAULT 'CONVEYOR_CAM_01',
        detected_class TEXT,
        confidence REAL,
        x_center REAL,
        y_center REAL,
        width REAL,
        height REAL,
        capture_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        frame_number INTEGER,
        sorting_decision TEXT,
        sorting_status TEXT DEFAULT 'SUCCESS',
        FOREIGN KEY (batch_id) REFERENCES waste_batches (batch_id)
    );
    """)
    conn.commit()
    return conn

def make_sorting_decision(class_name, conf, threshold=0.40):
    if conf < threshold:
        return "UNCERTAIN", "UNCERTAIN"
    
    mapping = {
        "wet": ("WET BIN", "wet_bin"),
        "dry": ("DRY BIN", "dry_bin"),
        "recyclable": ("RECYCLABLE BIN", "recyclable_bin")
    }
    decision_text, command = mapping.get(class_name.lower(), ("UNCERTAIN", "uncertain"))
    return decision_text, command

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "conveyor.yaml")

def get_default_camera_idx():
    if os.path.exists(CONFIG_PATH):
        try:
            import yaml
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                return cfg.get("camera_index", 1)
        except Exception:
            pass
    return 1

def run_conveyor_inference(source=None, conf_thresh=0.40):
    if source is None:
        source = get_default_camera_idx()
    model_path = get_model_path()
    print(f"Loading YOLO model: {model_path}")
    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(model_path)
    
    conn = init_database()
    cursor = conn.cursor()
    
    use_simulation = False
    cap = None
    if isinstance(source, str) and source.lower() == "simulate":
        use_simulation = True
    else:
        try:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                use_simulation = True
        except Exception:
            use_simulation = True

    if use_simulation:
        print("\n[SIMULATION MODE ACTIVE] Live hardware camera not found or simulation requested.")
        print("Generating animated Conveyor Belt video stream with real-time AI object tracking & database logging...")
    else:
        print("\nStarting Real-Time Conveyor Inference with Object Tracking & Sorting Decisions...")
    
    print("Press 'Q' to exit.")
    
    class_names = {0: "wet", 1: "dry", 2: "recyclable"}
    tracked_objects = set()
    frame_count = 0
    sim_tick = 0
    
    # Create initial batch in DB
    cursor.execute("INSERT INTO waste_batches (primary_waste_type, detected_items_summary) VALUES (?, ?)",
                   ("Pending", json.dumps({})))
    batch_id = cursor.lastrowid
    conn.commit()

    prev_time = time.time()
    
    def generate_sim_frame(tick):
        import numpy as np
        frame = np.full((480, 640, 3), (45, 40, 35), dtype=np.uint8)
        cv2.rectangle(frame, (40, 60), (600, 420), (30, 30, 30), -1)
        cv2.rectangle(frame, (40, 60), (600, 420), (0, 255, 200), 2)
        offset = (tick * 8) % 60
        for x in range(40 + offset, 600, 60):
            cv2.line(frame, (x, 60), (x, 420), (55, 55, 55), 2)
        cv2.rectangle(frame, (20, 50), (620, 60), (90, 80, 70), -1)
        cv2.rectangle(frame, (20, 420), (620, 430), (90, 80, 70), -1)
        
        # Sim item 1: Recyclable bottle
        x1 = (100 + tick * 5) % 520 + 40
        y1 = 90
        cv2.rectangle(frame, (x1, y1), (x1 + 110, y1 + 65), (220, 140, 30), -1)
        
        # Sim item 2: Organic wet
        x2 = (280 + tick * 5) % 520 + 40
        y2 = 200
        cv2.rectangle(frame, (x2, y2), (x2 + 120, y2 + 75), (30, 140, 50), -1)
        
        # Sim item 3: Dry cloth
        x3 = (460 + tick * 5) % 520 + 40
        y3 = 310
        cv2.rectangle(frame, (x3, y3), (x3 + 115, y3 + 70), (40, 120, 210), -1)
        
        return frame

    while True:
        if use_simulation:
            sim_tick += 1
            frame = generate_sim_frame(sim_tick)
            ret = True
            time.sleep(0.033)
        else:
            ret, frame = cap.read()
            if not ret:
                break
            
        frame_count += 1
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time + 1e-6)
        prev_time = curr_time
        
        # Track objects
        results = model.track(frame, persist=True, device=device, conf=conf_thresh, verbose=False)
        
        if results and len(results) > 0:
            res = results[0]
            boxes = res.boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    cname = class_names.get(cls_id, "unknown")
                    
                    obj_id = int(box.id[0].item()) if box.id is not None else frame_count
                    
                    # Bbox coordinates
                    xywh = box.xywh[0].tolist()
                    x_c, y_c, w, h = xywh[0], xywh[1], xywh[2], xywh[3]
                    
                    decision, command = make_sorting_decision(cname, conf, conf_thresh)
                    
                    # Log unique tracked objects to DB
                    if obj_id not in tracked_objects:
                        tracked_objects.add(obj_id)
                        cursor.execute("""
                        INSERT INTO waste_detections 
                        (batch_id, object_id, camera_id, detected_class, confidence, x_center, y_center, width, height, frame_number, sorting_decision)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (batch_id, obj_id, "CONVEYOR_CAM_01", cname, conf, x_c, y_c, w, h, frame_count, decision))
                        conn.commit()
                        print(f"[SORTING] Object #{obj_id} ({cname.upper()} {conf:.2f}) → {decision} [Command: {command}]")

                    # Draw on frame
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"ID:{obj_id} {cname.upper()} {conf:.2f} -> {decision}", 
                                (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Overlay FPS & Camera Info
        cv2.putText(frame, f"CONVEYOR CAM | FPS: {fps:.1f} | Active Objects: {len(tracked_objects)}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow("SmartWasteGrid Conveyor Tracking & Sorting", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    conn.close()
    print("Conveyor inference session completed cleanly.")

if __name__ == "__main__":
    src = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_conveyor_inference(src)
