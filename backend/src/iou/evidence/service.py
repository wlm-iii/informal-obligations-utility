"""Durable upload intents, immutable objects, and immediate logical removal.

No provider request runs while a database lock/transaction is held. Tombstones
remain discoverable for cleanup even if a worker uploads after a concurrent removal.
"""

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from iou.auth import Identity
from iou.config import get_settings
from iou.evidence import images
from iou.evidence.models import Evidence
from iou.evidence.schemas import EvidenceCreate, EvidenceRead, SignedEvidenceURL
from iou.evidence.storage import StorageUnavailable, get_storage
from iou.ledger import service as ledger
from iou.ledger.corrections import event_for_owner
from iou.ledger.models import Audit


def evidence_for_owner(session: Session, owner: UUID, evidence_id: UUID) -> Evidence:
    row = session.scalar(
        select(Evidence)
        .where(
            Evidence.id == evidence_id,
            Evidence.owner_id == owner,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Evidence not found.")
    return row


def create_intent(
    session: Session, owner: UUID, loan_id: UUID, body: EvidenceCreate
) -> EvidenceRead:
    ledger.loan_for_owner(session, owner, loan_id)
    if body.event_id is not None:
        event_for_owner(session, owner, loan_id, body.event_id)
    storage = get_storage()  # Configuration only, no remote I/O under the mutation lock.
    now = ledger.now_utc()
    row = Evidence(
        id=uuid4(),
        owner_id=owner,
        loan_id=loan_id,
        state="pending",
        bucket=storage.bucket,
        storage_origin=storage.origin,
        created_at=now,
        expires_at=now + timedelta(hours=24),
        **body.model_dump(),
    )
    session.add(row)
    session.flush()
    return EvidenceRead.model_validate(row)


def upload_preflight(session: Session, owner: UUID, evidence_id: UUID, content_type: str):
    row = evidence_for_owner(session, owner, evidence_id)
    if row.state == "removed":
        raise HTTPException(409, "Removed evidence cannot be uploaded.")
    if row.state != "ready" and ledger.utc(row.expires_at) <= ledger.now_utc():
        raise HTTPException(409, "Upload intent has expired; create a new one.")
    if content_type != row.content_type:
        raise HTTPException(422, "Content-Type must match the upload intent.")
    target = (row.bucket, row.storage_origin)
    session.rollback()  # Release the connection before streaming/decoding the body.
    return target


def mark_removed(session: Session, row: Evidence, reason: str, actor: str):
    now = ledger.now_utc()
    row.state = "removed"
    row.removed_at = now
    session.add(
        Audit(
            id=uuid4(),
            owner_id=row.owner_id,
            loan_id=row.loan_id,
            action="evidence_removed",
            actor=actor,
            reason=reason,
            event_id=row.event_id,
            evidence_id=row.id,
            effective_at=now,
            recorded_at=now,
        )
    )
    session.flush()


def remove(session: Session, owner: UUID, evidence_id: UUID, reason: str) -> EvidenceRead:
    row = evidence_for_owner(session, owner, evidence_id)
    if row.state == "removed":
        raise HTTPException(409, "Evidence has already been removed.")
    mark_removed(session, row, reason, "owner")
    return EvidenceRead.model_validate(row)


def upload(
    session: Session,
    user: Identity,
    evidence_id: UUID,
    data: bytes,
    content_type: str,
) -> EvidenceRead:
    target = upload_preflight(session, user.id, evidence_id, content_type)
    storage = get_storage(*target)
    image = images.normalize(data, content_type)
    ledger.lock_owner(session, user)
    row = evidence_for_owner(session, user.id, evidence_id)
    if row.state == "removed" or (
        row.state != "ready" and ledger.utc(row.expires_at) <= ledger.now_utc()
    ):
        raise HTTPException(409, "Upload intent is no longer active.")
    if row.original_sha256 is not None and (
        row.original_sha256 != image.original_sha256 or row.sha256 != image.sha256
    ):
        raise HTTPException(
            409, "This intent is reserved for a different file; create a new intent."
        )
    if row.state == "ready":
        result = EvidenceRead.model_validate(row)
        session.rollback()
        return result
    if row.state == "pending":
        extension = "jpg" if content_type == "image/jpeg" else "png"
        row.object_path = f"{user.id}/{row.loan_id}/{row.id}/{image.sha256}.{extension}"
        row.original_sha256 = image.original_sha256
        row.sha256 = image.sha256
        row.original_size_bytes = len(data)
        row.size_bytes = len(image.data)
        row.width, row.height = image.width, image.height
        row.state = "uploading"
    path = row.object_path
    session.commit()  # Durable reference BEFORE any object can exist remotely.
    try:
        storage.upload(path, image.data, content_type)
    except StorageUnavailable:
        raise HTTPException(
            503, "Evidence storage is temporarily unavailable; retry the same file."
        ) from None
    ledger.lock_owner(session, user)
    row = evidence_for_owner(session, user.id, evidence_id)
    if row.state == "removed" or (
        row.state != "ready" and ledger.utc(row.expires_at) <= ledger.now_utc()
    ):
        if row.state != "removed":
            mark_removed(session, row, "Upload intent expired", "system")
        session.commit()
        try:
            storage.delete(path)
        except StorageUnavailable:
            pass  # The durable tombstone is still queued for cleanup.
        raise HTTPException(409, "Upload was removed or expired before completion.")
    if row.state != "ready":
        now = ledger.now_utc()
        row.state = "ready"
        row.uploaded_at = now
        session.add(
            Audit(
                id=uuid4(),
                owner_id=user.id,
                loan_id=row.loan_id,
                action="evidence_added",
                actor="owner",
                evidence_id=row.id,
                event_id=row.event_id,
                effective_at=now,
                recorded_at=now,
            )
        )
        session.flush()
    result = EvidenceRead.model_validate(row)
    session.commit()
    return result


def signed_url(session: Session, user: Identity, evidence_id: UUID) -> SignedEvidenceURL:
    row = evidence_for_owner(session, user.id, evidence_id)
    if row.state != "ready":
        raise HTTPException(409, "Only ready evidence can be viewed.")
    path, bucket, origin = row.object_path, row.bucket, row.storage_origin
    session.rollback()
    seconds = get_settings().evidence_signed_url_seconds
    expires = ledger.now_utc() + timedelta(seconds=seconds)
    try:
        url = get_storage(bucket, origin).signed_url(path, seconds)
    except StorageUnavailable:
        raise HTTPException(503, "Evidence storage is temporarily unavailable.") from None
    # Removal during the provider request must not issue a new viewing capability.
    ledger.lock_owner(session, user)
    row = evidence_for_owner(session, user.id, evidence_id)
    if row.state != "ready":
        raise HTTPException(409, "Evidence was removed while preparing the link.")
    session.rollback()
    return SignedEvidenceURL(url=url, expires_at=expires)
