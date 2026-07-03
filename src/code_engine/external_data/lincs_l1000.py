"""Local LINCS L1000 preparation and compact metadata-first indexing."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def load_lincs_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"dataset_id", "raw_dir", "unpacked_dir", "index_dir", "files"}
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"lincs_manifest_missing_fields:{','.join(missing)}")
    return value


def _rooted(data_root: Path, configured: str, dataset_id: str, kind: str) -> Path:
    # CLI data_root is the lincs_l1000 root and deliberately overrides the
    # repository-relative paths in the distributable manifest.
    mapping = {"raw": data_root / "raw" / dataset_id, "unpacked": data_root / "working" / "unpacked" / dataset_id,
               "index": data_root / "index" / dataset_id, "manifests": data_root / "manifests"}
    return mapping[kind]


def _hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_lincs_dataset(*, dataset: str, data_root: str | Path, manifest_path: str | Path,
                          check: bool = True, unpack: bool = False) -> dict[str, Any]:
    manifest = load_lincs_manifest(manifest_path); root = Path(data_root)
    if manifest["dataset_id"] != dataset:
        raise ValueError("lincs_dataset_manifest_mismatch")
    raw = _rooted(root, manifest["raw_dir"], dataset, "raw"); unpacked = _rooted(root, manifest["unpacked_dir"], dataset, "unpacked")
    raw.mkdir(parents=True, exist_ok=True); unpacked.mkdir(parents=True, exist_ok=True)
    missing_required, missing_optional, sizes, hashes = [], [], {}, {}
    for spec in manifest["files"]:
        path = raw / spec["filename"]
        if not path.exists():
            (missing_required if spec.get("required") else missing_optional).append(spec["filename"]); continue
        sizes[spec["filename"]] = path.stat().st_size; hashes[spec["filename"]] = _hash(path)
        if unpack and spec.get("unpack"):
            destination = unpacked / spec["unpacked_filename"]
            if not destination.exists() or destination.stat().st_size == 0:
                temporary = destination.with_suffix(destination.suffix + ".partial")
                with gzip.open(path, "rb") as source, temporary.open("wb") as target:
                    shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
                temporary.replace(destination)
    matrix_spec = next(item for item in manifest["files"] if item["role"] == "level5_matrix")
    unpacked_matrix = unpacked / matrix_spec["unpacked_filename"]
    checksum_spec = next((item for item in manifest["files"] if item["role"] == "sha512sums"), None)
    checksum_status: bool | str = "not_available"
    if checksum_spec and (raw / checksum_spec["filename"]).exists():
        expected = {}
        with gzip.open(raw / checksum_spec["filename"], "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.strip().replace(" *", "  ").split()
                if len(parts) >= 2:
                    expected[Path(parts[-1]).name] = parts[0]
        checked = [(raw / name, digest) for name, digest in expected.items() if (raw / name).exists()]
        checksum_status = bool(checked) and all(_hash(path, "sha512") == digest for path, digest in checked)
    status = {"dataset_id": dataset, "raw_files_present": not (missing_required or missing_optional),
        "required_files_present": not missing_required, "missing_required_files": missing_required,
        "missing_optional_files": missing_optional, "unpacked_gctx_present": unpacked_matrix.exists(),
        "sha512_verified": checksum_status, "index_built": any(_rooted(root, manifest["index_dir"], dataset, "index").glob("*_index_summary.json")),
        "created_at": datetime.now(timezone.utc).isoformat(), "code_version": "code_engine", "file_sizes": sizes, "file_hashes": hashes,
        "raw_dir": str(raw), "unpacked_dir": str(unpacked), "check_requested": bool(check), "unpack_requested": bool(unpack)}
    local = _rooted(root, "", dataset, "manifests") / f"{dataset}_local_manifest.json"; local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    status["local_manifest_path"] = str(local)
    return status


def _table(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _file(manifest: dict[str, Any], raw: Path, role: str) -> Path:
    return raw / next(item["filename"] for item in manifest["files"] if item["role"] == role)


def _decode(values: Any) -> list[str]:
    return [value.decode() if isinstance(value, bytes) else str(value) for value in values]


def _number_and_unit(value: Any) -> tuple[float | int | None, str | None, str | None]:
    text = str(value or "").strip()
    if not text or text in {"-666", "-666.0", "NA", "nan", "None"}:
        return None, None, None
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([A-Za-zµμ]+)?", text)
    if not match:
        return None, None, text
    number = float(match.group(1)); number = int(number) if number.is_integer() else number
    unit = match.group(2).upper().replace("Μ", "U").replace("µ", "U") if match.group(2) else None
    label = f"{number}{unit or ''}"
    return number, unit, label


def extract_perturbation_metadata(metadata: dict[str, Any], sig_id: str) -> dict[str, Any]:
    """Extract generic LINCS time/dose fields with sig-id time fallback."""
    explicit_time = next((metadata.get(key) for key in ("pert_time", "pert_itime", "pert_timepoint", "time") if metadata.get(key) not in (None, "")), None)
    time, time_unit, time_label = _number_and_unit(explicit_time)
    time_source = "sig_info" if time is not None else "not_available"
    if time is None:
        match = re.search(r"_(\d+(?:\.\d+)?)(H|D|M)(?=[:_])", str(sig_id), re.IGNORECASE)
        if match:
            time, time_unit, time_label = _number_and_unit("".join(match.groups()))
            time_source = "sig_id_fallback"
    explicit_dose = next((metadata.get(key) for key in ("pert_dose", "pert_idose", "dose") if metadata.get(key) not in (None, "")), None)
    dose, dose_unit, dose_label = _number_and_unit(explicit_dose)
    return {"pert_time": time, "pert_time_unit": time_unit, "pert_time_label": time_label,
        "pert_time_source": time_source, "pert_dose": dose, "pert_dose_unit": dose_unit,
        "pert_dose_label": dose_label, "pert_dose_source": "sig_info" if dose is not None else "not_available"}


def _detect_gctx_axes(matrix_shape: tuple[int, int], row_id_count: int, col_id_count: int) -> tuple[int, int]:
    """Return ``(signature_axis, gene_axis)`` from GCTX metadata dimensions."""
    if matrix_shape == (col_id_count, row_id_count):
        return 0, 1
    if matrix_shape == (row_id_count, col_id_count):
        return 1, 0
    raise ValueError(
        f"gctx_axis_orientation_unresolved:matrix_shape={matrix_shape}:"
        f"row_id_count={row_id_count}:col_id_count={col_id_count}"
    )


def _read_selected_matrix(path: Path, requested_signature_ids: list[str], landmark_gene_ids: set[str],
                          diagnostics: dict[str, Any] | None = None) -> tuple[list[str], list[str], np.ndarray]:
    """Read only requested GCTX signatures/genes as signatures x genes."""
    try:
        import h5py  # type: ignore
    except ImportError:
        h5py = None
    if h5py is not None and h5py.is_hdf5(path):
        with h5py.File(path, "r") as handle:
            matrix = handle["0/DATA/0/matrix"]
            gene_ids = _decode(handle["0/META/ROW/id"][:])
            signature_ids = _decode(handle["0/META/COL/id"][:])
            try:
                signature_axis, gene_axis = _detect_gctx_axes(tuple(matrix.shape), len(gene_ids), len(signature_ids))
            except ValueError as exc:
                raise ValueError(f"{exc}:requested_signature_count={len(requested_signature_ids)}:requested_gene_count={len(landmark_gene_ids)}") from exc
            selected_gene_indices = sorted(index for index, value in enumerate(gene_ids) if value in landmark_gene_ids)
            signature_lookup = {value: index for index, value in enumerate(signature_ids)}
            selected_signature_indices = [signature_lookup[value] for value in requested_signature_ids if value in signature_lookup]
            selected_gene_ids = [gene_ids[index] for index in selected_gene_indices]
            selected_signature_ids = [signature_ids[index] for index in selected_signature_indices]
            selected_rows = []
            for signature_index in selected_signature_indices:
                if signature_axis == 0:
                    row = np.asarray(matrix[signature_index, selected_gene_indices], dtype=np.float32)
                else:
                    row = np.asarray(matrix[selected_gene_indices, signature_index], dtype=np.float32)
                selected_rows.append(row)
            values_signatures_x_genes = np.vstack(selected_rows) if selected_rows else np.empty((0, len(selected_gene_indices)), np.float32)
            if diagnostics is not None:
                diagnostics.update({"gctx_matrix_shape": list(matrix.shape), "gctx_signature_axis": signature_axis,
                    "gctx_gene_axis": gene_axis, "signature_metadata_count": len(signature_ids),
                    "gene_metadata_count": len(gene_ids), "selected_signature_count": len(selected_signature_ids),
                    "selected_gene_count": len(selected_gene_ids), "compact_matrix_orientation": "signatures_x_genes",
                    "compact_values_shape": list(values_signatures_x_genes.shape)})
            return selected_gene_ids, selected_signature_ids, values_signatures_x_genes
    # Tiny-fixture fallback: an NPZ payload may use a .gctx filename.
    with np.load(path, allow_pickle=False) as payload:
        gene_ids = _decode(payload["row_ids"]); signature_ids = _decode(payload["col_ids"]); matrix = payload["matrix"]
        try:
            signature_axis, gene_axis = _detect_gctx_axes(tuple(matrix.shape), len(gene_ids), len(signature_ids))
        except ValueError as exc:
            raise ValueError(f"{exc}:requested_signature_count={len(requested_signature_ids)}:requested_gene_count={len(landmark_gene_ids)}") from exc
        selected_gene_indices = sorted(i for i, value in enumerate(gene_ids) if value in landmark_gene_ids)
        signature_lookup = {value: i for i, value in enumerate(signature_ids)}
        selected_signature_indices = [signature_lookup[x] for x in requested_signature_ids if x in signature_lookup]
        if signature_axis == 0:
            values = np.asarray(matrix[np.ix_(selected_signature_indices, selected_gene_indices)], dtype=np.float32)
        else:
            values = np.asarray(matrix[np.ix_(selected_gene_indices, selected_signature_indices)].T, dtype=np.float32)
        if diagnostics is not None:
            diagnostics.update({"gctx_matrix_shape": list(matrix.shape), "gctx_signature_axis": signature_axis,
                "gctx_gene_axis": gene_axis, "signature_metadata_count": len(signature_ids), "gene_metadata_count": len(gene_ids),
                "selected_signature_count": len(selected_signature_indices), "selected_gene_count": len(selected_gene_indices),
                "compact_matrix_orientation": "signatures_x_genes", "compact_values_shape": list(values.shape)})
        return [gene_ids[i] for i in selected_gene_indices], [signature_ids[i] for i in selected_signature_indices], values


def build_compact_lincs_index(*, dataset: str, data_root: str | Path, manifest_path: str | Path,
                              perturbagen: str, context: str | None = None, landmark_only: bool = True,
                              top_k_genes: int = 50) -> dict[str, Any]:
    manifest = load_lincs_manifest(manifest_path); root = Path(data_root); raw = root / "raw" / dataset
    unpacked = root / "working" / "unpacked" / dataset; output = root / "index" / dataset; output.mkdir(parents=True, exist_ok=True)
    sig_rows = _table(_file(manifest, raw, "sig_info")); gene_rows = _table(_file(manifest, raw, "gene_info"))
    metrics_spec = next((item for item in manifest["files"] if item["role"] == "sig_metrics"), None)
    metrics_path = raw / metrics_spec["filename"] if metrics_spec else None
    metrics_available = bool(metrics_path and metrics_path.exists())
    metrics_by_id = {str(row.get("sig_id")): row for row in _table(metrics_path)} if metrics_available and metrics_path else {}
    pert = perturbagen.casefold()
    selected_meta = [row for row in sig_rows if pert in str(row.get("pert_iname") or row.get("pert_id") or "").casefold()]
    signature_ids = [str(row.get("sig_id") or row.get("id")) for row in selected_meta]
    gene_id_key = "pr_gene_id" if gene_rows and "pr_gene_id" in gene_rows[0] else "gene_id"
    gene_symbol_key = "pr_gene_symbol" if gene_rows and "pr_gene_symbol" in gene_rows[0] else "gene_symbol"
    landmark = {str(row.get(gene_id_key)) for row in gene_rows if not landmark_only or str(row.get("pr_is_lm", "1")) in {"1", "1.0", "true", "True"}}
    symbol_by_id = {str(row.get(gene_id_key)): str(row.get(gene_symbol_key) or row.get(gene_id_key)) for row in gene_rows}
    matrix_spec = next(item for item in manifest["files"] if item["role"] == "level5_matrix")
    matrix_path = unpacked / matrix_spec["unpacked_filename"]
    if not matrix_path.exists():
        raise FileNotFoundError(f"unpacked_lincs_gctx_missing:{matrix_path}")
    if not signature_ids:
        summary = {"dataset_id": dataset, "status": "not_built", "index_built": False,
            "reason": "no_matching_signatures", "perturbagen": perturbagen, "context": context,
            "signature_count": 0, "selected_signature_count": 0, "selected_gene_count": 0,
            "full_matrix_loaded": False, "warnings": []}
        (output / f"{perturbagen}_index_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    matrix_diagnostics: dict[str, Any] = {}
    selected_gene_ids, selected_signature_ids, values_signatures_x_genes = _read_selected_matrix(
        matrix_path, signature_ids, landmark, matrix_diagnostics)
    meta_by_id = {str(row.get("sig_id") or row.get("id")): row for row in selected_meta}
    npz_path = output / f"{perturbagen}_landmark_vectors.npz"
    records = []; vectors = {}
    for signature_position, sig_id in enumerate(selected_signature_ids):
        vector = values_signatures_x_genes[signature_position, :]
        order = np.argsort(vector); k = min(top_k_genes, len(vector)); meta = meta_by_id[sig_id]
        top_down = [symbol_by_id.get(selected_gene_ids[i], selected_gene_ids[i]) for i in order[:k]]
        top_up = [symbol_by_id.get(selected_gene_ids[i], selected_gene_ids[i]) for i in order[-k:][::-1]]
        vectors[sig_id] = vector
        perturbation = extract_perturbation_metadata(meta, sig_id)
        metrics = metrics_by_id.get(sig_id)
        signature_quality = {"sig_metrics_available": metrics_available,
            "metrics_for_signature_found": metrics is not None}
        if metrics is not None:
            for key in ("distil_cc_q75", "distil_ss", "tas", "pct_self_rank_q25", "distil_nsample"):
                if metrics.get(key) not in (None, ""):
                    signature_quality[key] = metrics[key]
            signature_quality["raw_metrics"] = {key: value for key, value in metrics.items() if key and key != "sig_id"}
        records.append({"sig_id": sig_id, "pert_iname": meta.get("pert_iname", perturbagen), "cell_id": meta.get("cell_id"),
            **perturbation, "landmark_vector_path": str(npz_path),
            "top_up_genes": top_up, "top_down_genes": top_down,
            "signature_quality": signature_quality})
    np.savez_compressed(npz_path, gene_ids=np.asarray(selected_gene_ids), **vectors)
    jsonl = output / f"{perturbagen}_top_genes.jsonl"; jsonl.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    sqlite_path = output / f"{perturbagen}_compact_index.sqlite"
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute("create table if not exists signatures (sig_id text primary key, pert_iname text, cell_id text, pert_dose text, pert_time text, record_json text)")
        connection.executemany("insert or replace into signatures values (?,?,?,?,?,?)", [(r["sig_id"],r["pert_iname"],r["cell_id"],r["pert_dose"],r["pert_time"],json.dumps(r)) for r in records])
        connection.commit()
    finally:
        connection.close()
    summary = {"dataset_id": dataset, "status": "completed", "strategy": "metadata_first_selected_rows_and_columns",
        "perturbagen": perturbagen, "context": context, "signature_count": len(records),
        "landmark_gene_count": len(selected_gene_ids), "selected_signature_count": len(selected_signature_ids),
        "selected_gene_count": len(selected_gene_ids), **matrix_diagnostics,
        "full_matrix_loaded": False, "storage_backend": "sqlite_jsonl_numpy_npz", "sqlite_path": str(sqlite_path),
        "top_genes_path": str(jsonl), "vectors_path": str(npz_path), "warnings": []}
    (output / f"{perturbagen}_index_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    prepare_lincs_dataset(dataset=dataset, data_root=root, manifest_path=manifest_path, check=True, unpack=False)
    return summary


__all__ = ["load_lincs_manifest", "prepare_lincs_dataset", "build_compact_lincs_index"]
