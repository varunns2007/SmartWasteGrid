import numpy as np
import math
from datetime import datetime, timedelta

class WasteAnalytics:
    @staticmethod
    def estimate_calorific_value(organic_pct, recyclable_pct, hazardous_pct, moisture_pct):
        """
        Estimates the Lower Heating Value (LHV) in kcal/kg of the waste batch.
        - Dry Organic: ~2400 kcal/kg
        - Dry Recyclables (plastic, paper, cardboard): ~4800 kcal/kg
        - Dry Hazardous/Other: ~1400 kcal/kg
        """
        # Calculate dry weight components
        dry_organic = organic_pct * 24.0
        dry_recyclable = recyclable_pct * 48.0
        dry_hazardous = hazardous_pct * 14.0
        
        dry_calorific_value = dry_organic + dry_recyclable + dry_hazardous
        
        # Wet calorific value accounts for moisture reducing the heat energy
        # 1% moisture reduces LHV by approximately 6 kcal/kg (latent heat of vaporization)
        wet_calorific_value = dry_calorific_value * (1 - moisture_pct / 100.0) - (6 * moisture_pct)
        
        # Clamp to realistic range for municipal solid waste in India (700 to 3200 kcal/kg)
        return max(700.0, min(3200.0, wet_calorific_value))

    @staticmethod
    def calculate_priority_score(organic_pct, moisture_pct, fill_level_pct=75.0):
        """
        Calculates collection priority (1 to 5) based on fill level and biodegradable degradation speed.
        High organic content + high moisture = high microbial decay rate = urgent collection priority.
        """
        decay_factor = (organic_pct / 100.0) * (moisture_pct / 100.0)
        # Weight organic decay at 60%, fill level at 40%
        base_score = (decay_factor * 6.0) + (fill_level_pct / 100.0 * 4.0)
        # Clamp between 1.0 and 5.0
        return round(max(1.0, min(5.0, base_score)), 1)

    @staticmethod
    def calculate_awvs(weight_tons, organic_pct, recyclable_pct, hazardous_pct, moisture_pct,
                       distance_km=0.0, tech_type=None, available_heat_mw=0.0,
                       plant_efficiency=0.8, queue_length=0, current_utilization_tons=0.0,
                       max_capacity_tons=1000.0, fill_level_pct=75.0):
        """
        Calculates the upgraded Adaptive Waste Value Score (AWVS) in INR for a waste batch.
        Includes:
        - Energy Recovery Potential (electricity, methane, heat offsets)
        - Material Recyclability Yield
        - Transportation Distance & Fuel Costs
        - Processing Cost Rates
        - Carbon Credit Valuation (CO2 offsets)
        - Plant Queue Wait Penalties
        - Plant Capacity Utilization Penalty
        - Collection Priority Bonus
        """
        # 1. Expected Energy Output
        energy = WasteAnalytics.estimate_energy_potential(weight_tons, organic_pct, recyclable_pct, hazardous_pct, moisture_pct)
        lhv = WasteAnalytics.estimate_calorific_value(organic_pct, recyclable_pct, hazardous_pct, moisture_pct)
        
        # Default to best technology recommendation if none specified
        suitability = WasteAnalytics.classify_waste(organic_pct, recyclable_pct, hazardous_pct, moisture_pct)
        tech = tech_type if tech_type is not None else suitability['recommendation']
        
        # Efficiency modifier
        eff_modifier = plant_efficiency / 0.8
        
        # Base Benefits in INR
        energy_benefit = 0.0
        recycling_benefit = 0.0
        drying_cost = 0.0
        processing_cost_rate = 100.0 # Default fallback
        
        # 2. Technology-specific revenue & costs
        if tech == "Biomethanation":
            energy_benefit = energy['electricity_biogas_kwh'] * eff_modifier * 6.5  # Rs. 6.5/kWh feed-in tariff
            processing_cost_rate = 110.0
            
        elif tech in ["RDF", "Waste-to-Energy", "Gasification"]:
            base_drying_energy = energy['drying_energy_required_kwh']
            # Thermal heat recovery offset
            heat_offset_kwh = available_heat_mw * 100.0 * weight_tons
            net_drying_energy = max(0.0, base_drying_energy - heat_offset_kwh)
            drying_cost = net_drying_energy * 4.5  # Rs. 4.5/kWh drying cost
            
            lhv_boosted = WasteAnalytics.estimate_calorific_value(organic_pct, recyclable_pct, hazardous_pct, min(20.0, moisture_pct))
            boost_factor = lhv_boosted / lhv if lhv > 0 else 1.0
            
            energy_benefit = energy['electricity_thermal_kwh'] * boost_factor * eff_modifier * 8.5  # Rs. 8.5/kWh feed-in tariff
            # RDF sales value
            energy_benefit += energy['rdf_potential_tons'] * 1800.0  # Rs 1800/ton RDF
            processing_cost_rate = 160.0 if tech == "Waste-to-Energy" else 150.0
            if tech == "Gasification":
                processing_cost_rate = 180.0
                
        elif tech == "Composting":
            energy_benefit = energy['compost_output_tons'] * 1000.0 * 12.0  # Rs. 12/kg compost
            processing_cost_rate = 55.0
            
        elif tech == "Recycling":
            # Direct material sales for paper/cardboard/plastics
            # Ambattur Recycling Plant recovers dry recyclables at Rs 5,500/ton yield
            recycling_benefit = weight_tons * (recyclable_pct / 100.0) * 5500.0
            processing_cost_rate = 80.0
            
        else: # Landfill fallback
            processing_cost_rate = 250.0  # Tipping fees + environmental penalty
            
        # 3. Recyclability recovery fraction for other facilities (secondary sorting)
        if tech != "Recycling" and tech != "Landfill":
            # Other plants recover ~15% of dry recyclables before processing
            recycling_benefit = weight_tons * (recyclable_pct / 100.0) * 0.15 * 3500.0
            
        # 4. Processing Cost
        processing_cost = weight_tons * processing_cost_rate
        
        # 5. Transportation Cost (Rs 4.5 per ton-km)
        transport_cost = weight_tons * distance_km * 4.5
        
        # 6. Carbon Credit Offset Value (Rs. 1.20 per kg CO2e offset)
        electricity_generated = 0.0
        if tech == "Biomethanation":
            electricity_generated = energy['electricity_biogas_kwh']
        elif tech in ["RDF", "Waste-to-Energy", "Gasification"]:
            electricity_generated = energy['electricity_thermal_kwh']
            
        co2_offset = WasteAnalytics.calculate_carbon_offset(
            weight_tons, organic_pct, electricity_generated, distance_km
        )
        carbon_credit_value = max(0.0, co2_offset) * 1.20 # Rs 1.2 per kg CO2
        
        # 7. Collection Priority Bonus
        priority = WasteAnalytics.calculate_priority_score(organic_pct, moisture_pct, fill_level_pct)
        priority_bonus = priority * weight_tons * 150.0  # Priority level factor reward (Rs. 150 per level per ton)
        
        # 8. Plant Queue Wait Penalty
        queue_penalty = queue_length * weight_tons * 40.0  # Rs. 40 penalty per queue node per ton
        
        # 9. Plant Capacity Utilization Penalty (High penalty if close to capacity)
        cap_penalty = 0.0
        predicted_utilization = current_utilization_tons + weight_tons
        if predicted_utilization > max_capacity_tons:
            # Overcapacity penalty (Rs. 800 per excess ton)
            cap_penalty = (predicted_utilization - max_capacity_tons) * 800.0
        elif (predicted_utilization / max_capacity_tons) > 0.90:
            # Mild warning penalty to encourage distribution (Capacity Balancing)
            cap_penalty = weight_tons * 100.0
            
        # 10. Process Suitability Score Bonus
        suitability_score = suitability['suitability_scores'].get(tech if tech != "Waste-to-Energy" else "RDF", 50.0)
        suitability_bonus = suitability_score * 6.0
        
        # Net Economic and Environmental Value (AWVS)
        awvs = (energy_benefit + recycling_benefit + carbon_credit_value + priority_bonus + suitability_bonus
                - transport_cost - drying_cost - processing_cost - queue_penalty - cap_penalty)
                
        return round(max(0.0, awvs), 2)

    @staticmethod
    def classify_waste(organic_pct, recyclable_pct, hazardous_pct, moisture_pct):
        """
        Classifies waste batches and recommends an optimal processing method.
        """
        # Calculate suitability scores for each technique (0 to 100)
        
        # 1. Biomethanation (Anaerobic Digestion)
        # Prefers high organics, high moisture, low hazardous contaminants
        biomethanation_score = (organic_pct * 0.5) + (moisture_pct * 0.4) + (max(0, 100 - hazardous_pct * 20) * 0.1)
        if hazardous_pct >= 4.0:
            biomethanation_score *= 0.15
            
        # 2. Composting
        # Prefers high organics, moderate moisture (45-60% is ideal)
        moisture_deviation = abs(moisture_pct - 50.0)
        moisture_factor = max(0, 100 - moisture_deviation * 3.5)
        composting_score = (organic_pct * 0.5) + (moisture_factor * 0.4) + (max(0, 100 - hazardous_pct * 20) * 0.1)
        if hazardous_pct >= 4.0:
            composting_score *= 0.1
            
        # 3. RDF & Waste-to-Energy
        # Prefers high combustibles (recyclables like paper, plastics), low moisture
        rdf_score = (recyclable_pct * 0.6) + (max(0, 100 - moisture_pct) * 0.3) + (max(0, 100 - hazardous_pct * 10) * 0.1)
        
        # 4. Gasification
        # Prefers very low moisture, high organic + recyclable combustibles
        total_combustibles = organic_pct + recyclable_pct
        gasification_score = (total_combustibles * 0.4) + (max(0, 100 - moisture_pct * 2) * 0.5) + (max(0, 100 - hazardous_pct * 10) * 0.1)
        
        # 5. Recycling
        # Prefers extremely high recyclable percentages and dry material
        recycling_score = (recyclable_pct * 0.75) + (max(0, 100 - moisture_pct) * 0.15) + (max(0, 100 - hazardous_pct * 20) * 0.1)
        
        # 6. Landfill fallback
        landfill_score = hazardous_pct * 12.0
        
        scores = {
            "Biomethanation": round(biomethanation_score, 2),
            "Composting": round(composting_score, 2),
            "RDF": round(rdf_score, 2),
            "Gasification": round(gasification_score, 2),
            "Recycling": round(recycling_score, 2),
            "Landfill": round(landfill_score, 2)
        }
        
        recommended = max(scores, key=scores.get)
        
        # Specific overrides
        if hazardous_pct > 12.0:
            recommended = "Landfill"
            reasoning = "Hazardous fraction exceeds safety limit (>12%). Route directly to secured landfill."
        elif recommended == "Biomethanation":
            reasoning = f"High organic content ({organic_pct:.1f}%) and moisture ({moisture_pct:.1f}%) make it ideal for anaerobic digestion to produce biogas."
        elif recommended == "Composting":
            reasoning = f"High organic content ({organic_pct:.1f}%) with ideal moisture ({moisture_pct:.1f}%) supports compost production."
        elif recommended == "RDF":
            reasoning = f"High fraction of dry combustibles ({recyclable_pct:.1f}%) and low moisture ({moisture_pct:.1f}%) suit Refuse-Derived Fuel processing."
        elif recommended == "Gasification":
            reasoning = f"Low moisture ({moisture_pct:.1f}%) and organic/recyclable components support efficient thermal gasification."
        elif recommended == "Recycling":
            reasoning = f"High fraction of recyclables ({recyclable_pct:.1f}%) encourages sorting and mechanical material recycling."
        else:
            reasoning = f"Inert or high hazardous materials ({hazardous_pct:.1f}%) suggest secure landfill disposal."
            
        return {
            "recommendation": recommended,
            "reasoning": reasoning,
            "suitability_scores": scores
        }

    @staticmethod
    def estimate_energy_potential(weight_tons, organic_pct, recyclable_pct, hazardous_pct, moisture_pct):
        """
        Estimates energy recovery yield potential.
        """
        # 1. Thermal Drying Requirements
        target_moisture = 20.0
        if moisture_pct > target_moisture:
            water_to_evaporate = weight_tons * (moisture_pct - target_moisture) / 100.0
            drying_energy = water_to_evaporate * 780.0  # 780 kWh per ton of water
        else:
            water_to_evaporate = 0.0
            drying_energy = 0.0
            
        # 2. Biomethanation Yield
        wet_organic_tons = weight_tons * (organic_pct / 100.0)
        dry_organic_tons = wet_organic_tons * (1 - moisture_pct / 100.0)
        # 1 dry ton organic yields ~210 m3 of methane (CH4)
        methane_m3 = dry_organic_tons * 210.0
        # Methane = 9.97 kWh/m3, 38% electrical conversion efficiency
        electricity_biogas = methane_m3 * 9.97 * 0.38
        
        # 3. Waste-to-Energy Combustion Yield
        lhv_kcal_kg = WasteAnalytics.estimate_calorific_value(organic_pct, recyclable_pct, hazardous_pct, moisture_pct)
        total_energy_kcal = (weight_tons * 1000.0) * lhv_kcal_kg
        total_energy_kwh = total_energy_kcal * 0.001163
        # 24% efficiency for state-of-the-art grate combustion WtE
        electricity_thermal = total_energy_kwh * 0.24
        
        # 4. Compost yield: 30% of dry organic weight
        compost_output_tons = dry_organic_tons * 0.32
        
        # 5. RDF yield: 65% of dry combustibles
        dry_recyclable_tons = (weight_tons * (recyclable_pct / 100.0)) * (1 - moisture_pct / 100.0)
        rdf_potential_tons = (dry_recyclable_tons + dry_organic_tons * 0.4) * 0.65
        
        return {
            "electricity_thermal_kwh": round(electricity_thermal, 2),
            "methane_m3": round(methane_m3, 2),
            "electricity_biogas_kwh": round(electricity_biogas, 2),
            "water_to_evaporate_tons": round(water_to_evaporate, 2),
            "drying_energy_required_kwh": round(drying_energy, 2),
            "compost_output_tons": round(compost_output_tons, 2),
            "rdf_potential_tons": round(rdf_potential_tons, 2)
        }

    @staticmethod
    def calculate_carbon_offset(weight_tons, organic_pct, electricity_kwh, distance_km):
        """
        Calculates Net Carbon Offset in kg of CO2 equivalent (CO2e).
        1. Landfill Methane Avoidance: Diverting organics avoids landfill anaerobic decay
           (approx 1400 kg CO2e offset per organic ton).
        2. Fossil Fuel (Coal) displacement: Electricity offset (approx 0.9 kg CO2 per kWh in India).
        3. Transit Emissions (penalty): Emissions from hauling waste (approx 0.12 kg CO2 per ton-km).
        """
        organic_mass_tons = weight_tons * (organic_pct / 100.0)
        co2_landfill_avoided = organic_mass_tons * 1400.0
        co2_coal_displaced = electricity_kwh * 0.9
        co2_transit_emitted = weight_tons * distance_km * 0.12
        
        net_offset = co2_landfill_avoided + co2_coal_displaced - co2_transit_emitted
        return round(net_offset, 2)

    @staticmethod
    def predict_waste_generation(zone_name):
        """
        AI Waste Generation Forecasting: Predicts waste tonnage generated in a Chennai zone
        for the upcoming 7 days based on seasonal models, population, and weekday indexes.
        """
        # Map Chennai zones to population factor multipliers
        zone_factors = {
            "Zone 1 (Kathivakkam)": 1.2,
            "Zone 9 (Teynampet)": 1.8,
            "Zone 10 (Kodambakkam)": 2.1,
            "Zone 13 (Adyar)": 1.6,
            "Zone 6 (Thiru-Vi-Ka Nagar)": 1.5
        }
        
        factor = zone_factors.get(zone_name, 1.5)
        
        # Base daily generation ~ 80 tons per factor unit
        base_tons = 75.0 * factor
        
        predictions = []
        today = datetime.now()
        
        for d in range(7):
            future_date = today + timedelta(days=d)
            # Weekend variation (higher commercial waste in Chennai on Fri-Sat-Sun)
            weekday = future_date.weekday()
            day_mult = 1.15 if weekday in [4, 5, 6] else 0.95
            
            # Seasonal variation (June-August is southwest monsoon, slightly lower collection but heavier mass due to moisture)
            month = future_date.month
            season_mult = 1.12 if month in [6, 7, 8] else 1.0
            
            # Simulating forecasting model predictions with slight random variations
            noise = np.random.normal(0, 3.0)
            predicted_tons = (base_tons * day_mult * season_mult) + noise
            predictions.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "day": future_date.strftime("%a"),
                "predicted_tons": round(max(10.0, predicted_tons), 2)
            })
            
        return predictions

    @staticmethod
    def calculate_business_value_metrics(total_weight_tons, total_distance_km, total_co2_offset_kg, total_energy_kwh):
        """
        Calculates business and commercial metrics for municipal deployment:
        - Monthly Savings (INR)
        - Fuel Cost Reduction (INR)
        - Fuel Saved (Liters)
        - Carbon reduction credits
        - Higher WtE efficiency benefit
        - Revenue Increase
        - ROI and Payback Period
        """
        # Baseline (Non-optimized logistics):
        # - Vehicles haul waste to the nearest landfill, average distance ~25km, fuel efficiency 2.5 km/l.
        # - Fuel cost is Rs. 95/liter.
        # - Tipping fees paid at landfill instead of recovering value.
        # Optimized route has 25% average distance reduction.
        
        non_opt_distance = total_distance_km * 1.33  # baseline is 33% longer without quantum optimization
        fuel_saved_liters = (non_opt_distance - total_distance_km) / 3.0 # 3.0 km per liter
        fuel_savings_inr = fuel_saved_liters * 95.0
        
        # Diversion from landfill saves Rs. 500/ton tipping fee
        tipping_fee_savings = total_weight_tons * 500.0
        
        # Energy sales revenue (average tariff of Rs 7.5/kWh across grid feeds)
        energy_revenue = total_energy_kwh * 7.5
        
        # Recyclables material sales (Assume 25% recyclables, recovered at Rs. 5,500/ton with 80% sorting yield)
        recyclable_sales = total_weight_tons * 0.25 * 0.80 * 5500.0
        
        # Carbon Credit Revenue: Rs. 1.20 per kg CO2e
        carbon_revenue = max(0.0, total_co2_offset_kg) * 1.20
        
        total_monthly_benefits = fuel_savings_inr + tipping_fee_savings + energy_revenue + recyclable_sales + carbon_revenue
        
        # Investment details (Hardware: ESP32 grids, LoRa gateways, Software: Quantum and AI server deployment)
        # Assuming typical municipality deployment cost of Rs. 4,50,00,000 (4.5 Crore INR)
        initial_investment_inr = 45000000.0
        annual_maintenance_inr = 4500000.0
        
        # Annual benefits (Benefits scale up to daily collections of ~3500 tons across Chennai)
        # Scaling factor: our database tracks a simulation sample. Let's scale to a full municipal system.
        # Chennai generates ~5000 tons/day. If platform optimizes 3500 tons/day, we scale sample by a factor of 100 for annual analysis.
        annual_savings_scaled = total_monthly_benefits * 12.0 * 20.0 # scale factor of 20
        net_annual_profit = annual_savings_scaled - annual_maintenance_inr
        
        roi_pct = (net_annual_profit / initial_investment_inr) * 100.0 if initial_investment_inr > 0 else 0
        payback_period_years = initial_investment_inr / net_annual_profit if net_annual_profit > 0 else 99
        
        # Market details
        market_size_india = "USD 3.2 Billion (Municipal Waste Management Market by 2030)"
        commercialization = "SaaS Platform licensing to Municipal Corporations (Greater Chennai Corp) + Revenue share from Waste-to-Energy and Recyclables."
        roadmap = "Phase 1: Pilot in Zones 9 & 10 (Months 1-3) | Phase 2: Scale to 15 Zones (Months 4-6) | Phase 3: Commercial WtE plant integration (Months 7-12)."
        
        return {
            "fuel_saved_liters": round(fuel_saved_liters, 2),
            "fuel_savings_inr": round(fuel_savings_inr, 2),
            "tipping_fee_savings_inr": round(tipping_fee_savings, 2),
            "energy_revenue_inr": round(energy_revenue, 2),
            "recyclable_sales_inr": round(recyclable_sales, 2),
            "carbon_revenue_inr": round(carbon_revenue, 2),
            "total_monthly_savings_inr": round(total_monthly_benefits, 2),
            "scaled_annual_savings_inr": round(annual_savings_scaled, 2),
            "roi_pct": round(roi_pct, 2),
            "payback_period_years": round(payback_period_years, 2),
            "market_size": market_size_india,
            "commercialization": commercialization,
            "roadmap": roadmap
        }
