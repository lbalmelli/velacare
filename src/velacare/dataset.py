"""Download, normalize, cache, and validate the UCI WDBC dataset."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np


DATASET_ID = 17
DATASET_NAME = "Breast Cancer Wisconsin (Diagnostic)"
DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/17/"
    "breast+cancer+wisconsin+diagnostic.zip"
)
DATASET_PAGE = "https://archive.ics.uci.edu/dataset/17/breast-cancer-wisconsin-diagnostic"
DOI = "10.24432/C5DW2B"
CSV_NAME = "breast_cancer.csv"
METADATA_NAME = "dataset_metadata.json"
LABELS = {"B": "benign", "M": "malignant"}
LABEL_TO_INT = {"benign": 0, "malignant": 1}
INT_TO_LABEL = {value: key for key, value in LABEL_TO_INT.items()}

# Human-readable names in the original WDBC feature order. The source variable
# identifiers are recorded alongside these names in dataset_metadata.json.
_DIMENSIONS = (
    ("mean", "1"),
    ("standard error", "2"),
    ("worst", "3"),
)
_MEASURES = (
    ("radius", "radius"),
    ("texture", "texture"),
    ("perimeter", "perimeter"),
    ("area", "area"),
    ("smoothness", "smoothness"),
    ("compactness", "compactness"),
    ("concavity", "concavity"),
    ("concave points", "concave_points"),
    ("symmetry", "symmetry"),
    ("fractal dimension", "fractal_dimension"),
)
FEATURE_NAMES = tuple(
    f"{dimension} {display}"
    for dimension, _suffix in _DIMENSIONS
    for display, _source in _MEASURES
)
SOURCE_FEATURE_NAMES = tuple(
    f"{source}{suffix}"
    for _dimension, suffix in _DIMENSIONS
    for _display, source in _MEASURES
)


class DatasetError(RuntimeError):
    """A clear, user-facing dataset download or validation failure."""


@dataclass(frozen=True)
class Dataset:
    X: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...] = FEATURE_NAMES


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def parse_uci_archive(archive_bytes: bytes) -> list[tuple[str, list[float]]]:
    """Parse the original WDBC data file from a UCI dataset ZIP archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            member = next(name for name in archive.namelist() if name.lower().endswith("wdbc.data"))
            raw_text = archive.read(member).decode("utf-8-sig")
    except (zipfile.BadZipFile, StopIteration, KeyError, UnicodeDecodeError) as exc:
        raise DatasetError(
            "UCI returned an archive that does not contain a readable wdbc.data file. "
            "Check the UCI dataset page and try again."
        ) from exc

    rows: list[tuple[str, list[float]]] = []
    for line_number, row in enumerate(csv.reader(io.StringIO(raw_text)), start=1):
        if len(row) != 32:
            raise DatasetError(f"UCI row {line_number} has {len(row)} fields; expected 32.")
        label = row[1].strip().upper()
        if label not in LABELS:
            raise DatasetError(f"UCI row {line_number} has unexpected diagnosis {label!r}.")
        try:
            features = [float(value) for value in row[2:]]
        except ValueError as exc:
            raise DatasetError(f"UCI row {line_number} contains a non-numeric feature.") from exc
        if not np.all(np.isfinite(features)):
            raise DatasetError(f"UCI row {line_number} contains a non-finite feature.")
        rows.append((LABELS[label], features))
    validate_rows(rows)
    return rows


def validate_rows(rows: Iterable[tuple[str, list[float]]]) -> None:
    rows = list(rows)
    if len(rows) != 569:
        raise DatasetError(f"Expected 569 samples in UCI dataset 17, received {len(rows)}.")
    classes = {label for label, _features in rows}
    if classes != {"benign", "malignant"}:
        raise DatasetError(f"Expected benign and malignant classes, received {sorted(classes)}.")
    for row_number, (label, features) in enumerate(rows, start=1):
        if label not in LABEL_TO_INT or len(features) != 30:
            raise DatasetError(f"Normalized sample {row_number} must have a known label and 30 features.")
        if not np.all(np.isfinite(features)):
            raise DatasetError(f"Normalized sample {row_number} contains a non-finite feature.")


