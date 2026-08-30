"""
Calculations module for SmartWaste backend.
Provides configurable formulas for WQI, LHV, energy potential, carbon offset, transport cost, and plant suitability.
All calculations are clearly identified as estimates suitable for prototype evaluation.
"""

def calculate_percentages(wet_count: int, dry_count: int, recyclable_count: int):
    total = wet_count + dry_count + recyclable_count
    if total == 0:
        return 0.0, 0.0, 0.0
    wet_pct = (wet_count / total) * 100.0
    dry_pct = (dry_count / total) * 100.0
    rec_pct = (recyclable_count / total) * 100.0
    return round(wet_pct, 2), round(dry_pct, 2), round(rec_pct, 2)

def estimate_moisture(wet_percentage: float, dry_percentage: float, recyclable_percentage: float):
    # Estimated moisture based on wet (organic) fraction (~60-70% moisture) and dry/recyclable (~5-10%)
    moisture = (wet_percentage * 0.65) + (dry_percentage * 0.10) + (recyclable_percentage * 0.05)
    return round(max(0.0, min(100.0, moisture)), 2)

def calculate_wqi(moisture_percentage: float, organic_percentage: float, recyclable_percentage: float, dry_percentage: float) -> float:
    """
    Waste Quality Index (WQI): Scale 0 to 100.
    Rewards high recyclable fraction and balanced organic content; penalizes excess moisture and unsegregated dry fraction.
    """
    base_score = 50.0
    rec_bonus = recyclable_percentage * 0.40
    org_score = organic_percentage * 0.20
    moisture_penalty = moisture_percentage * 0.30
    wqi = base_score + rec_bonus + org_score - moisture_penalty
    return round(max(0.0, min(100.0, wqi)), 2)

def calculate_lhv(organic_pct: float, dry_pct: float, rec_pct: float, moisture_pct: float) -> float:
    """
    Estimated Lower Heating Value (LHV) in MJ/kg.
    """
    # Dry combustible / plastics LHV ~25 MJ/kg, paper/wood ~15 MJ/kg, organic ~5 MJ/kg, water reduces LHV
    lhv = (rec_pct * 0.20) + (dry_pct * 0.15) + (organic_pct * 0.05) - (moisture_pct * 0.08)
    return round(max(1.0, lhv), 3)

def calculate_energy_potential(total_waste_kg: float, lhv_mj_kg: float, conversion_efficiency: float = 0.25) -> float:
    """
    Theoretical Energy Potential in kWh:
    1 MJ = 0.277778 kWh.
    Energy (kWh) = Total_Mass_kg * LHV_MJ_kg * 0.277778 * efficiency
    """
    total_mj = total_waste_kg * lhv_mj_kg
    total_kwh_raw = total_mj * 0.277778
    energy_kwh = total_kwh_raw * conversion_efficiency
    return round(energy_kwh, 2)

def calculate_carbon_offset(organic_kg: float, recyclable_kg: float, dry_kg: float) -> float:
    """
    Estimated Carbon Offset in kg CO2e:
    Recycling offset factor: ~1.5 kg CO2e/kg
    Composting offset factor vs landfill methane: ~0.5 kg CO2e/kg
    Energy recovery dry offset factor: ~0.3 kg CO2e/kg
    """
    co2_rec = recyclable_kg * 1.50
    co2_org = organic_kg * 0.50
    co2_dry = dry_kg * 0.30
    return round(co2_rec + co2_org + co2_dry, 2)

def calculate_transport_cost(distance_km: float, weight_kg: float, rate_per_km_ton: float = 2.0) -> float:
    weight_tons = weight_kg / 1000.0
    cost = distance_km * max(weight_tons, 0.1) * rate_per_km_ton
    return round(max(5.0, cost), 2)

def calculate_suitability_score(plant_type: str, organic_pct: float, dry_pct: float, rec_pct: float, moisture_pct: float) -> float:
    """
    Returns plant suitability score (0-100) based on waste composition.
    """
    ptype = plant_type.lower()
    score = 50.0
    if "recycling" in ptype:
        score = rec_pct * 0.8 + dry_pct * 0.2
    elif "compost" in ptype or "biometh" in ptype:
        score = organic_pct * 0.8 + moisture_pct * 0.2
    elif "waste-to-energy" in ptype or "gasification" in ptype:
        score = dry_pct * 0.5 + rec_pct * 0.3 + (100.0 - moisture_pct) * 0.2
    return round(max(0.0, min(100.0, score)), 2)
