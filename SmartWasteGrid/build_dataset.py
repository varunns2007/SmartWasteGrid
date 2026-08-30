import os
import shutil
import zipfile
from pathlib import Path
from collections import Counter

# ============================================================
# CONFIGURATION
# ============================================================

BASE = Path.cwd()
ZIP_DIR = BASE / "datasets"

EXTRA_RECYCLABLE_ZIP = ZIP_DIR / "EXTRARECYCLABLE.zip"
DRY_WASTE_ZIP = ZIP_DIR / "DRYWASTE.zip"
ORGANIC_ZIP = ZIP_DIR / "Organic - Inorganic Detection.v1i.yolov8.zip"

SOURCE_DIR = BASE / "_sources"
FINAL_DIR = BASE / "dataset" / "waste_3class_final"

# ============================================================
# CLEAN OLD TEMPORARY DATA
# ============================================================

if SOURCE_DIR.exists():
    print("Removing old extracted sources...")
    shutil.rmtree(SOURCE_DIR)

SOURCE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# EXTRACT ZIP FILES
# ============================================================

def extract_zip(zip_path, destination):
    print(f"\nExtracting:")
    print(zip_path.name)

    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(destination)

    print("Done!")


extract_zip(
    EXTRA_RECYCLABLE_ZIP,
    SOURCE_DIR / "recyclable"
)

extract_zip(
    DRY_WASTE_ZIP,
    SOURCE_DIR / "dry"
)

extract_zip(
    ORGANIC_ZIP,
    SOURCE_DIR / "organic"
)

# ============================================================
# FIND DATASET ROOT
# ============================================================

def find_yaml(root):
    yamls = list(root.rglob("data.yaml"))

    if not yamls:
        raise FileNotFoundError(
            f"No data.yaml found inside {root}"
        )

    # Prefer the first YAML found
    return yamls[0]


recyclable_yaml = find_yaml(SOURCE_DIR / "recyclable")
dry_yaml = find_yaml(SOURCE_DIR / "dry")
organic_yaml = find_yaml(SOURCE_DIR / "organic")

print("\n============================================================")
print("DATASET YAML FILES")
print("============================================================")

print("Recyclable:", recyclable_yaml)
print("Dry:", dry_yaml)
print("Organic:", organic_yaml)

# Dataset root is the folder containing data.yaml
RECYCLABLE_ROOT = recyclable_yaml.parent
DRY_ROOT = dry_yaml.parent
ORGANIC_ROOT = organic_yaml.parent

# ============================================================
# CREATE FINAL STRUCTURE
# ============================================================

if FINAL_DIR.exists():
    print("\nRemoving old final dataset...")
    shutil.rmtree(FINAL_DIR)

