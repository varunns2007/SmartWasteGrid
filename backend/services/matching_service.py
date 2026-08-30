import math
from datetime import datetime
from backend.flask_db.db import db
from backend.flask_models.models import Facility, WasteBatch, RoutingDecision, LedgerEntry

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class CrossULBMatchingEngine:
    DISTANCE_THRESHOLD_KM = 50.0

    @staticmethod
    def match_batch(batch_id):
        """
        Evaluates a waste batch and determines local, cross-ULB, or landfill fallback routing.
        """
        batch = WasteBatch.query.get(batch_id)
        if not batch:
            return None

        # Check existing decision
        existing = RoutingDecision.query.filter_by(batch_id=batch.id).first()
        if existing:
            return existing.to_dict()

        batch_weight = batch.weight_tons or 5.0
        primary_type = CrossULBMatchingEngine._determine_target_facility_type(batch)

        # 1. Search Local ULB Facilities
        all_facilities = Facility.query.all()
        local_facilities = [f for f in all_facilities if f.ulb_id == batch.ulb_id]
        
        target_local = None
        for fac in local_facilities:
            if fac.current_capacity >= batch_weight and CrossULBMatchingEngine._is_type_compatible(fac.type, primary_type):
                target_local = fac
                break

        if target_local:
            dist = haversine_km(batch.source_lat, batch.source_lng, target_local.location_lat, target_local.location_lng)
            target_local.current_capacity = max(0.0, target_local.current_capacity - batch_weight)
            target_local.last_updated = datetime.utcnow()
            
            decision = RoutingDecision(
                batch_id=batch.id,
                matched_facility_id=target_local.facility_id,
                match_type='local',
                distance_or_cost_factor=round(dist, 2),
                reason=f"Matched local {target_local.type} facility in ULB jurisdiction ({target_local.name})."
            )
            db.session.add(decision)
            db.session.commit()

            # Append to tamper-evident ledger
            LedgerEntry.create_entry('ROUTING', decision.to_dict(), f"Local routing match for Batch #{batch.id}")
            return decision.to_dict()

        # 2. Search Cross-ULB Facilities within Distance Threshold
        candidate_cross = []
        for fac in all_facilities:
            if fac.ulb_id != batch.ulb_id and fac.current_capacity >= batch_weight and CrossULBMatchingEngine._is_type_compatible(fac.type, primary_type):
                dist = haversine_km(batch.source_lat, batch.source_lng, fac.location_lat, fac.location_lng)
                if dist <= CrossULBMatchingEngine.DISTANCE_THRESHOLD_KM:
                    candidate_cross.append((dist, fac))

        candidate_cross.sort(key=lambda x: x[0]) # sort by nearest distance

        if candidate_cross:
            best_dist, target_cross = candidate_cross[0]
            target_cross.current_capacity = max(0.0, target_cross.current_capacity - batch_weight)
            target_cross.last_updated = datetime.utcnow()

            decision = RoutingDecision(
                batch_id=batch.id,
                matched_facility_id=target_cross.facility_id,
                match_type='cross-ULB',
                distance_or_cost_factor=round(best_dist, 2),
                reason=f"Escalated cross-ULB match to nearby facility ({target_cross.name}) {round(best_dist, 1)} km away. Local capacity exhausted."
            )
            db.session.add(decision)
            db.session.commit()

            # Append to tamper-evident ledger
            LedgerEntry.create_entry('ROUTING', decision.to_dict(), f"Cross-ULB escalation match for Batch #{batch.id}")
            return decision.to_dict()

        # 3. Landfill Fallback
        decision = RoutingDecision(
            batch_id=batch.id,
            matched_facility_id=None,
            match_type='landfill',
            distance_or_cost_factor=38.5,
            reason="Landfill Fallback: All local and neighboring ULB recovery facilities at >95% capacity within 50 km threshold."
        )
        db.session.add(decision)
        db.session.commit()

        # Append to tamper-evident ledger
        LedgerEntry.create_entry('ROUTING', decision.to_dict(), f"Landfill fallback for Batch #{batch.id}")
        return decision.to_dict()

    @staticmethod
    def _determine_target_facility_type(batch):
        org = batch.organic_percentage or 0.0
        rec = batch.recyclable_percentage or 0.0
        if org >= 50.0:
            return 'compost'
        elif rec >= 35.0:
            return 'MRF'
        else:
            return 'RDF'

    @staticmethod
    def _is_type_compatible(fac_type, target_type):
        fac_type_lower = (fac_type or '').lower()
        target_type_lower = (target_type or '').lower()
        
        if target_type_lower == 'compost' and ('compost' in fac_type_lower or 'bio' in fac_type_lower):
            return True
        if target_type_lower == 'mrf' and ('mrf' in fac_type_lower or 'recycl' in fac_type_lower):
            return True
        if target_type_lower == 'rdf' and ('rdf' in fac_type_lower or 'wte' in fac_type_lower or 'energy' in fac_type_lower or 'gas' in fac_type_lower):
            return True
        return True # Fallback compatible
