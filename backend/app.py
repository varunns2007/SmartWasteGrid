from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db, engine, Base
from backend.models import WasteBatch
from backend.schemas import BatchCreate, BatchResponse, StatisticsResponse, OptimizeRequest
from backend import calculations, optimizer

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SmartWaste Grid API",
    description="Smart Waste Segregation & Logistics Backend Prototype",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {
        "status": "healthy",
        "service": "SmartWaste Backend API",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/batches", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(batch_in: BatchCreate, db: Session = Depends(get_db)):
    total_kg = max(batch_in.total_waste_kg, 0.0)
    
    organic_kg = total_kg * (batch_in.organic_percentage / 100.0) if total_kg > 0 else batch_in.organic_kg
    other_kg = total_kg - organic_kg
    
    moisture_pct = batch_in.moisture_percentage if batch_in.moisture_percentage > 0 else calculations.estimate_moisture(
        batch_in.organic_percentage, batch_in.dry_percentage, batch_in.recyclable_percentage
    )
    
    wqi = calculations.calculate_wqi(
        moisture_pct, batch_in.organic_percentage, batch_in.recyclable_percentage, batch_in.dry_percentage
    )
    
    lhv = calculations.calculate_lhv(
        batch_in.organic_percentage, batch_in.dry_percentage, batch_in.recyclable_percentage, moisture_pct
    )
    
    energy_kwh = calculations.calculate_energy_potential(total_kg, lhv)
    
    batch_dict = {
        "latitude": batch_in.latitude,
        "longitude": batch_in.longitude,
        "total_waste_kg": total_kg,
        "organic_percentage": batch_in.organic_percentage,
        "dry_percentage": batch_in.dry_percentage,
        "recyclable_percentage": batch_in.recyclable_percentage,
        "moisture_percentage": moisture_pct
    }
    opt_res = optimizer.optimize_plant_assignment(batch_dict, method="Classical")

    # Determine primary waste type
    max_pct = max(batch_in.organic_percentage, batch_in.dry_percentage, batch_in.recyclable_percentage)
    if max_pct == batch_in.organic_percentage and max_pct > 0:
        pw_type = "wet"
    elif max_pct == batch_in.recyclable_percentage and max_pct > 0:
        pw_type = "recyclable"
    elif max_pct == batch_in.dry_percentage and max_pct > 0:
        pw_type = "dry"
    else:
        pw_type = batch_in.primary_waste_type or "recyclable"

    db_batch = WasteBatch(
        area_name=batch_in.area_name,
        latitude=batch_in.latitude,
        longitude=batch_in.longitude,
        camera_id=batch_in.camera_id,
        capture_time=datetime.utcnow(),
        primary_waste_type=pw_type,
        detected_items_summary=batch_in.detected_items_summary or "{}",
        total_waste_kg=total_kg,
        organic_kg=round(organic_kg, 2),
        plastic_kg=None,
        paper_kg=None,
        cardboard_kg=None,
        glass_kg=None,
        metal_kg=None,
        other_kg=round(other_kg, 2),
        organic_percentage=batch_in.organic_percentage,
        recyclable_percentage=batch_in.recyclable_percentage,
        dry_percentage=batch_in.dry_percentage,
        moisture_percentage=moisture_pct,
        waste_quality_index=wqi,
        lhv_mj_kg=lhv,
        energy_potential_kwh=energy_kwh,
        dumping_detected=False,
        dumping_severity="NONE",
        recommended_plant=opt_res["recommended_plant"],
        plant_type=opt_res["plant_type"],
        plant_distance_km=opt_res["plant_distance_km"],
        plant_capacity_available_kg=opt_res["plant_capacity_available_kg"],
        transport_cost=opt_res["transport_cost"],
        carbon_offset_kg=opt_res["carbon_offset_kg"],
        suitability_score=opt_res["suitability_score"],
        optimization_method=opt_res["optimization_method"],
        optimization_status=opt_res["optimization_status"],
        processing_status="NEW",
        processed_at=datetime.utcnow()
    )

    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch

@app.get("/api/batches", response_model=List[BatchResponse])
def get_batches(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(WasteBatch).order_by(WasteBatch.batch_id.desc()).limit(limit).all()

@app.get("/api/batches/latest", response_model=BatchResponse)
def get_latest_batch(db: Session = Depends(get_db)):
    batch = db.query(WasteBatch).order_by(WasteBatch.batch_id.desc()).first()
    if not batch:
        raise HTTPException(status_code=404, detail="No batches found")
    return batch

@app.get("/api/batches/{batch_id}", response_model=BatchResponse)
def get_batch_by_id(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(WasteBatch).filter(WasteBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch ID {batch_id} not found")
    return batch

@app.put("/api/batches/{batch_id}", response_model=BatchResponse)
def update_batch(batch_id: int, batch_in: BatchCreate, db: Session = Depends(get_db)):
    batch = db.query(WasteBatch).filter(WasteBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch ID {batch_id} not found")

    batch.total_waste_kg = batch_in.total_waste_kg
    batch.organic_percentage = batch_in.organic_percentage
    batch.dry_percentage = batch_in.dry_percentage
    batch.recyclable_percentage = batch_in.recyclable_percentage
    if batch_in.primary_waste_type: batch.primary_waste_type = batch_in.primary_waste_type
    if batch_in.detected_items_summary: batch.detected_items_summary = batch_in.detected_items_summary
    
    batch.organic_kg = round(batch.total_waste_kg * (batch.organic_percentage / 100.0), 2)
    batch.other_kg = round(batch.total_waste_kg - batch.organic_kg, 2)
    
    batch.moisture_percentage = calculations.estimate_moisture(
        batch.organic_percentage, batch.dry_percentage, batch.recyclable_percentage
    )
    batch.waste_quality_index = calculations.calculate_wqi(
        batch.moisture_percentage, batch.organic_percentage, batch.recyclable_percentage, batch.dry_percentage
    )
    batch.lhv_mj_kg = calculations.calculate_lhv(
        batch.organic_percentage, batch.dry_percentage, batch.recyclable_percentage, batch.moisture_percentage
    )
    batch.energy_potential_kwh = calculations.calculate_energy_potential(batch.total_waste_kg, batch.lhv_mj_kg)

    db.commit()
    db.refresh(batch)
    return batch

@app.post("/api/optimize/{batch_id}", response_model=BatchResponse)
def optimize_batch(batch_id: int, opt_req: OptimizeRequest, db: Session = Depends(get_db)):
    batch = db.query(WasteBatch).filter(WasteBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch ID {batch_id} not found")

    batch_dict = {
        "latitude": float(batch.latitude or 0.0),
        "longitude": float(batch.longitude or 0.0),
        "total_waste_kg": float(batch.total_waste_kg or 0.0),
        "organic_percentage": float(batch.organic_percentage or 0.0),
        "dry_percentage": float(batch.dry_percentage or 0.0),
        "recyclable_percentage": float(batch.recyclable_percentage or 0.0),
        "moisture_percentage": float(batch.moisture_percentage or 0.0)
    }

    opt_res = optimizer.optimize_plant_assignment(batch_dict, method=opt_req.method)
    
    batch.recommended_plant = opt_res["recommended_plant"]
    batch.plant_type = opt_res["plant_type"]
    batch.plant_distance_km = opt_res["plant_distance_km"]
    batch.plant_capacity_available_kg = opt_res["plant_capacity_available_kg"]
    batch.transport_cost = opt_res["transport_cost"]
    batch.carbon_offset_kg = opt_res["carbon_offset_kg"]
    batch.suitability_score = opt_res["suitability_score"]
    batch.optimization_method = opt_res["optimization_method"]
    batch.optimization_status = opt_res["optimization_status"]

    db.commit()
    db.refresh(batch)
    return batch

@app.post("/api/detection")
def record_detection(payload: dict):
    return {"status": "received", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/statistics", response_model=StatisticsResponse)
def get_statistics(db: Session = Depends(get_db)):
    batches = db.query(WasteBatch).all()
    count = len(batches)
    if count == 0:
        return StatisticsResponse(
            total_batches=0,
            total_waste_kg=0.0,
            average_wqi=0.0,
            total_energy_kwh=0.0,
            total_carbon_offset_kg=0.0,
            organic_kg_sum=0.0,
            dry_kg_sum=0.0,
            recyclable_kg_sum=0.0
        )
        
    tot_waste = sum(float(b.total_waste_kg or 0) for b in batches)
    tot_wqi = sum(float(b.waste_quality_index or 0) for b in batches)
    tot_energy = sum(float(b.energy_potential_kwh or 0) for b in batches)
    tot_carbon = sum(float(b.carbon_offset_kg or 0) for b in batches)
    tot_org = sum(float(b.organic_kg or 0) for b in batches)
    tot_dry = sum(float(b.total_waste_kg or 0) * (float(b.dry_percentage or 0)/100.0) for b in batches)
    tot_rec = sum(float(b.total_waste_kg or 0) * (float(b.recyclable_percentage or 0)/100.0) for b in batches)

    return StatisticsResponse(
        total_batches=count,
        total_waste_kg=round(tot_waste, 2),
        average_wqi=round(tot_wqi / count, 2),
        total_energy_kwh=round(tot_energy, 2),
        total_carbon_offset_kg=round(tot_carbon, 2),
        organic_kg_sum=round(tot_org, 2),
        dry_kg_sum=round(tot_dry, 2),
        recyclable_kg_sum=round(tot_rec, 2)
    )
