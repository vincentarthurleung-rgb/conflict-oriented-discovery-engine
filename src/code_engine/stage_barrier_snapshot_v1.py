"""Immutable, mechanically bound two-phase snapshots; no OA computation."""

from dataclasses import dataclass

from . import append_only_attempt_journal_v1 as j


def barrier_record(manifest, states):
    outcomes = []
    for request in manifest.record()["requests"]:
        if request["stage"] != "OA":
            continue
        state = states[request["request_id"]]
        j.require(state["outcome"] in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"}, "OA_BARRIER_NOT_COMPLETE")
        terminal = state["attempts"][-1]["terminal"]
        outcomes.append({"request_id": request["request_id"], "outcome": state["outcome"],
                         "raw_artifact": terminal["raw_artifact"], "eligibility": terminal["eligibility"]})
    j.require(bool(outcomes), "OA_BARRIER_EMPTY")
    return {"schema_version": "StageBarrierSnapshotV1", "manifest_sha256": manifest.sha256,
            "authority": j.AUTHORITY, "oa_outcomes": outcomes}


@dataclass(frozen=True)
class StageBarrierSnapshotV1:
    serialized: bytes

    def record(self):
        return j.strict_json(self.serialized)

    @property
    def sha256(self):
        return j.sha(self.serialized)

    @classmethod
    def from_reference(cls, reference, manifest, states):
        raw = j.verify_artifact(reference)
        j.require(raw == j.canonical(barrier_record(manifest, states)), "BARRIER_NOT_BOUND_TO_DURABLE_OA_OUTCOMES")
        return cls(raw)

    @classmethod
    def freeze(cls, journal, *, timestamp):
        states, existing, _ = j._reduce(journal.verified().events, journal.manifest)
        if existing is not None:
            return existing
        raw = j.canonical(barrier_record(journal.manifest, states))
        reference = _freeze_or_verify_uncommitted(journal.directory / "stage_barrier.json", raw)
        journal.commit_stage_reference("STAGE_BARRIER_COMMITTED", dict(reference.__dict__), timestamp=timestamp)
        return cls(raw)


def activation_record(manifest, barrier):
    outcomes = {r["request_id"]: r for r in barrier.record()["oa_outcomes"]}
    activated, not_required = [], []
    for request in manifest.record()["requests"]:
        if request["stage"] != "JATS":
            continue
        # Only a frozen opaque parent request identity is consulted. No article,
        # topic, current source availability or live OA result is inspected.
        parent = request["request_payload"].get("oa_request_id")
        j.require(parent in outcomes, "UNBOUND_ACTIVATION_PARENT")
        target = activated if outcomes[parent]["outcome"] == "VALID_SUCCESS" else not_required
        target.append(request["request_id"])
    return {"schema_version": "FrozenActivationManifestV1", "manifest_sha256": manifest.sha256,
            "barrier_sha256": barrier.sha256, "activation_contract_sha256": manifest.record()["activation_contract_sha256"],
            "activated_request_ids": activated, "not_required_request_ids": not_required}


@dataclass(frozen=True)
class FrozenActivationManifestV1:
    serialized: bytes

    def record(self):
        return j.strict_json(self.serialized)

    @property
    def sha256(self):
        return j.sha(self.serialized)

    @classmethod
    def from_reference(cls, reference, manifest, barrier):
        raw = j.verify_artifact(reference)
        j.require(raw == j.canonical(activation_record(manifest, barrier)), "FROZEN_ACTIVATION_SET_CHANGED")
        return cls(raw)

    @classmethod
    def freeze(cls, journal, *, timestamp):
        _, barrier, existing = j._reduce(journal.verified().events, journal.manifest)
        j.require(barrier is not None, "ACTIVATION_REQUIRES_DURABLE_BARRIER")
        if existing is not None:
            return existing
        raw = j.canonical(activation_record(journal.manifest, barrier))
        reference = _freeze_or_verify_uncommitted(journal.directory / "activation_manifest.json", raw)
        journal.commit_stage_reference("ACTIVATION_MANIFEST_COMMITTED", dict(reference.__dict__), timestamp=timestamp)
        return cls(raw)


def _freeze_or_verify_uncommitted(path, expected):
    if path.exists():
        # Recover an atomic, complete orphan companion only when it is exactly
        # derivable from already authoritative journal records. Never rewrite it.
        raw = j.read_bytes(path)
        j.require(raw == expected, "PARTIAL_OR_CONFLICTING_BARRIER_ARTIFACT")
        artifact = j.t.RawArtifactV1(str(path), j.sha(raw), len(raw))
        fd = j.os.open(j.physical(path), j.os.O_RDONLY | j.os.O_NOFOLLOW)
        try:
            j.os.fsync(fd)
        finally:
            j.os.close(fd)
        j.sync_directory(path.parent)
        return artifact
    return j.atomic_freeze(path, expected)
