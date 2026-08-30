import os
import sys
import unittest
import json
from PIL import Image
from ultralytics import YOLO

# Import app components for testing
sys.path.append(os.path.dirname(__file__))
from app import app, analyze_grid_matrix, generate_detections, MODEL_PATH, SAMPLE_IMG_PATH

def run_ultralytics_inference():
    """Executes Ultralytics YOLO model inference on test.jpg."""
    test_img = os.path.join(os.path.dirname(__file__), 'test.jpg')
    if not os.path.exists(test_img):
        # Fallback to sample image
        test_img = SAMPLE_IMG_PATH

    print(f"\n[*] Initializing YOLO model from {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)

    print(f"[*] Running model prediction on source: {test_img} (conf=0.5)...")
    results = model.predict(
        source=test_img,
        conf=0.5,
        save=True
    )
    print("Detection completed!")
    return results

class TestSmartWasteGrid(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_model_file_exists_and_loads(self):
        """Verify model/best.pt exists and can be loaded via Ultralytics YOLO."""
        self.assertTrue(os.path.exists(MODEL_PATH), f"Model file missing at {MODEL_PATH}")
        model = YOLO(MODEL_PATH)
        self.assertIsNotNone(model)
        print(f"\n[TEST PASS] Ultralytics YOLO successfully loaded model checkpoint: {MODEL_PATH}")

    def test_02_sample_data_file(self):
        """Verify sample test image exists and is readable."""
        self.assertTrue(os.path.exists(SAMPLE_IMG_PATH), f"Sample image missing at {SAMPLE_IMG_PATH}")
        img = Image.open(SAMPLE_IMG_PATH)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (640, 480))
        print(f"[TEST PASS] Sample test image verified ({img.size[0]}x{img.size[1]} px)")

    def test_03_grid_matrix_calculation(self):
        """Verify spatial 3x3 grid division and fill percent calculation."""
        width, height = 640, 480
        sample_detections = [
            {'bbox': [50, 50, 150, 150], 'class': 'plastic'},
            {'bbox': [60, 60, 180, 180], 'class': 'paper'},
            {'bbox': [450, 300, 600, 420], 'class': 'hazard'}
        ]
        grid = analyze_grid_matrix(width, height, sample_detections, grid_rows=3, grid_cols=3)
        self.assertIn('A1', grid)
        self.assertIn('C3', grid)
        self.assertEqual(grid['A1']['item_count'], 2)
        print(f"[TEST PASS] Spatial Grid Matrix calculation verified")

    def test_04_api_status_endpoint(self):
        """Test GET /api/status API response."""
        response = self.app.get('/api/status')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'online')
        print(f"[TEST PASS] API /api/status returned 200 OK")

    def test_05_ultralytics_prediction_run(self):
        """Test Ultralytics YOLO predict snippet."""
        results = run_ultralytics_inference()
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)
        print(f"[TEST PASS] Ultralytics predict pipeline successfully executed")

if __name__ == '__main__':
    print("==================================================")
    print("      Running SmartWasteGrid System Tests         ")
    print("==================================================")
    unittest.main()
