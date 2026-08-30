# SmartWasteGrid

**SmartWasteGrid** is an AI-powered Waste Detection, Sector Density Analysis, and IoT Bin Telemetry monitoring system built with PyTorch, Ultralytics YOLOv8, OpenCV, Flask, and an interactive modern web dashboard.

---

## Repository Structure

```
SmartWasteGrid/
│
├── model/
│   └── best.pt               # Trained Ultralytics YOLO PyTorch model weight file
│
├── static/
│   ├── css/
│   │   └── style.css         # Glassmorphism dark theme CSS styling
│   └── js/
│       └── main.js           # Client controller & real-time dashboard script
│
├── templates/
│   └── index.html            # Web dashboard interface template
│
├── data/
│   └── sample_test.jpg       # Sample test input frame
│
├── app.py                    # Flask server, vision grid engine, REST APIs
├── predict.py                # Command-line image test tool
├── test.py                   # Automated system test suite
├── requirements.txt          # Project Python dependencies
└── README.md                 # Documentation
```

---

## How to Test an Image

### Method 1: Command Line Interface (`predict.py`)
Run prediction on any image file:

```bash
# Test default image (test.jpg)
python predict.py

# Test any custom image
python predict.py path/to/your_image.jpg

# Adjust confidence threshold
python predict.py path/to/your_image.jpg --conf 0.5 --output result.jpg
```
The annotated grid matrix output image will be saved to `output_prediction.jpg` (or your chosen `--output` path).

---

### Method 2: Web Dashboard UI
Launch the interactive web UI to test images via drag-and-drop or file selection:

```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser and click **Upload Image** to process any image.

---

### Method 3: Python Ultralytics Script
```python
from ultralytics import YOLO

model = YOLO("model/best.pt")

results = model.predict(
    source="path/to/your_image.jpg",
    conf=0.5,
    save=True
)

print("Detection completed!")
```

---

## Run Unit Tests
```bash
python test.py
```
