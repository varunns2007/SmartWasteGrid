import os
import sys
import time
import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def test_api():
    print("============================================================", flush=True)
    print("END-TO-END API & PIPELINE INTEGRATION TEST", flush=True)
    print("============================================================", flush=True)
    
    # 1. Health check
    health_url = f"{API_URL.rstrip('/')}/health"
    print(f"1. Testing API Health Check at {health_url}...", flush=True)
    try:
        r = requests.get(health_url, timeout=5)
        if r.status_code == 200:
            print(f"   Success! Health status: {r.json()}", flush=True)
        else:
            print(f"   FAILED: Status {r.status_code}", flush=True)
            sys.exit(1)
    except Exception as e:
        print(f"   FAILED: Could not connect to API server: {e}", flush=True)
        print("   Ensure backend is running: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000", flush=True)
        sys.exit(1)

    # 2. Simulate Section 45 Batch Creation
    # Detections: Wet=5, Dry=3, Recyclable=7 -> Total = 15 objects
    # Weight: 12.5 kg
    total_objects = 15
    wet_pct = round((5 / 15) * 100.0, 2)  # 33.33%
    dry_pct = round((3 / 15) * 100.0, 2)  # 20.00%
    rec_pct = round((7 / 15) * 100.0, 2)  # 46.67%
    
    batch_payload = {
        "area_name": "Hackathon Conveyor Test Area",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "camera_id": "CAM_001",
        "total_waste_kg": 12.5,
        "organic_kg": 0,
        "plastic_kg": None,
        "paper_kg": None,
        "cardboard_kg": None,
        "glass_kg": None,
        "metal_kg": None,
        "other_kg": 0,
        "organic_percentage": wet_pct,
        "recyclable_percentage": rec_pct,
        "dry_percentage": dry_pct,
        "moisture_percentage": 0.0
    }

    batches_url = f"{API_URL.rstrip('/')}/api/batches"
    print("\n2. Creating simulated waste batch (15 objects: 5 Wet, 3 Dry, 7 Recyclable, 12.5 kg)...", flush=True)
    r = requests.post(batches_url, json=batch_payload, timeout=5)
    if r.status_code == 201:
        created_batch = r.json()
        batch_id = created_batch["batch_id"]
        print(f"   Success! Created Batch ID: {batch_id}", flush=True)
        print(f"     Organic %:    {created_batch['organic_percentage']}%", flush=True)
        print(f"     Dry %:        {created_batch['dry_percentage']}%", flush=True)
        print(f"     Recyclable %: {created_batch['recyclable_percentage']}%", flush=True)
        print(f"     Estimated WQI:{created_batch['waste_quality_index']}", flush=True)
        print(f"     Estimated LHV:{created_batch['lhv_mj_kg']} MJ/kg", flush=True)
        print(f"     Energy:       {created_batch['energy_potential_kwh']} kWh", flush=True)
        print(f"     Recommended Plant: {created_batch['recommended_plant']}", flush=True)
    else:
        print(f"   FAILED to create batch: {r.status_code} - {r.text}", flush=True)
        sys.exit(1)

    # 3. Retrieve batch
    get_url = f"{API_URL.rstrip('/')}/api/batches/{batch_id}"
    print(f"\n3. Retrieving created batch from GET {get_url}...", flush=True)
    r = requests.get(get_url, timeout=5)
    if r.status_code == 200:
        retrieved = r.json()
        print(f"   Success! Retrieved Batch #{retrieved['batch_id']}", flush=True)
    else:
        print(f"   FAILED to retrieve batch: {r.status_code}", flush=True)
        sys.exit(1)

    # 4. Trigger Optimization
    opt_url = f"{API_URL.rstrip('/')}/api/optimize/{batch_id}"
    print(f"\n4. Triggering optimization (method=Classical) at POST {opt_url}...", flush=True)
    r = requests.post(opt_url, json={"method": "Classical"}, timeout=5)
    if r.status_code == 200:
        opt_res = r.json()
        print(f"   Success! Optimization Method: {opt_res['optimization_method']}", flush=True)
        print(f"     Recommended Plant: {opt_res['recommended_plant']}", flush=True)
        print(f"     Plant Type:        {opt_res['plant_type']}", flush=True)
        print(f"     Transport Cost:    ${opt_res['transport_cost']}", flush=True)
        print(f"     Carbon Offset:     {opt_res['carbon_offset_kg']} kg CO2e", flush=True)
    else:
        print(f"   FAILED optimization call: {r.status_code}", flush=True)
        sys.exit(1)

    # 5. Retrieve global statistics
    stats_url = f"{API_URL.rstrip('/')}/api/statistics"
    print(f"\n5. Retrieving global system statistics from GET {stats_url}...", flush=True)
    r = requests.get(stats_url, timeout=5)
    if r.status_code == 200:
        stats = r.json()
        print(f"   Success! Total Batches: {stats['total_batches']}", flush=True)
        print(f"     Total Waste Managed: {stats['total_waste_kg']} kg", flush=True)
        print(f"     Total Energy Output: {stats['total_energy_kwh']} kWh", flush=True)
        print(f"     Total Carbon Offset: {stats['total_carbon_offset_kg']} kg CO2e", flush=True)
    else:
        print(f"   FAILED to retrieve statistics: {r.status_code}", flush=True)
        sys.exit(1)

    print("\n============================================================", flush=True)
    print("ALL API END-TO-END TESTS COMPLETED SUCCESSFULLY!", flush=True)
    print("============================================================", flush=True)

if __name__ == "__main__":
    test_api()
