import os
import sys
import yaml
import cv2

try:
    from pygrabber.dshow_graph import FilterGraph
    PYGRABBER_AVAILABLE = True
except ImportError:
    PYGRABBER_AVAILABLE = False

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "conveyor.yaml")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

def detect_cameras():
    """Detect all available camera indices and their DirectShow names/resolutions."""
    cameras = []
    
    device_names = []
    if PYGRABBER_AVAILABLE:
        try:
            graph = FilterGraph()
            device_names = graph.get_input_devices()
        except Exception:
            pass

    print("============================================================", flush=True)
    print("SEARCHING & DETECTING AVAILABLE WEBCAMS", flush=True)
    print("============================================================", flush=True)

    for idx in range(10):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Get device name from pygrabber or fallback
            if idx < len(device_names):
                name = device_names[idx]
            else:
                name = f"Camera Device #{idx}"
                
            is_usb = "usb" in name.lower() or "external" in name.lower() or ("integrated" not in name.lower() and idx > 0)
            
            cameras.append({
                "index": idx,
                "name": name,
                "width": w,
                "height": h,
                "frame_captured": ret,
                "is_usb": is_usb
            })
            
            print(f"  [Camera Index {idx}]", flush=True)
            print(f"    Name:           {name}", flush=True)
            print(f"    Resolution:     {w}x{h}", flush=True)
            print(f"    Frame Readable: {'YES' if ret else 'NO'}", flush=True)
            print(f"    Type:           {'USB External Webcam' if is_usb else 'Integrated / Default Camera'}", flush=True)
            print("  --------------------------------------------------", flush=True)
            cap.release()
        else:
            cap.release()
            
    return cameras

def select_usb_webcam(cameras):
    """Identify the USB webcam index from detected cameras."""
    usb_cams = [c for c in cameras if c["is_usb"]]
    if usb_cams:
        return usb_cams[0]["index"], usb_cams[0]["name"]
    elif len(cameras) > 1:
        # Fallback to index 1 if multiple cameras exist
        return 1, cameras[1]["name"]
    elif cameras:
        return cameras[0]["index"], cameras[0]["name"]
    return 1, "USB Camera (Fallback)"

def configure_camera_source(camera_index):
    """Update config/conveyor.yaml and .env with the target camera_index."""
    print(f"\n[CONFIGURING] Setting USB Webcam (Index: {camera_index}) as default camera source...", flush=True)
    
    # 1. Update config/conveyor.yaml
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cfg["camera_index"] = camera_index
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)
        print(f"  Updated '{CONFIG_PATH}': camera_index = {camera_index}", flush=True)
    else:
        print(f"  Warning: Config file '{CONFIG_PATH}' not found.", flush=True)

    # 2. Update .env
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("CAMERA_INDEX="):
                new_lines.append(f"CAMERA_INDEX={camera_index}\n")
                updated = True
            else:
                new_lines.append(line)
                
        if not updated:
            new_lines.append(f"CAMERA_INDEX={camera_index}\n")
            
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"  Updated '{ENV_PATH}': CAMERA_INDEX = {camera_index}", flush=True)

if __name__ == "__main__":
    cams = detect_cameras()
    if not cams:
        print("ERROR: No camera devices detected on system!", flush=True)
        sys.exit(1)
        
    usb_idx, usb_name = select_usb_webcam(cams)
    print(f"\n[DETECTED USB WEBCAM] Index {usb_idx}: {usb_name}", flush=True)
    
    configure_camera_source(usb_idx)
    print("\n[SUCCESS] USB Webcam configuration completed successfully!", flush=True)
