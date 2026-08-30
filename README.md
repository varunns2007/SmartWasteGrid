# SmartWaste Segregation & Logistics Prototype

SmartWaste is an automated waste-segregation and logistics prototype. It uses computer vision (Ultralytics YOLO11s) mounted above a conveyor belt to classify waste into **wet (0)**, **dry (1)**, and **recyclable (2)** categories, aggregates detections into 10-second operational batches, calculates key environmental & energy metrics (WQI, LHV, kWh potential, Carbon Offset), and recommends optimal processing plants using a dual-mode (Classical / QAOA) optimization engine.

---

## 1. Environment & CUDA Verification

Ensure Python virtual environment is activated:
```powershell
.\.venv\Scripts\python.exe -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0))"
```
*Target GPU: NVIDIA GeForce RTX 2050 (4 GB VRAM)*

---

## 2. Dataset Building & Validation

Extract datasets, remap classes to 3 target categories (`0: wet`, `1: dry`, `2: recyclable`), convert polygon labels, and run dataset integrity validation:
```powershell
.\.venv\Scripts\python.exe -u tools/build_dataset.py
```
Outputs:
- Target dataset directory: `dataset/waste_3class_final/`
- Data configuration: `dataset/waste_3class_final/data.yaml`
- Detailed report: `reports/dataset/dataset_report.txt`

Generate dataset visualization plots:
```powershell
.\.venv\Scripts\python.exe tools/inspect_dataset.py
```
Outputs in `reports/dataset/`:
- `class_distribution.png`
- `wet_samples.png`
- `dry_samples.png`
- `recyclable_samples.png`
- `multi_object_samples.png`
- `random_training_samples.png`

---

## 3. YOLO11s Model Training

Train Ultralytics YOLO11s on CUDA GPU (device 0) with VRAM safety fallback:
```powershell
.\.venv\Scripts\python.exe tools/train.py
```
Saved weights location:
- Best weights: `runs/SmartWasteGrid_YOLO11s/weights/best.pt`
- Last weights: `runs/SmartWasteGrid_YOLO11s/weights/last.pt`

---

## 4. Test Set Evaluation

Evaluate trained `best.pt` model on the holdout test set (`dataset/waste_3class_final/test/images`):
```powershell
.\.venv\Scripts\python.exe tools/eval_test.py
```
Outputs in `reports/test/`:
- `test_report.txt` (Precision, Recall, mAP50, mAP50-95, per-class metrics)
- `confusion_matrix.png`

---

## 5. MySQL Database & Backend Setup

Copy environment configuration:
```powershell
Copy-Item .env.example .env
```

Configure `.env` database connection:
```ini
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/smartwaste
API_URL=http://127.0.0.1:8000
CAMERA_ID=CAM_001
AREA_NAME=Demo Area
LATITUDE=0.0
LONGITUDE=0.0
WEIGHT_MODE=manual
MOISTURE_MODE=estimated
```

Run database integrity test:
```powershell
.\.venv\Scripts\python.exe tools/test_database.py
```

Start FastAPI Backend server:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```
Interactive API Documentation: `http://127.0.0.1:8000/docs`

---

## 6. End-to-End API Integration Test

Run end-to-end simulation testing API health, batch creation, metric calculation, plant optimization, and database insertion:
```powershell
.\.venv\Scripts\python.exe tools/test_api.py
```

---

## 7. Conveyor Belt Real-Time Webcam Operation

Run real-time webcam detection preview:
```powershell
.\.venv\Scripts\python.exe tools/webcam_test.py --camera 0
```

Run automated conveyor belt batch client (uploads 10-second aggregated batches directly to MySQL backend):
```powershell
.\.venv\Scripts\python.exe tools/webcam_client.py --camera 0 --duration 10 --weight 12.5
```

---

## 8. API Endpoints Reference

- `GET /health`: Server health check
- `POST /api/batches`: Create a new waste batch & calculate metrics
- `GET /api/batches`: Retrieve recent waste batches
- `GET /api/batches/latest`: Fetch latest recorded batch
- `GET /api/batches/{batch_id}`: Fetch specific batch by ID
- `PUT /api/batches/{batch_id}`: Update batch details
- `POST /api/optimize/{batch_id}`: Re-run logistics optimization (`method: Classical | QAOA`)
- `GET /api/statistics`: Aggregated system statistics (total waste, kWh, carbon offset)
