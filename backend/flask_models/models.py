from datetime import datetime
from backend.flask_db.db import db

class Plant(db.Model):
    __tablename__ = 'plants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    technology_type = db.Column(db.String(50), nullable=False) # Biomethanation, RDF, Composting, Gasification, Recycling, Waste-to-Energy
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    max_capacity_tons = db.Column(db.Float, nullable=False)
    current_utilization_tons = db.Column(db.Float, default=0.0)
    recovered_heat_mw = db.Column(db.Float, default=0.0)
    efficiency_factor = db.Column(db.Float, default=1.0) # Used for energy estimation
    processing_cost_per_ton = db.Column(db.Float, default=100.0)
    available_heat_mw = db.Column(db.Float, default=0.0)
    processing_efficiency = db.Column(db.Float, default=0.8)
    queue_length = db.Column(db.Integer, default=0)
    
    historical_generations = db.relationship('HistoricalEnergyGeneration', backref='plant', lazy=True)
    optimization_results = db.relationship('OptimizationResult', backref='plant', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'technology_type': self.technology_type,
            'lat': self.lat,
            'lng': self.lng,
            'max_capacity_tons': self.max_capacity_tons,
            'current_utilization_tons': self.current_utilization_tons,
            'recovered_heat_mw': self.recovered_heat_mw,
            'efficiency_factor': self.efficiency_factor,
            'processing_cost_per_ton': self.processing_cost_per_ton,
            'available_heat_mw': self.available_heat_mw,
            'processing_efficiency': self.processing_efficiency,
            'queue_length': self.queue_length
        }

class Truck(db.Model):
    __tablename__ = 'trucks'
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    capacity_tons = db.Column(db.Float, nullable=False)
    current_load = db.Column(db.Float, default=0.0)
    assigned_plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=True)
    route_status = db.Column(db.String(50), default='IDLE')
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    
    batches = db.relationship('WasteBatch', backref='truck', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'registration_number': self.registration_number,
            'capacity_tons': self.capacity_tons,
            'current_load': self.current_load,
            'assigned_plant_id': self.assigned_plant_id,
            'route_status': self.route_status,
            'lat': self.lat,
            'lng': self.lng
        }

class WasteBatch(db.Model):
    __tablename__ = 'waste_batches'
    id = db.Column(db.Integer, primary_key=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'), nullable=False)
    source_lat = db.Column(db.Float, nullable=False)
    source_lng = db.Column(db.Float, nullable=False)
    weight_tons = db.Column(db.Float, nullable=False)
    organic_percentage = db.Column(db.Float, nullable=False)
    recyclable_percentage = db.Column(db.Float, nullable=False)
    hazardous_percentage = db.Column(db.Float, nullable=False)
    moisture_percentage = db.Column(db.Float, nullable=False)
    awvs_score = db.Column(db.Float, nullable=True) # Adaptive Waste Value Score
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Upgraded IoT and GIS parameters
    transfer_station_name = db.Column(db.String(100), nullable=True)
    zone = db.Column(db.String(100), nullable=True)
    iot_device_id = db.Column(db.String(50), nullable=True)
    iot_protocol = db.Column(db.String(50), nullable=True)
    moisture_raw_v = db.Column(db.Float, default=0.0)
    load_cell_mv = db.Column(db.Float, default=0.0)
    fill_level_pct = db.Column(db.Float, default=75.0)

    optimization_results = db.relationship('OptimizationResult', backref='waste_batch', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'truck_id': self.truck_id,
            'source_lat': self.source_lat,
            'source_lng': self.source_lng,
            'weight_tons': self.weight_tons,
            'organic_percentage': self.organic_percentage,
            'recyclable_percentage': self.recyclable_percentage,
            'hazardous_percentage': self.hazardous_percentage,
            'moisture_percentage': self.moisture_percentage,
            'awvs_score': self.awvs_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'transfer_station_name': self.transfer_station_name,
            'zone': self.zone,
            'iot_device_id': self.iot_device_id,
            'iot_protocol': self.iot_protocol,
            'moisture_raw_v': self.moisture_raw_v,
            'load_cell_mv': self.load_cell_mv,
            'fill_level_pct': self.fill_level_pct
        }

class OptimizationRun(db.Model):
    __tablename__ = 'optimization_runs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False) # e.g., 'SUCCESS', 'FAILED'
    computation_time_ms = db.Column(db.Float, nullable=True)
    
    results = db.relationship('OptimizationResult', backref='run', lazy=True)

class OptimizationResult(db.Model):
    __tablename__ = 'optimization_results'
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('optimization_runs.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('waste_batches.id'), nullable=False)
    assigned_plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    estimated_energy_kwh = db.Column(db.Float, nullable=False) # Estimated yield for this batch at this plant
    heat_recovery_utilized = db.Column(db.Boolean, default=False)
    heat_utilized_mw = db.Column(db.Float, default=0.0)
    lhv_increase_pct = db.Column(db.Float, default=0.0)
    recommendation_reason = db.Column(db.Text, nullable=True)

class HistoricalEnergyGeneration(db.Model):
    __tablename__ = 'historical_energy_generation'
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    energy_generated_kwh = db.Column(db.Float, nullable=False)
    total_waste_processed_tons = db.Column(db.Float, nullable=False)


class ConveyorItem(db.Model):
    __tablename__ = 'conveyor_items'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, nullable=False) # 0=wet, 1=dry, 2=recyclable
    class_name = db.Column(db.String(50), nullable=False) # wet, dry, recyclable
    confidence = db.Column(db.Float, nullable=False, default=0.95)
    sorting_decision = db.Column(db.String(50), nullable=False) # WET BIN, DRY BIN, RECYCLABLE BIN
    item_weight_kg = db.Column(db.Float, default=0.25)
    camera_id = db.Column(db.String(50), default='CONVEYOR_CAM_01')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'confidence': round(float(self.confidence or 0.95), 4),
            'sorting_decision': self.sorting_decision,
            'item_weight_kg': round(float(self.item_weight_kg or 0.25), 2),
            'camera_id': self.camera_id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }


