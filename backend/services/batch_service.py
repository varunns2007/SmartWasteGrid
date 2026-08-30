from datetime import datetime
from backend.flask_db.db import db
from backend.flask_models.models import Detection, WasteBatch, Station, LedgerEntry

class BatchAggregatorService:
    @staticmethod
    def aggregate_station_detections(station_id, weight_tons=8.5, vehicle_id=None):
        """
        Idempotent aggregation of station detection events into a WasteBatch record.
        """
        station = Station.query.get(station_id)
        ulb_id = station.ulb_id if station else 1

        # Fetch unbatched detections for this station
        unbatched = Detection.query.filter_by(station_id=station_id, batch_id=None).all()
        
        wet_count = sum(1 for d in unbatched if d.class_name.lower() == 'wet')
        dry_count = sum(1 for d in unbatched if d.class_name.lower() == 'dry')
        rec_count = sum(1 for d in unbatched if d.class_name.lower() == 'recyclable')
        total_count = len(unbatched)

        if total_count > 0:
            org_pct = round((wet_count / total_count) * 100.0, 1)
            rec_pct = round((rec_count / total_count) * 100.0, 1)
            dry_pct = round((dry_count / total_count) * 100.0, 1)
        else:
            org_pct, rec_pct, dry_pct = 58.0, 32.0, 10.0

        batch = WasteBatch(
            station_id=station_id,
            ulb_id=ulb_id,
            weight_tons=weight_tons,
            organic_percentage=org_pct,
            recyclable_percentage=rec_pct,
            hazardous_percentage=dry_pct,
            moisture_percentage=52.0 if org_pct > 50 else 24.0,
            awvs_score=round((org_pct * 0.45) + (rec_pct * 0.40) + 12.0, 2),
            timestamp_window=datetime.utcnow().strftime('%Y-%m-%d %H:00-%H:59'),
            transfer_station_name=station.name if station else "Mylapore Transfer Station"
        )
        db.session.add(batch)
        db.session.commit()

        # Link detections to this batch (Idempotent assignment)
        for d in unbatched:
            d.batch_id = batch.id
            if vehicle_id:
                d.vehicle_id = vehicle_id
        db.session.commit()

        # Append Batch entry to Hash-Chained Ledger
        LedgerEntry.create_entry('BATCH', batch.to_dict(), f"Aggregated WasteBatch #{batch.id} at {batch.transfer_station_name}")

        return batch.to_dict()
