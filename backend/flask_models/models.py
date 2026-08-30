from datetime import datetime
import hashlib
import json
from backend.flask_db.db import db

class ULB(db.Model):
    __tablename__ = 'ulbs'
    ulb_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False, default='Corporation') # Corporation, Municipality, Town Panchayat
    district = db.Column(db.String(100), nullable=False, default='Chennai')

    stations = db.relationship('Station', backref='ulb', lazy=True)
    wards = db.relationship('Ward', backref='ulb', lazy=True)
    facilities = db.relationship('Facility', backref='ulb', lazy=True)
    batches = db.relationship('WasteBatch', backref='ulb', lazy=True)

    def to_dict(self):
        return {
            'ulb_id': self.ulb_id,
            'name': self.name,
            'type': self.type,
            'district': self.district
        }

class Station(db.Model):
    __tablename__ = 'stations'
    station_id = db.Column(db.Integer, primary_key=True)
    ulb_id = db.Column(db.Integer, db.ForeignKey('ulbs.ulb_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    location_lat = db.Column(db.Float, nullable=False, default=13.0368)
    location_lng = db.Column(db.Float, nullable=False, default=80.2676)

    detections = db.relationship('Detection', backref='station', lazy=True)
    batches = db.relationship('WasteBatch', backref='station', lazy=True)

    def to_dict(self):
        return {
            'station_id': self.station_id,
            'ulb_id': self.ulb_id,
            'ulb_name': self.ulb.name if self.ulb else 'Unknown ULB',
            'name': self.name,
            'location_lat': self.location_lat,
            'location_lng': self.location_lng
        }

class Ward(db.Model):
    __tablename__ = 'wards'
    ward_id = db.Column(db.Integer, primary_key=True)
    ulb_id = db.Column(db.Integer, db.ForeignKey('ulbs.ulb_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    compliance_score = db.Column(db.Float, default=78.5)

    def to_dict(self):
        return {
            'ward_id': self.ward_id,
            'ulb_id': self.ulb_id,
            'ulb_name': self.ulb.name if self.ulb else 'Unknown ULB',
            'name': self.name,
            'compliance_score': self.compliance_score
        }

class Facility(db.Model):
    __tablename__ = 'facilities'
    facility_id = db.Column(db.Integer, primary_key=True)
    ulb_id = db.Column(db.Integer, db.ForeignKey('ulbs.ulb_id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # compost, biomethanation, MRF, RDF, Waste-to-Energy
    current_capacity = db.Column(db.Float, nullable=False, default=100.0) # remaining tons
    max_capacity = db.Column(db.Float, nullable=False, default=200.0)
    location_lat = db.Column(db.Float, nullable=False, default=13.04)
    location_lng = db.Column(db.Float, nullable=False, default=80.22)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    routing_decisions = db.relationship('RoutingDecision', backref='facility', lazy=True)

    def to_dict(self):
        return {
            'facility_id': self.facility_id,
            'ulb_id': self.ulb_id,
            'ulb_name': self.ulb.name if self.ulb else 'Unknown ULB',
            'name': self.name,
            'technology_type': self.type.capitalize() if self.type else 'Composting',
            'type': self.type,
            'current_capacity': round(float(self.current_capacity or 0.0), 2),
            'max_capacity': round(float(self.max_capacity or 0.0), 2),
            'capacity': round(float(self.max_capacity or 0.0), 2),
            'utilization': round(float(self.max_capacity - self.current_capacity), 2),
            'utilization_pct': round(((self.max_capacity - self.current_capacity) / self.max_capacity * 100) if self.max_capacity > 0 else 0, 1),
            'lat': self.location_lat,
            'lng': self.location_lng,
            'location_lat': self.location_lat,
            'location_lng': self.location_lng,
            'recovered_heat_mw': 2.4 if 'energy' in (self.type or '').lower() or 'wte' in (self.type or '').lower() else 0.0,
            'processing_cost_per_ton': 110.0,
            'queue_length': 1,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }

# Backwards compatibility alias Plant -> Facility
Plant = Facility

class Detection(db.Model):
    __tablename__ = 'detections'
    detection_id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'), nullable=False)
    class_name = db.Column(db.String(50), nullable=False) # Wet, Dry, Recyclable
    confidence = db.Column(db.Float, nullable=False, default=0.95)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    batch_id = db.Column(db.Integer, db.ForeignKey('waste_batches.id'), nullable=True)
    vehicle_id = db.Column(db.String(50), nullable=True) # Traceability metadata only

    def to_dict(self):
        return {
            'detection_id': self.detection_id,
            'station_id': self.station_id,
            'station_name': self.station.name if self.station else 'Mylapore TS',
            'class_name': self.class_name,
            'confidence': round(float(self.confidence or 0.95), 4),
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'batch_id': self.batch_id,
            'vehicle_id': self.vehicle_id or 'TN-01-AM-1042'
        }

# Backwards compatibility alias ConveyorItem -> Detection
class ConveyorItem(db.Model):
    __tablename__ = 'conveyor_items'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, nullable=False) # 0=wet, 1=dry, 2=recyclable
    class_name = db.Column(db.String(50), nullable=False) # wet, dry, recyclable
    confidence = db.Column(db.Float, nullable=False, default=0.95)
    sorting_decision = db.Column(db.String(50), nullable=False)
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

class WasteBatch(db.Model):
    __tablename__ = 'waste_batches'
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.station_id'), nullable=True)
    ulb_id = db.Column(db.Integer, db.ForeignKey('ulbs.ulb_id'), nullable=True)
    truck_id = db.Column(db.Integer, nullable=True) # Traceability metadata
    source_lat = db.Column(db.Float, nullable=False, default=13.04)
    source_lng = db.Column(db.Float, nullable=False, default=80.22)
    weight_tons = db.Column(db.Float, nullable=False, default=10.0)
    organic_percentage = db.Column(db.Float, nullable=False, default=60.0)
    recyclable_percentage = db.Column(db.Float, nullable=False, default=30.0)
    hazardous_percentage = db.Column(db.Float, nullable=False, default=10.0)
    moisture_percentage = db.Column(db.Float, nullable=False, default=45.0)
    awvs_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp_window = db.Column(db.String(100), nullable=True)
    
    # Telemetry Columns
    transfer_station_name = db.Column(db.String(100), nullable=True)
    zone = db.Column(db.String(100), nullable=True)
    iot_device_id = db.Column(db.String(50), nullable=True)

    routing_decisions = db.relationship('RoutingDecision', backref='batch', lazy=True)
    mrv_records = db.relationship('MRVRecord', backref='batch', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.id,
            'station_id': self.station_id,
            'ulb_id': self.ulb_id,
            'ulb_name': self.ulb.name if self.ulb else (self.transfer_station_name or 'GCC Zone 9 Teynampet'),
            'weight_tons': round(float(self.weight_tons or 0.0), 2),
            'organic_percentage': round(float(self.organic_percentage or 0.0), 1),
            'recyclable_percentage': round(float(self.recyclable_percentage or 0.0), 1),
            'hazardous_percentage': round(float(self.hazardous_percentage or 0.0), 1),
            'moisture_percentage': round(float(self.moisture_percentage or 0.0), 1),
            'awvs_score': round(float(self.awvs_score or 0.0), 2) if self.awvs_score is not None else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'timestamp_window': self.timestamp_window or (self.created_at.strftime('%Y-%m-%d 08:00-12:00') if self.created_at else '2026-08-30 08:00-12:00'),
            'transfer_station_name': self.transfer_station_name or 'Mylapore TS',
            'source_lat': self.source_lat,
            'source_lng': self.source_lng
        }

class Truck(db.Model):
    __tablename__ = 'trucks'
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    capacity_tons = db.Column(db.Float, nullable=False)
    current_load = db.Column(db.Float, default=0.0)
    assigned_plant_id = db.Column(db.Integer, nullable=True)
    route_status = db.Column(db.String(50), default='IDLE')
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)

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

class RoutingDecision(db.Model):
    __tablename__ = 'routing_decisions'
    decision_id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('waste_batches.id'), nullable=False)
    matched_facility_id = db.Column(db.Integer, db.ForeignKey('facilities.facility_id'), nullable=True) # Null = Landfill Fallback
    match_type = db.Column(db.String(50), nullable=False) # local, cross-ULB, landfill
    distance_or_cost_factor = db.Column(db.Float, default=0.0)
    reason = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    mrv_records = db.relationship('MRVRecord', backref='routing_decision', lazy=True)

    def to_dict(self):
        fac_name = self.facility.name if self.facility else "Landfill Fallback"
        return {
            'decision_id': self.decision_id,
            'id': self.decision_id,
            'batch_id': self.batch_id,
            'matched_facility_id': self.matched_facility_id,
            'matched_facility': fac_name,
            'source_ulb': self.batch.ulb.name if (self.batch and self.batch.ulb) else "GCC Zone 9 (Teynampet)",
            'match_type': self.match_type,
            'escalation_status': 'MATCHED' if self.match_type == 'local' else ('ESCALATED' if self.match_type == 'cross-ULB' else 'FALLBACK'),
            'distance_or_cost_factor': round(float(self.distance_or_cost_factor or 0.0), 2),
            'distance_km': round(float(self.distance_or_cost_factor or 0.0), 1),
            'cost_factor_inr': round(float((self.distance_or_cost_factor or 5.0) * 110.0), 2),
            'reason': self.reason,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

class DiversionMetric(db.Model):
    __tablename__ = 'diversion_metrics'
    id = db.Column(db.Integer, primary_key=True)
    ulb_id = db.Column(db.Integer, db.ForeignKey('ulbs.ulb_id'), nullable=False)
    district = db.Column(db.String(100), nullable=False, default='Chennai')
    period = db.Column(db.String(50), nullable=False, default='Current Month')
    diversion_rate = db.Column(db.Float, nullable=False, default=0.0) # Percentage 0-100
    total_diverted_weight = db.Column(db.Float, nullable=False, default=0.0)
    total_landfill_weight = db.Column(db.Float, nullable=False, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        total_gen = self.total_diverted_weight + self.total_landfill_weight
        return {
            'id': self.id,
            'ulb_id': self.ulb_id,
            'ulb_name': self.ulb.name if self.ulb else 'Unknown ULB',
            'district': self.district,
            'period': self.period,
            'diversion_rate': round(float(self.diversion_rate or 0.0), 1),
            'diversion_rate_pct': round(float(self.diversion_rate or 0.0), 1),
            'total_diverted_weight': round(float(self.total_diverted_weight or 0.0), 2),
            'total_landfill_weight': round(float(self.total_landfill_weight or 0.0), 2),
            'total_generated_weight': round(total_gen, 2),
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

# Backwards compatibility alias ULBDiversionStat
ULBDiversionStat = DiversionMetric

class MRVRecord(db.Model):
    __tablename__ = 'mrv_records'
    record_id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('waste_batches.id'), nullable=False)
    routing_decision_id = db.Column(db.Integer, db.ForeignKey('routing_decisions.decision_id'), nullable=False)
    estimated_co2e_avoided = db.Column(db.Float, nullable=False, default=0.0) # Tons CO2e
    calculation_method = db.Column(db.String(150), nullable=False, default='IPCC 2019 Methane Avoidance Factor vs Landfill Baseline')
    ledger_hash_reference = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'record_id': self.record_id,
            'batch_id': self.batch_id,
            'routing_decision_id': self.routing_decision_id,
            'estimated_co2e_avoided': round(float(self.estimated_co2e_avoided or 0.0), 3),
            'calculation_method': self.calculation_method,
            'ledger_hash_reference': self.ledger_hash_reference,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        }

class LedgerEntry(db.Model):
    __tablename__ = 'ledger_entries'
    entry_id = db.Column(db.Integer, primary_key=True)
    entry_type = db.Column(db.String(50), nullable=False) # DETECTION, BATCH, ROUTING, MRV_RECORD
    payload_hash = db.Column(db.String(64), nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    current_hash = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metadata_info = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'entry_id': self.entry_id,
            'entry_type': self.entry_type,
            'payload_hash': self.payload_hash,
            'previous_hash': self.previous_hash,
            'current_hash': self.current_hash,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'metadata_info': self.metadata_info
        }

    @staticmethod
    def create_entry(entry_type, payload_dict, metadata_info=''):
        last_entry = LedgerEntry.query.order_by(LedgerEntry.entry_id.desc()).first()
        prev_hash = last_entry.current_hash if last_entry else "0000000000000000000000000000000000000000000000000000000000000000"
        
        payload_str = json.dumps(payload_dict, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        
        combined_str = f"{prev_hash}{payload_hash}{datetime.utcnow().isoformat()}"
        current_hash = hashlib.sha256(combined_str.encode('utf-8')).hexdigest()
        
        entry = LedgerEntry(
            entry_type=entry_type,
            payload_hash=payload_hash,
            previous_hash=prev_hash,
            current_hash=current_hash,
            metadata_info=metadata_info
        )
        db.session.add(entry)
        db.session.commit()
        return entry