class RoutingAuditLog(db.Model):
    __tablename__ = 'routing_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, nullable=False)
    source_ulb = db.Column(db.String(100), nullable=False) # e.g., GCC Zone 9 Teynampet
    matched_facility = db.Column(db.String(100), nullable=False) # Facility Name or "Landfill — No Match"
    escalation_status = db.Column(db.String(50), nullable=False) # MATCHED, ESCALATED, FALLBACK
    distance_km = db.Column(db.Float, default=0.0)
    cost_factor_inr = db.Column(db.Float, default=0.0)
    carbon_offset_kg = db.Column(db.Float, default=0.0)
    reason = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'source_ulb': self.source_ulb,
            'matched_facility': self.matched_facility,
            'escalation_status': self.escalation_status,
            'distance_km': round(float(self.distance_km or 0.0), 2),
            'cost_factor_inr': round(float(self.cost_factor_inr or 0.0), 2),
            'carbon_offset_kg': round(float(self.carbon_offset_kg or 0.0), 2),
            'reason': self.reason,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

class ULBDiversionStat(db.Model):
    __tablename__ = 'ulb_diversion_stats'
    id = db.Column(db.Integer, primary_key=True)
    ulb_name = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False, default='Chennai District')
    total_generated_tons = db.Column(db.Float, nullable=False, default=0.0)
    recovered_tons = db.Column(db.Float, nullable=False, default=0.0)
    landfilled_tons = db.Column(db.Float, nullable=False, default=0.0)
    diversion_rate_pct = db.Column(db.Float, nullable=False, default=0.0)
    baseline_diversion_pct = db.Column(db.Float, nullable=False, default=32.5) # Pre-system baseline
    segregation_compliance_pct = db.Column(db.Float, nullable=False, default=70.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'ulb_name': self.ulb_name,
            'district': self.district,
            'total_generated_tons': round(float(self.total_generated_tons or 0.0), 2),
            'recovered_tons': round(float(self.recovered_tons or 0.0), 2),
            'landfilled_tons': round(float(self.landfilled_tons or 0.0), 2),
            'diversion_rate_pct': round(float(self.diversion_rate_pct or 0.0), 2),
            'baseline_diversion_pct': round(float(self.baseline_diversion_pct or 32.5), 2),
            'segregation_compliance_pct': round(float(self.segregation_compliance_pct or 70.0), 2),
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }
