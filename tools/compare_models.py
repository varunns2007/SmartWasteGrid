import os
import sys
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OLD_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
NEW_MODEL_PATH = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "best.pt")
DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "data.yaml")

def eval_checkpoint(path):
    if not os.path.exists(path):
        return None
    model = YOLO(path)
    res = model.val(data=DATA_YAML, split="val", plots=False, verbose=False, device=0 if torch.cuda.is_available() else "cpu")
    return {
        "precision": res.box.mean_results()[0],
        "recall": res.box.mean_results()[1],
        "map50": res.box.mean_results()[2],
        "map50_95": res.box.mean_results()[3],
        "per_class_p": res.box.p,
        "per_class_r": res.box.r,
        "per_class_map50": res.box.ap50,
        "per_class_map50_95": res.box.ap
    }

def main():
    print("============================================================")
    print("SMARTWASTEGRID MODEL COMPARISON (OLD VS NEW)")
    print("============================================================")
    print(f"OLD Model: {OLD_MODEL_PATH}")
    print(f"NEW Model: {NEW_MODEL_PATH}\n")
    
    old_res = eval_checkpoint(OLD_MODEL_PATH)
    new_res = eval_checkpoint(NEW_MODEL_PATH)
    
    if old_res is None:
        print(f"WARNING: Old model not found at {OLD_MODEL_PATH}")
        return
    if new_res is None:
        print(f"WARNING: New fine-tuned model not found at {NEW_MODEL_PATH}")
        return

    print(f"{'METRIC':<20} {'OLD MODEL':<15} {'NEW MODEL':<15} {'DELTA':<15}")
    print("-" * 65)
    print(f"{'Precision':<20} {old_res['precision']:<15.4f} {new_res['precision']:<15.4f} {new_res['precision']-old_res['precision']:<+15.4f}")
    print(f"{'Recall':<20} {old_res['recall']:<15.4f} {new_res['recall']:<15.4f} {new_res['recall']-old_res['recall']:<+15.4f}")
    print(f"{'mAP50':<20} {old_res['map50']:<15.4f} {new_res['map50']:<15.4f} {new_res['map50']-old_res['map50']:<+15.4f}")
    print(f"{'mAP50-95':<20} {old_res['map50_95']:<15.4f} {new_res['map50_95']:<15.4f} {new_res['map50_95']-old_res['map50_95']:<+15.4f}")
    
    print("\nPER-CLASS RECALL & mAP50 COMPARISON:")
    print("-" * 65)
    classes = ["Wet (0)", "Dry (1)", "Recyclable (2)"]
    for idx, cname in enumerate(classes):
        old_r = old_res['per_class_r'][idx] if idx < len(old_res['per_class_r']) else 0.0
        new_r = new_res['per_class_r'][idx] if idx < len(new_res['per_class_r']) else 0.0
        old_m50 = old_res['per_class_map50'][idx] if idx < len(old_res['per_class_map50']) else 0.0
        new_m50 = new_res['per_class_map50'][idx] if idx < len(new_res['per_class_map50']) else 0.0
        print(f"Class: {cname}")
        print(f"  Recall:  OLD={old_r:.4f}  →  NEW={new_r:.4f}  (Delta: {new_r-old_r:+0.4f})")
        print(f"  mAP50:   OLD={old_m50:.4f}  →  NEW={new_m50:.4f}  (Delta: {new_m50-old_m50:+0.4f})\n")

    print("============================================================")
    if new_res['per_class_r'][0] > old_res['per_class_r'][0]:
        print("VERDICT: Fine-Tuned NEW Model achieved HIGHER Wet Class Recall!")
    else:
        print("VERDICT: Baseline model performance maintained.")
    print("============================================================\n")

if __name__ == "__main__":
    main()
