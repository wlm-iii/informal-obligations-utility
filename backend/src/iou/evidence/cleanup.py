"""One-shot orphan cleanup. Dry-run by default; never run timers in API workers.

Run with the backend on PYTHONPATH: python -m iou.evidence.cleanup --apply --limit 100
Tombstones are retained and revisited hourly, so even late provider writes remain
tracked and eventually removed. Ready evidence is never expired by this command.
"""

import argparse
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from iou.database import get_engine
from iou.evidence.models import Evidence
from iou.evidence.service import mark_removed
from iou.evidence.storage import StorageUnavailable, get_storage
from iou.ledger import service as ledger
from iou.profiles import Profile


def candidates(now):
    return or_(
        and_(Evidence.state.in_(("pending", "uploading")), Evidence.expires_at <= now),
        and_(
            Evidence.state == "removed",
            or_(
                Evidence.cleanup_attempted_at.is_(None),
                Evidence.cleanup_attempted_at <= now - timedelta(hours=1),
            ),
        ),
    )


def prepare(engine, owner_id, evidence_id):
    now = ledger.now_utc()
    with Session(engine) as session:
        session.scalar(select(Profile).where(Profile.id == owner_id).with_for_update())
        row = session.scalar(
            select(Evidence).where(
                Evidence.id == evidence_id,
                Evidence.owner_id == owner_id,
                candidates(now),
            )
        )
        if row is None:
            return None
        if row.state != "removed":
            mark_removed(session, row, "Upload intent expired", "system")
        row.cleanup_attempted_at = now
        path, bucket, origin = row.object_path, row.bucket, row.storage_origin
        if path is None:
            row.cleaned_at = now
        session.commit()
        return (owner_id, evidence_id, path, bucket, origin)


def cleanup_batch(engine, *, apply=False, limit=100):
    if not 1 <= limit <= 1000:
        raise ValueError("Cleanup limit must be between 1 and 1000.")
    now = ledger.now_utc()
    with Session(engine) as session:
        rows = session.execute(
            select(Evidence.owner_id, Evidence.id)
            .where(candidates(now))
            .order_by(
                func.coalesce(Evidence.cleanup_attempted_at, Evidence.created_at),
                Evidence.id,
            )
            .limit(limit)
        ).all()
    result = {
        "candidates": len(rows),
        "cleaned": 0,
        "failed": 0,
        "skipped": 0,
        "dry_run": not apply,
    }
    if not apply:
        return result
    for owner_id, evidence_id in rows:
        work = prepare(engine, owner_id, evidence_id)
        if work is None:
            result["skipped"] += 1
            continue
        _, _, path, bucket, origin = work
        if path is not None:
            try:
                get_storage(bucket, origin).delete(path)
            except (StorageUnavailable, HTTPException):
                result["failed"] += 1
                continue
            with Session(engine) as session:
                session.scalar(select(Profile).where(Profile.id == owner_id).with_for_update())
                row = session.get(Evidence, evidence_id)
                if row is not None and row.owner_id == owner_id and row.state == "removed":
                    row.cleaned_at = ledger.now_utc()
                    session.commit()
        result["cleaned"] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Expire intents and delete tombstoned objects"
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    try:
        result = cleanup_batch(get_engine(), apply=args.apply, limit=args.limit)
    except (SQLAlchemyError, ValueError):
        print("Cleanup failed. Check database configuration and migrations; credentials withheld.")
        return 1
    print(result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
