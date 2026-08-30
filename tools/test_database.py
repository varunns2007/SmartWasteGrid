import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import SessionLocal, engine, Base
from backend.models import WasteBatch

def test_database():
    print("============================================================", flush=True)
    print("DATABASE INTEGRITY TEST", flush=True)
    print("============================================================", flush=True)
    
    # 1. Connect & Create tables
    print("Connecting to database & initializing tables...", flush=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # 2. Insert test batch
        print("1. Inserting test batch...", flush=True)
        test_batch = WasteBatch(
            area_name="Integration Test Area",
            latitude=12.9716,
            longitude=77.5946,
            camera_id="CAM_TEST_001",
            capture_time=datetime.utcnow(),
            total_waste_kg=12.50,
            organic_kg=4.17,
            plastic_kg=None,
            paper_kg=None,
            cardboard_kg=None,
            glass_kg=None,
            metal_kg=None,
            other_kg=8.33,
            organic_percentage=33.33,
            recyclable_percentage=46.67,
            dry_percentage=20.00,
            moisture_percentage=23.67,
            waste_quality_index=64.20,
            lhv_mj_kg=12.450,
            energy_potential_kwh=10.81,
            dumping_detected=False,
            dumping_severity="NONE",
            recommended_plant="GreenCycle Resource Recovery Facility [DEMO]",
            plant_type="Recycling",
            plant_distance_km=8.50,
            plant_capacity_available_kg=49987.50,
            transport_cost=15.00,
            carbon_offset_kg=12.50,
            suitability_score=82.00,
            optimization_method="Classical",
            optimization_status="OPTIMAL",
            processing_status="TEST"
        )
        
        db.add(test_batch)
        db.commit()
        db.refresh(test_batch)
        test_id = test_batch.batch_id
        print(f"   Success! Created test batch ID: {test_id}", flush=True)

        # 3. Read test batch
        print("2. Reading inserted test batch...", flush=True)
        read_batch = db.query(WasteBatch).filter(WasteBatch.batch_id == test_id).first()
        if not read_batch:
            print("   ERROR: Unable to retrieve inserted batch!", flush=True)
            sys.exit(1)
            
        print(f"   Fetched Batch #{read_batch.batch_id}:", flush=True)
        print(f"     Area:        {read_batch.area_name}", flush=True)
        print(f"     Camera:      {read_batch.camera_id}", flush=True)
        print(f"     Total Mass:  {read_batch.total_waste_kg} kg", flush=True)
        print(f"     Organic %:   {read_batch.organic_percentage}%", flush=True)
        print(f"     Dry %:       {read_batch.dry_percentage}%", flush=True)
        print(f"     Recyclable %:{read_batch.recyclable_percentage}%", flush=True)
        print(f"     WQI:         {read_batch.waste_quality_index}", flush=True)
        print(f"     LHV:         {read_batch.lhv_mj_kg} MJ/kg", flush=True)
        print(f"     Energy:      {read_batch.energy_potential_kwh} kWh", flush=True)
        print(f"     Plant:       {read_batch.recommended_plant}", flush=True)

        # 4. Delete test batch
        print("3. Cleaning up test batch...", flush=True)
        db.delete(read_batch)
        db.commit()
        
        verify_deleted = db.query(WasteBatch).filter(WasteBatch.batch_id == test_id).first()
        if verify_deleted is None:
            print("   Success! Test batch cleaned up.", flush=True)
        else:
            print("   WARNING: Batch cleanup failed.", flush=True)
            
        print("\nDATABASE INTEGRITY TEST PASSED SUCCESSFULLY!", flush=True)

    except Exception as e:
        print(f"\nDATABASE TEST FAILED: {e}", flush=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    test_database()
