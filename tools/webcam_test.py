import argparse
import os
import sys
import time
import cv2
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BEST_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
FALLBACK_MODEL = "yolo11s.pt"

CLASS_NAMES = {0: "wet", 1: "dry", 2: "recyclable"}
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

def run_webcam(camera_idx=None):
    if camera_idx is None:
        camera_idx = get_default_camera_idx()
    model_path = BEST_MODEL_PATH if os.path.exists(BEST_MODEL_PATH) else FALLBACK_MODEL
    print(f"Loading model from: {model_path}", flush=True)
    
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}", flush=True)
    model = YOLO(model_path)
    
    cap = cv2.VideoCapture(camera_idx)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print(f"ERROR: Unable to open webcam at index {camera_idx}", flush=True)
        sys.exit(1)
        
    print(f"Webcam {camera_idx} opened. Press 'q' or 'ESC' to exit.", flush=True)
    
    prev_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Webcam frame read failed.", flush=True)
            break
            
        # Run inference
        results = model.predict(frame, imgsz=640, device=device, verbose=False)
        
        wet_cnt = 0
        dry_cnt = 0
        rec_cnt = 0
        
        if len(results) > 0 and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                
                if cls_id == 0:
                    wet_cnt += 1
                elif cls_id == 1:
                    dry_cnt += 1
                elif cls_id == 2:
                    rec_cnt += 1
                    
                color = CLASS_COLORS.get(cls_id, (255, 255, 255))
                cname = CLASS_NAMES.get(cls_id, str(cls_id))
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{cname} {conf*100:.1f}%", (x1, max(y1 - 5, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        curr_time = time.time()
        fps = 1.0 / max(curr_time - prev_time, 0.001)
        prev_time = curr_time
        
        # Display HUD info
        cv2.putText(frame, f"SmartWaste Live Detection | Cam: {camera_idx}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"Wet: {wet_cnt} | Dry: {dry_cnt} | Recyclable: {rec_cnt} | Total: {wet_cnt+dry_cnt+rec_cnt}",
                    (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow("SmartWaste Live Detection", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27: # 27 = ESC
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmartWaste Webcam Real-Time Inference")
    parser.add_argument("--camera", type=int, default=None, help="Webcam camera index (defaults to USB webcam setting)")
    args = parser.parse_args()
    
    run_webcam(args.camera)
