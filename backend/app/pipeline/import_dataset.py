"""Admin dataset import: data/ → CHANNEL + TELEMETRY_READING (REQ-1). Idempotent."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models import Channel, Satellite, TelemetryReading
from app.pipeline.dataset import anomaly_mask, load_channel, load_labels
from app.pipeline.fleet import build_fleet_channel_map
from app.pipeline.ingest import REPLAY_EPOCH

# Fallback used only when a channel has no entry in the per-channel map below
# (e.g. a caller passes a custom spacecraft-keyed map, as the tests do).
DEFAULT_SATELLITE_FOR_SPACECRAFT = {"SMAP": "SAT-001", "MSL": "SAT-002"}
CHUNK = 2000


def channel_pk(chan_id: str) -> str:
    return f"CHN-{chan_id}"


def import_dataset(
    db: Session,
    data_dir: Path | None = None,
    *,
    include_readings: bool = False,
    satellite_map: dict[str, str] | None = None,
) -> dict:
    """satellite_map may be keyed by dataset_chan_id (the ADR-004 fleet split,
    the default) or by spacecraft name (a coarser override, e.g. in tests);
    a channel is resolved against the per-channel key first."""
    data_dir = data_dir or settings.data_dir
    satellite_map = satellite_map or build_fleet_channel_map(data_dir)
    labels = load_labels(data_dir)
    created_channels = 0
    updated_channels = 0
    readings = 0

    for chan_id, label in labels.items():
        satellite_id = satellite_map.get(chan_id) or satellite_map.get(label.spacecraft)
        if satellite_id is None or db.get(Satellite, satellite_id) is None:
            continue
        pk = channel_pk(chan_id)
        row = db.get(Channel, pk)
        if row is None:
            db.add(
                Channel(
                    channel_id=pk,
                    satellite_id=satellite_id,
                    channel_name=chan_id,
                    dataset_chan_id=chan_id,
                    spacecraft=label.spacecraft,
                    description=f"{label.spacecraft} channel {chan_id}",
                )
            )
            created_channels += 1
        else:
            row.satellite_id = satellite_id
            row.dataset_chan_id = chan_id
            row.spacecraft = label.spacecraft
            updated_channels += 1

        if not include_readings:
            continue
        db.execute(delete(TelemetryReading).where(TelemetryReading.channel_id == pk))
        for split in ("train", "test"):
            series = load_channel(chan_id, split, data_dir)[:, 0]
            mask = anomaly_mask(label, len(series)) if split == "test" else None
            batch: list[TelemetryReading] = []
            for i, value in enumerate(series):
                batch.append(
                    TelemetryReading(
                        channel_id=pk,
                        timestamp=REPLAY_EPOCH + timedelta(seconds=i),
                        value=float(value),
                        split=split,
                        is_labeled_anomaly=bool(mask[i]) if mask is not None else False,
                    )
                )
                if len(batch) >= CHUNK:
                    db.add_all(batch)
                    readings += len(batch)
                    batch = []
            if batch:
                db.add_all(batch)
                readings += len(batch)
        db.flush()

    db.commit()
    imported = db.scalar(
        select(func.count()).select_from(Channel).where(Channel.dataset_chan_id.is_not(None))
    )
    return {
        "channelsCreated": created_channels,
        "channelsUpdated": updated_channels,
        "channels": int(imported or 0),
        "readings": readings,
        "includeReadings": include_readings,
    }


def channel_ids_for_satellite(db: Session, satellite_id: str) -> list[str]:
    rows = db.scalars(select(Channel).where(Channel.satellite_id == satellite_id)).all()
    return [row.dataset_chan_id for row in rows if row.dataset_chan_id]


if __name__ == "__main__":
    import argparse

    from app.core.db import SessionLocal

    parser = argparse.ArgumentParser(
        description="Import the SMAP/MSL dataset into CHANNEL (+ TELEMETRY_READING)."
    )
    parser.add_argument("--include-readings", action="store_true", help="also import TELEMETRY_READING rows")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = import_dataset(db, include_readings=args.include_readings)
    print(result)
