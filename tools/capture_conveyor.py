import argparse
import os
import sys
import time
import cv2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_CONVEYOR_DIR = os.path.join(PROJECT_ROOT, "dataset", "conveyor_real", "raw")

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

def capture_conveyor_feed(camera_idx=None, req_width=1280, req_height=720, auto_interval_ms=0):
    if camera_idx is None:
        camera_idx = get_default_camera_idx()
    os.makedirs(RAW_CONVEYOR_DIR, exist_ok=True)
    
    cap = cv2.VideoCapture(camera_idx)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, req_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, req_height)
    
    act_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    act_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    if not cap.isOpened():
        print(f"ERROR: Unable to open webcam at index {camera_idx}", flush=True)
        sys.exit(1)
        
    print("============================================================", flush=True)
    print(f"REAL CONVEYOR WEBCAM CAPTURE TOOL (Cam: {camera_idx})", flush=True)
    print(f"Resolution: {act_w}x{act_h}", flush=True)
    print("Controls:", flush=True)
    print("  's' or SPACE : Capture single image frame", flush=True)
    print("  'q' or ESC   : Exit capture tool", flush=True)
    print(f"Saving to: {RAW_CONVEYOR_DIR}", flush=True)
    print("============================================================", flush=True)
    
    captured_count = 0
    prev_time = time.time()
    last_auto_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Webcam frame capture failed.", flush=True)
            break
            
        curr_time = time.time()
        fps = 1.0 / max(curr_time - prev_time, 0.001)
        prev_time = curr_time
        
        # Auto-capture check
        if auto_interval_ms > 0 and (curr_time - last_auto_time) * 1000 >= auto_interval_ms:
            last_auto_time = curr_time
            ts = time.strftime("%Y%m%d_%H%M%S")
            fn = f"frame_{ts}_{captured_count:04d}.jpg"
            save_path = os.path.join(RAW_CONVEYOR_DIR, fn)
            cv2.imwrite(save_path, frame)
            captured_count += 1
            print(f"Auto-captured frame: {fn}", flush=True)

        display_frame = frame.copy()
        cv2.putText(display_frame, f"Conveyor Feed | Resolution: {act_w}x{act_h} | FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Captured: {captured_count} frames | Press 's' to Save", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        cv2.imshow("SmartWaste Real Conveyor Feed Capture", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s') or key == 32: # 's' or space
            ts = time.strftime("%Y%m%d_%H%M%S")
            fn = f"frame_{ts}_{captured_count:04d}.jpg"
            save_path = os.path.join(RAW_CONVEYOR_DIR, fn)
            cv2.imwrite(save_path, frame)
            captured_count += 1
            print(f"Captured frame: {save_path}", flush=True)
        elif key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture Conveyor Waste Images")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (defaults to USB webcam setting)")
    parser.add_argument("--width", type=int, default=1280, help="Target resolution width")
    parser.add_argument("--height", type=int, default=720, help="Target resolution height")
    parser.add_argument("--auto", type=int, default=0, help="Auto capture interval in ms (0 = disabled)")
    args = parser.parse_args()
    
    capture_conveyor_feed(args.camera, args.width, args.height, args.auto)
