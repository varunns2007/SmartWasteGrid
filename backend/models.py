from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text
from datetime import datetime
from backend.database import Base

class WasteBatch(Base):
    __tablename__ = "waste_batches"

    batch_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    area_name = Column(String(255), default="Demo Area")
    latitude = Column(Numeric(10, 7), default=0.0)
    longitude = Column(Numeric(10, 7), default=0.0)
    camera_id = Column(String(100), default="CAM_001")
    capture_time = Column(DateTime, default=datetime.utcnow)

    # Waste Classification Details
    primary_waste_type = Column(String(100), default="recyclable")
    detected_items_summary = Column(Text, default="{}")

    # Weights (kg)
    total_waste_kg = Column(Numeric(10, 2), default=0.0)
    organic_kg = Column(Numeric(10, 2), default=0.0)
    plastic_kg = Column(Numeric(10, 2), nullable=True, default=None)
    paper_kg = Column(Numeric(10, 2), nullable=True, default=None)
    cardboard_kg = Column(Numeric(10, 2), nullable=True, default=None)
    glass_kg = Column(Numeric(10, 2), nullable=True, default=None)
    metal_kg = Column(Numeric(10, 2), nullable=True, default=None)
    other_kg = Column(Numeric(10, 2), default=0.0)

    # Percentages
    organic_percentage = Column(Numeric(6, 2), default=0.0)
    recyclable_percentage = Column(Numeric(6, 2), default=0.0)
    dry_percentage = Column(Numeric(6, 2), default=0.0)
    moisture_percentage = Column(Numeric(6, 2), default=0.0)

    # Derived metrics
    waste_quality_index = Column(Numeric(8, 2), default=0.0)
    lhv_mj_kg = Column(Numeric(8, 3), default=0.0)
    energy_potential_kwh = Column(Numeric(12, 2), default=0.0)
    
    # Dumping detection
    dumping_detected = Column(Boolean, default=False)
    dumping_severity = Column(String(20), default="NONE")

    # Optimization outputs
    recommended_plant = Column(String(255), nullable=True)
    plant_type = Column(String(100), nullable=True)
    plant_distance_km = Column(Numeric(10, 2), nullable=True)
    plant_capacity_available_kg = Column(Numeric(12, 2), nullable=True)
    transport_cost = Column(Numeric(12, 2), nullable=True)
    carbon_offset_kg = Column(Numeric(12, 2), nullable=True)
    suitability_score = Column(Numeric(8, 2), nullable=True)
    optimization_method = Column(String(50), default="Classical")
    optimization_status = Column(String(50), default="PENDING")
    
    # Processing status
    processing_status = Column(String(50), default="NEW")
    processed_at = Column(DateTime, nullable=True)
