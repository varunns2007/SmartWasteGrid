import random
from datetime import datetime, timedelta

# Chennai, India Bounding Box
CHENNAI_LAT_MIN, CHENNAI_LAT_MAX = 12.85, 13.15
CHENNAI_LNG_MIN, CHENNAI_LNG_MAX = 80.15, 80.30

# Smart Transfer Stations in Chennai
TRANSFER_STATIONS = [
    {"name": "Athipattu Transfer Station", "lat": 13.2010, "lng": 80.2280, "zone": "Zone 1 (Kathivakkam)"},
    {"name": "Mylapore Transfer Station", "lat": 13.0330, "lng": 80.2680, "zone": "Zone 9 (Teynampet)"},
    {"name": "Koyambedu Transfer Station", "lat": 13.0680, "lng": 80.2010, "zone": "Zone 10 (Kodambakkam)"},
    {"name": "Saidapet Transfer Station", "lat": 13.0210, "lng": 80.2230, "zone": "Zone 13 (Adyar)"},
    {"name": "Pulianthope Transfer Station", "lat": 13.0980, "lng": 80.2590, "zone": "Zone 6 (Thiru-Vi-Ka Nagar)"}
]

# In-memory database for tracking conveyor segregation counts (reset on app startup)
# Accumulates items and weights segregated at each transit center
TALLY_DB = {
    ts["name"]: {
        "organic_count": 120,
        "organic_tons": 32.4,
        "recyclable_count": 85,
        "recyclable_tons": 18.2,
        "hazardous_count": 12,
        "hazardous_tons": 2.1,
        "inert_count": 45,
        "inert_tons": 11.8,
        "total_scanned_count": 262
    } for ts in TRANSFER_STATIONS
}

class WasteSimulator:
    @staticmethod
    def generate_batch(truck_id):
        """
        Generates a realistic municipal waste batch from Chennai transfer stations
        with simulated IoT telemetry fields.
        """
        ts = random.choice(TRANSFER_STATIONS)
        lat = ts["lat"] + random.uniform(-0.015, 0.015)
        lng = ts["lng"] + random.uniform(-0.015, 0.015)
        
        organic_pct = random.uniform(45.0, 65.0)
        recyclable_pct = random.uniform(20.0, 35.0)
        hazardous_pct = random.uniform(1.0, 4.0)
        
        total = organic_pct + recyclable_pct + hazardous_pct
        organic_pct = (organic_pct / total) * 100
        recyclable_pct = (recyclable_pct / total) * 100
        hazardous_pct = (hazardous_pct / total) * 100
        
        moisture_pct = random.uniform(35.0, 75.0)
        weight_tons = random.uniform(5.0, 15.0)
        
        moisture_sensor_voltage = round(random.uniform(1.2, 3.1), 2)
        load_cell_voltage = round(random.uniform(0.5, 4.5), 3)
        fill_level_pct = round(random.uniform(60.0, 98.0), 1)
        
        protocol_used = random.choice(["MQTT (TCP/IP)", "LoRaWAN (OTA)", "REST API (HTTPS)"])
        device_id = f"ESP32-GW-{random.randint(100, 999)}"
        
        hours_ago = random.uniform(0, 4)
        timestamp = datetime.utcnow() - timedelta(hours=hours_ago)
        
        return {
            "truck_id": truck_id,
            "source_lat": round(lat, 5),
            "source_lng": round(lng, 5),
            "weight_tons": round(weight_tons, 2),
            "organic_percentage": round(organic_pct, 2),
            "recyclable_percentage": round(recyclable_pct, 2),
            "hazardous_percentage": round(hazardous_pct, 2),
            "moisture_percentage": round(moisture_pct, 2),
            "timestamp": timestamp.isoformat(),
            
            "transfer_station_name": ts["name"],
            "zone": ts["zone"],
            "iot_device_id": device_id,
            "iot_protocol": protocol_used,
            "moisture_raw_v": moisture_sensor_voltage,
            "load_cell_mv": load_cell_voltage,
            "fill_level_pct": fill_level_pct,
            "sensor_telemetry_rate_sec": 1
        }

    @staticmethod
    def generate_multiple_batches(truck_ids, count_per_truck=1):
        batches = []
        for truck_id in truck_ids:
            for _ in range(count_per_truck):
                batches.append(WasteSimulator.generate_batch(truck_id))
        return batches

