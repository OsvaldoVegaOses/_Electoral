import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datetime import datetime, timezone

from app.auth import log_audit, verify_audit_checkpoint, verify_audit_log_chain
from app.models import AuditChainHead, AuditLog


DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    if os.getenv("REQUIRE_S2_SERVICES") == "1":
        raise RuntimeError("DATABASE_URL PostgreSQL es obligatoria en integración.")
    pytest.skip("S2-D requiere PostgreSQL 16 configurado en DATABASE_URL", allow_module_level=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def test_parallel_audit_writers_build_one_linear_chain():
    marker = str(uuid4())
    actions = [f"S2-D concurrent {marker} {index}" for index in range(100)]

    def write(action):
        with SessionLocal() as db:
            log_audit(db, accion=action, usuario="s2-d-test")

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(write, actions))

    with SessionLocal() as db:
        matching = (
            db.query(AuditLog)
            .filter(AuditLog.accion.in_(actions))
            .order_by(AuditLog.id.asc())
            .all()
        )
        assert len(matching) == 100
        assert verify_audit_log_chain(db)["integro"] is True
        for previous, current in zip(matching, matching[1:]):
            assert current.prev_hash == previous.record_hash

        head = db.query(AuditChainHead).filter_by(id=1).one()
        last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert head.last_log_id == last_log.id
        assert head.head_hash == last_log.record_hash

        artifact_fields = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_records": db.query(AuditLog).count(),
            "last_record_id": last_log.id,
            "head_hash": last_log.record_hash,
        }
        canonical = json.dumps(artifact_fields, sort_keys=True, separators=(",", ":"))
        artifact = {
            **artifact_fields,
            "digest_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }
        assert verify_audit_checkpoint(db, artifact)["integro"] is True
        artifact["total_records"] += 1
        assert verify_audit_checkpoint(db, artifact)["integro"] is False

        head.head_hash = "f" * 64
        db.commit()
        assert verify_audit_log_chain(db)["integro"] is False
        head.head_hash = last_log.record_hash
        db.commit()


def test_audit_rollback_does_not_advance_chain_head():
    marker = f"S2-D rollback {uuid4()}"
    with SessionLocal() as db:
        head_before = db.query(AuditChainHead).filter_by(id=1).one()
        hash_before = head_before.head_hash
        last_id_before = head_before.last_log_id

        log_audit(db, accion=marker, usuario="s2-d-test", commit=False)
        db.rollback()

    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(accion=marker).count() == 0
        head_after = db.query(AuditChainHead).filter_by(id=1).one()
        assert head_after.head_hash == hash_before
        assert head_after.last_log_id == last_id_before
