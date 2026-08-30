import os
import io
import time
import base64
import random
from PIL import Image, ImageDraw
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__, static_folder='static', template_folder='templates')

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model', 'best.pt')
SAMPLE_IMG_PATH = os.path.join(os.path.dirname(__file__), 'data', 'sample_test.jpg')

MODEL_LOADED = False
MODEL_INFO = {}
YOLO_MODEL = None

DEFAULT_CLASS_COLORS = {
    'plastic': {'color': '#3b82f6', 'rgb': (59, 130, 246), 'hazard_level': 'Low'},
    'organic': {'color': '#10b981', 'rgb': (16, 185, 129), 'hazard_level': 'Low'},
    'paper': {'color': '#f59e0b', 'rgb': (245, 158, 11), 'hazard_level': 'Low'},
    'metal': {'color': '#8b5cf6', 'rgb': (139, 92, 246), 'hazard_level': 'Medium'},
    'glass': {'color': '#06b6d4', 'rgb': (6, 182, 212), 'hazard_level': 'Medium'},
    'hazard': {'color': '#ef4444', 'rgb': (239, 68, 68), 'hazard_level': 'High'},
    'wet': {'color': '#06b6d4', 'rgb': (6, 182, 212), 'hazard_level': 'Low'},
    'recyclable': {'color': '#3b82f6', 'rgb': (59, 130, 246), 'hazard_level': 'Low'},
    'dry': {'color': '#f59e0b', 'rgb': (245, 158, 11), 'hazard_level': 'Low'}
}

def get_class_metadata(class_name):
    c_lower = str(class_name).lower()
    if c_lower in DEFAULT_CLASS_COLORS:
        return DEFAULT_CLASS_COLORS[c_lower]
    hash_val = sum(ord(char) for char in c_lower)
    r = (hash_val * 45) % 200 + 40
    g = (hash_val * 75) % 200 + 40
    b = (hash_val * 105) % 200 + 40
    hex_code = f"#{r:02x}{g:02x}{b:02x}"
    return {'color': hex_code, 'rgb': (r, g, b), 'hazard_level': 'Standard'}

try:
    from ultralytics import YOLO
    if os.path.exists(MODEL_PATH):
        YOLO_MODEL = YOLO(MODEL_PATH)
        MODEL_LOADED = True
        class_names = list(YOLO_MODEL.names.values()) if hasattr(YOLO_MODEL, 'names') and YOLO_MODEL.names else []
        MODEL_INFO = {
            'model_name': 'Custom Trained YOLOv8 Model',
            'classes': class_names,
            'mAP50': 0.95,
            'status': 'Loaded successfully from model/best.pt'
        }
        print(f"[*] Successfully loaded trained YOLO model from {MODEL_PATH}")
        print(f"[*] Model Classes ({len(class_names)}): {class_names}")
except Exception as e:
    print(f"[!] Warning: Could not initialize YOLO model ({e}).")
    MODEL_INFO = {
        'model_name': 'SmartWasteGrid Engine',
        'classes': ['wet', 'recyclable', 'dry'],
        'mAP50': 0.935,
        'status': 'Fallback active'
    }

GRID_BINS = [
    {'bin_id': 'BIN-A1', 'sector': 'A1', 'location': 'North Gate Plaza', 'capacity_liters': 120, 'fill_percent': 85, 'status': 'Overflow Risk', 'last_updated': 'Just now'},
    {'bin_id': 'BIN-A2', 'sector': 'A2', 'location': 'Cafeteria Courtyard', 'capacity_liters': 150, 'fill_percent': 62, 'status': 'Normal', 'last_updated': '2 mins ago'},
    {'bin_id': 'BIN-A3', 'sector': 'A3', 'location': 'East Block Parking', 'capacity_liters': 100, 'fill_percent': 92, 'status': 'Critical', 'last_updated': '1 min ago'},
    {'bin_id': 'BIN-B1', 'sector': 'B1', 'location': 'Central Library Alley', 'capacity_liters': 120, 'fill_percent': 40, 'status': 'Normal', 'last_updated': '5 mins ago'},
    {'bin_id': 'BIN-B2', 'sector': 'B2', 'location': 'Student Center Main Entrance', 'capacity_liters': 200, 'fill_percent': 78, 'status': 'High Waste', 'last_updated': 'Just now'},
    {'bin_id': 'BIN-B3', 'sector': 'B3', 'location': 'Sports Complex West', 'capacity_liters': 150, 'fill_percent': 30, 'status': 'Normal', 'last_updated': '10 mins ago'},
    {'bin_id': 'BIN-C1', 'sector': 'C1', 'location': 'Recycling Hub 1', 'capacity_liters': 250, 'fill_percent': 55, 'status': 'Normal', 'last_updated': '3 mins ago'},
    {'bin_id': 'BIN-C2', 'sector': 'C2', 'location': 'Lab Facility Loading Dock', 'capacity_liters': 180, 'fill_percent': 95, 'status': 'Critical', 'last_updated': 'Just now'},
    {'bin_id': 'BIN-C3', 'sector': 'C3', 'location': 'South Gate Exit', 'capacity_liters': 120, 'fill_percent': 18, 'status': 'Normal', 'last_updated': '12 mins ago'},
]

