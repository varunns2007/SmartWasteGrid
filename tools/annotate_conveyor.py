import os
import sys
import glob
import cv2
import shutil
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(PROJECT_ROOT, "dataset", "conveyor_real", "raw")
TRAIN_IMG_DIR = os.path.join(PROJECT_ROOT, "dataset", "conveyor_real", "train", "images")
TRAIN_LBL_DIR = os.path.join(PROJECT_ROOT, "dataset", "conveyor_real", "train", "labels")

CLASS_NAMES = {0: "0: wet", 1: "1: dry", 2: "2: recyclable"}
CLASS_COLORS = {0: (0, 255, 0), 1: (0, 165, 255), 2: (255, 0, 0)}

drawing = False
ix, iy = -1, -1
current_box = None
boxes = [] # list of (cls_id, x1, y1, x2, y2)
current_cls = 0

def draw_callback(event, x, y, flags, param):
    global ix, iy, drawing, current_box, boxes
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            current_box = (ix, iy, x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, x2 = min(ix, x), max(ix, x)
        y1, y2 = min(iy, y), max(iy, y)
        if (x2 - x1) > 5 and (y2 - y1) > 5:
            boxes.append((current_cls, x1, y1, x2, y2))
        current_box = None

def load_existing_yolo_labels(lbl_path, w, h):
    existing_boxes = []
    if os.path.exists(lbl_path):
        with open(lbl_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    cid = int(parts[0])
                    xc, yc, bw, bh = map(float, parts[1:])
                    x1 = int((xc - bw / 2.0) * w)
                    y1 = int((yc - bh / 2.0) * h)
                    x2 = int((xc + bw / 2.0) * w)
                    y2 = int((yc + bh / 2.0) * h)
                    existing_boxes.append((cid, max(0, x1), max(0, y1), min(w, x2), min(h, y2)))
    return existing_boxes

def annotate_images(force_all=False):
    global current_cls, boxes, current_box
    os.makedirs(TRAIN_IMG_DIR, exist_ok=True)
    os.makedirs(TRAIN_LBL_DIR, exist_ok=True)
    
    all_raw_images = sorted(glob.glob(os.path.join(RAW_DIR, "*.jpg")) + glob.glob(os.path.join(RAW_DIR, "*.png")))
    if not all_raw_images:
        print(f"No raw images found in {RAW_DIR}. Use tools/capture_conveyor.py to capture frames first.", flush=True)
        return

    target_images = []
    if force_all:
        target_images = all_raw_images
    else:
        for img_p in all_raw_images:
            bname = os.path.basename(img_p)
            if not os.path.exists(os.path.join(TRAIN_IMG_DIR, bname)):
                target_images.append(img_p)

    if not target_images:
        print("\n============================================================", flush=True)
        print("ALL CAPTURED IMAGES HAVE ALREADY BEEN ANNOTATED!", flush=True)
        print("------------------------------------------------------------", flush=True)
        print("1. To capture NEW images for a second object, run:")
        print("   python tools/capture_conveyor.py")
        print("\n2. To review or edit existing annotations, run:")
        print("   python tools/annotate_conveyor.py --all")
        print("============================================================\n", flush=True)
        return

    print("============================================================", flush=True)
    print(f"CONVEYOR ANNOTATION TOOL ({'REVIEW ALL' if force_all else 'UNANNOTATED ONLY'})", flush=True)
    print(f"Images to annotate: {len(target_images)} of {len(all_raw_images)} total in raw folder", flush=True)
    print("Controls:", flush=True)
    print("  Drag Mouse : Draw bounding box around object", flush=True)
    print("  '0'        : Select WET class", flush=True)
    print("  '1'        : Select DRY class", flush=True)
    print("  '2'        : Select RECYCLABLE class", flush=True)
    print("  'c'        : Clear drawn boxes", flush=True)
    print("  'd'        : DELETE unwanted image & skip to next", flush=True)
    print("  'n' / SPACE: SAVE bounding boxes & move to next image", flush=True)
    print("  'q' / ESC  : Quit annotation tool", flush=True)
    print("============================================================", flush=True)
    
    cv2.namedWindow("Annotate Conveyor Image")
    cv2.setMouseCallback("Annotate Conveyor Image", draw_callback)
    
    total_imgs = len(target_images)
    
    for idx, img_path in enumerate(target_images, 1):
        basename = os.path.basename(img_path)
        stem = os.path.splitext(basename)[0]
        lbl_path = os.path.join(TRAIN_LBL_DIR, f"{stem}.txt")
        
        img = cv2.imread(img_path)
        if img is None: continue
        h, w, _ = img.shape
        
        # Load existing labels if present
        boxes = load_existing_yolo_labels(lbl_path, w, h)
        current_box = None
        
        while True:
            canvas = img.copy()
            
            # Draw existing boxes
            for cid, x1, y1, x2, y2 in boxes:
                col = CLASS_COLORS.get(cid, (255, 255, 255))
                cv2.rectangle(canvas, (x1, y1), (x2, y2), col, 2)
                cv2.putText(canvas, CLASS_NAMES[cid], (x1, max(y1-5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
                            
            # Draw box currently being drawn
            if current_box:
                x1, y1, x2, y2 = current_box
                col = CLASS_COLORS.get(current_cls, (255, 255, 255))
                cv2.rectangle(canvas, (x1, y1), (x2, y2), col, 1)

            # HUD Instructions
            cv2.putText(canvas, f"[{idx}/{total_imgs}] Image: {basename} | Class: {CLASS_NAMES[current_cls]}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(canvas, f"Boxes: {len(boxes)} | '0','1','2'=Set Class | 'n'/SPACE=Save | 'd'=DELETE | 'c'=Clear", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            cv2.imshow("Annotate Conveyor Image", canvas)
            
            key = cv2.waitKey(20) & 0xFF
            if key == ord('0'): current_cls = 0
            elif key == ord('1'): current_cls = 1
            elif key == ord('2'): current_cls = 2
            elif key == ord('c'): boxes = []
            elif key == ord('d'):
                # Delete unwanted image & labels
                try:
                    if os.path.exists(img_path): os.remove(img_path)
                    dst_img = os.path.join(TRAIN_IMG_DIR, basename)
                    if os.path.exists(dst_img): os.remove(dst_img)
                    if os.path.exists(lbl_path): os.remove(lbl_path)
                    print(f"[{idx}/{total_imgs}] DELETED image & label: {basename}", flush=True)
                except Exception as e:
                    print(f"Error deleting {basename}: {e}")
                break
            elif key == ord('n') or key == 32:
                # Save annotation
                dst_img = os.path.join(TRAIN_IMG_DIR, basename)
                shutil.copy(img_path, dst_img)
                
                yolo_lines = []
                for cid, x1, y1, x2, y2 in boxes:
                    xc = (x1 + x2) / (2.0 * w)
                    yc = (y1 + y2) / (2.0 * h)
                    bw = (x2 - x1) / float(w)
                    bh = (y2 - y1) / float(h)
                    yolo_lines.append(f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                    
                with open(lbl_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(yolo_lines) + ("\n" if yolo_lines else ""))
                print(f"[{idx}/{total_imgs}] SAVED {len(boxes)} bounding boxes for {basename}", flush=True)
                break
            elif key == ord('q') or key == 27:
                cv2.destroyAllWindows()
                return

    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Review and edit all images including previously annotated ones")
    args = parser.parse_args()
    annotate_images(force_all=args.all)
