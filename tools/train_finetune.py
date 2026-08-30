import os
import sys
import json
import time
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STARTING_CHECKPOINT = os.path.join(PROJECT_ROOT, "runs", "SmartWasteGrid_YOLO11s", "weights", "best.pt")
FT_DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_ft", "data.yaml")
BASE_DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "data.yaml")
FT_RUNS_DIR = os.path.join(PROJECT_ROOT, "runs")
FT_RUN_NAME = "SmartWasteGrid_YOLO11s_FT"
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

def verify_gpu_cuda():
    print("============================================================", flush=True)
    print("GPU / CUDA VERIFICATION & STABLE ULTRA ACCELERATION", flush=True)
    print("============================================================", flush=True)
    pytorch_ver = torch.__version__
    cuda_avail = torch.cuda.is_available()
    print(f"PyTorch:            {pytorch_ver}", flush=True)
    print(f"CUDA:               {cuda_avail}", flush=True)
    
    if not cuda_avail:
        print("CRITICAL ERROR: CUDA is unavailable! Aborting fine-tuning.", flush=True)
        sys.exit(1)
        
    dev_count = torch.cuda.device_count()
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    cuda_ver = torch.version.cuda
    
    torch.backends.cudnn.benchmark = True
    
    print(f"CUDA Device Count:  {dev_count}", flush=True)
    print(f"GPU:                {gpu_name}", flush=True)
    print(f"VRAM:               {vram_gb:.2f} GB", flush=True)
    print(f"cuDNN Benchmark:    ENABLED", flush=True)
    print("============================================================\n", flush=True)
    return gpu_name, vram_gb

def run_fine_tuning():
    gpu_name, vram_gb = verify_gpu_cuda()
    
    if not os.path.exists(STARTING_CHECKPOINT):
        print(f"ERROR: Starting checkpoint not found at {STARTING_CHECKPOINT}", flush=True)
        sys.exit(1)
        
    data_yaml = FT_DATA_YAML if os.path.exists(FT_DATA_YAML) else BASE_DATA_YAML
    print("============================================================", flush=True)
    print("STABLE ULTRA-ACCELERATED GPU FINE-TUNING ENGINE", flush=True)
    print(f"Starting Checkpoint: {STARTING_CHECKPOINT}", flush=True)
    print(f"Dataset Config:      {data_yaml}", flush=True)
    print("Optimizations:       AMP=FP16, imgsz=384, batch=8, val=False, workers=0", flush=True)
    print("============================================================", flush=True)
    
    torch.cuda.empty_cache()
    
    model = YOLO(STARTING_CHECKPOINT)
    start_time = time.time()
    
    config = {
        "data": data_yaml,
        "epochs": 25,
        "patience": 8,
        "imgsz": 384,
        "batch": 8,
        "device": 0,
        "amp": True,
        "val": False,
        "lr0": 0.001,
        "cos_lr": True,
        "close_mosaic": 5,
        "save_period": 5,
        "workers": 0,
        "cache": False,
        "project": FT_RUNS_DIR,
        "name": FT_RUN_NAME,
        "plots": True,
        "exist_ok": True
    }
    
    print("Starting fast fine-tuning on RTX 2050 GPU...", flush=True)
    results = model.train(**config)

    elapsed_sec = time.time() - start_time
    
    os.makedirs(REPORTS_DIR, exist_ok=True)
    summary = {
        "starting_model": STARTING_CHECKPOINT,
        "fine_tune_model": os.path.join(FT_RUNS_DIR, FT_RUN_NAME, "weights", "best.pt"),
        "dataset_used": data_yaml,
        "epochs_requested": config["epochs"],
        "training_time_seconds": round(elapsed_sec, 2),
        "gpu": gpu_name,
        "vram_gb": round(vram_gb, 2)
    }
    
    summary_path = os.path.join(REPORTS_DIR, "training_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFine-tuning completed in {elapsed_sec/60:.2f} mins! Summary saved to {summary_path}", flush=True)

if __name__ == "__main__":
    run_fine_tuning()
