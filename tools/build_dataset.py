import os
import sys
import zipfile
import shutil
import io
import glob
import math
import stat
from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASETS_DIR = os.path.join(PROJECT_ROOT, "datasets")
FINAL_DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset", "waste_3class_final")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports", "dataset")

# Mappings
# Organic - Inorganic Detection mapping
ORG_INORG_MAP = {
    0: 1, # Battery -> dry (1)
    1: 1, # Bugs Spray -> dry (1)
    2: 0, # Dry Leave -> wet (0)
    3: 0, # Fruit Waste -> wet (0)
    4: 2, # Glass -> recyclable (2)
    5: 2, # Paper -> recyclable (2)
    6: 2, # Plastic Bag -> recyclable (2)
    7: 2, # Plastic Bottle -> recyclable (2)
    8: 2, # Tin -> recyclable (2)
}

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    try:
        func(path)
    except Exception:
        pass

def clean_and_prepare_dirs():
    if os.path.exists(FINAL_DATASET_DIR):
        print(f"Cleaning existing directory: {FINAL_DATASET_DIR}", flush=True)
        try:
            shutil.rmtree(FINAL_DATASET_DIR, onerror=remove_readonly)
        except Exception as e:
            print(f"Warning cleaning directory: {e}", flush=True)
            
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    for split in ["train", "valid", "test"]:
        os.makedirs(os.path.join(FINAL_DATASET_DIR, split, "images"), exist_ok=True)
        os.makedirs(os.path.join(FINAL_DATASET_DIR, split, "labels"), exist_ok=True)

def write_data_yaml():
    yaml_path = os.path.join(FINAL_DATASET_DIR, "data.yaml")
    yaml_content = (
        "path: dataset/waste_3class_final\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n\n"
        "nc: 3\n\n"
        "names:\n"
        "  0: wet\n"
        "  1: dry\n"
        "  2: recyclable\n"
    )
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"Created {yaml_path}", flush=True)

def normalize_split_name(dir_name):
    lower = dir_name.lower()
    if "train" in lower:
        return "train"
    elif "valid" in lower or "val" in lower:
        return "valid"
    elif "test" in lower:
        return "test"
    return None

def convert_line_to_box(line, remap_fn):
    parts = line.strip().split()
    if not parts:
        return None
    try:
        orig_cls = int(float(parts[0]))
        new_cls = remap_fn(orig_cls)
        if new_cls is None:
            return None
        
        vals = [float(x) for x in parts[1:]]
        if len(vals) == 4:
            xc, yc, w, h = vals
        elif len(vals) >= 6 and len(vals) % 2 == 0:
            xs = vals[0::2]
            ys = vals[1::2]
            xmin = max(0.0, min(1.0, min(xs)))
            xmax = max(0.0, min(1.0, max(xs)))
            ymin = max(0.0, min(1.0, min(ys)))
            ymax = max(0.0, min(1.0, max(ys)))
            xc = (xmin + xmax) / 2.0
            yc = (ymin + ymax) / 2.0
            w = xmax - xmin
            h = ymax - ymin
        else:
            return None
            
        xc = max(0.0, min(1.0, xc))
        yc = max(0.0, min(1.0, yc))
        w = max(0.0, min(1.0, w))
        h = max(0.0, min(1.0, h))
        
        if w > 0 and h > 0:
            return f"{new_cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"
    except Exception:
        pass
    return None

