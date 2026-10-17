from datetime import timedelta
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ledger import NOW, new_friend, new_loan, post
from test_ledger import api as api

from iou.api import app
from iou.config import Settings
from iou.evidence import cleanup, service
from iou.evidence.images import LimitedOutput
from iou.evidence.models import MAX_BYTES, Evidence
from iou.evidence.storage import StorageUnavailable
from iou.ledger import pagination as cursors
from iou.ledger import service as ledger
from iou.ledger.models import Audit


class FakeStorage:
    def __init__(self):
        self.files = {}
        self.bucket = "iou-evidence"
        self.origin = "https://storage.example.test"
        self.uploads = 0
        self.deletes = 0
        self.signs = 0
        self.fail_upload = False
        self.fail_after_upload = False
        self.fail_delete = False
        self.on_upload = None
        self.on_sign = None

    def upload(self, path, data, content_type):
        self.uploads += 1
        if self.fail_upload:
            raise StorageUnavailable
        if self.on_upload:
            self.on_upload()
        if path in self.files and self.files[path] != data:
            raise StorageUnavailable
        self.files[path] = data
        if self.fail_after_upload:
            raise StorageUnavailable

    def signed_url(self, path, seconds):
        self.signs += 1
        if self.on_sign:
            self.on_sign()
        assert 30 <= seconds <= 300
        return "https://storage.example.test/signed?token=test-only"

    def delete(self, path):
        self.deletes += 1
        if self.fail_delete:
            raise StorageUnavailable
        self.files.pop(path, None)


@pytest.fixture
def proof(api, monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(service, "get_storage", lambda *args: fake)
    monkeypatch.setattr(cleanup, "get_storage", lambda *args: fake)
    api.storage = fake
    return api


def image_bytes(format="PNG", size=(3, 2), metadata=False):
    output = BytesIO()
    image = Image.new("RGB", size, (10, 20, 30))
    options = {}
    if metadata and format == "PNG":
        info = PngImagePlugin.PngInfo()
        info.add_text("location", "private GPS metadata")
        options["pnginfo"] = info
    if metadata and format == "JPEG":
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = "private GPS metadata"
        options["exif"] = exif
    image.save(output, format=format, **options)
    image.close()
    return output.getvalue()


def intent(api, loan=None, key=None, **changes):
    if loan is None:
        loan = new_loan(api, new_friend(api)["id"])
    response = post(
        api,
        f"/loans/{loan['id']}/evidence",
        {
            "filename": "proof.png",
            "content_type": "image/png",
            **changes,
        },
        key,
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(api, row, data=None, content_type=None):
    return api.client.put(
        f"/evidence/{row['id']}/content",
        content=data if data is not None else image_bytes(),
        headers={"Content-Type": content_type or row["content_type"]},
    )


def object_path(api, row):
    with Session(api.engine) as session:
        return session.get(Evidence, UUID(row["id"])).object_path


def test_complete_image_flow_strips_metadata_and_tracks_history(proof):
    api = proof
    row = intent(api, filename="../../proof.png", note="Screenshot")
    assert row["filename"] == "proof.png" and row["state"] == "pending"
    assert "object_path" not in row
    raw = image_bytes(metadata=True) + b"trailing non-image data"
    ready = upload(api, row, raw)
    assert ready.status_code == 200
    data = ready.json()
    assert data["state"] == "ready"
    assert data["original_sha256"] != data["sha256"]
    assert data["width"] == 3 and data["height"] == 2
    path = object_path(api, row)
    assert path.startswith(f"{api.user.id}/{row['loan_id']}/{row['id']}/")
    stored = api.storage.files[path]
    assert b"private GPS metadata" not in stored and b"trailing non-image" not in stored
    assert Image.open(BytesIO(stored)).format == "PNG"
    assert upload(api, row, raw).json() == data
    assert api.storage.uploads == 1
    view = api.client.post(f"/evidence/{row['id']}/view-url")
    assert view.status_code == 200
    assert view.headers["cache-control"] == "no-store"
    assert "test-only" in view.json()["url"]
    assert api.client.get(f"/evidence/{row['id']}").json()["state"] == "ready"
    loan = api.client.get(f"/loans/{row['loan_id']}").json()
    history = api.client.get(f"/friends/{loan['friend_id']}/history").json()["items"]
    assert next(r for r in history if r["action"] == "evidence_added")["evidence_id"] == row["id"]


def test_jpeg_orientation_and_exif_are_normalized(proof):
    row = intent(proof, filename="photo.jpg", content_type="image/jpeg")
    ready = upload(proof, row, image_bytes("JPEG", metadata=True))
    assert ready.status_code == 200
    assert (ready.json()["width"], ready.json()["height"]) == (2, 3)
    normalized = Image.open(BytesIO(proof.storage.files[object_path(proof, row)]))
    assert not normalized.getexif()


@pytest.mark.parametrize(
    "data", [b"<svg><script>alert(1)</script></svg>", b"not an image", image_bytes()[:-10]]
)
def test_invalid_images_never_reach_storage(proof, data):
    row = intent(proof)
    assert upload(proof, row, data).status_code == 422
    assert proof.storage.uploads == 0
    assert proof.client.get(f"/evidence/{row['id']}").json()["state"] == "pending"


def test_type_mismatch_animation_dimensions_and_size_limits(proof):
    row = intent(proof)
    assert upload(proof, row, image_bytes("JPEG")).status_code == 422
    assert upload(proof, row, content_type="image/jpeg").status_code == 422
    assert upload(proof, row, image_bytes(size=(8001, 1))).status_code == 413
    assert upload(proof, row, b"x" * (MAX_BYTES + 1)).status_code == 413
    assert upload(proof, row, b"").status_code == 413
    animation = BytesIO()
    Image.new("RGB", (2, 2), "red").save(
        animation,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (2, 2), "blue")],
        duration=100,
    )
    assert upload(proof, row, animation.getvalue()).status_code == 422
    assert proof.storage.uploads == 0


