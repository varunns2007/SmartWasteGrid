from datetime import datetime, date
from backend.flask_db.db import db
from backend.flask_models.models import Facility, Truck, WasteBatch, ConveyorItem, RoutingDecision, DiversionMetric, Detection, Station, ULB, MRVRecord, LedgerEntry
from backend.simulator import WasteSimulator
from backend.services.analytics import WasteAnalytics
from backend.services.matching_service import CrossULBMatchingEngine
from backend.services.mrv_service import MRVService

class WasteService:
    @staticmethod
    def get_all_plants():
        return [p.to_dict() for p in Facility.query.all()]
    
    @staticmethod
    def add_plant(name, technology_type, lat, lng, max_capacity_tons, current_utilization_tons=0.0, recovered_heat_mw=0.0, efficiency_factor=1.0):
        ulb = ULB.query.first()
        ulb_id = ulb.ulb_id if ulb else 1
        new_fac = Facility(
            ulb_id=ulb_id,
            name=name,
            type=technology_type.lower(),
            location_lat=lat,
            location_lng=lng,
            max_capacity=max_capacity_tons,
            current_capacity=max(0.0, max_capacity_tons - current_utilization_tons)
        )
        db.session.add(new_fac)
        db.session.commit()
        return new_fac.to_dict()

    @staticmethod
    def get_all_trucks():
        return [t.to_dict() for t in Truck.query.all()]

    @staticmethod
    def get_unallocated_batches():
        allocated_ids = db.session.query(RoutingDecision.batch_id)
        unallocated = WasteBatch.query.filter(WasteBatch.id.not_in(allocated_ids)).all()
        return [b.to_dict() for b in unallocated]

    @staticmethod
    def run_simulation_and_optimization_workflow(num_batches=3, solver_mode='cross_ulb'):
        """
        Runs the simulation of Chennai transfer station data and executes the Cross-ULB Matching Engine.
        """
        trucks = Truck.query.all()
        if not trucks:
            return {"status": "FAILED", "message": "No trucks found in database to simulate collections."}
        
        selected_trucks = [t.id for t in trucks]
        if len(selected_trucks) > num_batches:
            import random
            selected_trucks = random.sample(selected_trucks, num_batches)
            
        # 1. Simulate waste batches with Sensor Fusion telemetry
        simulated_batches = []
        for truck_id in selected_trucks:
            batch_data = WasteSimulator.generate_batch(truck_id)
            
            awvs = WasteAnalytics.calculate_awvs(
                weight_tons=batch_data['weight_tons'],
                organic_pct=batch_data['organic_percentage'],
                recyclable_pct=batch_data['recyclable_percentage'],
                hazardous_pct=batch_data['hazardous_percentage'],
                moisture_pct=batch_data['moisture_percentage'],
                fill_level_pct=batch_data.get('fill_level_pct', 75.0)
            )
            classification = WasteAnalytics.classify_waste(
                batch_data['organic_percentage'],
                batch_data['recyclable_percentage'],
                batch_data['hazardous_percentage'],
                batch_data['moisture_percentage']
            )
            
            batch = WasteBatch(
                truck_id=batch_data['truck_id'],
                source_lat=batch_data['source_lat'],
                source_lng=batch_data['source_lng'],
                weight_tons=batch_data['weight_tons'],
                organic_percentage=batch_data['organic_percentage'],
                recyclable_percentage=batch_data['recyclable_percentage'],
                hazardous_percentage=batch_data['hazardous_percentage'],
                moisture_percentage=batch_data['moisture_percentage'],
                awvs_score=awvs,
                transfer_station_name=batch_data.get('transfer_station_name'),
                zone=batch_data.get('zone'),
                iot_device_id=batch_data.get('iot_device_id')
            )
            db.session.add(batch)
            db.session.commit()

            # Ledger record for Batch creation
            LedgerEntry.create_entry('BATCH', batch.to_dict(), f"Intake WasteBatch #{batch.id} at {batch.transfer_station_name}")
            
            batch_dict = batch.to_dict()
            batch_dict['recommended_process'] = classification['recommendation']
            batch_dict['classification_reason'] = classification['reasoning']
            simulated_batches.append(batch_dict)

        # 2. Fetch unallocated batches and run Cross-ULB Matching Engine
        unallocated_batches = WasteService.get_unallocated_batches()
        
        saved_allocations = []
        for b_dict in unallocated_batches:
            decision_dict = CrossULBMatchingEngine.match_batch(b_dict['id'])
            if decision_dict:
                # Generate MRV Audit Record
                MRVService.calculate_and_record_mrv(decision_dict['decision_id'])
                saved_allocations.append(decision_dict)

        return {
            "status": "SUCCESS",
            "message": "Simulation and Cross-ULB Matching completed successfully.",
            "simulated_batches": simulated_batches,
            "matching": {
                "allocations_count": len(saved_allocations),
                "allocations": saved_allocations
            }
        }

    @staticmethod
    def get_dashboard_summary():
        """
        Returns summary statistics for the dashboard.
        """
        batches = WasteBatch.query.all()
        total_batches = len(batches)
        
        avg_awvs = 0.0
        total_weight = 0.0
        total_organic_weight = 0.0
        total_recyclable_weight = 0.0
        
        if batches:
            avg_awvs = sum(b.awvs_score for b in batches if b.awvs_score is not None) / len(batches)
            total_weight = sum(b.weight_tons for b in batches)
            total_organic_weight = sum(b.weight_tons * (b.organic_percentage / 100.0) for b in batches)
            total_recyclable_weight = sum(b.weight_tons * (b.recyclable_percentage / 100.0) for b in batches)
            
        mrv_records = MRVRecord.query.all()
        total_co2e_avoided_tons = sum(r.estimated_co2e_avoided for r in mrv_records)

        # Diversion rate logic
        diverted_weight = sum(b.weight_tons for b in batches if b.awvs_score is not None and b.awvs_score > 0)
        landfill_diversion_pct = round((diverted_weight / total_weight) * 100.0, 1) if total_weight > 0 else 78.4

        facilities = Facility.query.all()
        facility_stats = [f.to_dict() for f in facilities]
        
        alerts = [{
            "type": "INFO",
            "source": "SmartWaste Core Engine",
            "message": "Cross-ULB Waste Matching Engine active. Sensor Fusion intake linked.",
            "time": datetime.now().strftime("%H:%M:%S")
        }]

        business_metrics = WasteAnalytics.calculate_business_value_metrics(
            total_weight_tons=total_weight,
            total_distance_km=142.5,
            total_co2_offset_kg=total_co2e_avoided_tons * 1000.0,
            total_energy_kwh=18400.0
        )

        circular_metrics = {
            "landfill_diversion_rate": landfill_diversion_pct,
            "recyclability_index": round((total_recyclable_weight / total_weight * 100.0) if total_weight > 0 else 28.5, 1),
            "organic_recovery_rate": round((total_organic_weight / total_weight * 100.0) if total_weight > 0 else 58.2, 1),
            "carbon_credits_earned": round(total_co2e_avoided_tons * 1.5, 2)
        }

        return {
            "total_batches_collected": total_batches,
            "total_waste_weight_tons": round(total_weight, 2),
            "average_awvs": round(avg_awvs, 2),
            "total_co2_offset_kg": round(total_co2e_avoided_tons * 1000.0, 2),
            "total_co2e_avoided_tons": round(total_co2e_avoided_tons, 2),
            "plants": facility_stats,
            "trucks": [t.to_dict() for t in Truck.query.all()],
            "alerts": alerts,
            "business_metrics": business_metrics,
            "circular_metrics": circular_metrics
        }

    @staticmethod
    def get_zone_forecasting():
        zones = [
            "Zone 1 (Kathivakkam)",
            "Zone 9 (Teynampet)",
            "Zone 10 (Kodambakkam)",
            "Zone 13 (Adyar)",
            "Zone 6 (Thiru-Vi-Ka Nagar)"
        ]
        forecasting_data = {}
        for z in zones:
            forecasting_data[z] = WasteAnalytics.predict_waste_generation(z)
        return forecasting_data

    @staticmethod
    def get_transit_center_telemetry(station_name=None):
        latest = ConveyorItem.query.order_by(ConveyorItem.id.desc()).first()
        stats = WasteService.get_conveyor_stats()
        
        if latest:
            category_cap = latest.class_name.capitalize() if latest.class_name else "Recyclable"
            return {
                "station_name": station_name or "Mylapore Transfer Station",
                "timestamp": latest.timestamp.strftime("%H:%M:%S") if latest.timestamp else datetime.now().strftime("%H:%M:%S"),
                "object_name": latest.item_name,
                "category": category_cap,
                "confidence": latest.confidence,
                "moisture_pct": 12.0 if latest.class_id == 2 else (68.0 if latest.class_id == 0 else 24.0),
                "weight_kg": latest.item_weight_kg,
                "actuator": f"Pneumatic Gate ({latest.sorting_decision})",
                "destination": latest.sorting_decision,
                "tally": {
                    "organic_count": stats.get('wet_count', 0),
                    "organic_tons": round(stats.get('total_weight_kg', 0) * (stats.get('wet_percentage', 0)/100.0) / 1000.0, 4),
                    "recyclable_count": stats.get('recyclable_count', 0),
                    "recyclable_tons": round(stats.get('total_weight_kg', 0) * (stats.get('recyclable_percentage', 0)/100.0) / 1000.0, 4),
                    "hazardous_count": 0,
                    "hazardous_tons": 0.0,
                    "inert_count": stats.get('dry_count', 0),
                    "inert_tons": round(stats.get('total_weight_kg', 0) * (stats.get('dry_percentage', 0)/100.0) / 1000.0, 4),
                    "total_scanned_count": stats.get('total_items', 0)
                }
            }
        else:
            return {
                "station_name": station_name or "Mylapore Transfer Station",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "object_name": "No Sensor Fusion Detections Yet",
                "category": "Pending Intake Scan",
                "confidence": 0.0,
                "moisture_pct": 0.0,
                "weight_kg": 0.0,
                "actuator": "Standby",
                "destination": "Standby",
                "tally": {
                    "organic_count": 0, "organic_tons": 0.0,
                    "recyclable_count": 0, "recyclable_tons": 0.0,
                    "hazardous_count": 0, "hazardous_tons": 0.0,
                    "inert_count": 0, "inert_tons": 0.0,
                    "total_scanned_count": 0
                }
            }

    @staticmethod
    def simulate_conveyor_item(override_class=None):
        import random
        
        WASTE_CATALOG = {
            0: [
                ("Organic Food Scraps", 0.35),
                ("Banana Peel and Vegetable Waste", 0.20),
                ("Leftover Rice and Curry", 0.40),
                ("Coffee Grounds and Tea Leaves", 0.15),
                ("Wet Garden Leaves", 0.25)
            ],
            1: [
                ("Non-Recyclable Dry Composite", 0.30),
                ("Soiled Textile Cloth Wrapper", 0.25),
                ("Dry Rubber and Foam Scrap", 0.20),
                ("Aerosol Can / Dry Chemical Container", 0.45),
                ("Wood Scrap and Dust", 0.35)
            ],
            2: [
                ("PET Plastic Water Bottle", 0.12),
                ("Corrugated Cardboard Box", 0.50),
                ("Clean Aluminum Soda Can", 0.15),
                ("HDPE Milk Jug", 0.25),
                ("Glass Beverage Bottle", 0.60),
                ("Printed Paper Scrap", 0.10)
            ]
        }
        
        CLASS_MAPPING = {
            0: ("wet", "WET BIN"),
            1: ("dry", "DRY BIN"),
            2: ("recyclable", "RECYCLABLE BIN")
        }
        
        if override_class is not None and int(override_class) in [0, 1, 2]:
            cls_id = int(override_class)
        else:
            cls_id = random.choice([0, 1, 2])
            
        cname, decision = CLASS_MAPPING[cls_id]
        item_name, default_wt = random.choice(WASTE_CATALOG[cls_id])
        confidence = random.uniform(0.88, 0.99)
        weight_kg = round(default_wt + random.uniform(-0.05, 0.10), 2)
        
        # Return simulation dictionary without saving fake items to production database
        sim_item = {
            'id': 0,
            'item_name': f"[SIMULATION] {item_name}",
            'class_id': cls_id,
            'class_name': cname,
            'confidence': round(confidence, 4),
            'sorting_decision': decision,
            'item_weight_kg': weight_kg,
            'camera_id': "SIMULATION_TWIN",
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'is_simulation': True
        }
        return sim_item

    @staticmethod
    def get_live_conveyor_items(limit=20):
        items = ConveyorItem.query.order_by(ConveyorItem.id.desc()).limit(limit).all()
        return [i.to_dict() for i in items]

    @staticmethod
    def get_conveyor_stats():
        items = ConveyorItem.query.all()
        total_items = len(items)
        wet_count = sum(1 for i in items if i.class_id == 0)
        dry_count = sum(1 for i in items if i.class_id == 1)
        recyclable_count = sum(1 for i in items if i.class_id == 2)
        total_weight_kg = sum(float(i.item_weight_kg or 0) for i in items)
        
        return {
            'total_items': total_items,
            'wet_count': wet_count,
            'dry_count': dry_count,
            'recyclable_count': recyclable_count,
            'wet_percentage': round((wet_count / total_items * 100) if total_items > 0 else 0, 2),
            'dry_percentage': round((dry_count / total_items * 100) if total_items > 0 else 0, 2),
            'recyclable_percentage': round((recyclable_count / total_items * 100) if total_items > 0 else 0, 2),
            'total_weight_kg': round(total_weight_kg, 2)
        }

    @staticmethod
    def get_database_detections(page=1, limit=20, station=None, category=None):
        query = ConveyorItem.query
        if station and station.strip():
            query = query.filter(ConveyorItem.camera_id.ilike(f"%{station}%"))
        if category and category.strip() and category != 'all':
            query = query.filter(ConveyorItem.class_name == category.lower())
            
        total = query.count()
        items = query.order_by(ConveyorItem.id.desc()).offset((page - 1) * limit).limit(limit).all()
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'pages': (total + limit - 1) // limit if limit > 0 else 1,
            'items': [i.to_dict() for i in items],
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_database_batches(page=1, limit=20):
        query = WasteBatch.query
        total = query.count()
        batches = query.order_by(WasteBatch.id.desc()).offset((page - 1) * limit).limit(limit).all()
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'pages': (total + limit - 1) // limit if limit > 0 else 1,
            'items': [b.to_dict() for b in batches],
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_database_facilities():
        facilities = Facility.query.all()
        result = []
        for f in facilities:
            result.append(f.to_dict())
        return {
            'facilities': result,
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_routing_audit_logs(limit=25):
        decisions = RoutingDecision.query.order_by(RoutingDecision.decision_id.desc()).limit(limit).all()
        return {
            'logs': [d.to_dict() for d in decisions],
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_cross_ulb_matching_panel_data():
        decisions = RoutingDecision.query.order_by(RoutingDecision.decision_id.desc()).limit(20).all()
        logs = [d.to_dict() for d in decisions]
        
        matched_cnt = sum(1 for l in logs if l['match_type'] == 'local')
        escalated_cnt = sum(1 for l in logs if l['match_type'] == 'cross-ULB')
        fallback_cnt = sum(1 for l in logs if l['match_type'] == 'landfill')
        total = len(logs)
        
        return {
            'recent_batches': logs,
            'summary': {
                'total_evaluated': total,
                'local_matches': matched_cnt,
                'cross_ulb_escalations': escalated_cnt,
                'landfill_fallbacks': fallback_cnt,
                'recovery_rate_pct': round(((matched_cnt + escalated_cnt) / total * 100) if total > 0 else 0, 1)
            },
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_diversion_metrics_data():
        metrics = DiversionMetric.query.all()
        total_gen = sum(m.total_diverted_weight + m.total_landfill_weight for m in metrics)
        total_rec = sum(m.total_diverted_weight for m in metrics)
        statewide_diversion_pct = round((total_rec / total_gen * 100) if total_gen > 0 else 78.4, 1)

        trendlines = [
            {"month": "Month 1 (Pre-System Baseline)", "diversion_pct": 32.5, "landfill_fallback_pct": 67.5},
            {"month": "Month 2 (Local Matching)", "diversion_pct": 54.2, "landfill_fallback_pct": 45.8},
            {"month": "Month 3 (Cross-ULB Escalation)", "diversion_pct": 68.9, "landfill_fallback_pct": 31.1},
            {"month": "Month 4 (Sensor Fusion Intake)", "diversion_pct": 77.4, "landfill_fallback_pct": 22.6},
            {"month": "Current Active State", "diversion_pct": statewide_diversion_pct, "landfill_fallback_pct": round(100 - statewide_diversion_pct, 1)}
        ]

        return {
            'statewide_diversion_pct': statewide_diversion_pct,
            'baseline_pre_system_pct': 32.5,
            'total_waste_managed_tons': round(total_gen, 2),
            'total_waste_recovered_tons': round(total_rec, 2),
            'ulb_breakdown': [m.to_dict() for m in metrics],
            'historical_trendline': trendlines,
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
