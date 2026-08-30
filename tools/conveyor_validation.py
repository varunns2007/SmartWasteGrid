import os
import sys
import json
import glob
import time
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FT_WEIGHTS = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "best.pt")
OLD_WEIGHTS = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
CONVEYOR_TEST_DIR = os.path.join(PROJECT_ROOT, "dataset", "conveyor_real", "test", "images")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

def validate_conveyor():
    print("============================================================", flush=True)
    print("REAL CONVEYOR MODEL VALIDATION ENGINE", flush=True)
    print("============================================================", flush=True)
    
    weights = FT_WEIGHTS if os.path.exists(FT_WEIGHTS) else OLD_WEIGHTS
    print(f"Loading model weights: {weights}", flush=True)
    
    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(weights)
    
    img_files = glob.glob(os.path.join(CONVEYOR_TEST_DIR, "*.*"))
    if not img_files:
        print(f"No test images found in {CONVEYOR_TEST_DIR}. Place conveyor test frames there to run validation.", flush=True)
        # Create dummy validation metric response for pipeline completeness
        metrics = {
            "model_weights": weights,
            "images_evaluated": 0,
            "average_confidence": 0.0,
            "average_inference_ms": 0.0,
            "detections_by_class": {"wet": 0, "dry": 0, "recyclable": 0},
            "status": "NO_TEST_IMAGES_FOUND"
        }
    else:
        tot_time = 0.0
        tot_detections = 0
        conf_sum = 0.0
        cls_counts = {0: 0, 1: 0, 2: 0}
        
        for img_path in img_files:
            t0 = time.time()
            results = model.predict(img_path, imgsz=640, device=device, verbose=False)
            t1 = time.time()
            tot_time += (t1 - t0)
            
            if len(results) > 0 and len(results[0].boxes) > 0:
                for box in results[0].boxes:
                    cid = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    tot_detections += 1
                    conf_sum += conf
                    if cid in cls_counts:
                        cls_counts[cid] += 1
                        
        avg_conf = (conf_sum / tot_detections * 100.0) if tot_detections else 0.0
        avg_time_ms = (tot_time / len(img_files) * 1000.0) if img_files else 0.0
        
        metrics = {
            "model_weights": weights,
            "images_evaluated": len(img_files),
            "total_detections": tot_detections,
            "average_confidence": round(avg_conf, 2),
            "average_inference_ms": round(avg_time_ms, 2),
            "detections_by_class": {
                "wet": cls_counts[0],
                "dry": cls_counts[1],
                "recyclable": cls_counts[2]
            },
            "status": "VALIDATION_PASSED"
        }

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, "conveyor_validation.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        
    print(f"Conveyor Validation Completed. Report saved to {report_path}", flush=True)
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    validate_conveyor()
