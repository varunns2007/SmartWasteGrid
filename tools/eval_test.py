import os
import sys
import shutil
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BEST_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
TEST_IMAGES_DIR = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "test", "images")
DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "data.yaml")
REPORTS_TEST_DIR = os.path.join(PROJECT_ROOT, "reports", "test")

def evaluate_test_set():
    print("============================================================", flush=True)
    print("EVALUATING BEST MODEL ON TEST DATASET", flush=True)
    print("============================================================", flush=True)
    
    if not os.path.exists(BEST_MODEL_PATH):
        print(f"ERROR: Best weights file not found at {BEST_MODEL_PATH}", flush=True)
        sys.exit(1)
        
    os.makedirs(REPORTS_TEST_DIR, exist_ok=True)
    
    model = YOLO(BEST_MODEL_PATH)
    
    # Run validation on test split
    print(f"Running model validation on test set...", flush=True)
    results = model.val(
        data=DATA_YAML,
        split="test",
        batch=4,
        imgsz=640,
        device=0,
        project=os.path.join(PROJECT_ROOT, "runs"),
        name="test_eval",
        plots=True,
        exist_ok=True
    )
    
    # Extract metrics
    metrics = results.results_dict
    mp = metrics.get("metrics/precision(B)", 0.0)
    mr = metrics.get("metrics/recall(B)", 0.0)
    map50 = metrics.get("metrics/mAP50(B)", 0.0)
    map50_95 = metrics.get("metrics/mAP50-95(B)", 0.0)
    
    class_names = ["wet", "dry", "recyclable"]
    per_class_str = ""
    
    try:
        p_per_class = results.box.p
        r_per_class = results.box.r
        ap50_per_class = results.box.ap50
        ap_per_class = results.box.ap
        
        for i, cname in enumerate(class_names):
            p_val = p_per_class[i] if i < len(p_per_class) else 0.0
            r_val = r_per_class[i] if i < len(r_per_class) else 0.0
            ap50_val = ap50_per_class[i] if i < len(ap50_per_class) else 0.0
            ap_val = ap_per_class[i] if i < len(ap_per_class) else 0.0
            per_class_str += f"  {cname.upper()}:\n    Precision: {p_val:.4f}\n    Recall:    {r_val:.4f}\n    mAP50:     {ap50_val:.4f}\n    mAP50-95:  {ap_val:.4f}\n\n"
    except Exception as e:
        per_class_str = f"  Per-class extraction warning: {e}\n"

    report_lines = [
        "SMARTWASTE YOLO11s TEST SET EVALUATION REPORT",
        "===========================================================",
        f"Model Weight Path: {BEST_MODEL_PATH}",
        f"Test Set Location: {TEST_IMAGES_DIR}",
        "",
        "OVERALL METRICS:",
        f"  Precision (B): {mp:.4f}",
        f"  Recall (B):    {mr:.4f}",
        f"  mAP50 (B):     {map50:.4f}",
        f"  mAP50-95 (B):  {map50_95:.4f}",
        "",
        "PER-CLASS METRICS:",
        per_class_str.strip()
    ]
    
    report_text = "\n".join(report_lines)
    print(report_text, flush=True)
    
    summary_path = os.path.join(REPORTS_TEST_DIR, "test_report.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"Saved evaluation report to {summary_path}", flush=True)
    
    # Copy confusion matrix plot if generated
    eval_run_dir = os.path.join(PROJECT_ROOT, "runs", "test_eval")
    cm_path = os.path.join(eval_run_dir, "confusion_matrix.png")
    if os.path.exists(cm_path):
        dst_cm = os.path.join(REPORTS_TEST_DIR, "confusion_matrix.png")
        shutil.copy(cm_path, dst_cm)
        print(f"Copied confusion matrix to {dst_cm}", flush=True)

if __name__ == "__main__":
    evaluate_test_set()