def _csv_bytes(rows: Iterable[tuple[str, list[float]]]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(("diagnosis", *FEATURE_NAMES))
    for label, features in rows:
        writer.writerow((label, *(format(value, ".17g") for value in features)))
    return out.getvalue().encode("utf-8")


def _metadata(csv_bytes: bytes) -> dict:
    counts = {"benign": 0, "malignant": 0}
    # The class counts are obtained from the normalized CSV, not hard-coded.
    for row in csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))):
        counts[row["diagnosis"]] += 1
    return {
        "dataset_id": DATASET_ID,
        "name": DATASET_NAME,
        "source": "UCI Machine Learning Repository",
        "source_url": DATASET_PAGE,
        "download_url": DATASET_URL,
        "doi": DOI,
        "license": "CC BY 4.0",
        "attribution": "Wolberg, Mangasarian, Street, and Street (1993).",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "sample_count": 569,
        "feature_count": 30,
        "class_counts": counts,
        "label_mapping": {"B": "benign (0)", "M": "malignant (1)"},
        "feature_order": [
            {"name": display, "source_name": source}
            for display, source in zip(FEATURE_NAMES, SOURCE_FEATURE_NAMES, strict=True)
        ],
    }


def _download_archive(timeout: float = 45.0) -> bytes:
    request = urllib.request.Request(
        DATASET_URL,
        headers={"User-Agent": "VelaCare-Evolution-Engine/1.0 (+UCI dataset 17)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise DatasetError(
            f"Could not download dataset 17 from UCI ({reason}). Check network access, then retry. "
            f"You can also place a valid {CSV_NAME} and {METADATA_NAME} in the workspace data/ directory."
        ) from exc


def _load_cached(csv_path: Path, metadata_path: Path) -> Dataset:
    try:
        content = csv_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(
            f"The cached dataset is incomplete at {csv_path.parent}. Remove that cache directory "
            "and rerun to download a fresh copy."
        ) from exc
    digest = hashlib.sha256(content).hexdigest()
    if digest != metadata.get("sha256"):
        raise DatasetError(
            f"Cached dataset checksum does not match {metadata_path}. Restore the original cache "
            "or remove the data/ directory and rerun to download it again."
        )

    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    if reader.fieldnames != ["diagnosis", *FEATURE_NAMES]:
        raise DatasetError(f"Cached CSV feature order is invalid: {csv_path}.")
    labels: list[int] = []
    matrix: list[list[float]] = []
    try:
        for row in reader:
            labels.append(LABEL_TO_INT[row["diagnosis"]])
            matrix.append([float(row[name]) for name in FEATURE_NAMES])
    except (KeyError, ValueError) as exc:
        raise DatasetError(f"Cached CSV has invalid labels or features: {csv_path}.") from exc
    validate_rows([(INT_TO_LABEL[label], values) for label, values in zip(labels, matrix, strict=True)])
    if len(matrix) != metadata.get("sample_count") or metadata.get("feature_count") != len(FEATURE_NAMES):
        raise DatasetError(f"Cached dataset metadata does not match the data in {csv_path.parent}.")
    return Dataset(np.asarray(matrix, dtype=np.float64), np.asarray(labels, dtype=np.int8))


def load_dataset(workspace: Path, *, refresh: bool = False) -> tuple[Dataset, dict]:
    """Load the validated cache or download and atomically persist it."""
    data_dir = workspace / "data"
    csv_path = data_dir / CSV_NAME
    metadata_path = data_dir / METADATA_NAME
    if not refresh and csv_path.is_file() and metadata_path.is_file():
        dataset = _load_cached(csv_path, metadata_path)
        return dataset, json.loads(metadata_path.read_text(encoding="utf-8"))

    rows = parse_uci_archive(_download_archive())
    csv_bytes = _csv_bytes(rows)
    metadata = _metadata(csv_bytes)
    _atomic_write(csv_path, csv_bytes)
    _atomic_write(metadata_path, (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode())
    return Dataset(
        np.asarray([features for _label, features in rows], dtype=np.float64),
        np.asarray([LABEL_TO_INT[label] for label, _features in rows], dtype=np.int8),
    ), metadata
