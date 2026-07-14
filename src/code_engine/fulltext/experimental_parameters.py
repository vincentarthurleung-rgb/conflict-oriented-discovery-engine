"""Deterministic experimental parameter classification for full-text chains."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

PARAMETER_CLASSIFIER_VERSION = "experimental_parameter_classifier_v2"


@dataclass(frozen=True)
class ClassifiedParameter:
    raw_text: str
    normalized_value: str | None = None
    unit: str | None = None
    parameter_type: str = "unknown_parameter"
    classification_basis: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source_anchor_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


VALUE_UNIT_RE = re.compile(
    r"(?P<raw>"
    r"(?:p\s*[<=>]\s*\d+(?:\.\d+)?)|"
    r"(?:OD\s*\d{3,4})|"
    r"(?:\d+(?:\.\d+)?\s*(?:mg\s*/\s*kg|ug\s*/\s*kg|µg\s*/\s*kg|μg\s*/\s*kg|mg|ug|µg|μg|"
    r"nM|uM|µM|μM|mM|M|mg\s*/\s*mL|ng\s*/\s*mL|ug\s*/\s*mL|µg\s*/\s*mL|μg\s*/\s*mL|"
    r"s|sec|secs|min|mins|h|hr|hrs|hour|hours|day|days|week|weeks|"
    r"nm|°C|C|K|rpm|x\s*g|×\s*g|g-force|mL|uL|µL|μL|L|Hz|kHz|%))"
    r")",
    re.I,
)


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _unit(raw: str) -> str | None:
    if re.match(r"p\s*[<=>]", raw, flags=re.I):
        return "p"
    if re.match(r"OD\s*\d{3,4}", raw, flags=re.I):
        return "OD"
    match = re.search(r"(mg\s*/\s*kg|ug\s*/\s*kg|µg\s*/\s*kg|μg\s*/\s*kg|mg\s*/\s*mL|ng\s*/\s*mL|ug\s*/\s*mL|µg\s*/\s*mL|μg\s*/\s*mL|x\s*g|×\s*g|g-force|[A-Za-z°µμ%]+)$", raw.strip(), flags=re.I)
    return re.sub(r"\s+", "", match.group(1)) if match else None


def classify_parameter(raw_text: str, *, context: str = "", source_anchor_ids: list[str] | None = None) -> ClassifiedParameter:
    raw = _norm_text(raw_text).strip(" .;,")
    ctx = _norm_text(f"{context} {raw}").casefold()
    unit = _unit(raw)
    basis: list[str] = []
    ptype = "unknown_parameter"
    confidence = 0.0
    u = (unit or "").casefold().replace("μ", "µ")

    if re.match(r"p\s*[<=>]", raw, flags=re.I) or any(x in ctx for x in ("confidence interval", " ci ", " sem", " sd ")):
        ptype, confidence = "statistical_value", 0.95; basis.append("statistical notation")
    elif re.match(r"OD\s*\d{3,4}", raw, flags=re.I):
        ptype, confidence = "assay_readout", 0.95; basis.append("OD readout")
    elif u == "nm":
        if any(x in ctx for x in ("absorbance", "wavelength", "od", "read at", "measured at")):
            ptype, confidence = "wavelength", 0.98; basis.append("nm in assay/wavelength context")
        else:
            ptype, confidence = "wavelength", 0.9; basis.append("nm unit")
    elif u in {"°c", "c", "k"}:
        ptype, confidence = "temperature", 0.9; basis.append("temperature unit")
    elif u == "rpm":
        ptype, confidence = "rotation_speed", 0.95; basis.append("rpm unit")
    elif u in {"xg", "×g", "g-force"}:
        ptype, confidence = "centrifugation_speed", 0.95; basis.append("centrifugation g-force unit")
    elif u in {"ml", "ul", "µl", "l"}:
        ptype, confidence = "volume", 0.9; basis.append("volume unit")
    elif u in {"hz", "khz"}:
        ptype, confidence = "frequency", 0.9; basis.append("frequency unit")
    elif u in {"m", "mm", "µm", "um", "nm", "mg/ml", "ng/ml", "ug/ml", "µg/ml"}:
        ptype, confidence = "concentration", 0.92; basis.append("concentration unit")
    elif u in {"s", "sec", "secs", "min", "mins", "h", "hr", "hrs", "hour", "hours", "day", "days", "week", "weeks"}:
        if any(x in ctx for x in ("after treatment", "after stimulation", "post-treatment", "post treatment", "after ", "at ")) and not any(x in ctx for x in ("treated for", "incubated for", "exposed for")):
            ptype, confidence = "timepoint", 0.82; basis.append("time unit with after/at measurement context")
        else:
            ptype, confidence = "duration", 0.82; basis.append("time unit")
    elif u in {"mg/kg", "ug/kg", "µg/kg"}:
        if any(x in ctx for x in ("treated", "treatment", "administered", "injected", "dose", "drug", "ketamine")):
            ptype, confidence = "dose", 0.9; basis.append("mass-per-body-weight unit with intervention context")
        else:
            ptype, confidence = "unknown_parameter", 0.45; basis.append("dose-like unit without intervention context")
    elif u in {"mg", "ug", "µg"}:
        if any(x in ctx for x in ("tissue", "protein", "sample", "lysate")):
            ptype, confidence = "mass", 0.82; basis.append("mass unit with sample/tissue context")
        elif any(x in ctx for x in ("treated", "administered", "dose")):
            ptype, confidence = "dose", 0.7; basis.append("mass unit with intervention context")
        else:
            ptype, confidence = "mass", 0.6; basis.append("mass unit")

    return ClassifiedParameter(
        raw_text=raw,
        normalized_value=None,
        unit=unit,
        parameter_type=ptype if confidence >= 0.5 else "unknown_parameter",
        classification_basis=basis,
        confidence=confidence,
        source_anchor_ids=source_anchor_ids or [],
    )


def extract_parameters(text: str, *, context: str = "", source_anchor_ids: list[str] | None = None) -> list[ClassifiedParameter]:
    rows: list[ClassifiedParameter] = []
    seen: set[str] = set()
    haystack = _norm_text(text)
    for match in VALUE_UNIT_RE.finditer(haystack):
        raw = _norm_text(match.group("raw"))
        if raw.casefold() in seen:
            continue
        seen.add(raw.casefold())
        rows.append(classify_parameter(raw, context=context or haystack, source_anchor_ids=source_anchor_ids))
    return rows


def first_parameter(parameters: list[ClassifiedParameter], parameter_type: str) -> str | None:
    for item in parameters:
        if item.parameter_type == parameter_type:
            return item.raw_text
    return None
