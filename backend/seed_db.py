import random
from datetime import datetime, timedelta
from backend.flask_db.db import db
from backend.flask_models.models import ULB, Station, Ward, Facility, Truck, WasteBatch, ConveyorItem, RoutingDecision, DiversionMetric, MRVRecord, LedgerEntry
from backend.services.matching_service import CrossULBMatchingEngine
from backend.services.mrv_service import MRVService

def seed_data_if_empty(app=None):
    if app:
        with app.app_context():
            _do_seed()
    else:
        _do_seed()

def _do_seed():
    db.drop_all()
    db.create_all()

    # Seed ULBs
    if ULB.query.count() == 0:
        ulbs = [
            ULB(ulb_id=1, name="GCC Zone 9 (Teynampet)", type="Corporation", district="Chennai"),
            ULB(ulb_id=2, name="GCC Zone 10 (Kodambakkam)", type="Corporation", district="Chennai"),
            ULB(ulb_id=3, name="Tambaram City Corporation", type="Corporation", district="Chengalpattu"),
            ULB(ulb_id=4, name="Avadi City Corporation", type="Corporation", district="Tiruvallur"),
            ULB(ulb_id=5, name="Kanchipuram Municipality", type="Municipality", district="Kanchipuram")
        ]
        db.session.bulk_save_objects(ulbs)
        db.session.commit()

    # Seed Stations
    if Station.query.count() == 0:
        stations = [
            Station(station_id=1, ulb_id=1, name="Mylapore Transfer Station", location_lat=13.0368, location_lng=80.2676),
            Station(station_id=2, ulb_id=1, name="T. Nagar Collection Hub", location_lat=13.0418, location_lng=80.2341),
            Station(station_id=3, ulb_id=1, name="Adyar Transfer Hub", location_lat=12.9985, location_lng=80.2565),
            Station(station_id=4, ulb_id=2, name="Kodambakkam Station Queue", location_lat=13.0500, location_lng=80.2120),
            Station(station_id=5, ulb_id=3, name="Tambaram Central Queue", location_lat=12.9249, location_lng=80.1000),
            Station(station_id=6, ulb_id=4, name="Avadi West Station", location_lat=13.1147, location_lng=80.1098)
        ]
        db.session.bulk_save_objects(stations)
        db.session.commit()

    # Seed Wards for Compliance Heatmap
    if Ward.query.count() == 0:
        wards = [
            Ward(ward_id=114, ulb_id=1, name="Ward 114 (Teynampet North)", compliance_score=84.5),
            Ward(ward_id=115, ulb_id=1, name="Ward 115 (Mylapore Beach Road)", compliance_score=91.2),
            Ward(ward_id=116, ulb_id=1, name="Ward 116 (Royapettah East)", compliance_score=76.8),
            Ward(ward_id=121, ulb_id=2, name="Ward 121 (Kodambakkam Market)", compliance_score=68.4),
            Ward(ward_id=122, ulb_id=2, name="Ward 122 (Vadapalani Hub)", compliance_score=82.0),
            Ward(ward_id=150, ulb_id=3, name="Ward 150 (Tambaram Railway Area)", compliance_score=79.5),
        ]
        db.session.bulk_save_objects(wards)
        db.session.commit()

    # Seed Facilities
    if Facility.query.count() == 0:
        facilities = [
            Facility(facility_id=1, ulb_id=1, name="Kodungaiyur Waste-to-Energy Plant", type="RDF", current_capacity=380.0, max_capacity=450.0, location_lat=13.1420, location_lng=80.2680),
            Facility(facility_id=2, ulb_id=1, name="Perungudi WtE & RDF Plant", type="RDF", current_capacity=290.0, max_capacity=380.0, location_lat=12.9350, location_lng=80.2310),
            Facility(facility_id=3, ulb_id=2, name="Koyambedu Bio-CNG Plant", type="compost", current_capacity=140.0, max_capacity=200.0, location_lat=13.0690, location_lng=80.1915),
            Facility(facility_id=4, ulb_id=1, name="Chetpet Micro Composting Center", type="compost", current_capacity=62.0, max_capacity=80.0, location_lat=13.0685, location_lng=80.2345),
            Facility(facility_id=5, ulb_id=1, name="Otteri Composting Facility", type="compost", current_capacity=48.0, max_capacity=60.0, location_lat=13.0940, location_lng=80.2520),
            Facility(facility_id=6, ulb_id=4, name="Ambattur Industrial Recycling Plant", type="MRF", current_capacity=110.0, max_capacity=150.0, location_lat=13.0990, location_lng=80.1620)
        ]
        db.session.bulk_save_objects(facilities)
        db.session.commit()

    # Seed Fleet Trucks
    if Truck.query.count() == 0:
        trucks = [
            Truck(id=1, registration_number="TN-01-AM-1042", capacity_tons=12.0, current_load=9.4, route_status="ACTIVE", lat=13.0410, lng=80.2540),
            Truck(id=2, registration_number="TN-01-AM-2084", capacity_tons=14.0, current_load=11.2, route_status="ACTIVE", lat=13.0620, lng=80.2180),
            Truck(id=3, registration_number="TN-09-CB-4091", capacity_tons=10.0, current_load=8.5, route_status="ACTIVE", lat=12.9850, lng=80.2410),
            Truck(id=4, registration_number="TN-07-BW-5512", capacity_tons=15.0, current_load=12.8, route_status="EN_ROUTE", lat=13.0910, lng=80.1840),
            Truck(id=5, registration_number="TN-11-DX-9901", capacity_tons=12.0, current_load=7.9, route_status="ACTIVE", lat=12.9340, lng=80.1210)
        ]
        db.session.bulk_save_objects(trucks)
        db.session.commit()

    # Seed Conveyor Intake Scanned Items
    if ConveyorItem.query.count() == 0:
        conveyor_items = [
            ConveyorItem(item_name="PET Plastic Beverage Bottle", class_id=2, class_name="recyclable", confidence=0.96, sorting_decision="RECYCLABLE BIN", item_weight_kg=0.15, camera_id="CONVEYOR_CAM_01"),
            ConveyorItem(item_name="Organic Vegetable Scraps", class_id=0, class_name="wet", confidence=0.98, sorting_decision="WET BIN", item_weight_kg=0.35, camera_id="CONVEYOR_CAM_01"),
            ConveyorItem(item_name="Corrugated Shipping Box", class_id=2, class_name="recyclable", confidence=0.94, sorting_decision="RECYCLABLE BIN", item_weight_kg=0.48, camera_id="CONVEYOR_CAM_01"),
            ConveyorItem(item_name="Soiled Textile Cloth Scrap", class_id=1, class_name="dry", confidence=0.91, sorting_decision="DRY BIN", item_weight_kg=0.22, camera_id="CONVEYOR_CAM_01"),
            ConveyorItem(item_name="HDPE Milk Container", class_id=2, class_name="recyclable", confidence=0.97, sorting_decision="RECYCLABLE BIN", item_weight_kg=0.28, camera_id="CONVEYOR_CAM_01")
        ]
        db.session.bulk_save_objects(conveyor_items)
        db.session.commit()

    # Seed Batches, Routing Decisions & MRV Records
    if WasteBatch.query.count() == 0:
        st_names = ["Mylapore Transfer Station", "T. Nagar Collection Hub", "Adyar Transfer Hub", "Kodambakkam Station Queue", "Tambaram Central Queue", "Avadi West Station"]
        for i in range(1, 13):
            s_id = (i % 6) + 1
            st_name = st_names[s_id - 1]
            u_id = 1 if s_id <= 3 else (2 if s_id == 4 else (3 if s_id == 5 else 4))
            
            org = random.choice([58.0, 62.0, 48.0, 65.0, 42.0])
            rec = random.choice([28.0, 24.0, 36.0, 22.0, 40.0])
            haz = round(100.0 - org - rec, 1)
            wt = round(random.uniform(8.0, 15.0), 1)

            batch = WasteBatch(
                id=i,
                station_id=s_id,
                ulb_id=u_id,
                truck_id=(i % 5) + 1,
                source_lat=13.0368 + (i * 0.005),
                source_lng=80.2676 - (i * 0.004),
                weight_tons=wt,
                organic_percentage=org,
                recyclable_percentage=rec,
                hazardous_percentage=haz,
                moisture_percentage=54.0 if org > 50 else 22.0,
                awvs_score=round((org * 0.45) + (rec * 0.40) + 14.0, 2),
                transfer_station_name=st_name,
                timestamp_window=f"2026-08-30 0{8 + (i % 4)}:00-12:00"
            )
            db.session.add(batch)
            db.session.commit()

            # Create Routing Decision
            decision_dict = CrossULBMatchingEngine.match_batch(batch.id)
            if decision_dict:
                MRVService.calculate_and_record_mrv(decision_dict['decision_id'])

    # Seed Diversion Metrics
    if DiversionMetric.query.count() == 0:
        metrics = [
            DiversionMetric(ulb_id=1, district="Chennai", period="Current Month", diversion_rate=84.1, total_diverted_weight=1220.0, total_landfill_weight=230.0),
            DiversionMetric(ulb_id=2, district="Chennai", period="Current Month", diversion_rate=81.8, total_diverted_weight=1490.0, total_landfill_weight=330.0),
            DiversionMetric(ulb_id=3, district="Chengalpattu", period="Current Month", diversion_rate=82.1, total_diverted_weight=780.0, total_landfill_weight=170.0),
            DiversionMetric(ulb_id=4, district="Tiruvallur", period="Current Month", diversion_rate=74.5, total_diverted_weight=820.0, total_landfill_weight=280.0),
            DiversionMetric(ulb_id=5, district="Kanchipuram", period="Current Month", diversion_rate=63.0, total_diverted_weight=410.0, total_landfill_weight=240.0)
        ]
        db.session.bulk_save_objects(metrics)
        db.session.commit()

    print("[SUCCESS] SmartWasteGrid database seeded successfully with ULB models, facilities, batches, matching decisions, and MRV ledger entries.")

if __name__ == '__main__':
    from backend.app import create_app
    app = create_app()
    seed_data_if_empty(app)