class ConveyorSimulator:
    # Typical municipal solid waste objects scanned on conveyor belts
    CONVEYOR_ITEMS = [
        # Organic objects
        {"name": "Banana Peel", "category": "Organic", "moisture_range": (65.0, 85.0), "weight_range": (0.05, 0.20)},
        {"name": "Cabbage Leaves", "category": "Organic", "moisture_range": (70.0, 90.0), "weight_range": (0.10, 0.40)},
        {"name": "Coconut Shell", "category": "Organic", "moisture_range": (15.0, 30.0), "weight_range": (0.50, 1.20)},
        {"name": "Leftover Roti", "category": "Organic", "moisture_range": (20.0, 45.0), "weight_range": (0.05, 0.15)},
        {"name": "Vegetable Trimmings", "category": "Organic", "moisture_range": (60.0, 85.0), "weight_range": (0.15, 0.60)},
        {"name": "Tea Dust Waste", "category": "Organic", "moisture_range": (50.0, 75.0), "weight_range": (0.20, 0.80)},

        # Recyclable objects
        {"name": "PET Water Bottle", "category": "Recyclable", "moisture_range": (1.0, 8.0), "weight_range": (0.02, 0.06)},
        {"name": "Cardboard Carton Box", "category": "Recyclable", "moisture_range": (5.0, 15.0), "weight_range": (0.20, 0.80)},
        {"name": "Aluminium Beverage Can", "category": "Recyclable", "moisture_range": (0.0, 5.0), "weight_range": (0.01, 0.04)},
        {"name": "Glass Juice Bottle", "category": "Recyclable", "moisture_range": (0.0, 3.0), "weight_range": (0.30, 0.70)},
        {"name": "Shredded Newspaper", "category": "Recyclable", "moisture_range": (8.0, 18.0), "weight_range": (0.10, 0.50)},
        {"name": "HDPE Milk Jug", "category": "Recyclable", "moisture_range": (2.0, 10.0), "weight_range": (0.05, 0.15)},

        # Hazardous objects
        {"name": "Used Syringe Needle", "category": "Hazardous", "moisture_range": (2.0, 10.0), "weight_range": (0.01, 0.03)},
        {"name": "Lithium-Ion Cell Battery", "category": "Hazardous", "moisture_range": (0.0, 2.0), "weight_range": (0.03, 0.08)},
        {"name": "Insecticide Spray Can", "category": "Hazardous", "moisture_range": (1.0, 5.0), "weight_range": (0.15, 0.35)},
        {"name": "Discarded Paint Tin", "category": "Hazardous", "moisture_range": (10.0, 30.0), "weight_range": (0.50, 1.80)},

        # Inert / Landfill objects
        {"name": "Concrete Rubble Brick", "category": "Inert", "moisture_range": (2.0, 8.0), "weight_range": (1.50, 4.20)},
        {"name": "Clay Roof Shard", "category": "Inert", "moisture_range": (1.0, 5.0), "weight_range": (0.40, 1.10)},
        {"name": "Conveyor Mud Clod", "category": "Inert", "moisture_range": (20.0, 40.0), "weight_range": (0.80, 2.50)},
        {"name": "Road Sweepings Grit", "category": "Inert", "moisture_range": (5.0, 15.0), "weight_range": (0.50, 2.00)}
    ]

    @staticmethod
    def tick_sensor_feed(station_name):
        """
        Simulates a 1-second conveyor belt scan of an individual waste item.
        Performs CV-based object classification, raw moisture sensor voltage conversion,
        and fires appropriate mechanical actuators for sorting.
        """
        if station_name not in TALLY_DB:
            station_name = TRANSFER_STATIONS[0]["name"]
            
        tally = TALLY_DB[station_name]
        
        # Select a random waste item on the conveyor belt
        base_item = random.choice(ConveyorSimulator.CONVEYOR_ITEMS)
        
        # Add slight variation to moisture and weight
        moisture = round(random.uniform(*base_item["moisture_range"]), 1)
        weight = round(random.uniform(*base_item["weight_range"]), 3)
        
        # Convert moisture % to analog capacitive sensor voltage:
        # Capacitive moisture sensors read high voltage (~3.0V) in dry conditions,
        # and drop to low voltage (~1.1V) in wet conditions due to elevated dielectric constant.
        # Linear approximation: V_out = 3.3V - (moisture_pct / 100) * 2.2V
        raw_voltage = round(3.3 - (moisture / 100.0) * 2.2 + random.uniform(-0.05, 0.05), 2)
        raw_voltage = max(1.0, min(3.3, raw_voltage))
        
        # Generate CV Model attributes
        yolo_confidence = round(random.uniform(0.85, 0.99), 3)
        
        # Determine sorting logic and mechanical actuator outputs
        category = base_item["category"]
        if category == "Organic":
            # Sorting sub-logic: moisture determines anaerobic vs aerobic composting suitability
            if moisture >= 55.0:
                actuator = "Diverter Gate A (Bio-CNG Loop)"
                destination = "Koyambedu Biomethanation Plant"
            else:
                actuator = "Diverter Gate B (Compost Loop)"
                destination = "Chetpet MCC Composting Plant"
            tally["organic_count"] += 1
            tally["organic_tons"] += (weight / 1000.0) # convert kg to tons
        elif category == "Recyclable":
            actuator = "Pneumatic Air Jet Array (Recycle Bin)"
            destination = "Ambattur Plastics Recycling Facility"
            tally["recyclable_count"] += 1
            tally["recyclable_tons"] += (weight / 1000.0)
        elif category == "Hazardous":
            actuator = "Robotic Sorting Arm C (Hazardous Chute)"
            destination = "Secure Storage Annex"
            tally["hazardous_count"] += 1
            tally["hazardous_tons"] += (weight / 1000.0)
        else: # Inert
            actuator = "Linear Diverter Arm D (Landfill Chute)"
            destination = "Secured Landfill (Kodungaiyur/Perungudi)"
            tally["inert_count"] += 1
            tally["inert_tons"] += (weight / 1000.0)
            
        tally["total_scanned_count"] += 1
        
        # Round tally sums
        tally["organic_tons"] = round(tally["organic_tons"], 5)
        tally["recyclable_tons"] = round(tally["recyclable_tons"], 5)
        tally["hazardous_tons"] = round(tally["hazardous_tons"], 5)
        tally["inert_tons"] = round(tally["inert_tons"], 5)
        
        return {
            "station_name": station_name,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "object_name": base_item["name"],
            "category": category,
            "confidence": yolo_confidence,
            "moisture_pct": moisture,
            "moisture_voltage": raw_voltage,
            "weight_kg": weight,
            "actuator": actuator,
            "destination": destination,
            "tally": tally
        }
