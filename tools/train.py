import os
import sys
import torch
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_YAML = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final", "data.yaml")

def verify_environment():
    print("============================================================", flush=True)
    print("ENVIRONMENT & CUDA VERIFICATION", flush=True)
    print("============================================================", flush=True)
    pytorch_version = torch.__version__
    cuda_available = torch.cuda.is_available()
    
    print(f"PyTorch Version: {pytorch_version}", flush=True)
    print(f"CUDA Available:  {cuda_available}", flush=True)
    
    if not cuda_available:
        print("CRITICAL ERROR: CUDA is NOT available! Aborting training.", flush=True)
        sys.exit(1)
        
    device_count = torch.cuda.device_count()
    gpu_name = torch.cuda.get_device_name(0)
    total_memory = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    
    print(f"CUDA Device Count: {device_count}", flush=True)
    print(f"GPU Device 0:      {gpu_name}", flush=True)
    print(f"GPU VRAM Memory:   {total_memory:.2f} GB", flush=True)
    print("============================================================\n", flush=True)
    
    return gpu_name, total_memory

def train_yolo():
    gpu_name, total_memory = verify_environment()
    
    model_name = "yolo11s.pt"
    print(f"Loading pretrained model: {model_name}", flush=True)
    model = YOLO(model_name)
    
    # Base configuration
    config = {
        "data": DATA_YAML,
        "epochs": 200,
        "imgsz": 640,
        "batch": 4,
        "workers": 2,
        "patience": 30,
        "device": 0,
        "pretrained": True,
        "hsv_h": 0.015,
        "hsv_s": 0.5,
        "hsv_v": 0.35,
        "degrees": 3,
        "translate": 0.08,
        "scale": 0.4,
        "fliplr": 0.5,
        "mosaic": 0.8,
        "mixup": 0.05,
        "close_mosaic": 15,
        "project": os.path.join(PROJECT_ROOT, "runs"),
        "name": "SmartWasteGrid_YOLO11s",
        "plots": True,
        "exist_ok": True
    }
    
    try:
        print(f"Starting YOLO11s training on GPU device 0 (batch={config['batch']}, imgsz={config['imgsz']})...", flush=True)
        model.train(**config)
    except torch.cuda.OutOfMemoryError as e:
        print(f"\nCUDA OOM detected! Retrying with batch=2...", flush=True)
        torch.cuda.empty_cache()
        config["batch"] = 2
        try:
            model.train(**config)
        except torch.cuda.OutOfMemoryError:
            print(f"\nCUDA OOM detected again! Retrying with batch=2 and imgsz=512...", flush=True)
            torch.cuda.empty_cache()
            config["batch"] = 2
            config["imgsz"] = 512
            model.train(**config)

if __name__ == "__main__":
    train_yolo()
