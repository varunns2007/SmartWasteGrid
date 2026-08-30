import argparse
import os
import sys
import time
import json
import yaml
import requests
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "conveyor.yaml")
FT_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "best.pt")
OLD_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
FALLBACK_MODEL = "yolo11s.pt"

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM_001")
AREA_NAME = os.getenv("AREA_NAME", "Demo Area")
LATITUDE = float(os.getenv("LATITUDE", "0.0"))
LONGITUDE = float(os.getenv("LONGITUDE", "0.0"))

CLASS_NAMES = {0: "wet", 1: "dry", 2: "recyclable"}
CLASS_COLORS = {0: (0, 255, 0), 1: (0, 165, 255), 2: (255, 0, 0)}

# Waste Item Name Inference Lookup
ITEM_NAMES_MAP = {
    0: "Organic Scraps / Food Waste",
    1: "Dry Waste Material",
    2: "Recyclable Bottle / Container"
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "camera_index": 1, "resolution": {"width": 1280, "height": 720},
        "confidence_threshold": 0.40, "roi": {"enabled": False},
        "temporal_stabilization": {"enabled": True, "minimum_confirmed_frames": 3},
        "batch_duration_seconds": 10, "default_waste_weight_kg": 12.5
    }

def send_batch_to_backend(batch_payload):
    endpoint = f"{API_URL.rstrip('/')}/api/batches"
    try:
        r = requests.post(endpoint, json=batch_payload, timeout=5)
        if r.status_code == 201:
            data = r.json()
            print(f"\n[CLIENT SUCCESS] Batch #{data.get('batch_id')} Created & Saved!", flush=True)
            print(f"   Primary Waste Type: {data.get('primary_waste_type')}", flush=True)
            print(f"   Detected Items:     {data.get('detected_items_summary')}", flush=True)
            print(f"   Recommended Plant:  {data.get('recommended_plant')}", flush=True)
            print(f"   WQI: {data.get('waste_quality_index')} | Energy: {data.get('energy_potential_kwh')} kWh | Carbon: {data.get('carbon_offset_kg')} kg CO2e", flush=True)
            return True, data.get('batch_id')
        else:
            print(f"[CLIENT ERROR] API returned status {r.status_code}: {r.text}", flush=True)
            return False, None
    except Exception as e:
        print(f"[CLIENT ERROR] Failed connecting to API: {e}", flush=True)
        return False, None

