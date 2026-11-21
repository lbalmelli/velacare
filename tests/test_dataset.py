import io
import zipfile

from velacare.dataset import (
    FEATURE_NAMES,
    LABELS,
    SOURCE_FEATURE_NAMES,
    load_dataset,
    parse_uci_archive,
)


def sample_archive() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        rows = []
        for index in range(569):
            diagnosis = "M" if index < 212 else "B"
            features = [str(index / 10 + column / 100) for column in range(30)]
            rows.append(f"{index + 1},{diagnosis},{','.join(features)}")
        archive.writestr("wdbc.data", "\n".join(rows) + "\n")
    return output.getvalue()


def test_dataset_shape_feature_order_and_label_mapping(tmp_path, monkeypatch):
    import velacare.dataset as dataset_module

    assert len(FEATURE_NAMES) == 30
    assert FEATURE_NAMES[:10] == (
        "mean radius", "mean texture", "mean perimeter", "mean area", "mean smoothness",
        "mean compactness", "mean concavity", "mean concave points", "mean symmetry", "mean fractal dimension",
    )
    assert len(SOURCE_FEATURE_NAMES) == 30
    assert SOURCE_FEATURE_NAMES[:3] == ("radius1", "texture1", "perimeter1")
    assert LABELS == {"B": "benign", "M": "malignant"}

    monkeypatch.setattr(dataset_module, "_download_archive", sample_archive)
    data, metadata = load_dataset(tmp_path)
    assert data.X.shape == (569, 30)
    assert data.y.shape == (569,)
    assert set(data.y.tolist()) == {0, 1}
    assert int((data.y == 1).sum()) == 212
    assert metadata["feature_count"] == 30
    assert metadata["sample_count"] == 569
    assert [entry["source_name"] for entry in metadata["feature_order"]] == list(SOURCE_FEATURE_NAMES)

    cached, cached_metadata = load_dataset(tmp_path)
    assert (cached.X == data.X).all()
    assert (cached.y == data.y).all()
    assert cached_metadata["sha256"] == metadata["sha256"]


def test_uci_archive_rejects_wrong_row_count():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("wdbc.data", "1,M," + ",".join(["1"] * 30) + "\n")
    try:
        parse_uci_archive(output.getvalue())
    except Exception as exc:
        assert "569" in str(exc)
    else:
        raise AssertionError("incomplete UCI dataset should not be accepted")