def test_chunked_upload_is_bounded(proof):
    row = intent(proof)
    response = proof.client.put(
        f"/evidence/{row['id']}/content",
        content=(b"x" * 1024 * 1024 for _ in range(6)),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 413
    assert proof.storage.uploads == 0


def test_normalized_output_is_bounded():
    with pytest.raises(HTTPException) as error:
        LimitedOutput().write(b"x" * (MAX_BYTES + 1))
    assert error.value.status_code == 413


def test_storage_failure_reserves_file_for_retry_and_is_recoverable(proof):
    row = intent(proof)
    proof.storage.fail_after_upload = True
    response = upload(proof, row)
    assert response.status_code == 503
    assert proof.client.get(f"/evidence/{row['id']}").json()["state"] == "uploading"
    assert object_path(proof, row) in proof.storage.files
    assert upload(proof, row, image_bytes(size=(4, 4))).status_code == 409
    proof.storage.fail_after_upload = False
    assert upload(proof, row).json()["state"] == "ready"
    with Session(proof.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "evidence_added")
            )
            == 1
        )


def test_crash_after_provider_write_keeps_durable_reference(proof, monkeypatch):
    row = intent(proof)
    original = ledger.lock_owner
    calls = 0

    def crash_after_upload(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated worker crash")
        return original(*args)

    monkeypatch.setattr(ledger, "lock_owner", crash_after_upload)
    with pytest.raises(RuntimeError, match="worker crash"):
        upload(proof, row)
    assert object_path(proof, row) in proof.storage.files
    monkeypatch.setattr(ledger, "lock_owner", original)
    assert proof.client.get(f"/evidence/{row['id']}").json()["state"] == "uploading"
    assert upload(proof, row).json()["state"] == "ready"


def test_removal_during_upload_cannot_publish_and_cleanup_can_retry(proof, monkeypatch):
    row = intent(proof)

    def remove_during_upload():
        assert (
            post(proof, f"/evidence/{row['id']}/remove", {"reason": "Wrong screenshot"}).status_code
            == 201
        )

    proof.storage.on_upload = remove_during_upload
    proof.storage.fail_delete = True
    assert upload(proof, row).status_code == 409
    assert proof.client.get(f"/evidence/{row['id']}").json()["state"] == "removed"
    assert proof.client.post(f"/evidence/{row['id']}/view-url").status_code == 409
    result = cleanup.cleanup_batch(proof.engine, apply=True)
    assert result["failed"] == 1 and proof.storage.files
    proof.storage.fail_delete = False
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(hours=1))
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert not proof.storage.files


