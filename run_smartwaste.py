import os
import sys
import time
import subprocess
import requests

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DASHBOARD_URL = "http://127.0.0.1:5000"

def main():
    print("============================================================", flush=True)
    print("      SMARTWASTEGRID WASTE INTELLIGENCE PLATFORM            ", flush=True)
    print("============================================================", flush=True)
    
    # Start SmartWasteGrid Dashboard if not active
    try:
        r = requests.get(f"{DASHBOARD_URL}/", timeout=2)
        if r.status_code == 200:
            print(f"[OK] SmartWasteGrid Dashboard active at {DASHBOARD_URL}", flush=True)
    except Exception:
        print("[STARTING] Launching SmartWasteGrid Dashboard on http://127.0.0.1:5000...", flush=True)
        py_exe = sys.executable
        app_file = os.path.join(PROJECT_ROOT, "backend", "app.py")
        if os.path.exists(app_file):
            subprocess.Popen([py_exe, app_file], cwd=PROJECT_ROOT)
            time.sleep(2)

    # Launch Live Conveyor Segregation Tracking Feed
    print("\n[STARTING] Launching Live Conveyor Segregation Inference Feed...", flush=True)
    conveyor_script = os.path.join(PROJECT_ROOT, "tools", "conveyor_inference.py")
    
    camera_idx = 1
    config_path = os.path.join(PROJECT_ROOT, "config", "conveyor.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                camera_idx = cfg.get("camera_index", 1)
        except Exception:
            pass
    elif os.getenv("CAMERA_INDEX"):
        try:
            camera_idx = int(os.getenv("CAMERA_INDEX"))
        except Exception:
            pass

    simulate_flag = "--simulate" in sys.argv or "-s" in sys.argv
    cam_arg = "simulate" if simulate_flag else str(camera_idx)
    subprocess.run([sys.executable, conveyor_script, cam_arg])

if __name__ == "__main__":
    main()