for split in ["train", "valid", "test"]:
    (FINAL_DIR / split / "images").mkdir(parents=True, exist_ok=True)
    (FINAL_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

# ============================================================
# SPLIT HANDLING
# ============================================================

SPLITS = {
    "train": "train",
    "valid": "valid",
    "test": "test"
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp"
}

# ============================================================
# ADD DATASET
# ============================================================

final_counts = {
    "train": Counter(),
    "valid": Counter(),
    "test": Counter()
}


def add_dataset(
    dataset_root,
    dataset_name,
    class_mapping
):
    """
    class_mapping:
        original class ID -> final class ID

    Final classes:
        0 = wet
        1 = dry
        2 = recyclable
    """

    print("\n============================================================")
    print(f"ADDING DATASET: {dataset_name}")
    print("============================================================")

    for final_split, source_split in SPLITS.items():

        image_dir = dataset_root / source_split / "images"
        label_dir = dataset_root / source_split / "labels"

        if not image_dir.exists():
            print(f"{source_split}: image directory not found")
            continue

        if not label_dir.exists():
            print(f"{source_split}: label directory not found")
            continue

        images = [
            p for p in image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]

        print(f"{source_split}: {len(images)} images")

        copied_images = 0
        copied_labels = 0

        for image_path in images:

            label_path = label_dir / (image_path.stem + ".txt")

            if not label_path.exists():
                print(
                    f"WARNING: Missing label for {image_path.name}"
                )
                continue

            # Prefix prevents filename collisions
            new_stem = f"{dataset_name}_{image_path.stem}"

            new_image = (
                FINAL_DIR /
                final_split /
                "images" /
                f"{new_stem}{image_path.suffix}"
            )

            new_label = (
                FINAL_DIR /
                final_split /
                "labels" /
                f"{new_stem}.txt"
            )

            # ------------------------------------------------
            # Convert YOLO labels
            # ------------------------------------------------

            converted_lines = []

            with open(label_path, "r", encoding="utf-8") as f:

                for line in f:
                    line = line.strip()

                    if not line:
                        continue

                    parts = line.split()

                    if len(parts) != 5:
                        print(
                            f"WARNING: Invalid label: {label_path}"
                        )
                        continue

                    original_class = int(parts[0])

                    if original_class not in class_mapping:
                        print(
                            f"WARNING: Unknown class "
                            f"{original_class} in "
                            f"{label_path.name}"
                        )
                        continue

                    final_class = class_mapping[original_class]

                    converted_lines.append(
                        f"{final_class} "
                        f"{parts[1]} "
                        f"{parts[2]} "
                        f"{parts[3]} "
                        f"{parts[4]}\n"
                    )

                    final_counts[final_split][final_class] += 1

            # Don't copy image if no valid annotations remain
            if not converted_lines:
                continue

            shutil.copy2(image_path, new_image)

            with open(new_label, "w", encoding="utf-8") as f:
                f.writelines(converted_lines)

            copied_images += 1
            copied_labels += 1

        print(
            f"Copied: {copied_images} images | "
            f"{copied_labels} labels"
        )


# ============================================================
# DATASET 1: RECYCLABLE
# ============================================================

add_dataset(
    RECYCLABLE_ROOT,
    "recyclable",
    {
        0: 2
    }
)

# ============================================================
# DATASET 2: DRY
# ============================================================

add_dataset(
    DRY_ROOT,
    "dry",
    {
        0: 1
    }
)

# ============================================================
# DATASET 3: ORGANIC / INORGANIC
# ============================================================

add_dataset(
    ORGANIC_ROOT,
    "organic",
    {
        # Dry
        0: 1,  # Battery
        1: 1,  # Bugs Spray

        # Wet
        2: 0,  # Dry Leave
        3: 0,  # Fruit Waste

        # Recyclable
        4: 2,  # Glass
        5: 2,  # Paper
        6: 2,  # Plastic Bag
        7: 2,  # Plastic Bottle
        8: 2   # Tin
    }
)

# ============================================================
# CREATE DATA.YAML
# ============================================================

yaml_content = """path: dataset/waste_3class_final

train: train/images
val: valid/images
test: test/images

nc: 3

names:
  0: wet
  1: dry
  2: recyclable
"""

yaml_path = FINAL_DIR / "data.yaml"

with open(yaml_path, "w", encoding="utf-8") as f:
    f.write(yaml_content)

# ============================================================
# FINAL DATASET SUMMARY
# ============================================================

print("\n")
print("=" * 70)
print("FINAL DATASET CREATED")
print("=" * 70)

for split in ["train", "valid", "test"]:

    image_count = len(
        list(
            (FINAL_DIR / split / "images").glob("*")
        )
    )

    label_count = len(
        list(
            (FINAL_DIR / split / "labels").glob("*.txt")
        )
    )

    print(f"\n{split.upper()}")
    print("-" * 40)
    print("Images :", image_count)
    print("Labels :", label_count)

    print(
        "Wet        :",
        final_counts[split][0]
    )

    print(
        "Dry        :",
        final_counts[split][1]
    )

    print(
        "Recyclable :",
        final_counts[split][2]
    )

print("\n")
print("=" * 70)
print("DATA.YAML")
print("=" * 70)

print(yaml_content)

print("\nDataset location:")
print(FINAL_DIR.resolve())

print("\nDONE!")