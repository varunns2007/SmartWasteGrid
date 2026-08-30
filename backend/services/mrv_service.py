import io
import csv
from datetime import datetime
from backend.flask_db.db import db
from backend.flask_models.models import MRVRecord, RoutingDecision, WasteBatch, LedgerEntry, Facility

class MRVService:
    # Carbon Emission Factors (EPA WARM & IPCC 2019 Methane Avoidance Baselines)
    # Note: These are estimated avoidance factors against a unmanaged tropical landfill baseline.
    ORGANIC_METHANE_AVOIDANCE_FACTOR = 1.18 # tCO2e avoided per ton organic waste diverted to compost/biomethanation
    RECYCLABLE_RECOVERY_FACTOR = 0.82       # tCO2e avoided per ton recyclable material recovered
    RDF_ENERGY_OFFSET_FACTOR = 0.45         # tCO2e avoided per ton RDF/WtE substituting fossil energy

    @staticmethod
    def calculate_and_record_mrv(routing_decision_id):
        """
        Calculates avoided CO2e for a routing decision and records it in MRVRecord and tamper-evident LedgerEntry.
        """
        decision = RoutingDecision.query.get(routing_decision_id)
        if not decision:
            return None

        # Check existing MRV record
        existing = MRVRecord.query.filter_by(routing_decision_id=decision.decision_id).first()
        if existing:
            return existing.to_dict()

        batch = WasteBatch.query.get(decision.batch_id)
        if not batch:
            return None

        if decision.match_type == 'landfill' or not decision.matched_facility_id:
            # Landfill fallback achieves 0.0 avoided emissions
            co2e_avoided = 0.0
            calc_method = "Landfill Fallback Baseline (0.0 tCO2e Avoided)"
        else:
            weight = batch.weight_tons or 5.0
            org_tons = weight * ((batch.organic_percentage or 60.0) / 100.0)
            rec_tons = weight * ((batch.recyclable_percentage or 30.0) / 100.0)
            dry_tons = max(0.0, weight - org_tons - rec_tons)

            co2e_avoided = (
                (org_tons * MRVService.ORGANIC_METHANE_AVOIDANCE_FACTOR) +
                (rec_tons * MRVService.RECYCLABLE_RECOVERY_FACTOR) +
                (dry_tons * MRVService.RDF_ENERGY_OFFSET_FACTOR)
            )
            calc_method = "IPCC 2019 Tier-1 Waste Methane Avoidance Factor + EPA WARM Recovery Offset"

        # Create Ledger Entry for MRV
        payload = {
            "batch_id": batch.id,
            "routing_decision_id": decision.decision_id,
            "match_type": decision.match_type,
            "weight_tons": batch.weight_tons,
            "co2e_avoided_tons": round(co2e_avoided, 3),
            "timestamp": datetime.utcnow().isoformat()
        }
        ledger_entry = LedgerEntry.create_entry('MRV_RECORD', payload, f"MRV Audit Record for Batch #{batch.id}")

        mrv = MRVRecord(
            batch_id=batch.id,
            routing_decision_id=decision.decision_id,
            estimated_co2e_avoided=round(co2e_avoided, 3),
            calculation_method=calc_method,
            ledger_hash_reference=ledger_entry.current_hash
        )
        db.session.add(mrv)
        db.session.commit()

        return mrv.to_dict()

    @staticmethod
    def get_carbon_impact_summary():
        mrv_records = MRVRecord.query.all()
        ledger_entries = LedgerEntry.query.order_by(LedgerEntry.entry_id.desc()).limit(30).all()
        
        total_co2e_avoided = sum(r.estimated_co2e_avoided for r in mrv_records)
        mrv_count = len(mrv_records)

        return {
            'total_co2e_avoided_tons': round(total_co2e_avoided, 2),
            'mrv_records_count': mrv_count,
            'calculation_baseline': "IPCC 2019 Methane Avoidance & EPA WARM Factors (Estimated Baseline)",
            'recent_mrv_records': [r.to_dict() for r in mrv_records[-15:]],
            'cryptographic_ledger': [l.to_dict() for l in ledger_entries],
            'last_synced': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def generate_auditor_csv_report():
        """
        Generates auditor-ready CSV report containing tamper-evident MRV cryptographic evidence.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "MRV_RECORD_ID",
            "BATCH_ID",
            "ULB_JURISDICTION",
            "FACILITY_MATCH",
            "MATCH_TYPE",
            "BATCH_WEIGHT_TONS",
            "ESTIMATED_CO2E_AVOIDED_TONS",
            "CALCULATION_METHOD",
            "PAYLOAD_HASH",
            "PREVIOUS_LEDGER_HASH",
            "CURRENT_LEDGER_HASH",
            "TIMESTAMP"
        ])

        mrv_records = MRVRecord.query.order_by(MRVRecord.record_id.asc()).all()
        for r in mrv_records:
            batch = r.batch
            decision = r.routing_decision
            ulb_name = batch.ulb.name if (batch and batch.ulb) else "GCC Zone 9 Teynampet"
            fac_name = decision.facility.name if (decision and decision.facility) else "Landfill Fallback"
            match_type = decision.match_type if decision else "N/A"
            weight = batch.weight_tons if batch else 0.0

            # Find matching ledger entry
            ledger = LedgerEntry.query.filter_by(current_hash=r.ledger_hash_reference).first()
            p_hash = ledger.payload_hash if ledger else "N/A"
            prev_hash = ledger.previous_hash if ledger else "N/A"
            curr_hash = r.ledger_hash_reference or "N/A"

            writer.writerow([
                r.record_id,
                r.batch_id,
                ulb_name,
                fac_name,
                match_type,
                weight,
                r.estimated_co2e_avoided,
                r.calculation_method,
                p_hash,
                prev_hash,
                curr_hash,
                r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else ''
            ])

        return output.getvalue()