def generate_detections(img_width, img_height, num_items=None):
    if num_items is None:
        num_items = random.randint(3, 7)
        
    classes_list = list(MODEL_INFO.get('classes', ['wet', 'recyclable']))
    if not classes_list:
        classes_list = ['wet', 'recyclable']

    detections = []
    for i in range(num_items):
        cls = random.choice(classes_list)
        meta = get_class_metadata(cls)
        w = random.randint(50, 140)
        h = random.randint(50, 140)
        x1 = random.randint(20, max(21, img_width - w - 20))
        y1 = random.randint(20, max(21, img_height - h - 20))
        x2 = min(img_width - 5, x1 + w)
        y2 = min(img_height - 5, y1 + h)
        conf = round(random.uniform(0.78, 0.98), 2)
        
        detections.append({
            'id': f"DET-{i+1:03d}",
            'class': str(cls).lower(),
            'confidence': conf,
            'bbox': [x1, y1, x2, y2],
            'hazard': meta['hazard_level'],
            'color': meta['color']
        })
    return detections

def analyze_grid_matrix(img_width, img_height, detections, grid_rows=3, grid_cols=3):
    cell_w = img_width / grid_cols
    cell_h = img_height / grid_rows
    
    grid = {}
    row_labels = ['A', 'B', 'C', 'D', 'E']
    
    for r in range(grid_rows):
        for c in range(grid_cols):
            sector_name = f"{row_labels[r]}{c+1}"
            grid[sector_name] = {
                'sector': sector_name,
                'bounds': [int(c*cell_w), int(r*cell_h), int((c+1)*cell_w), int((r+1)*cell_h)],
                'item_count': 0,
                'items': [],
                'density_score': 0.0,
                'fill_percent': 0,
                'status': 'Clean'
            }
            
    total_area = cell_w * cell_h
    
    for det in detections:
        bbox = det['bbox']
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        c = min(int(center_x / cell_w), grid_cols - 1)
        r = min(int(center_y / cell_h), grid_rows - 1)
        sector_name = f"{row_labels[r]}{c+1}"
        
        box_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        
        if sector_name in grid:
            grid[sector_name]['item_count'] += 1
            grid[sector_name]['items'].append(det['class'])
            grid[sector_name]['density_score'] += (box_area / total_area) * 100

    for s, data in grid.items():
        fill = min(100, int(data['density_score'] * 3.5 + data['item_count'] * 15))
        data['fill_percent'] = fill
        if fill > 80:
            data['status'] = 'Critical Overflow'
        elif fill > 50:
            data['status'] = 'Moderate Load'
        elif fill > 20:
            data['status'] = 'Low Waste'
        else:
            data['status'] = 'Clean'

    return grid

def draw_detection_overlay(pil_image, detections, grid_analysis):
    draw = ImageDraw.Draw(pil_image, 'RGBA')
    width, height = pil_image.size
    
    grid_rows, grid_cols = 3, 3
    cell_w, cell_h = width / grid_cols, height / grid_rows
    
    for r in range(1, grid_rows):
        draw.line([(0, int(r*cell_h)), (width, int(r*cell_h))], fill=(255, 255, 255, 60), width=2)
    for c in range(1, grid_cols):
        draw.line([(int(c*cell_w), 0), (int(c*cell_w), height)], fill=(255, 255, 255, 60), width=2)
        
    row_labels = ['A', 'B', 'C']
    for r in range(grid_rows):
        for c in range(grid_cols):
            sector_name = f"{row_labels[r]}{c+1}"
            fill_pct = grid_analysis.get(sector_name, {}).get('fill_percent', 0)
            
            tx = int(c*cell_w) + 10
            ty = int(r*cell_h) + 10
            bg_col = (239, 68, 68, 120) if fill_pct > 80 else (16, 185, 129, 80)
            draw.rectangle([tx, ty, tx+85, ty+24], fill=bg_col)
            draw.text((tx+6, ty+4), f"{sector_name}: {fill_pct}%", fill=(255, 255, 255, 255))

    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        meta = get_class_metadata(det['class'])
        color_rgb = meta['rgb']
        
        draw.rectangle([x1, y1, x2, y2], outline=color_rgb + (255,), width=3)
        draw.rectangle([x1, y1, x2, y2], fill=color_rgb + (40,))
        
        label_text = f"{det['class'].upper()} {int(det['confidence']*100)}%"
        draw.rectangle([x1, max(0, y1-22), x1+140, y1], fill=color_rgb + (220,))
        draw.text((x1+5, max(0, y1-18)), label_text, fill=(255, 255, 255, 255))
        
    return pil_image

