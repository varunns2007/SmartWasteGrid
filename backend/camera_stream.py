import os
import cv2
import time
import threading
import numpy as np
from datetime import datetime

def get_configured_camera_index():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "conveyor.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                if "camera_index" in cfg:
                    return int(cfg["camera_index"])
        except Exception:
            pass
    env_idx = os.getenv("CAMERA_INDEX")
    if env_idx is not None and env_idx != "":
        try:
            return int(env_idx)
        except Exception:
            pass
    return 0  # Default to 0 (Integrated Camera or first available)

_webcam_cache = []
_webcam_cache_time = 0.0

def detect_connected_webcams():
    """Probes available video cameras with caching to avoid stealing active stream."""
    global _webcam_cache, _webcam_cache_time
    now = time.time()
    if now - _webcam_cache_time < 15.0 and _webcam_cache:
        return _webcam_cache

    active_cam = VideoCamera._instance
    active_idx = active_cam.camera_index if (active_cam and active_cam.use_hardware_cam) else None

    found = []
    for idx in range(3):
        if active_idx is not None and idx == active_idx:
            found.append({
                "index": idx,
                "name": "Integrated Camera" if idx == 0 else f"USB Webcam #{idx}",
                "resolution": "640x480",
                "active": True
            })
            continue

        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    name = "Integrated Camera" if idx == 0 else f"USB Webcam #{idx}"
                    found.append({
                        "index": idx,
                        "name": name,
                        "resolution": f"{w}x{h}",
                        "active": True
                    })
                cap.release()
        except Exception:
            pass

    if not found:
        found = [
            {"index": 0, "name": "Integrated Camera (Cam 0)", "resolution": "640x480", "active": True},
            {"index": 1, "name": "USB Webcam (Cam 1)", "resolution": "640x480", "active": False}
        ]

    _webcam_cache = found
    _webcam_cache_time = now
    return found

