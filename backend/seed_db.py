import sys
import os
import random
from datetime import datetime

# Add root directory to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.flask_db.db import db
from backend.flask_models.models import Plant, Truck, WasteBatch

def seed_data(app=None):
    if app is None:
        from backend.quantum_app import create_app
        app = create_app()
        
    with app.app_context():
        if Plant.query.count() > 0 and Truck.query.count() > 0:
            return

        print("[*] Seeding database with Chennai treatment facilities, fleet, and batches...")
        
        # 1. Seed Chennai Waste Processing & Disposal Plants
        plants = [
            Plant(
                name="Kodungaiyur Waste-to-Energy Plant",
                technology_type="Waste-to-Energy",
                lat=13.1420,
                lng=80.2680,
                max_capacity_tons=2500.0,
                current_utilization_tons=1500.0,
                recovered_heat_mw=12.0,
                efficiency_factor=1.1,
                processing_cost_per_ton=160.0,
                available_heat_mw=8.0,
                processing_efficiency=0.85,
                queue_length=2
            ),
            Plant(
                name="Perungudi WtE & RDF Plant",
                technology_type="RDF",
                lat=12.9350,
                lng=80.2310,
                max_capacity_tons=2000.0,
                current_utilization_tons=1100.0,
                recovered_heat_mw=10.0,
                efficiency_factor=1.15,
                processing_cost_per_ton=150.0,
                available_heat_mw=6.0,
                processing_efficiency=0.82,
                queue_length=3
            ),
            Plant(
                name="Koyambedu Bio-CNG Plant",
                technology_type="Biomethanation",
                lat=13.0690,
                lng=80.1915,
                max_capacity_tons=600.0,
                current_utilization_tons=400.0,
                recovered_heat_mw=2.5,
                efficiency_factor=0.9,
                processing_cost_per_ton=110.0,
                available_heat_mw=1.5,
                processing_efficiency=0.80,
                queue_length=1
            ),
            Plant(
                name="Chetpet Micro Composting Center",
                technology_type="Composting",
                lat=13.0685,
                lng=80.2345,
                max_capacity_tons=100.0,
                current_utilization_tons=60.0,
                recovered_heat_mw=0.0,
                efficiency_factor=0.8,
                processing_cost_per_ton=50.0,
                available_heat_mw=0.0,
                processing_efficiency=0.88,
                queue_length=1
            ),
            Plant(
                name="Otteri Composting Facility",
                technology_type="Composting",
                lat=13.0940,
                lng=80.2520,
                max_capacity_tons=150.0,
                current_utilization_tons=80.0,
                recovered_heat_mw=0.0,
                efficiency_factor=0.82,
                processing_cost_per_ton=55.0,
                available_heat_mw=0.0,
                processing_efficiency=0.85,
                queue_length=0
            ),
            Plant(
                name="Ambattur Industrial Recycling Plant",
                technology_type="Recycling",
                lat=13.0990,
                lng=80.1620,
                max_capacity_tons=400.0,
                current_utilization_tons=220.0,
                recovered_heat_mw=0.0,
                efficiency_factor=0.95,
                processing_cost_per_ton=80.0,
                available_heat_mw=0.0,
                processing_efficiency=0.92,
                queue_length=1
            ),
            Plant(
                name="Koyambedu Gasification Plant",
                technology_type="Gasification",
                lat=13.0720,
                lng=80.1890,
                max_capacity_tons=500.0,
                current_utilization_tons=300.0,
                recovered_heat_mw=3.0,
                efficiency_factor=1.2,
                processing_cost_per_ton=180.0,
                available_heat_mw=2.0,
                processing_efficiency=0.87,
                queue_length=1
            )
        ]
        for p in plants:
            db.session.add(p)
        db.session.commit()

        # 2. Seed Tamil Nadu / Chennai Registered Collection Trucks
        truck_objs = []
        zones_tn = ["TN-01", "TN-02", "TN-05", "TN-06", "TN-07", "TN-09", "TN-10", "TN-13"]
        for i in range(1, 13): # 12 active fleet trucks
            prefix = random.choice(zones_tn)
            t = Truck(
                registration_number=f"{prefix}-AM-{random.randint(1000, 9999)}",
                capacity_tons=float(random.choice([8.0, 10.0, 12.0, 15.0])),
                current_load=0.0,
                route_status="IDLE",
                lat=13.0400 + random.uniform(-0.05, 0.05),
                lng=80.2200 + random.uniform(-0.05, 0.05)
            )
            db.session.add(t)
            truck_objs.append(t)
        db.session.commit()

        # 3. Seed Initial Waste Batches in Transfer Station Queues
        stations = [
            ("Mylapore Transfer Station", 13.0368, 80.2676),
            ("T. Nagar Collection Hub", 13.0418, 80.2341),
            ("Adyar Transfer Hub", 12.9985, 80.2565),
            ("Anna Nagar West Station", 13.0878, 80.1994),
            ("Velachery Station Queue", 12.9750, 80.2210),
            ("Tambaram Central Queue", 12.9249, 80.1000)
        ]

        for idx, (st_name, st_lat, st_lng) in enumerate(stations, 0):
            w_tons = round(random.uniform(5.5, 14.5), 2)
            org_pct = round(random.uniform(35.0, 65.0), 1)
            rec_pct = round(random.uniform(20.0, 45.0), 1)
            haz_pct = round(random.uniform(1.0, 5.0), 1)
            moisture = round(random.uniform(30.0, 65.0), 1)
            assigned_truck = truck_objs[idx % len(truck_objs)]

            b = WasteBatch(
                truck_id=assigned_truck.id,
                source_lat=st_lat,
                source_lng=st_lng,
                weight_tons=w_tons,
                organic_percentage=org_pct,
                recyclable_percentage=rec_pct,
                hazardous_percentage=haz_pct,
                moisture_percentage=moisture,
                awvs_score=round(random.uniform(0.65, 0.92), 2),
                transfer_station_name=st_name,
                created_at=datetime.utcnow()
            )
            db.session.add(b)
        db.session.commit()

        print("[+] Database successfully seeded with 7 plants, 12 trucks, and 6 initial unallocated batches.")

def seed_data_if_empty(app=None):
    seed_data(app)

if __name__ == '__main__':
    seed_data()