def run_webcam_client(camera_idx=None, batch_duration=10, weight_kg=12.5, conf_thresh=0.40):
    cfg = load_config()
    if camera_idx is None:
        camera_idx = cfg.get("camera_index", 1)
    
    # Select best available model weights
    if os.path.exists(FT_MODEL_PATH):
        model_path = FT_MODEL_PATH
    elif os.path.exists(OLD_MODEL_PATH):
        model_path = OLD_MODEL_PATH
    else:
        model_path = FALLBACK_MODEL
        
    print("============================================================", flush=True)
    print(f"STABILIZED SMARTWASTE CONVEYOR CLIENT", flush=True)
    print(f"Model: {model_path}", flush=True)
    print(f"Camera ID: {CAMERA_ID} (index: {camera_idx})", flush=True)
    print("============================================================", flush=True)

    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(model_path)
    
    cap = cv2.VideoCapture(camera_idx)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["resolution"]["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["resolution"]["height"])
    
    if not cap.isOpened():
        print(f"ERROR: Unable to open webcam at index {camera_idx}", flush=True)
        sys.exit(1)

    min_frames = cfg.get("temporal_stabilization", {}).get("minimum_confirmed_frames", 3)
    roi_enabled = cfg.get("roi", {}).get("enabled", False)
    
    # Active tracks: track_id -> {'cls': int, 'hits': int, 'last_seen': float, 'name': str}
    active_tracks = {}
    next_track_id = 1
    
    # Batch aggregators
    confirmed_items = [] # list of (cls_id, item_name)
    batch_counter = 1000
    batch_start_time = time.time()
    prev_time = time.time()
    
    upload_msg = ""
    upload_msg_timer = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Webcam frame capture failed.", flush=True)
            break
            
        fh, fw, _ = frame.shape
        
        # Apply ROI crop if enabled
        if roi_enabled:
            x1_r, y1_r = cfg["roi"].get("x1", 0), cfg["roi"].get("y1", 0)
            x2_r, y2_r = cfg["roi"].get("x2", fw), cfg["roi"].get("y2", fh)
            cv2.rectangle(frame, (x1_r, y1_r), (x2_r, y2_r), (255, 255, 0), 2)
            cv2.putText(frame, "ROI REGION", (x1_r+5, y1_r+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Run inference
        results = model.predict(frame, imgsz=640, device=device, conf=conf_thresh, verbose=False)
        
        frame_detections = []
        if len(results) > 0 and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                bx1, by1, bx2, by2 = [int(v) for v in box.xyxy[0].tolist()]
                
                # Check ROI bounding
                if roi_enabled:
                    if bx1 < x1_r or by1 < y1_r or bx2 > x2_r or by2 > y2_r:
                        continue
                        
                frame_detections.append((cls_id, conf, (bx1, by1, bx2, by2)))
                
                col = CLASS_COLORS.get(cls_id, (255, 255, 255))
                cname = CLASS_NAMES.get(cls_id, str(cls_id))
                item_name = ITEM_NAMES_MAP.get(cls_id, cname)
                
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), col, 2)
                cv2.putText(frame, f"{cname} ({conf*100:.0f}%)", (bx1, max(by1-5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)

        # Simple Temporal Frame Stabilization (Duplicate Suppression)
        curr_time = time.time()
        for cls_id, conf, bbox in frame_detections:
            matched = False
            for tid, track in active_tracks.items():
                if track['cls'] == cls_id and (curr_time - track['last_seen']) < 1.5:
                    track['hits'] += 1
                    track['last_seen'] = curr_time
                    matched = True
                    if track['hits'] == min_frames and not track.get('confirmed'):
                        track['confirmed'] = True
                        item_name = ITEM_NAMES_MAP.get(cls_id, CLASS_NAMES[cls_id])
                        confirmed_items.append((cls_id, item_name))
                        print(f"[STABILIZED DETECTION] Confirmed object #{tid}: {item_name} ({CLASS_NAMES[cls_id]})", flush=True)
                    break
                    
            if not matched:
                active_tracks[next_track_id] = {
                    'cls': cls_id,
                    'hits': 1,
                    'last_seen': curr_time,
                    'confirmed': False
                }
                next_track_id += 1

        # Clean stale tracks
        stale_ids = [tid for tid, tr in active_tracks.items() if (curr_time - tr['last_seen']) > 2.0]
        for tid in stale_ids:
            del active_tracks[tid]

        # Calculate counts
        fps = 1.0 / max(curr_time - prev_time, 0.001)
        prev_time = curr_time
        
        elapsed_batch = int(curr_time - batch_start_time)
        remaining_time = max(0, batch_duration - elapsed_batch)
        
        wet_cnt = sum(1 for cid, _ in confirmed_items if cid == 0)
        dry_cnt = sum(1 for cid, _ in confirmed_items if cid == 1)
        rec_cnt = sum(1 for cid, _ in confirmed_items if cid == 2)
        tot_cnt = len(confirmed_items)

        # HUD Overlay
        cv2.putText(frame, f"SmartWaste Conveyor Feed | Cam: {CAMERA_ID} | FPS: {fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Batch #{batch_counter} | Timer: {remaining_time}s remaining", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(frame, f"Confirmed Items -> Wet: {wet_cnt} | Dry: {dry_cnt} | Recyclable: {rec_cnt} | Total: {tot_cnt}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        if upload_msg and time.time() < upload_msg_timer:
            cv2.putText(frame, upload_msg, (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("SmartWaste Stabilized Conveyor Client", frame)
        
        # Check batch interval expiry
        if elapsed_batch >= batch_duration:
            batch_counter += 1
            print(f"\n[BATCH INTERVAL EXPIRED] Aggregated {tot_cnt} confirmed objects in {batch_duration}s.", flush=True)
            
            if tot_cnt > 0:
                wet_pct = (wet_cnt / tot_cnt) * 100.0
                dry_pct = (dry_cnt / tot_cnt) * 100.0
                rec_pct = (rec_cnt / tot_cnt) * 100.0
            else:
                wet_pct, dry_pct, rec_pct = 0.0, 0.0, 0.0
                
            # Build item name summary dict
            item_summary_dict = {}
            for _, item_name in confirmed_items:
                item_summary_dict[item_name] = item_summary_dict.get(item_name, 0) + 1
                
            # Determine primary waste type
            if wet_pct >= dry_pct and wet_pct >= rec_pct and wet_pct > 0:
                primary_type = "wet"
            elif rec_pct >= wet_pct and rec_pct >= dry_pct and rec_pct > 0:
                primary_type = "recyclable"
            elif dry_pct > 0:
                primary_type = "dry"
            else:
                primary_type = "recyclable"

            payload = {
                "area_name": AREA_NAME,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "camera_id": CAMERA_ID,
                "primary_waste_type": primary_type,
                "detected_items_summary": json.dumps(item_summary_dict),
                "total_waste_kg": weight_kg,
                "organic_kg": round(weight_kg * (wet_pct / 100.0), 2),
                "plastic_kg": None,
                "paper_kg": None,
                "cardboard_kg": None,
                "glass_kg": None,
                "metal_kg": None,
                "other_kg": round(weight_kg * ((dry_pct + rec_pct) / 100.0), 2),
                "organic_percentage": round(wet_pct, 2),
                "recyclable_percentage": round(rec_pct, 2),
                "dry_percentage": round(dry_pct, 2),
                "moisture_percentage": 0.0
            }

            success, b_id = send_batch_to_backend(payload)
            if success:
                upload_msg = f"Batch #{b_id} Saved to Database!"
            else:
                upload_msg = "Database Upload Failed!"
            upload_msg_timer = time.time() + 4.0
            
            # Reset batch
            confirmed_items = []
            batch_start_time = time.time()

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmartWaste Conveyor Client")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (defaults to conveyor.yaml setting)")
    parser.add_argument("--duration", type=int, default=10, help="Batch duration in seconds")
    parser.add_argument("--weight", type=float, default=12.5, help="Total waste weight in kg")
    parser.add_argument("--conf", type=float, default=0.40, help="Confidence threshold")
    args = parser.parse_args()
    
    run_webcam_client(args.camera, args.duration, args.weight, args.conf)
