"""Stable, domain-independent source anchors for provider-visible experiment blocks."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from typing import Iterable


EVIDENCE_ANCHOR_VERSION = "fulltext_evidence_anchor_v1"


@dataclass(frozen=True)
class EvidenceAnchor:
    anchor_id: str
    source_document_id: str
    block_id: str
    section: str | None
    char_start: int
    char_end: int
    text: str
    text_hash: str
    source_role: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_role(line: str) -> str:
    if line.startswith("LINKED_METHODS:"):
        return "methods"
    if line.startswith("PRECEDING_SETUP:"):
        return "setup"
    if line.startswith("CURRENT_"):
        return "current"
    return "other"


def generate_evidence_anchors(*, block_id: str, source_document_id: str, block_text: str,
                              section: str | None = None) -> list[EvidenceAnchor]:
    units: list[tuple[int, int, str, str]] = []
    line_offset = 0
    for line in block_text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        role = _source_role(content)
        prefix_match = re.match(r"^(?:CURRENT_[A-Z_]+|PRECEDING_SETUP|LINKED_METHODS):\s*", content)
        prefix_end = prefix_match.end() if prefix_match else 0
        body = content[prefix_end:]
        for match in re.finditer(r"\S.*?(?:[.!?](?=\s+[A-Z0-9\[]|$)|$)", body):
            text = match.group(0)
            start = line_offset + prefix_end + match.start()
            units.append((start, start + len(text), text, role))
        line_offset += len(line)
    anchors = []
    for index, (start, end, text, role) in enumerate(units, 1):
        anchors.append(EvidenceAnchor(
            anchor_id=f"{block_id}:S{index:04d}", source_document_id=source_document_id,
            block_id=block_id, section=section, char_start=start, char_end=end,
            text=text, text_hash=_hash(text), source_role=role,
        ))
    return anchors


def render_anchored_block(anchors: Iterable[EvidenceAnchor]) -> str:
    return "\n".join(f"[{item.anchor_id}] {item.text}" for item in anchors)


def resolve_anchor(anchor_id: str, anchors: Iterable[EvidenceAnchor], *, expected_block_id: str,
                   required_source_role: str | None = None) -> EvidenceAnchor:
    match = next((item for item in anchors if item.anchor_id == anchor_id), None)
    if match is None:
        raise ValueError(f"evidence_anchor_not_found:{anchor_id}")
    if match.block_id != expected_block_id:
        raise ValueError(f"evidence_anchor_cross_block:{anchor_id}")
    if _hash(match.text) != match.text_hash:
        raise ValueError(f"evidence_anchor_hash_mismatch:{anchor_id}")
    if required_source_role and match.source_role != required_source_role:
        raise ValueError(f"evidence_anchor_source_role_mismatch:{anchor_id}:{match.source_role}")
    return match


__all__ = ["EVIDENCE_ANCHOR_VERSION", "EvidenceAnchor", "generate_evidence_anchors", "render_anchored_block", "resolve_anchor"]