def process_zip_file(zip_name, prefix, remap_fn):
    zip_path = os.path.join(DATASETS_DIR, zip_name)
    print(f"\nProcessing {zip_name}...", flush=True)
    if not os.path.exists(zip_path):
        print(f"ERROR: Zip file not found: {zip_path}", flush=True)
        sys.exit(1)
        
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        pairs = {}
        
        for name in namelist:
            if name.endswith("/"):
                continue
                
            parts = name.split("/")
            split = None
            for p in parts:
                norm = normalize_split_name(p)
                if norm:
                    split = norm
                    break
            
            if not split:
                continue
                
            filename = parts[-1]
            if not filename:
                continue
                
            stem, ext = os.path.splitext(filename)
            ext_lower = ext.lower()
            
            key = (split, stem)
            if key not in pairs:
                pairs[key] = {}
                
            if ext_lower in [".jpg", ".jpeg", ".png", ".bmp"]:
                pairs[key]['img'] = (name, ext_lower)
            elif ext_lower == ".txt":
                pairs[key]['txt'] = name

        print(f"Found {len(pairs)} image/label stem pairs in {zip_name}", flush=True)
        
        counter = 0
        extracted_count = 0
        
        for (split, stem), entry in pairs.items():
            counter += 1
            new_stem = f"{prefix}_{counter:06d}"
            
            img_entry = entry.get('img')
            if img_entry:
                img_name, ext = img_entry
                img_bytes = zf.read(img_name)
                dst_img_path = os.path.join(FINAL_DATASET_DIR, split, "images", f"{new_stem}{ext}")
                with open(dst_img_path, "wb") as f:
                    f.write(img_bytes)
            
            txt_entry = entry.get('txt')
            dst_txt_path = os.path.join(FINAL_DATASET_DIR, split, "labels", f"{new_stem}.txt")
            
            if txt_entry:
                txt_bytes = zf.read(txt_entry)
                lines = txt_bytes.decode('utf-8', errors='ignore').strip().splitlines()
                remapped_lines = []
                for line in lines:
                    converted = convert_line_to_box(line, remap_fn)
                    if converted:
                        remapped_lines.append(converted)
                with open(dst_txt_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(remapped_lines) + ("\n" if remapped_lines else ""))
            else:
                with open(dst_txt_path, "w", encoding="utf-8") as f:
                    f.write("")
            
            extracted_count += 1
            
        print(f"Extracted {extracted_count} items from {zip_name}", flush=True)