def test_remove_replay_blocks_links_and_preserves_audit(proof):
    row = intent(proof)
    upload(proof, row)
    key = uuid4()
    first = post(proof, f"/evidence/{row['id']}/remove", {"reason": "Personal information"}, key)
    assert first.status_code == 201
    assert (
        post(proof, f"/evidence/{row['id']}/remove", {"reason": "Personal information"}, key).json()
        == first.json()
    )
    assert upload(proof, row).status_code == 409
    assert proof.client.post(f"/evidence/{row['id']}/view-url").status_code == 409
    with Session(proof.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "evidence_removed")
            )
            == 1
        )
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert not proof.storage.files


def test_removal_during_signing_does_not_return_link(proof):
    row = intent(proof)
    upload(proof, row)
    proof.storage.on_sign = lambda: post(
        proof, f"/evidence/{row['id']}/remove", {"reason": "Private"}
    )
    response = proof.client.post(f"/evidence/{row['id']}/view-url")
    assert response.status_code == 409 and "test-only" not in response.text


def test_dry_run_expiration_and_ready_retention(proof, monkeypatch):
    pending = intent(proof)
    ready = intent(proof)
    upload(proof, ready)
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(hours=25))
    assert upload(proof, pending).status_code == 409
    dry = cleanup.cleanup_batch(proof.engine)
    assert dry["candidates"] == 1 and dry["dry_run"]
    assert proof.client.get(f"/evidence/{pending['id']}").json()["state"] == "pending"
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert proof.client.get(f"/evidence/{pending['id']}").json()["state"] == "removed"
    assert proof.client.get(f"/evidence/{ready['id']}").json()["state"] == "ready"
    assert proof.storage.files
    with Session(proof.engine) as session:
        audit = session.scalar(select(Audit).where(Audit.action == "evidence_removed"))
        assert audit.actor == "system"


def test_abandoned_provider_accepted_upload_is_expired_and_deleted(proof, monkeypatch):
    row = intent(proof)
    proof.storage.fail_after_upload = True
    assert upload(proof, row).status_code == 503
    assert proof.storage.files
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(hours=25))
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert not proof.storage.files
    state = proof.client.get(f"/evidence/{row['id']}").json()
    assert state["state"] == "removed" and state["cleaned_at"] is not None


def test_tombstones_reap_late_writes_after_successful_cleanup(proof, monkeypatch):
    row = intent(proof)
    upload(proof, row)
    path = object_path(proof, row)
    data = proof.storage.files[path]
    post(proof, f"/evidence/{row['id']}/remove", {"reason": "Remove"})
    cleanup.cleanup_batch(proof.engine, apply=True)
    proof.storage.files[path] = data  # A paused worker/provider completes after deletion.
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(hours=2))
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert not proof.storage.files


