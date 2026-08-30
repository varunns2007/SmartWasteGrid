import os
import glob
import random
import cv2
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports", "dataset")

CLASS_NAMES = {0: "wet", 1: "dry", 2: "recyclable"}
CLASS_COLORS = {0: (0, 200, 0), 1: (0, 165, 255), 2: (255, 0, 0)} # BGR: green, orange, blue

def draw_annotations(img_path, lbl_path):
    img = cv2.imread(img_path)
    if img is None:
        return None
    h, w, _ = img.shape
    
    if os.path.exists(lbl_path):
        with open(lbl_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        for line in lines:
            parts = line.split()
            if len(parts) == 5:
                try:
                    cls_id = int(parts[0])
                    xc, yc, bw, bh = [float(x) for x in parts[1:5]]
                    
                    x1 = int((xc - bw / 2) * w)
                    y1 = int((yc - bh / 2) * h)
                    x2 = int((xc + bw / 2) * w)
                    y2 = int((yc + bh / 2) * h)
                    
                    color = CLASS_COLORS.get(cls_id, (255, 255, 255))
                    label = CLASS_NAMES.get(cls_id, str(cls_id))
                    
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(img, label, (x1, max(y1 - 5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                except Exception:
                    pass
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

def generate_class_distribution_plot():
    train_labels = glob.glob(os.path.join(DATASET_DIR, "train", "labels", "*.txt"))
    counts = {0: 0, 1: 0, 2: 0}
    for lp in train_labels:
        with open(lp, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 1:
                    try:
                        cid = int(parts[0])
                        if cid in counts:
                            counts[cid] += 1
                    except ValueError:
                        pass

    categories = [CLASS_NAMES[i] for i in [0, 1, 2]]
    values = [counts[i] for i in [0, 1, 2]]
    colors = ['#2ecc71', '#e67e22', '#3498db']

    plt.figure(figsize=(8, 6))
    bars = plt.bar(categories, values, color=colors)
    plt.title("Train Set Class Distribution (Annotations)", fontsize=14)
    plt.xlabel("Class", fontsize=12)
    plt.ylabel("Annotation Count", fontsize=12)
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 10,
                 f'{int(height)}', ha='center', va='bottom', fontsize=11)
                 
    plt.tight_layout()
    out_path = os.path.join(REPORTS_DIR, "class_distribution.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")

def generate_image_grid(image_label_pairs, title, filename, max_samples=9):
    if not image_label_pairs:
        print(f"No samples for {title}")
        return
    
    samples = random.sample(image_label_pairs, min(len(image_label_pairs), max_samples))
    n = len(samples)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    
    plt.figure(figsize=(4 * cols, 4 * rows))
    plt.suptitle(title, fontsize=16)
    
    for i, (img_path, lbl_path) in enumerate(samples):
        annotated = draw_annotations(img_path, lbl_path)
        if annotated is not None:
            plt.subplot(rows, cols, i + 1)
            plt.imshow(annotated)
            plt.axis("off")
            plt.title(os.path.basename(img_path), fontsize=8)
            
    plt.tight_layout()
    out_path = os.path.join(REPORTS_DIR, filename)
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")

def inspect_dataset():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    generate_class_distribution_plot()
    
    train_img_dir = os.path.join(DATASET_DIR, "train", "images")
    train_lbl_dir = os.path.join(DATASET_DIR, "train", "labels")
    
    img_files = sorted(glob.glob(os.path.join(train_img_dir, "*.*")))
    
    pairs_by_class = {0: [], 1: [], 2: [], "multi": [], "all": []}
    
    for img_path in img_files:
        stem = os.path.splitext(os.path.basename(img_path))[0]
        lbl_path = os.path.join(train_lbl_dir, f"{stem}.txt")
        
        pairs_by_class["all"].append((img_path, lbl_path))
        
        if os.path.exists(lbl_path):
            with open(lbl_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            cids = set()
            for line in lines:
                parts = line.split()
                if len(parts) >= 1:
                    try:
                        cids.add(int(parts[0]))
                    except ValueError:
                        pass
            for cid in cids:
                if cid in pairs_by_class:
                    pairs_by_class[cid].append((img_path, lbl_path))
            if len(lines) > 1 or len(cids) > 1:
                pairs_by_class["multi"].append((img_path, lbl_path))

    generate_image_grid(pairs_by_class[0], "Wet Class Examples", "wet_samples.png")
    generate_image_grid(pairs_by_class[1], "Dry Class Examples", "dry_samples.png")
    generate_image_grid(pairs_by_class[2], "Recyclable Class Examples", "recyclable_samples.png")
    generate_image_grid(pairs_by_class["multi"], "Multi-Object Examples", "multi_object_samples.png")
    generate_image_grid(pairs_by_class["all"], "Random Training Samples", "random_training_samples.png")

if __name__ == "__main__":
    inspect_dataset()