def validate_dataset():
    print("\n============================================================", flush=True)
    print("DATASET VALIDATION", flush=True)
    print("============================================================", flush=True)
    
    stats = {}
    report_lines = []
    
    total_images = 0
    total_labels = 0
    total_wet = 0
    total_dry = 0
    total_rec = 0
    total_missing_labels = 0
    total_invalid_labels = 0
    
    for split in ["train", "valid", "test"]:
        img_dir = os.path.join(FINAL_DATASET_DIR, split, "images")
        lbl_dir = os.path.join(FINAL_DATASET_DIR, split, "labels")
        
        img_files = sorted([f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f))])
        lbl_files = sorted([f for f in os.listdir(lbl_dir) if os.path.isfile(os.path.join(lbl_dir, f))])
        
        img_stems = {os.path.splitext(f)[0]: f for f in img_files}
        lbl_stems = {os.path.splitext(f)[0]: f for f in lbl_files}
        
        wet_count = 0
        dry_count = 0
        rec_count = 0
        multi_class_images = 0
        missing_labels = 0
        invalid_labels = 0
        corrupted_images = 0
        
        for stem, img_file in img_stems.items():
            img_path = os.path.join(img_dir, img_file)
            if os.path.getsize(img_path) == 0:
                corrupted_images += 1
                
            if stem not in lbl_stems:
                missing_labels += 1
            else:
                lbl_path = os.path.join(lbl_dir, lbl_stems[stem])
                with open(lbl_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                
                classes_in_img = set()
                for line in lines:
                    parts = line.split()
                    if len(parts) != 5:
                        invalid_labels += 1
                        continue
                    try:
                        cls_id = int(parts[0])
                        coords = [float(x) for x in parts[1:5]]
                        
                        if cls_id not in [0, 1, 2]:
                            invalid_labels += 1
                            continue
                            
                        if any(c < 0.0 or c > 1.0 for c in coords):
                            invalid_labels += 1
                            continue
                            
                        classes_in_img.add(cls_id)
                        if cls_id == 0:
                            wet_count += 1
                        elif cls_id == 1:
                            dry_count += 1
                        elif cls_id == 2:
                            rec_count += 1
                    except ValueError:
                        invalid_labels += 1
                        
                if len(classes_in_img) > 1:
                    multi_class_images += 1
                    
        for stem in lbl_stems:
            if stem not in img_stems:
                missing_labels += 1
                
        split_stat = {
            "images": len(img_files),
            "labels": len(lbl_files),
            "wet": wet_count,
            "dry": dry_count,
            "recyclable": rec_count,
            "multi_class_images": multi_class_images,
            "missing_labels": missing_labels,
            "invalid_labels": invalid_labels,
            "corrupted_images": corrupted_images
        }
        stats[split] = split_stat
        
        total_images += len(img_files)
        total_labels += len(lbl_files)
        total_wet += wet_count
        total_dry += dry_count
        total_rec += rec_count
        total_missing_labels += missing_labels
        total_invalid_labels += invalid_labels

    total_annos = total_wet + total_dry + total_rec
    wet_pct = (total_wet / total_annos * 100) if total_annos > 0 else 0
    dry_pct = (total_dry / total_annos * 100) if total_annos > 0 else 0
    rec_pct = (total_rec / total_annos * 100) if total_annos > 0 else 0

    header = "SMARTWASTE 3-CLASS DATASET VALIDATION REPORT\n" + "=" * 55 + "\n"
    report_lines.append(header)
    
    for split in ["train", "valid", "test"]:
        st = stats[split]
        s_upper = split.upper()
        line = (
            f"{s_upper}:\n"
            f"  images: {st['images']}\n"
            f"  labels: {st['labels']}\n"
            f"  wet annotations: {st['wet']}\n"
            f"  dry annotations: {st['dry']}\n"
            f"  recyclable annotations: {st['recyclable']}\n"
            f"  multi-class images: {st['multi_class_images']}\n"
            f"  missing labels: {st['missing_labels']}\n"
            f"  invalid labels: {st['invalid_labels']}\n"
            f"  corrupted images: {st['corrupted_images']}\n"
        )
        report_lines.append(line)
        print(line, flush=True)
        
    summary_line = (
        f"OVERALL SUMMARY:\n"
        f"  Total Images: {total_images}\n"
        f"  Total Labels: {total_labels}\n"
        f"  Total Wet Annotations (0): {total_wet} ({wet_pct:.2f}%)\n"
        f"  Total Dry Annotations (1): {total_dry} ({dry_pct:.2f}%)\n"
        f"  Total Recyclable Annotations (2): {total_rec} ({rec_pct:.2f}%)\n"
        f"  Total Missing Labels: {total_missing_labels}\n"
        f"  Total Invalid Labels: {total_invalid_labels}\n"
    )
    report_lines.append(summary_line)
    print(summary_line, flush=True)
    
    report_path = os.path.join(REPORTS_DIR, "dataset_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"Saved report to {report_path}", flush=True)
    
    if total_invalid_labels > 0 or total_missing_labels > 0:
        print("WARNING: Found missing or invalid labels during validation!", flush=True)
    else:
        print("SUCCESS: Dataset validation passed with 0 missing and 0 invalid labels!", flush=True)

def main():
    print("Starting dataset build process...", flush=True)
    clean_and_prepare_dirs()
    write_data_yaml()
    
    # 1. DRYWASTE -> class 1
    process_zip_file("DRYWASTE.zip", "dry", lambda c: 1)
    
    # 2. EXTRARECYCLABLE -> class 2
    process_zip_file("EXTRARECYCLABLE.zip", "rec", lambda c: 2)
    
    # 3. Organic - Inorganic -> mapped classes
    process_zip_file("Organic - Inorganic Detection.v1i.yolov8.zip", "org_inorg", lambda c: ORG_INORG_MAP.get(c))
    
    # Run validation
    validate_dataset()

if __name__ == "__main__":
    main()