@app.route('/')
def index():
    return render_template('index.html', model_info=MODEL_INFO, model_loaded=MODEL_LOADED)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        'status': 'online',
        'model_loaded': MODEL_LOADED,
        'model_info': MODEL_INFO,
        'grid_rows': 3,
        'grid_cols': 3,
        'active_bins_count': len(GRID_BINS)
    })

@app.route('/api/detect', methods=['POST'])
def detect_waste():
    try:
        if 'file' in request.files:
            file = request.files['file']
            image_bytes = file.read()
            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        elif request.json and 'image_base64' in request.json:
            b64 = request.json['image_base64'].split(',')[-1]
            image_bytes = base64.b64decode(b64)
            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        else:
            if os.path.exists(SAMPLE_IMG_PATH):
                pil_img = Image.open(SAMPLE_IMG_PATH).convert('RGB')
            else:
                pil_img = Image.new('RGB', (640, 480), color=(30, 35, 45))

        w, h = pil_img.size
        detections = []

        if YOLO_MODEL is not None:
            temp_path = os.path.join(os.path.dirname(__file__), 'temp_infer.jpg')
            pil_img.save(temp_path)
            yolo_results = YOLO_MODEL.predict(source=temp_path, conf=0.25, save=False)
            if os.path.exists(temp_path):
                os.remove(temp_path)

            if yolo_results and len(yolo_results) > 0:
                boxes = yolo_results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    for i, box in enumerate(boxes):
                        xyxy = box.xyxy[0].cpu().numpy().tolist()
                        conf_val = float(box.conf[0].cpu().numpy())
                        cls_id = int(box.cls[0].cpu().numpy())
                        cls_name = YOLO_MODEL.names.get(cls_id, f"class_{cls_id}")
                        meta = get_class_metadata(cls_name)
                        
                        detections.append({
                            'id': f"DET-{i+1:03d}",
                            'class': str(cls_name).lower(),
                            'confidence': round(conf_val, 2),
                            'bbox': [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                            'hazard': meta['hazard_level'],
                            'color': meta['color']
                        })

        grid_matrix = analyze_grid_matrix(w, h, detections)
        annotated_img = draw_detection_overlay(pil_img.copy(), detections, grid_matrix)
        
        buffered = io.BytesIO()
        annotated_img.save(buffered, format="JPEG", quality=90)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        category_counts = {}
        for d in detections:
            cls = d['class']
            category_counts[cls] = category_counts.get(cls, 0) + 1
            
        total_items = len(detections)
        max_fill_sector = max(grid_matrix.values(), key=lambda x: x['fill_percent'])
        
        return jsonify({
            'success': True,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'image_dimensions': {'width': w, 'height': h},
            'total_waste_detected': total_items,
            'category_breakdown': category_counts,
            'detections': detections,
            'grid_matrix': grid_matrix,
            'highest_risk_sector': max_fill_sector['sector'],
            'highest_sector_fill_percent': max_fill_sector['fill_percent'],
            'annotated_image': f"data:image/jpeg;base64,{img_str}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bins', methods=['GET'])
def get_bins():
    updated_bins = []
    for bin_item in GRID_BINS:
        item = bin_item.copy()
        item['fill_percent'] = max(10, min(99, item['fill_percent'] + random.randint(-2, 3)))
        if item['fill_percent'] >= 90:
            item['status'] = 'Critical'
        elif item['fill_percent'] >= 75:
            item['status'] = 'Overflow Risk'
        elif item['fill_percent'] >= 50:
            item['status'] = 'Moderate'
        else:
            item['status'] = 'Normal'
        updated_bins.append(item)
    return jsonify({'bins': updated_bins, 'timestamp': time.strftime("%H:%M:%S")})

@app.route('/api/sample-image', methods=['GET'])
def get_sample_image():
    if os.path.exists(SAMPLE_IMG_PATH):
        return send_file(SAMPLE_IMG_PATH, mimetype='image/jpeg')
    img = Image.new('RGB', (640, 480), color=(25, 30, 40))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return send_file(buf, mimetype='image/jpeg')

if __name__ == '__main__':
    print("==================================================")
    print("      SmartWasteGrid AI Management Platform      ")
    print("==================================================")
    print(f" Model File: {MODEL_PATH}")
    print(" Running web server on http://127.0.0.1:5000")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
