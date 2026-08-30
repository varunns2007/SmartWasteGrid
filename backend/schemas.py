from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BatchCreate(BaseModel):
    area_name: Optional[str] = "Demo Area"
    latitude: Optional[float] = 0.0
    longitude: Optional[float] = 0.0
    camera_id: Optional[str] = "CAM_001"
    primary_waste_type: Optional[str] = "recyclable"
    detected_items_summary: Optional[str] = "{}"
    total_waste_kg: float = 0.0
    organic_kg: Optional[float] = 0.0
    plastic_kg: Optional[float] = None
    paper_kg: Optional[float] = None
    cardboard_kg: Optional[float] = None
    glass_kg: Optional[float] = None
    metal_kg: Optional[float] = None
    other_kg: Optional[float] = 0.0
    organic_percentage: float = 0.0
    recyclable_percentage: float = 0.0
    dry_percentage: float = 0.0
    moisture_percentage: Optional[float] = 0.0

class OptimizeRequest(BaseModel):
    method: Optional[str] = "Classical"

class BatchResponse(BaseModel):
    batch_id: int
    area_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    camera_id: Optional[str]
    capture_time: datetime
    primary_waste_type: Optional[str]
    detected_items_summary: Optional[str]
    total_waste_kg: float
    organic_kg: float
    plastic_kg: Optional[float]
    paper_kg: Optional[float]
    cardboard_kg: Optional[float]
    glass_kg: Optional[float]
    metal_kg: Optional[float]
    other_kg: float
    organic_percentage: float
    recyclable_percentage: float
    dry_percentage: float
    moisture_percentage: float
    waste_quality_index: float
    lhv_mj_kg: float
    energy_potential_kwh: float
    dumping_detected: bool
    dumping_severity: str
    recommended_plant: Optional[str]
    plant_type: Optional[str]
    plant_distance_km: Optional[float]
    plant_capacity_available_kg: Optional[float]
    transport_cost: Optional[float]
    carbon_offset_kg: Optional[float]
    suitability_score: Optional[float]
    optimization_method: str
    optimization_status: str
    processing_status: str
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True

class StatisticsResponse(BaseModel):
    total_batches: int
    total_waste_kg: float
    average_wqi: float
    total_energy_kwh: float
    total_carbon_offset_kg: float
    organic_kg_sum: float
    dry_kg_sum: float
    recyclable_kg_sum: float
