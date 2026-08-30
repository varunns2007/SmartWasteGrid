import os
import sys
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAST_CHECKPOINT = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s_FT", "weights", "last.pt")

def resume():
    print("============================================================", flush=True)
    print("RESUME INTERRUPTED FINE-TUNING ENGINE", flush=True)
    print("============================================================", flush=True)
    
    if not os.path.exists(LAST_CHECKPOINT):
        print(f"No checkpoint found at {LAST_CHECKPOINT}. Starting fine-tuning from beginning...", flush=True)
        from tools.train_finetune import run_fine_tuning
        run_fine_tuning()
        return

    print(f"Locating latest checkpoint: {LAST_CHECKPOINT}", flush=True)
    model = YOLO(LAST_CHECKPOINT)
    
    print("Resuming training from last checkpoint...", flush=True)
    model.train(resume=True)

if __name__ == "__main__":
    resume()
