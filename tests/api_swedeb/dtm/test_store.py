from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse

from api_swedeb.core.dtm import VectorizedCorpus
from api_swedeb.core.dtm import store as dtm_store


def _create_corpus(*, bag_term_matrix, token2id, document_index) -> VectorizedCorpus:
    return VectorizedCorpus(  # type: ignore[reportAbstractUsage]
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )


def _create_document_index() -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc0", "doc1"],
                "year": [2000, 2001],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )


@pytest.mark.parametrize(
    ("values", "expected_dtype"),
    [
        ([0, 255], np.uint8),
        ([0, 256], np.uint16),
        ([-128, 126], np.int8),
        ([-129, 100], np.int16),
    ],
)
def test_smallest_int_dtype_selects_expected_dtype(values, expected_dtype):
    series = pd.Series(values)

    assert dtm_store._smallest_int_dtype(series) is expected_dtype


def test_should_be_categorical_applies_expected_heuristics():
    categorical = pd.Series(pd.Categorical(["a", "b", "a"]))
    low_cardinality_strings = pd.Series(["x", "x", "y", "y"])
    low_cardinality_ids = pd.Series([1, 1, 2, 2], dtype=np.int64)
    repeated_document_names = pd.Series(["doc", "doc", "doc", "other", "other", "other"])
    high_cardinality_ids = pd.Series(range(10), dtype=np.int64)

    assert not dtm_store._should_be_categorical("category", categorical, categorical.nunique(), threshold=10)
    assert dtm_store._should_be_categorical(
        "label", low_cardinality_strings, low_cardinality_strings.nunique(), threshold=10
    )
    assert dtm_store._should_be_categorical("party_id", low_cardinality_ids, low_cardinality_ids.nunique(), threshold=10)
    assert dtm_store._should_be_categorical(
        "document_name",
        repeated_document_names,
        repeated_document_names.nunique(),
        threshold=10,
    )
    assert not dtm_store._should_be_categorical(
        "district_id",
        high_cardinality_ids,
        high_cardinality_ids.nunique(),
        threshold=5,
    )


def test_optimize_document_index_dtypes_applies_overrides_and_heuristics():
    df = pd.DataFrame(
        {
            "year": list(range(2000, 2020)),
            "n_documents": list(range(20)),
            "party_id": [1, 2] * 10,
            "district_id": list(range(20)),
            "label": ["a", "b"] * 10,
        }
    )

    optimized = dtm_store._optimize_document_index_dtypes(
        df.copy(),
        categorical_threshold=5,
        dtype_overrides={"year": np.int32},
    )

    assert optimized["year"].dtype == np.int32
    assert optimized["n_documents"].dtype == np.int32
    assert str(optimized["party_id"].dtype) == "category"
    assert str(optimized["label"].dtype) == "category"
    assert optimized["district_id"].dtype == np.uint8


def test_load_document_index_prefers_prepped_feather(tmp_path):
    csv_df = pd.DataFrame({"document_id": [0], "source": ["csv"], "year": [1999]}).set_index("document_id")
    feather_df = pd.DataFrame({"document_id": [0], "source": ["feather"], "year": [2001]})

    csv_df.to_csv(tmp_path / "sample_document_index.csv.gz", sep=";", compression="gzip")
    feather_df.to_feather(tmp_path / "sample_document_index.prepped.feather")

    loaded = dtm_store.load_document_index("sample", str(tmp_path), optimize_dtypes=False)

    assert loaded["source"].tolist() == ["feather"]
    assert loaded["year"].tolist() == [2001]


def test_load_document_index_optimizes_dtypes_for_csv_input(tmp_path):
    df = pd.DataFrame(
        {
            "document_id": list(range(8)),
            "year": list(range(2000, 2008)),
            "party_id": [1, 2] * 4,
            "n_documents": list(range(8)),
            "label": ["a", "b"] * 4,
        }
    ).set_index("document_id")
    df.to_csv(tmp_path / "sample_document_index.csv.gz", sep=";", compression="gzip")

    loaded = dtm_store.load_document_index("sample", str(tmp_path), categorical_threshold=4)

    assert loaded["year"].dtype == np.int16
    assert loaded["n_documents"].dtype == np.int32
    assert str(loaded["party_id"].dtype) == "category"
    assert str(loaded["label"].dtype) == "category"


def test_load_document_index_raises_for_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        dtm_store.load_document_index("missing", str(tmp_path))


def test_store_metadata_and_load_metadata_round_trip(tmp_path):
    document_index = _create_document_index()
    token2id = defaultdict(int, {"budget": 0, "debatt": 1})
    overridden_term_frequency = np.array([4, 7], dtype=np.int32)

    dtm_store.store_metadata(
        tag="sample",
        folder=str(tmp_path),
        document_index=document_index,
        token2id=token2id,
        overridden_term_frequency=overridden_term_frequency,
    )

    metadata = dtm_store.load_metadata(tag="sample", folder=str(tmp_path))

    assert metadata["token2id"] == {"budget": 0, "debatt": 1}
    assert metadata["document_index"]["document_name"].tolist() == ["doc0", "doc1"]
    np.testing.assert_array_equal(metadata["overridden_term_frequency"], overridden_term_frequency)


def test_store_metadata_rejects_invalid_modes(tmp_path):
    document_index = _create_document_index()

    with pytest.raises(DeprecationWarning):
        dtm_store.store_metadata(
            tag="sample",
            folder=str(tmp_path),
            mode="bundle",
            document_index=document_index,
            token2id={"budget": 0},
        )

    with pytest.raises(ValueError):
        dtm_store.store_metadata(
            tag="sample",
            folder=str(tmp_path),
            mode="invalid",
            document_index=document_index,
            token2id={"budget": 0},
        )