class VideoCamera:
    _instance = None
    
    def __new__(cls, camera_index=None):
        if cls._instance is None:
            cls._instance = super(VideoCamera, cls).__new__(cls)
            if camera_index is None:
                camera_index = get_configured_camera_index()
            cls._instance.init_camera(camera_index)
        return cls._instance

    def init_camera(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.cap_lock = threading.Lock()
        self.app = None
        self.current_boxes = []
        self.running = True
        self.last_db_log_time = 0.0
        self.sim_tick = 0
        self.use_hardware_cam = False
        self.force_simulation = False  # Start in hardware mode by default
        self.tracked_objects = []  # Tracks unique physical objects across frames
        self.tracked_lock = threading.Lock()

        self.class_names = {0: 'wet', 1: 'dry', 2: 'recyclable'}
        self.class_colors = {
            0: (16, 185, 129),   # Green (Wet)
            1: (245, 158, 11),   # Amber (Dry)
            2: (14, 165, 233)    # Sky Blue (Recyclable)
        }
        self.sorting_bins = {
            0: "WET BIN (COMPOST / BIO-CNG)",
            1: "DRY BIN (RDF / LANDFILL)",
            2: "RECYCLABLE BIN (MRF)"
        }

        # Initialize current_frame with synthetic conveyor frame immediately
        self.current_frame = self._generate_vibrant_conveyor_frame()

        # Load YOLO model for hardware mode
        model_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'runs', 'SmartWasteGrid_YOLO11s_FT', 'weights', 'best.pt'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'runs', 'SmartWasteGrid_YOLO11s', 'weights', 'best.pt'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'yolo11s.pt')
        ]
        
        self.model = None
        for mp in model_paths:
            if os.path.exists(mp):
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(mp)
                    print(f"[*] Loaded YOLO model for live video feed from {mp}")
                    break
                except Exception as e:
                    print(f"[!] Warning loading YOLO model {mp}: {e}")

        # Thread 1: Fast Frame Capture Thread (30 FPS)
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        # Thread 2: Asynchronous YOLO AI Worker Thread
        self.ai_thread = threading.Thread(target=self._ai_loop, daemon=True)
        self.ai_thread.start()

    def set_camera_index(self, index: int):
        with self.cap_lock:
            self.camera_index = index
            self.force_simulation = False
            if self.cap and self.cap.isOpened():
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def set_simulation_mode(self, enabled: bool):
        with self.cap_lock:
            self.force_simulation = enabled
            if enabled:
                self.use_hardware_cam = False
                if self.cap and self.cap.isOpened():
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
            else:
                if self.cap and self.cap.isOpened():
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None

    def _generate_vibrant_conveyor_frame(self):
        self.sim_tick += 1
        # Industrial metallic conveyor background
        frame = np.full((480, 640, 3), (45, 40, 35), dtype=np.uint8)
        
        # Conveyor belt track (steel slate grey)
        cv2.rectangle(frame, (40, 60), (600, 420), (30, 30, 30), -1)
        cv2.rectangle(frame, (40, 60), (600, 420), (0, 255, 200), 2)
        
        # Moving belt slots (animated)
        offset = (self.sim_tick * 8) % 60
        for x in range(40 + offset, 600, 60):
            cv2.line(frame, (x, 60), (x, 420), (55, 55, 55), 2)
            
        # Side guard rails
        cv2.rectangle(frame, (20, 50), (620, 60), (90, 80, 70), -1)
        cv2.rectangle(frame, (20, 420), (620, 430), (90, 80, 70), -1)
        
        # Dynamic moving waste objects with live YOLO bounding box overlays
        # Object 1: PET Plastic Bottle (Recyclable - Class 2)
        x1 = (100 + self.sim_tick * 5) % 520 + 40
        y1 = 90
        cv2.rectangle(frame, (x1, y1), (x1 + 110, y1 + 65), (220, 140, 30), -1)
        cv2.rectangle(frame, (x1, y1), (x1 + 110, y1 + 65), (14, 165, 233), 2)
        cv2.rectangle(frame, (x1, max(0, y1-25)), (x1+160, y1), (14, 165, 233), -1)
        cv2.putText(frame, "2:RECYCLABLE 96%", (x1+5, max(15, y1-7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(frame, "PET BOTTLE", (x1+10, y1+42), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Object 2: Organic Waste (Wet - Class 0)
        x2 = (280 + self.sim_tick * 5) % 520 + 40
        y2 = 200
        cv2.rectangle(frame, (x2, y2), (x2 + 120, y2 + 75), (30, 140, 50), -1)
        cv2.rectangle(frame, (x2, y2), (x2 + 120, y2 + 75), (16, 185, 129), 2)
        cv2.rectangle(frame, (x2, max(0, y2-25)), (x2+130, y2), (16, 185, 129), -1)
        cv2.putText(frame, "0:WET 98%", (x2+5, max(15, y2-7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(frame, "BANANA PEEL", (x2+10, y2+48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Object 3: Textile Cloth Rag (Dry - Class 1)
        x3 = (460 + self.sim_tick * 5) % 520 + 40
        y3 = 310
        cv2.rectangle(frame, (x3, y3), (x3 + 115, y3 + 70), (40, 120, 210), -1)
        cv2.rectangle(frame, (x3, y3), (x3 + 115, y3 + 70), (245, 158, 11), 2)
        cv2.rectangle(frame, (x3, max(0, y3-25)), (x3+130, y3), (245, 158, 11), -1)
        cv2.putText(frame, "1:DRY 94%", (x3+5, max(15, y3-7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        cv2.putText(frame, "CLOTH RAG", (x3+10, y3+45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        return frame

    def _capture_loop(self):
        while self.running:
            frame_captured = None
            if not self.force_simulation:
                with self.cap_lock:
                    if self.cap is None or not self.cap.isOpened():
                        # Try requested camera index first
                        indices_to_try = [self.camera_index]
                        if self.camera_index != 0:
                            indices_to_try.append(0)  # Fallback to index 0

                        for test_idx in indices_to_try:
                            try:
                                cap_test = cv2.VideoCapture(test_idx, cv2.CAP_DSHOW)
                                if cap_test.isOpened():
                                    ret, test_frame = cap_test.read()
                                    if ret and test_frame is not None and test_frame.size > 0:
                                        self.cap = cap_test
                                        self.camera_index = test_idx
                                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                                        self.cap.set(cv2.CAP_PROP_FPS, 30)
                                        frame_captured = test_frame
                                        break
                                    else:
                                        cap_test.release()
                                else:
                                    cap_test.release()
                            except Exception:
                                pass

                    elif self.cap and self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret and frame is not None and frame.size > 0:
                            frame_captured = frame
                        else:
                            try:
                                self.cap.release()
                            except Exception:
                                pass
                            self.cap = None

            if frame_captured is not None:
                self.current_frame = frame_captured
                self.use_hardware_cam = True
            else:
                self.use_hardware_cam = False
                self.current_frame = self._generate_vibrant_conveyor_frame()

            time.sleep(0.030)

    def _ai_loop(self):
        while self.running:
            if self.use_hardware_cam and self.model is not None and self.current_frame is not None:
                try:
                    frame_copy = self.current_frame.copy()
                    results = self.model.predict(source=frame_copy, conf=0.45, verbose=False)
                    boxes_list = []
                    now = time.time()

                    with self.tracked_lock:
                        # Retain spatial tracking memory for 60 seconds to prevent re-logging stationary objects
                        self.tracked_objects = [obj for obj in self.tracked_objects if (now - obj.get("last_seen", 0)) < 60.0]

                        if results and len(results) > 0:
                            boxes = results[0].boxes
                            if boxes is not None and len(boxes) > 0:
                                for box in boxes:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                                    cls_id = int(box.cls[0].cpu().numpy())
                                    conf = float(box.conf[0].cpu().numpy())
                                    cx = (x1 + x2) // 2
                                    cy = (y1 + y2) // 2

                                    boxes_list.append((x1, y1, x2, y2, cls_id, conf))

                                    # Match against currently tracked objects (distance < 120 pixels)
                                    matched = False
                                    for obj in self.tracked_objects:
                                        dist = ((obj["cx"] - cx) ** 2 + (obj["cy"] - cy) ** 2) ** 0.5
                                        if obj["cls_id"] == cls_id and dist < 120:
                                            obj["cx"] = cx
                                            obj["cy"] = cy
                                            obj["last_seen"] = now
                                            matched = True
                                            break

                                    if not matched and conf >= 0.50:
                                        # New unique physical item entered conveyor view
                                        self.tracked_objects.append({
                                            "cx": cx,
                                            "cy": cy,
                                            "cls_id": cls_id,
                                            "first_seen": now,
                                            "last_seen": now
                                        })
                                        self.log_detection_to_db(cls_id, self.class_names.get(cls_id, 'waste'), conf)

                    self.current_boxes = boxes_list
                except Exception as e:
                    print(f"[!] AI loop error: {e}")
            time.sleep(0.06)

    def log_detection_to_db(self, cls_id, cname, conf):
        if not self.use_hardware_cam:
            return  # Strictly do not log simulated items to the database

        now = time.time()
        if now - self.last_db_log_time < 2.0:
            return  
        self.last_db_log_time = now

        try:
            from backend.flask_db.db import db
            from backend.flask_models.models import ConveyorItem, LedgerEntry
            from flask import current_app
            
            ctx = None
            if hasattr(self, 'app') and self.app is not None:
                ctx = self.app.app_context()
            elif current_app:
                ctx = current_app.app_context()

            if ctx:
                with ctx:
                    item_names = {
                        0: "Live Organic / Wet Waste",
                        1: "Live Dry Scrap / RDF",
                        2: "Live Recyclable / PET Bottle"
                    }
                    item_name = item_names.get(cls_id, f"Live Detected Waste (Class {cls_id})")
                    bin_decision = self.sorting_bins.get(cls_id, "GENERAL BIN")
                    item_weight = round(float(np.random.uniform(0.15, 0.65)), 2)

                    item = ConveyorItem(
                        item_name=item_name,
                        class_id=cls_id,
                        class_name=cname,
                        confidence=float(conf),
                        sorting_decision=bin_decision,
                        item_weight_kg=item_weight,
                        camera_id=f"LIVE_WEBCAM_CAM_{self.camera_index}",
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(item)
                    db.session.commit()

                    try:
                        LedgerEntry.create_entry(
                            'CAMERA_DETECTION', 
                            item.to_dict(), 
                            f"Live Webcam Intake: {item_name} (Confidence: {int(conf*100)}%)"
                        )
                    except Exception:
                        pass
        except Exception as e:
            print(f"[!] Error logging camera detection to DB: {e}")

    def get_frame(self):
        if not hasattr(self, 'current_frame') or self.current_frame is None or np.mean(self.current_frame) < 1.0:
            self.current_frame = self._generate_vibrant_conveyor_frame()

        frame = self.current_frame.copy()

        if self.use_hardware_cam:
            for (x1, y1, x2, y2, cls_id, conf) in self.current_boxes:
                cname = self.class_names.get(cls_id, f"cls_{cls_id}")
                color = self.class_colors.get(cls_id, (255, 255, 255))
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                label_str = f"{cls_id}:{cname.upper()} {int(conf*100)}%"
                cv2.rectangle(frame, (x1, max(0, y1-25)), (x1+160, y1), color, -1)
                cv2.putText(frame, label_str, (x1+5, max(15, y1-7)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, f"LIVE WEBCAM #{self.camera_index} | YOLO11s ONLINE | {ts}", (15, 460),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        else:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, f"SIMULATION DIGITAL TWIN | {ts}", (15, 460),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 2)

        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes()


def gen_frames():
    camera = VideoCamera()
    while True:
        frame = camera.get_frame()
        time.sleep(0.033)  
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def start_camera_auto_logger(app):
    cam = VideoCamera()
    cam.app = app
