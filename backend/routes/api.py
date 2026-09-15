from flask import Blueprint, jsonify, request, Response
from backend.services.waste_service import WasteService
from backend.services.mrv_service import MRVService

api_bp = Blueprint('api', __name__)

@api_bp.route('/plants', methods=['GET'])
def get_plants():
    return jsonify(WasteService.get_all_plants())

@api_bp.route('/plants', methods=['POST'])
def add_plant():
    data = request.json or {}
    plant = WasteService.add_plant(
        name=data.get('name'),
        technology_type=data.get('technology_type'),
        lat=data.get('lat'),
        lng=data.get('lng'),
        max_capacity_tons=data.get('max_capacity_tons'),
        current_utilization_tons=data.get('current_utilization_tons', 0.0),
        recovered_heat_mw=data.get('recovered_heat_mw', 0.0),
        efficiency_factor=data.get('efficiency_factor', 1.0)
    )
    return jsonify(plant), 201

@api_bp.route('/trucks', methods=['GET'])
def get_trucks():
    return jsonify(WasteService.get_all_trucks())

@api_bp.route('/batches/unallocated', methods=['GET'])
def get_unallocated():
    return jsonify(WasteService.get_unallocated_batches())

@api_bp.route('/workflow', methods=['POST'])
def run_workflow():
    data = request.json or {}
    num_batches = data.get('num_batches', 3)
    result = WasteService.run_simulation_and_optimization_workflow(num_batches=num_batches)
    return jsonify(result)

@api_bp.route('/dashboard/summary', methods=['GET'])
def get_summary():
    result = WasteService.get_dashboard_summary()
    return jsonify(result)

@api_bp.route('/forecasting', methods=['GET'])
def get_forecasting():
    result = WasteService.get_zone_forecasting()
    return jsonify(result)

@api_bp.route('/transit-centers/telemetry', methods=['GET'])
def get_transit_telemetry():
    station_name = request.args.get('station_name')
    result = WasteService.get_transit_center_telemetry(station_name)
    return jsonify(result)

@api_bp.route('/config', methods=['GET'])
def get_config():
    import os
    from backend.camera_stream import get_configured_camera_index
    gmap_key = os.getenv('GOOGLE_MAPS_API_KEY', '').strip()
    return jsonify({
        'google_maps_api_key': gmap_key,
        'has_google_maps_key': bool(gmap_key),
        'camera_index': get_configured_camera_index(),
        'area_name': os.getenv('AREA_NAME', 'Chennai Metropolitan ULB'),
        'api_version': '2.0.0-2026'
    })

@api_bp.route('/config/maps-key', methods=['POST'])
def update_maps_key():
    import os
    data = request.json or {}
    new_key = data.get('api_key', '').strip()
    os.environ['GOOGLE_MAPS_API_KEY'] = new_key
    
    # Also update .env file if present
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    try:
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'GOOGLE_MAPS_API_KEY=' in content:
                import re
                content = re.sub(r'GOOGLE_MAPS_API_KEY=.*', f'GOOGLE_MAPS_API_KEY={new_key}', content)
            else:
                content += f"\nGOOGLE_MAPS_API_KEY={new_key}\n"
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception as e:
        print(f"[!] Note on updating .env: {e}")

    return jsonify({
        'status': 'SUCCESS',
        'google_maps_api_key': new_key,
        'has_google_maps_key': bool(new_key)
    })

@api_bp.route('/webcams', methods=['GET'])
def get_webcams():
    from backend.camera_stream import detect_connected_webcams, VideoCamera
    cams = detect_connected_webcams()
    cam_inst = VideoCamera()
    return jsonify({
        'webcams': cams,
        'current_index': cam_inst.camera_index,
        'mode': 'simulation' if cam_inst.force_simulation else 'hardware',
        'is_hardware_active': cam_inst.use_hardware_cam
    })

@api_bp.route('/trucks/search', methods=['GET'])
def search_trucks():
    q = (request.args.get('q') or '').strip().lower()
    trucks = WasteService.get_all_trucks()
    if not q:
        return jsonify(trucks)
    
    filtered = []
    for t in trucks:
        reg = (t.get('registration_number') or '').lower()
        plant = (t.get('assigned_plant_name') or '').lower()
        driver = (t.get('driver_name') or '').lower()
        status = (t.get('route_status') or '').lower()
        b = t.get('batch') or {}
        b_id = str(b.get('batch_id', ''))
        st = (b.get('station') or '').lower()

        if q in reg or q in plant or q in driver or q in status or q in b_id or q in st:
            filtered.append(t)
    return jsonify(filtered)

@api_bp.route('/camera/mode', methods=['GET', 'POST'])
def camera_mode():
    from backend.camera_stream import VideoCamera
    cam = VideoCamera()
    if request.method == 'POST':
        data = request.json or {}
        mode = data.get('mode', 'hardware').lower()
        idx = data.get('camera_index')
        if idx is None:
            idx = data.get('index')
        if idx is not None:
            try:
                cam.set_camera_index(int(idx))
            except Exception:
                pass
        sim_enabled = (mode == 'simulation')
        cam.set_simulation_mode(sim_enabled)
        return jsonify({
            'status': 'SUCCESS',
            'simulation_mode': sim_enabled,
            'mode': 'simulation' if sim_enabled else 'hardware',
            'camera_index': cam.camera_index,
            'is_hardware_active': cam.use_hardware_cam
        })
    return jsonify({
        'simulation_mode': cam.force_simulation,
        'mode': 'simulation' if cam.force_simulation else 'hardware',
        'camera_index': cam.camera_index,
        'is_hardware_active': cam.use_hardware_cam
    })

