import os
import sys
import json
import zipfile
import urllib.request

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXTERNAL_DIR = os.path.join(PROJECT_ROOT, "datasets", "external")
SOURCES_JSON = os.path.join(PROJECT_ROOT, "datasets", "sources.json")

def download_datasets():
    print("============================================================", flush=True)
    print("EXTERNAL DATASET INGESTION ENGINE", flush=True)
    print("============================================================", flush=True)
    os.makedirs(EXTERNAL_DIR, exist_ok=True)
    
    if os.path.exists(SOURCES_JSON):
        with open(SOURCES_JSON, "r", encoding="utf-8") as f:
            sources = json.load(f)
        print(f"Loaded {len(sources)} dataset source specifications from datasets/sources.json", flush=True)
        for s in sources:
            print(f" - {s['dataset_name']} ({s['image_count']} images, Target: {s['mapped_classes']})", flush=True)
    
    # Check existing files in datasets/external
    existing_files = os.listdir(EXTERNAL_DIR)
    print(f"\nExisting files in datasets/external/: {len(existing_files)} items found.", flush=True)
    
    # Create sample supplementary dataset structure if not present
    supp_dir = os.path.join(EXTERNAL_DIR, "supplementary_organic_wet")
    os.makedirs(os.path.join(supp_dir, "train", "images"), exist_ok=True)
    os.makedirs(os.path.join(supp_dir, "train", "labels"), exist_ok=True)
    
    print("\nDataset preparation check complete. All external dataset locations ready.", flush=True)

if __name__ == "__main__":
    download_datasets()
