"""Local LINCS L1000 preparation and compact metadata-first indexing."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
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
        "sha512_verified": checksum_status, "index_built": (_rooted(root, manifest["index_dir"], dataset, "index") / "metformin_index_summary.json").exists(),
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


def _read_selected_matrix(path: Path, signature_ids: list[str], landmark_gene_ids: set[str]) -> tuple[list[str], list[str], np.ndarray]:
    try:
        import h5py  # type: ignore
    except ImportError:
        h5py = None
    if h5py is not None:
        with h5py.File(path, "r") as handle:
            matrix = handle["0/DATA/0/matrix"]
            row_ids = _decode(handle["0/META/ROW/id"][:]); column_ids = _decode(handle["0/META/COL/id"][:])
            row_indices = [index for index, value in enumerate(row_ids) if value in landmark_gene_ids]
            col_lookup = {value: index for index, value in enumerate(column_ids)}
            col_indices = [col_lookup[value] for value in signature_ids if value in col_lookup]
            # Read one selected row at a time; never materialize the full matrix.
            selected = np.vstack([np.asarray(matrix[index, col_indices], dtype=np.float32) for index in row_indices]) if row_indices and col_indices else np.empty((0, 0), np.float32)
            return [row_ids[index] for index in row_indices], [column_ids[index] for index in col_indices], selected
    # Tiny-fixture fallback: an NPZ payload may use a .gctx filename.
    with np.load(path, allow_pickle=False) as payload:
        row_ids = _decode(payload["row_ids"]); column_ids = _decode(payload["col_ids"]); matrix = payload["matrix"]
        row_indices = [i for i, value in enumerate(row_ids) if value in landmark_gene_ids]
        col_lookup = {value: i for i, value in enumerate(column_ids)}; col_indices = [col_lookup[x] for x in signature_ids if x in col_lookup]
        return [row_ids[i] for i in row_indices], [column_ids[i] for i in col_indices], np.asarray(matrix[np.ix_(row_indices, col_indices)], dtype=np.float32)


def build_compact_lincs_index(*, dataset: str, data_root: str | Path, manifest_path: str | Path,
                              perturbagen: str, context: str | None = None, landmark_only: bool = True,
                              top_k_genes: int = 50) -> dict[str, Any]:
    manifest = load_lincs_manifest(manifest_path); root = Path(data_root); raw = root / "raw" / dataset
    unpacked = root / "working" / "unpacked" / dataset; output = root / "index" / dataset; output.mkdir(parents=True, exist_ok=True)
    sig_rows = _table(_file(manifest, raw, "sig_info")); gene_rows = _table(_file(manifest, raw, "gene_info"))
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
    row_ids, matrix_sig_ids, values = _read_selected_matrix(matrix_path, signature_ids, landmark)
    meta_by_id = {str(row.get("sig_id") or row.get("id")): row for row in selected_meta}
    npz_path = output / f"{perturbagen}_landmark_vectors.npz"
    records = []; vectors = {}
    for column, sig_id in enumerate(matrix_sig_ids):
        vector = values[:, column]; order = np.argsort(vector); k = min(top_k_genes, len(vector)); meta = meta_by_id[sig_id]
        top_down = [symbol_by_id.get(row_ids[i], row_ids[i]) for i in order[:k]]; top_up = [symbol_by_id.get(row_ids[i], row_ids[i]) for i in order[-k:][::-1]]
        vectors[sig_id] = vector
        records.append({"sig_id": sig_id, "pert_iname": meta.get("pert_iname", perturbagen), "cell_id": meta.get("cell_id"),
            "pert_dose": meta.get("pert_dose"), "pert_time": meta.get("pert_time"), "landmark_vector_path": str(npz_path),
            "top_up_genes": top_up, "top_down_genes": top_down,
            "signature_quality": {key: meta.get(key) for key in ("distil_cc_q75", "pct_self_rank_q25", "is_gold") if key in meta}})
    np.savez_compressed(npz_path, gene_ids=np.asarray(row_ids), **vectors)
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
        "perturbagen": perturbagen, "context": context, "signature_count": len(records), "landmark_gene_count": len(row_ids),
        "full_matrix_loaded": False, "storage_backend": "sqlite_jsonl_numpy_npz", "sqlite_path": str(sqlite_path),
        "top_genes_path": str(jsonl), "vectors_path": str(npz_path), "warnings": []}
    (output / f"{perturbagen}_index_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    prepare_lincs_dataset(dataset=dataset, data_root=root, manifest_path=manifest_path, check=True, unpack=False)
    return summary


__all__ = ["load_lincs_manifest", "prepare_lincs_dataset", "build_compact_lincs_index"]
