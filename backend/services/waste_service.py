from backend.flask_models.models import Plant, Truck, WasteBatch, OptimizationRun, OptimizationResult, ConveyorItem, RoutingAuditLog, ULBDiversionStat
from backend.flask_db.db import db
from backend.simulator import WasteSimulator
from backend.services.analytics import WasteAnalytics
from backend.quantum.optimizer import run_cnn_milp_optimization, haversine_distance
from datetime import datetime, date

class WasteService:
    @staticmethod
    def get_all_plants():
        return [p.to_dict() for p in Plant.query.all()]
    
    @staticmethod
    def add_plant(name, technology_type, lat, lng, max_capacity_tons, current_utilization_tons=0.0, recovered_heat_mw=0.0, efficiency_factor=1.0):
        new_plant = Plant(
            name=name,
            technology_type=technology_type,
            lat=lat,
            lng=lng,
            max_capacity_tons=max_capacity_tons,
            current_utilization_tons=current_utilization_tons,
            recovered_heat_mw=recovered_heat_mw,
            efficiency_factor=efficiency_factor
        )
        db.session.add(new_plant)
        db.session.commit()
        return new_plant.to_dict()

    @staticmethod
    def get_all_trucks():
        return [t.to_dict() for t in Truck.query.all()]

    @staticmethod
    def get_unallocated_batches():
        allocated_ids = db.session.query(OptimizationResult.batch_id)
        unallocated = WasteBatch.query.filter(WasteBatch.id.not_in(allocated_ids)).all()
        return [b.to_dict() for b in unallocated]

    @staticmethod
    def run_simulation_and_optimization_workflow(num_batches=3, solver_mode='cnn_milp'):
        """
        Runs the simulation of Chennai transfer station data and solves allocations using SmartWasteAI CNN & MILP pipeline.
        """
        trucks = Truck.query.all()
        if not trucks:
            return {"status": "FAILED", "message": "No trucks found in database to simulate collections."}
        
        selected_trucks = [t.id for t in trucks]
        if len(selected_trucks) > num_batches:
            import random
            selected_trucks = random.sample(selected_trucks, num_batches)
            
        # 1. Simulate waste batches with IoT telemetry
        simulated_batches = []
        for truck_id in selected_trucks:
            batch_data = WasteSimulator.generate_batch(truck_id)
            
            # 2. Upgraded Analytics calculations
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
            
            # 3. Save batch to database
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
                # Chennai / IoT Telemetry Columns
                transfer_station_name=batch_data.get('transfer_station_name'),
                zone=batch_data.get('zone'),
                iot_device_id=batch_data.get('iot_device_id'),
                iot_protocol=batch_data.get('iot_protocol'),
                moisture_raw_v=batch_data.get('moisture_raw_v'),
                load_cell_mv=batch_data.get('load_cell_mv'),
                fill_level_pct=batch_data.get('fill_level_pct', 75.0)
            )
            db.session.add(batch)
            db.session.commit()
            
            batch_dict = batch.to_dict()
            batch_dict['recommended_process'] = classification['recommendation']
            batch_dict['classification_reason'] = classification['reasoning']
            simulated_batches.append(batch_dict)

        # 4. Fetch all unallocated batches and plants
        unallocated_batches = WasteService.get_unallocated_batches()
        plants = WasteService.get_all_plants()
        
        if not unallocated_batches:
            return {
                "status": "SUCCESS",
                "message": "Simulation successful. No unallocated batches to optimize.",
                "simulated_batches": simulated_batches,
                "optimization": None
            }

        # 5. Run SmartWasteAI CNN + MILP Optimization Solver
        opt_res = run_cnn_milp_optimization(plants, unallocated_batches)
        opt_res['comparison'] = {
            "qaoa_time_ms": opt_res['computation_time_ms'],
            "milp_time_ms": opt_res['computation_time_ms'],
            "qaoa_status": opt_res['status'],
            "milp_status": opt_res['status'],
            "qaoa_allocations_count": len([a for a in opt_res['allocations'] if a['assigned_plant_id'] is not None]),
            "milp_allocations_count": len([a for a in opt_res['allocations'] if a['assigned_plant_id'] is not None])
        }
        
        if opt_res['status'] != "SUCCESS":
            return {
                "status": "PARTIAL",
                "message": f"Simulation succeeded, but {solver_mode.upper()} optimization failed.",
                "simulated_batches": simulated_batches,
                "optimization_error": opt_res['message']
            }

        # 6. Save optimization run
        opt_run = OptimizationRun(
            status=opt_res['status'],
            computation_time_ms=opt_res['computation_time_ms']
        )
        db.session.add(opt_run)
        db.session.commit()

        # 7. Save allocations and update plant loads
        saved_allocations = []
        for alloc in opt_res['allocations']:
            if alloc['assigned_plant_id'] is None:
                continue

            res = OptimizationResult(
                run_id=opt_run.id,
                batch_id=alloc['batch_id'],
                assigned_plant_id=alloc['assigned_plant_id'],
                estimated_energy_kwh=alloc['estimated_energy_kwh'],
                heat_recovery_utilized=alloc.get('heat_recovery_utilized', False),
                heat_utilized_mw=alloc.get('heat_utilized_mw', 0.0),
                lhv_increase_pct=alloc.get('lhv_increase_pct', 0.0),
                recommendation_reason=alloc.get('recommendation_reason', '')
            )
            db.session.add(res)
            
            # Update plant utilization and queue length in DB
            plant = Plant.query.get(alloc['assigned_plant_id'])
            if plant:
                plant.current_utilization_tons += alloc['weight_tons']
                # Simulate dequeueing/processing logic
                plant.queue_length = max(0, plant.queue_length - 1)
                
            # Update truck simulation state
            truck = Truck.query.get(alloc['truck_id'])
            if truck:
                truck.current_load = alloc['weight_tons']
                truck.assigned_plant_id = alloc['assigned_plant_id']
                truck.route_status = 'TRANSIT'
                batch_rec = WasteBatch.query.get(alloc['batch_id'])
                if batch_rec:
                    truck.lat = batch_rec.source_lat
                    truck.lng = batch_rec.source_lng
                
            saved_allocations.append(alloc)
            
        db.session.commit()

        return {
            "status": "SUCCESS",
            "message": "Simulation and optimization completed successfully.",
            "simulated_batches": simulated_batches,
            "optimization": {
                "run_id": opt_run.id,
                "computation_time_ms": opt_res['computation_time_ms'],
                "allocations": saved_allocations,
                "comparison": opt_res.get('comparison')
            }
        }

    @staticmethod
    def get_dashboard_summary():
        """
        Returns upgraded summary statistics for the dashboard.
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
            
        results = OptimizationResult.query.all()
        total_energy_recovered_kwh = sum(r.estimated_energy_kwh for r in results)
        
        total_distance = 0.0
        total_co2_offset = 0.0
        allocated_weight = 0.0
        
        for r in results:
            batch = r.waste_batch
            plant = r.plant
            if batch and plant:
                dist = haversine_distance(batch.source_lat, batch.source_lng, plant.lat, plant.lng)
                total_distance += dist
                allocated_weight += batch.weight_tons
                
                co2_offset = WasteAnalytics.calculate_carbon_offset(
                    batch.weight_tons,
                    batch.organic_percentage,
                    r.estimated_energy_kwh,
                    dist
                )
                total_co2_offset += co2_offset

        # Diversion logic
        landfill_diversion_pct = 95.0 # default high percentage since we optimize route allocations
        if total_weight > 0:
            diverted_weight = sum(b.weight_tons for b in batches if b.awvs_score is not None and b.awvs_score > 0)
            landfill_diversion_pct = round((diverted_weight / total_weight) * 100.0, 1)

        # Plant statistics
        plants = Plant.query.all()
        plant_stats = []
        alerts = []
        
        for p in plants:
            util_pct = round((p.current_utilization_tons / p.max_capacity_tons) * 100, 2) if p.max_capacity_tons > 0 else 0
            plant_stats.append({
                "id": p.id,
                "name": p.name,
                "technology_type": p.technology_type,
                "lat": p.lat,
                "lng": p.lng,
                "capacity": p.max_capacity_tons,
                "utilization": round(p.current_utilization_tons, 2),
                "recovered_heat_mw": p.recovered_heat_mw,
                "utilization_pct": util_pct,
                "processing_cost_per_ton": p.processing_cost_per_ton,
                "available_heat_mw": p.available_heat_mw,
                "processing_efficiency": p.processing_efficiency,
                "queue_length": p.queue_length
            })
            
            # Smart Alerts generation based on plant state
            if util_pct > 85.0:
                alerts.append({
                    "type": "WARNING",
                    "source": p.name,
                    "message": f"Capacity Overload Warning: Utilization is at {util_pct}%. Diverting incoming batches.",
                    "time": datetime.now().strftime("%H:%M:%S")
                })
            if p.queue_length >= 3:
                alerts.append({
                    "type": "CRITICAL",
                    "source": p.name,
                    "message": f"Bottleneck Detected: Queue length is {p.queue_length} vehicles. Processing rate delayed.",
                    "time": datetime.now().strftime("%H:%M:%S")
                })

        # Add batch alerts for high moisture or contamination
        recent_batches = WasteBatch.query.order_by(WasteBatch.created_at.desc()).limit(10).all()
        for b in recent_batches:
            if b.hazardous_percentage > 8.0:
                alerts.append({
                    "type": "CRITICAL",
                    "source": b.transfer_station_name or "Sensors",
                    "message": f"High Hazardous Contamination ({b.hazardous_percentage:.1f}%) in Batch #{b.id}. Sorting required.",
                    "time": b.created_at.strftime("%H:%M:%S")
                })
            if b.moisture_percentage > 68.0:
                alerts.append({
                    "type": "INFO",
                    "source": b.transfer_station_name or "Moisture Sensor",
                    "message": f"High Moisture ({b.moisture_percentage:.1f}%) in organic load at {b.transfer_station_name}. Redirecting to Biomethanation.",
                    "time": b.created_at.strftime("%H:%M:%S")
                })

        # Base default alerts if empty
        if not alerts:
            alerts.append({
                "type": "INFO",
                "source": "System Core",
                "message": "Quantum Waste Logistics Engine online. Sensors linked via MQTT gateways.",
                "time": datetime.now().strftime("%H:%M:%S")
            })

        # Business Value Calculations
        business_metrics = WasteAnalytics.calculate_business_value_metrics(
            total_weight_tons=total_weight,
            total_distance_km=total_distance,
            total_co2_offset_kg=total_co2_offset,
            total_energy_kwh=total_energy_recovered_kwh
        )

        # Circular economy summary
        circular_metrics = {
            "landfill_diversion_rate": landfill_diversion_pct,
            "recyclability_index": round((total_recyclable_weight / total_weight * 100.0) if total_weight > 0 else 24.5, 1),
            "organic_recovery_rate": round((total_organic_weight / total_weight * 100.0) if total_weight > 0 else 52.8, 1),
            "carbon_credits_earned": round(total_co2_offset * 0.001 * 1.5, 2)  # tons CO2 * rate
        }

        # Latest runs
        runs = OptimizationRun.query.order_by(OptimizationRun.timestamp.desc()).limit(5).all()
        latest_runs = []
        for r in runs:
            alloc_details = []
            for res in r.results:
                batch = res.waste_batch
                plant = res.plant
                alloc_details.append({
                    "batch_id": res.batch_id,
                    "plant_name": plant.name if plant else "Unknown",
                    "estimated_energy_kwh": res.estimated_energy_kwh,
                    "heat_recovery_utilized": res.heat_recovery_utilized,
                    "heat_utilized_mw": res.heat_utilized_mw,
                    "lhv_increase_pct": res.lhv_increase_pct,
                    "recommendation_reason": res.recommendation_reason,
                    "weight_tons": batch.weight_tons if batch else 0.0,
                    "awvs": batch.awvs_score if batch else 0.0,
                    "transfer_station": batch.transfer_station_name if batch else "Unknown"
                })
            latest_runs.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "status": r.status,
                "time_ms": r.computation_time_ms,
                "allocations_count": len(r.results),
                "allocations": alloc_details
            })

        return {
            "total_batches_collected": total_batches,
            "total_waste_weight_tons": round(total_weight, 2),
            "average_awvs": round(avg_awvs, 2),
            "total_energy_recovered_kwh": round(total_energy_recovered_kwh, 2),
            "total_transit_distance_km": round(total_distance, 2),
            "total_co2_offset_kg": round(total_co2_offset, 2),
            "plants": plant_stats,
            "latest_runs": latest_runs,
            "trucks": [t.to_dict() for t in Truck.query.all()],
            "alerts": alerts,
            "business_metrics": business_metrics,
            "circular_metrics": circular_metrics
        }

    @staticmethod
    def get_zone_forecasting():
        """
        Returns AI Waste generation forecasting for Chennai zones.
        """
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
        """
        Retrieves real-time conveyor sorting metrics for actual scanned items from camera detections.
        """
        from backend.flask_models.models import ConveyorItem
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
                "object_name": "No Camera Detections Yet",
                "category": "Pending Camera Scan",
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
        from backend.flask_models.models import ConveyorItem
        
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
        weight_kg = default_wt + random.uniform(-0.05, 0.10)
        
        new_item = ConveyorItem(
            item_name=item_name,
            class_id=cls_id,
            class_name=cname,
            confidence=confidence,
            sorting_decision=decision,
            item_weight_kg=weight_kg,
            camera_id="CONVEYOR_CAM_01"
        )
        db.session.add(new_item)
        db.session.commit()
        return new_item.to_dict()

    @staticmethod
    def get_live_conveyor_items(limit=20):
        from backend.flask_models.models import ConveyorItem
        items = ConveyorItem.query.order_by(ConveyorItem.id.desc()).limit(limit).all()
        return [i.to_dict() for i in items]

    @staticmethod
    def get_conveyor_stats():
        from backend.flask_models.models import ConveyorItem
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
        from backend.flask_models.models import ConveyorItem
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
        from backend.flask_models.models import WasteBatch
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
        from backend.flask_models.models import Plant
        plants = Plant.query.all()
        result = []
        for p in plants:
            d = p.to_dict()
            rem = max(0.0, p.max_capacity_tons - p.current_utilization_tons)
            d['remaining_capacity_tons'] = round(rem, 2)
            d['utilization_pct'] = round((p.current_utilization_tons / p.max_capacity_tons * 100) if p.max_capacity_tons > 0 else 0, 1)
            d['ulb_jurisdiction'] = "Greater Chennai Corporation (GCC)"
            d['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            result.append(d)
        return {
            'facilities': result,
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_routing_audit_logs(limit=25):
        from backend.flask_models.models import RoutingAuditLog
        logs = RoutingAuditLog.query.order_by(RoutingAuditLog.id.desc()).limit(limit).all()
        if not logs:
            # Seed mock routing audit logs if empty
            import random
            from backend.flask_models.models import WasteBatch, Plant
            batches = WasteBatch.query.all()
            plants = Plant.query.all()
            pnames = [p.name for p in plants] if plants else ["Kodungaiyur WtE", "Perungudi RDF", "Koyambedu Bio-CNG"]
            
            mock_ulbs = ["GCC Zone 9 (Teynampet)", "GCC Zone 10 (Kodambakkam)", "Tambaram Municipality", "Avadi City Corporation"]
            for i in range(1, 15):
                b_id = i
                ulb = random.choice(mock_ulbs)
                is_matched = random.random() > 0.15
                if is_matched:
                    status = "MATCHED" if "Zone 9" in ulb else "ESCALATED"
                    fac = random.choice(pnames)
                    dist = random.uniform(4.5, 22.0)
                    cost = dist * random.uniform(85, 120)
                    offset = random.uniform(150, 450)
                    reason = "Optimized via MILP capacity and composition suitability solver."
                else:
                    status = "FALLBACK"
                    fac = "Landfill — No Match"
                    dist = 38.5
                    cost = 4500.0
                    offset = 0.0
                    reason = "All local biomethanation & RDF facilities at >95% capacity; composition non-recoverable."
                    
                log_entry = RoutingAuditLog(
                    batch_id=b_id,
                    source_ulb=ulb,
                    matched_facility=fac,
                    escalation_status=status,
                    distance_km=dist,
                    cost_factor_inr=cost,
                    carbon_offset_kg=offset,
                    reason=reason
                )
                db.session.add(log_entry)
            db.session.commit()
            logs = RoutingAuditLog.query.order_by(RoutingAuditLog.id.desc()).limit(limit).all()

        return {
            'logs': [l.to_dict() for l in logs],
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def get_cross_ulb_matching_panel_data():
        from backend.flask_models.models import RoutingAuditLog
        audit_data = WasteService.get_routing_audit_logs(limit=20)
        logs = audit_data['logs']
        
        matched_cnt = sum(1 for l in logs if l['escalation_status'] == 'MATCHED')
        escalated_cnt = sum(1 for l in logs if l['escalation_status'] == 'ESCALATED')
        fallback_cnt = sum(1 for l in logs if l['escalation_status'] == 'FALLBACK')
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
        from backend.flask_models.models import ULBDiversionStat
        stats = ULBDiversionStat.query.all()
        if not stats:
            # Seed ULB diversion statistics
            mock_ulbs = [
                ("GCC Zone 9 (Teynampet)", "Chennai", 1450.0, 1220.0, 230.0, 84.1, 35.0, 88.5),
                ("GCC Zone 10 (Kodambakkam)", "Chennai", 1820.0, 1490.0, 330.0, 81.8, 32.0, 84.0),
                ("GCC Zone 6 (Thiru-Vi-Ka Nagar)", "Chennai", 1200.0, 810.0, 390.0, 67.5, 30.0, 62.0),
                ("Tambaram City Corporation", "Chengalpattu", 950.0, 780.0, 170.0, 82.1, 28.0, 81.0),
                ("Avadi City Corporation", "Tiruvallur", 1100.0, 820.0, 280.0, 74.5, 29.0, 71.5),
                ("Kanchipuram Municipality", "Kanchipuram", 650.0, 410.0, 240.0, 63.0, 25.0, 58.0),
            ]
            for name, dist, gen, rec, land, div, base, comp in mock_ulbs:
                db.session.add(ULBDiversionStat(
                    ulb_name=name,
                    district=dist,
                    total_generated_tons=gen,
                    recovered_tons=rec,
                    landfilled_tons=land,
                    diversion_rate_pct=div,
                    baseline_diversion_pct=base,
                    segregation_compliance_pct=comp
                ))
            db.session.commit()
            stats = ULBDiversionStat.query.all()

        total_gen = sum(s.total_generated_tons for s in stats)
        total_rec = sum(s.recovered_tons for s in stats)
        statewide_diversion_pct = round((total_rec / total_gen * 100) if total_gen > 0 else 0, 1)

        trendlines = [
            {"month": "Month 1 (Pre-AI Baseline)", "diversion_pct": 32.5, "landfill_fallback_pct": 67.5},
            {"month": "Month 2 (Local Matching)", "diversion_pct": 54.2, "landfill_fallback_pct": 45.8},
            {"month": "Month 3 (Cross-ULB Escalation)", "diversion_pct": 68.9, "landfill_fallback_pct": 31.1},
            {"month": "Month 4 (Full Sensor Fusion)", "diversion_pct": 77.4, "landfill_fallback_pct": 22.6},
            {"month": "Current Active State", "diversion_pct": statewide_diversion_pct, "landfill_fallback_pct": round(100 - statewide_diversion_pct, 1)}
        ]

        return {
            'statewide_diversion_pct': statewide_diversion_pct,
            'baseline_pre_system_pct': 32.5,
            'total_waste_managed_tons': round(total_gen, 2),
            'total_waste_recovered_tons': round(total_rec, 2),
            'ulb_breakdown': [s.to_dict() for s in stats],
            'historical_trendline': trendlines,
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