def test_dump_corpus_and_load_round_trip(tmp_path):
    corpus = _create_corpus(
        bag_term_matrix=scipy.sparse.csr_matrix([[1, 2], [0, 3]]),
        token2id={"budget": 0, "debatt": 1},
        document_index=_create_document_index(),
    )

    dtm_store.dump_corpus(corpus, tag="sample", folder=str(tmp_path), compressed=True)

    npz_filename = tmp_path / "sample_vector_data.npz"
    assert dtm_store.dump_exists(tag="sample", folder=str(tmp_path))
    assert dtm_store.is_dump(str(npz_filename))
    assert "sample" in dtm_store.find_tags(str(tmp_path))
    assert dtm_store.split(str(npz_filename)) == (str(tmp_path), "sample")

    loaded_by_tag = dtm_store.load(tag="sample", folder=str(tmp_path))
    loaded_by_filename = dtm_store.load(filename=str(npz_filename))

    for loaded in (loaded_by_tag, loaded_by_filename):
        assert isinstance(loaded, VectorizedCorpus)
        assert loaded.token2id == corpus.token2id
        np.testing.assert_array_equal(loaded.bag_term_matrix.toarray(), corpus.bag_term_matrix.toarray())


def test_dump_corpus_uncompressed_can_be_loaded(tmp_path):
    corpus = _create_corpus(
        bag_term_matrix=scipy.sparse.csr_matrix([[1, 0], [2, 3]]),
        token2id={"budget": 0, "debatt": 1},
        document_index=_create_document_index(),
    )

    dtm_store.dump_corpus(corpus, tag="sample", folder=str(tmp_path), compressed=False)

    loaded = dtm_store.load(tag="sample", folder=str(tmp_path))

    np.testing.assert_array_equal(loaded.bag_term_matrix.toarray(), corpus.bag_term_matrix.toarray())


def test_load_converts_term_frequency_mapping_to_ordered_array(monkeypatch, tmp_path):
    document_index = _create_document_index()
    captured = {}
    sentinel = object()

    monkeypatch.setattr(dtm_store, "dump_exists", lambda *, tag, folder: True)
    monkeypatch.setattr(
        dtm_store,
        "load_metadata",
        lambda *, tag, folder: {
            "token2id": {"budget": 0, "debatt": 1},
            "document_index": document_index,
            "term_frequency_mapping": {"budget": 5, "debatt": 9},
        },
    )
    monkeypatch.setattr(dtm_store.os.path, "isfile", lambda filename: str(filename).endswith("_vector_data.npz"))
    monkeypatch.setattr(dtm_store.scipy.sparse, "load_npz", lambda filename: scipy.sparse.csr_matrix([[1, 0], [0, 1]]))

    def fake_create_corpus_instance(bag_term_matrix, token2id, document_index, overridden_term_frequency=None):
        captured["bag_term_matrix"] = bag_term_matrix
        captured["token2id"] = token2id
        captured["document_index"] = document_index
        captured["overridden_term_frequency"] = overridden_term_frequency
        return sentinel

    monkeypatch.setattr(dtm_store, "create_corpus_instance", fake_create_corpus_instance)

    loaded = dtm_store.load(tag="sample", folder=str(tmp_path))

    assert loaded is sentinel
    np.testing.assert_array_equal(captured["overridden_term_frequency"], np.array([5, 9]))
    assert captured["token2id"] == {"budget": 0, "debatt": 1}
    assert captured["document_index"] is document_index


def test_dump_and_load_options_round_trip(tmp_path):
    options = {"ngram": 2, "token_filter": ["budget", "debatt"]}

    dtm_store.dump_options(tag="sample", folder=str(tmp_path), options=options)

    assert dtm_store.load_options(tag="sample", folder=str(tmp_path)) == options
    assert dtm_store.load_options(tag="missing", folder=str(tmp_path)) == {}


def test_remove_deletes_all_matching_dump_files(tmp_path):
    filenames = [
        "sample_vector_data.npz",
        "sample_vectorizer_data.json",
        "sample_document_index.csv.gz",
        "sample_token2id.json.gz",
        "sample_overridden_term_frequency.npy",
    ]
    for filename in filenames:
        (tmp_path / filename).write_text("x", encoding="utf-8")

    dtm_store.remove(tag="sample", folder=str(tmp_path))

    assert not any(Path(tmp_path).iterdir())


def test_load_unique_document_index_requires_one_dump(tmp_path):
    missing_folder = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        dtm_store.load_unique_document_index(str(missing_folder))

    folder_with_many = tmp_path / "many"
    folder_with_many.mkdir()
    (folder_with_many / "a_vector_data.npz").write_text("x", encoding="utf-8")
    (folder_with_many / "b_vector_data.npz").write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        dtm_store.load_unique_document_index(str(folder_with_many))


def test_load_unique_document_index_returns_document_index_for_single_dump(tmp_path):
    corpus = _create_corpus(
        bag_term_matrix=scipy.sparse.csr_matrix([[1, 0], [0, 1]]),
        token2id={"budget": 0, "debatt": 1},
        document_index=_create_document_index(),
    )
    dtm_store.dump_corpus(corpus, tag="sample", folder=str(tmp_path), compressed=True)

    document_index = dtm_store.load_unique_document_index(str(tmp_path))

    assert document_index["document_name"].tolist() == ["doc0", "doc1"]
