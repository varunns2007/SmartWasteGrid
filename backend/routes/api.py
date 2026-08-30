from flask import Blueprint, jsonify, request
from backend.services.waste_service import WasteService

api_bp = Blueprint('api', __name__)

@api_bp.route('/plants', methods=['GET'])
def get_plants():
    return jsonify(WasteService.get_all_plants())

@api_bp.route('/plants', methods=['POST'])
def add_plant():
    data = request.json
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
    solver_mode = data.get('solver_mode', 'cnn_milp')
    result = WasteService.run_simulation_and_optimization_workflow(num_batches=num_batches, solver_mode=solver_mode)
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


@api_bp.route('/camera/mode', methods=['GET', 'POST'])
def camera_mode():
    from backend.camera_stream import VideoCamera
    cam = VideoCamera()
    if request.method == 'POST':
        data = request.json or {}
        mode = data.get('mode', 'hardware').lower()
        idx = data.get('camera_index') or data.get('index')
        if idx is not None:
            try:
                cam.set_camera_index(int(idx))
            except Exception:
                pass
        sim_enabled = (mode == 'simulation')
        cam.set_simulation_mode(sim_enabled)
        return jsonify({'status': 'SUCCESS', 'simulation_mode': sim_enabled, 'mode': 'simulation' if sim_enabled else 'hardware', 'camera_index': cam.camera_index})
    return jsonify({'simulation_mode': cam.force_simulation, 'mode': 'simulation' if cam.force_simulation else 'hardware', 'camera_index': cam.camera_index})


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