@api_bp.route('/camera/classify_frame', methods=['POST'])
def classify_frame():
    import base64
    import numpy as np
    import cv2
    from backend.camera_stream import VideoCamera

    data = request.json or {}
    image_b64 = data.get('image', '')
    if not image_b64:
        return jsonify({'status': 'ERROR', 'error': 'No image data provided'}), 400

    try:
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[1]
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({'status': 'ERROR', 'error': 'Failed to decode image'}), 400

        cam = VideoCamera()
        if cam.model is None:
            return jsonify({'status': 'ERROR', 'error': 'YOLO model not loaded'}), 500

        results = cam.model.predict(source=frame, imgsz=320, conf=0.40, verbose=False)
        detections = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    cls_id = int(box.cls[0].cpu().numpy())
                    conf = float(box.conf[0].cpu().numpy())
                    cname = cam.class_names.get(cls_id, 'waste')
                    decision = cam.sorting_bins.get(cls_id, 'GENERAL BIN')
                    detections.append({
                        'box': [x1, y1, x2, y2],
                        'class_id': cls_id,
                        'class_name': cname,
                        'confidence': round(conf, 4),
                        'sorting_decision': decision
                    })
                    if data.get('log_db', False) and conf >= 0.50:
                        cam.log_detection_to_db(cls_id, cname, conf)

        return jsonify({
            'status': 'SUCCESS',
            'detections': detections,
            'count': len(detections)
        })
    except Exception as e:
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500

@api_bp.route('/conveyor/simulate', methods=['POST'])
def simulate_conveyor_detection():
    data = request.json or {}
    override_cls = data.get('class_id')
    from backend.camera_stream import VideoCamera
    VideoCamera().set_simulation_mode(True)
    res = WasteService.simulate_conveyor_item(override_class=override_cls)
    return jsonify(res), 201

@api_bp.route('/conveyor/live', methods=['GET'])
def get_live_conveyor():
    limit = request.args.get('limit', 20, type=int)
    items = WasteService.get_live_conveyor_items(limit=limit)
    return jsonify(items)

@api_bp.route('/conveyor/tick', methods=['GET'])
def get_conveyor_tick():
    try:
        from backend.flask_models.models import ConveyorItem
        latest_item = ConveyorItem.query.order_by(ConveyorItem.id.desc()).first()
        if latest_item:
            tick_data = {
                "tick": latest_item.id,
                "detected_item": {
                    "name": latest_item.item_name,
                    "category": latest_item.class_name,
                    "confidence": latest_item.confidence,
                    "bin": latest_item.sorting_decision,
                    "weight_kg": latest_item.item_weight_kg
                },
                "timestamp": latest_item.timestamp.isoformat() if latest_item.timestamp else ""
            }
        else:
            tick_data = {
                "tick": 1,
                "detected_item": {
                    "name": "PET Plastic Bottle",
                    "category": "recyclable",
                    "confidence": 0.94,
                    "bin": "RECYCLABLE BIN (MRF)",
                    "weight_kg": 0.35
                },
                "timestamp": ""
            }
        return jsonify(tick_data)
    except Exception as e:
        return jsonify({"tick": 0, "detected_item": None, "error": str(e)})

@api_bp.route('/conveyor/stats', methods=['GET'])
def get_conveyor_statistics():
    stats = WasteService.get_conveyor_stats()
    return jsonify(stats)

@api_bp.route('/database/detections', methods=['GET'])
def get_db_detections():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    station = request.args.get('station', None)
    category = request.args.get('category', None)
    res = WasteService.get_database_detections(page=page, limit=limit, station=station, category=category)
    return jsonify(res)

@api_bp.route('/database/detections/clear', methods=['POST', 'DELETE'])
def clear_db_detections():
    from backend.flask_db.db import db
    from backend.flask_models.models import ConveyorItem
    try:
        deleted = ConveyorItem.query.delete()
        db.session.commit()
        return jsonify({'status': 'SUCCESS', 'deleted_count': deleted, 'message': 'All detection records purged.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500

@api_bp.route('/database/batches', methods=['GET'])
def get_db_batches():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    res = WasteService.get_database_batches(page=page, limit=limit)
    return jsonify(res)

@api_bp.route('/database/facilities', methods=['GET'])
def get_db_facilities():
    res = WasteService.get_database_facilities()
    return jsonify(res)

@api_bp.route('/database/routing-logs', methods=['GET'])
def get_db_routing_logs():
    limit = request.args.get('limit', 25, type=int)
    res = WasteService.get_routing_audit_logs(limit=limit)
    return jsonify(res)

@api_bp.route('/matching/status', methods=['GET'])
def get_cross_ulb_matching_panel():
    res = WasteService.get_cross_ulb_matching_panel_data()
    return jsonify(res)

@api_bp.route('/metrics/diversion', methods=['GET'])
def get_diversion_metrics_panel():
    res = WasteService.get_diversion_metrics_data()
    return jsonify(res)

@api_bp.route('/mrv/summary', methods=['GET'])
def get_mrv_summary():
    res = MRVService.get_carbon_impact_summary()
    return jsonify(res)

@api_bp.route('/mrv/export', methods=['GET'])
def export_mrv_report():
    csv_data = MRVService.generate_auditor_csv_report()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=MRV_Auditor_Report_Cryptographic_Ledger.csv"}
    )
