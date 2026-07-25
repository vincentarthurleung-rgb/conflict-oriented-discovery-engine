"""Source snapshot recovery requires actual historical request bytes."""
from __future__ import annotations

from .models import SourceRecoveryStatus, SourceSnapshotForensicRecovery
from ..identities import sha256_bytes, stable_identity


def recover_source_snapshot(snapshot_identity: str, *, request_bytes: bytes | None = None,
                            direct_reference: str | None = None,
                            deterministic_hash: str | None = None,
                            template_identity: str | None = None,
                            encoding: str | None = "utf-8",
                            newline_policy: str | None = "preserved") -> SourceSnapshotForensicRecovery:
    text = request_bytes.decode(encoding) if request_bytes is not None and encoding else None
    digest = sha256_bytes(request_bytes) if request_bytes is not None else None
    if request_bytes is not None and direct_reference:
        status, authoritative, algorithm = SourceRecoveryStatus.exact, True, None
    elif (
        request_bytes is not None and deterministic_hash == digest and template_identity
        and encoding and newline_policy
    ):
        status, authoritative, algorithm = SourceRecoveryStatus.deterministic, True, "request_reconstruction_v1"
    else:
        status, authoritative, algorithm = SourceRecoveryStatus.incomplete, False, None
    payload = {"snapshot": snapshot_identity, "status": status.value, "hash": digest}
    return SourceSnapshotForensicRecovery(
        recovery_id=stable_identity("source_snapshot_forensic_recovery_id_v1", payload),
        source_snapshot_identity=snapshot_identity, status=status, authoritative=authoritative,
        actual_request_text=text if authoritative else None, request_text_sha256=digest if authoritative else None,
        encoding=encoding, newline_policy=newline_policy, template_identity=template_identity,
        evidence_refs=[direct_reference] if direct_reference else [],
        reconstruction_algorithm_version=algorithm,
        identity=stable_identity("source_snapshot_forensic_recovery_v1", payload),
    )

