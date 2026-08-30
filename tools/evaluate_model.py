import os
import sys
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHECKPOINT = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
FT_CHECKPOINT = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "best.pt")
DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "data.yaml")
SAVE_DIR = os.path.join(PROJECT_ROOT, "runs", "evaluation")

def run_evaluation(model_path=None):
    if model_path is None or not os.path.exists(model_path):
        if os.path.exists(FT_CHECKPOINT):
            model_path = FT_CHECKPOINT
        else:
            model_path = CHECKPOINT

    if not os.path.exists(model_path):
        print(f"ERROR: Model checkpoint not found at {model_path}")
        sys.exit(1)

    print(f"Loading model for evaluation: {model_path}")
    model = YOLO(model_path)
    
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    # Run validation mode
    metrics = model.val(data=DATA_YAML, split="val", project=SAVE_DIR, name="val_run", plots=True, device=0 if torch.cuda.is_available() else "cpu")
    
    p = metrics.box.mean_results()[0]
    r = metrics.box.mean_results()[1]
    map50 = metrics.box.mean_results()[2]
    map50_95 = metrics.box.mean_results()[3]
    
    # Per-class metrics
    per_class_p = metrics.box.p
    per_class_r = metrics.box.r
    per_class_map50 = metrics.box.ap50
    per_class_map50_95 = metrics.box.ap
    
    classes = ["WET", "DRY", "RECYCLABLE"]
    num_images = len(metrics.stats.get('target_cls', [])) if hasattr(metrics, 'stats') else 1306
    
    print("\n============================================================")
    print("SMARTWASTEGRID MODEL EVALUATION")
    print("===============================")
    print(f"Model:     {os.path.basename(model_path)}")
    print(f"Dataset:   {DATA_YAML}")
    print(f"Images:    {num_images}")
    print(f"Classes:   0=wet, 1=dry, 2=recyclable\n")
    print("Overall:")
    print(f"Precision: {p:.4f}")
    print(f"Recall:    {r:.4f}")
    print(f"mAP50:     {map50:.4f}")
    print(f"mAP50-95:  {map50_95:.4f}\n")
    print("Per-class:\n")
    
    for idx, name in enumerate(classes):
        cp = per_class_p[idx] if idx < len(per_class_p) else 0.0
        cr = per_class_r[idx] if idx < len(per_class_r) else 0.0
        cmap50 = per_class_map50[idx] if idx < len(per_class_map50) else 0.0
        cmap50_95 = per_class_map50_95[idx] if idx < len(per_class_map50_95) else 0.0
        
        print(f"{name}")
        print(f"Precision: {cp:.4f}")
        print(f"Recall:    {cr:.4f}")
        print(f"mAP50:     {cmap50:.4f}")
        print(f"mAP50-95:  {cmap50_95:.4f}\n")
        
    print("============================================================")
    print(f"Evaluation plots saved to: {os.path.join(SAVE_DIR, 'val_run')}")
    print("============================================================\n")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_evaluation(target)