def test_evidence_owner_and_event_boundaries(proof):
    loan = new_loan(proof, new_friend(proof)["id"])
    event = post(proof, f"/loans/{loan['id']}/repayments", {"amount_cents": 1}).json()["event"]
    row = intent(proof, loan, event_id=event["id"])
    other_loan = new_loan(proof, new_friend(proof)["id"])
    invalid = post(
        proof,
        f"/loans/{other_loan['id']}/evidence",
        {"filename": "x.png", "content_type": "image/png", "event_id": event["id"]},
    )
    assert invalid.status_code == 404
    proof.user = type(proof.user)(uuid4(), None, "Other")
    assert proof.client.get(f"/evidence/{row['id']}").status_code == 404
    assert upload(proof, row).status_code == 404
    assert proof.client.post(f"/evidence/{row['id']}/view-url").status_code == 404
    assert post(proof, f"/evidence/{row['id']}/remove", {"reason": "X"}).status_code == 404
    assert proof.client.get(f"/loans/{loan['id']}/evidence").status_code == 404
    assert proof.storage.uploads == proof.storage.signs == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"filename": ".."},
        {"filename": "x\n.png"},
        {"content_type": "image/svg+xml"},
        {"object_path": "chosen/path"},
        {"owner_id": str(uuid4())},
    ],
)
def test_invalid_intent_metadata(proof, changes):
    loan = new_loan(proof, new_friend(proof)["id"])
    response = post(
        proof,
        f"/loans/{loan['id']}/evidence",
        {"filename": "x.png", "content_type": "image/png", **changes},
    )
    assert response.status_code == 422


def test_intent_retry_and_evidence_cursor(proof, monkeypatch):
    loan = new_loan(proof, new_friend(proof)["id"])
    key = uuid4()
    first = intent(proof, loan, key)
    assert intent(proof, loan, key) == first
    intent(proof, loan)
    intent(proof, loan)
    monkeypatch.setattr(
        cursors, "get_settings", lambda: Settings(_env_file=None, cursor_signing_key="x" * 32)
    )
    path = f"/loans/{loan['id']}/evidence"
    page = proof.client.get(path, params={"pagination": "cursor", "limit": 2}).json()
    rest = proof.client.get(path, params={"cursor": page["next_cursor"]}).json()
    assert len(page["items"]) == 2 and len(rest["items"]) == 1
    assert len({r["id"] for r in page["items"] + rest["items"]}) == 3


def test_bucket_changes_do_not_orphan_existing_objects(proof, monkeypatch):
    row = intent(proof)
    old = proof.storage
    new = FakeStorage()
    new.bucket = "new-proof-bucket"

    def factory(bucket=None, origin=None):
        if bucket is None:
            return new
        assert bucket == old.bucket and origin == old.origin
        return old

    monkeypatch.setattr(service, "get_storage", factory)
    monkeypatch.setattr(cleanup, "get_storage", factory)
    assert upload(proof, row).status_code == 200
    assert proof.client.post(f"/evidence/{row['id']}/view-url").status_code == 200
    post(proof, f"/evidence/{row['id']}/remove", {"reason": "Delete"})
    assert cleanup.cleanup_batch(proof.engine, apply=True)["cleaned"] == 1
    assert old.uploads == old.deletes == 1
    assert new.uploads == new.deletes == 0


def test_new_routes_require_auth_and_openapi_describes_binary_upload():
    with TestClient(app) as client:
        key = {"Idempotency-Key": str(uuid4())}
        loan_id, evidence_id = uuid4(), uuid4()
        assert (
            client.post(f"/loans/{loan_id}/void", json={"reason": "X"}, headers=key).status_code
            == 401
        )
        assert (
            client.post(
                f"/loans/{loan_id}/evidence",
                json={"filename": "x.png", "content_type": "image/png"},
                headers=key,
            ).status_code
            == 401
        )
        assert (
            client.put(
                f"/evidence/{evidence_id}/content",
                content=b"x",
                headers={"Content-Type": "image/png"},
            ).status_code
            == 401
        )
        assert client.post(f"/evidence/{evidence_id}/view-url").status_code == 401
        schema = client.get("/openapi.json").json()
        content = schema["paths"]["/evidence/{evidence_id}/content"]["put"]["requestBody"][
            "content"
        ]
        assert set(content) == {"image/png", "image/jpeg"}


def test_storage_disabled_fails_closed(proof, monkeypatch):
    def unavailable():
        raise HTTPException(503, "Evidence storage is not configured.")

    monkeypatch.setattr(service, "get_storage", unavailable)
    loan = new_loan(proof, new_friend(proof)["id"])
    response = post(
        proof, f"/loans/{loan['id']}/evidence", {"filename": "x.png", "content_type": "image/png"}
    )
    assert response.status_code == 503
