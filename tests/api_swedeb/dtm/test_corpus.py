import numpy as np
import pandas as pd
import scipy.sparse

from penelope.corpus import VectorizedCorpus, find_matching_words_in_vocabulary


def _create_corpus(*, bag_term_matrix, token2id, document_index) -> VectorizedCorpus:
    return VectorizedCorpus(  # type: ignore[reportAbstractUsage]
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )


def test_zero_out_by_indices_preserves_csr_shape_and_skips_zero_tf_columns():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1, 2],
                "document_name": ["doc1", "doc2", "doc3"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"a": 0, "b": 1, "c": 2, "d": 3}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 2, 0, 0],
            [0, 3, 4, 0],
            [5, 0, 6, 0],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    zeroed_indices = corpus.zero_out_by_indices([1, 3, 1])

    assert zeroed_indices == [1]
    assert scipy.sparse.isspmatrix_csr(corpus.bag_term_matrix)
    assert corpus.shape == (3, 4)
    assert corpus.bag_term_matrix.toarray().tolist() == [
        [1, 0, 0, 0],
        [0, 0, 4, 0],
        [5, 0, 6, 0],
    ]


def test_zero_out_by_indices_returns_empty_when_all_targets_are_already_zero():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc1", "doc2"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"a": 0, "b": 1}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 0],
            [2, 0],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    zeroed_indices = corpus.zero_out_by_indices([1])

    assert zeroed_indices == []
    assert scipy.sparse.isspmatrix_csr(corpus.bag_term_matrix)
    assert corpus.bag_term_matrix.toarray().tolist() == [
        [1, 0],
        [2, 0],
    ]


def test_find_matching_words_in_vocabulary_matches_prefix_globs_without_full_pattern_scan_per_expr():
    token2id = {
        "budget": 0,
        "budgeten": 1,
        "budgetering": 2,
        "demokrati": 3,
        "debatt": 4,
    }

    matches = find_matching_words_in_vocabulary(token2id, ["bud*", "deb*"])

    assert matches == {"budget", "budgeten", "budgetering", "debatt"}


def test_find_matching_words_respects_updated_vocabulary_after_inplace_slice():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc1", "doc2"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"budget": 0, "budgeten": 1, "debatt": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 1, 0],
            [0, 1, 1],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    initial_matches = corpus.find_matching_words(["bud*"], n_max_count=None)
    corpus.slice_by_indices([2], inplace=True)
    updated_matches = corpus.find_matching_words(["bud*"], n_max_count=None)

    assert set(initial_matches) == {"budget", "budgeten"}
    assert updated_matches == []


def test_term_frequency_is_cached_until_matrix_changes():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1, 2],
                "document_name": ["doc1", "doc2", "doc3"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"a": 0, "b": 1, "c": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 2, 0],
            [0, 3, 4],
            [5, 0, 6],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    first = corpus.term_frequency
    second = corpus.term_frequency
    assert isinstance(first, np.ndarray)
    assert isinstance(second, np.ndarray)

    assert first is second
    assert first.tolist() == [6, 5, 10]

    corpus.zero_out_by_indices([1])
    updated = corpus.term_frequency
    assert isinstance(updated, np.ndarray)

    assert updated is not first
    assert updated.tolist() == [6, 0, 10]


def test_term_frequency_cache_is_invalidated_on_inplace_slice():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc1", "doc2"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"budget": 0, "budgeten": 1, "debatt": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 1, 0],
            [0, 1, 1],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    original = corpus.term_frequency
    corpus.slice_by_indices([2], inplace=True)
    sliced = corpus.term_frequency
    assert isinstance(original, np.ndarray)
    assert isinstance(sliced, np.ndarray)

    assert original.tolist() == [1, 2, 1]
    assert sliced.tolist() == [1]
    assert sliced is not original


def test_find_matching_words_respects_updated_vocabulary_after_inplace_translate():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc1", "doc2"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"budget": 0, "budgeten": 1, "debatt": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 1, 0],
            [0, 1, 1],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    initial_matches = corpus.find_matching_words(["bud*"], n_max_count=None)
    corpus.translate_to_vocab({0: "debatt"}, inplace=True)
    updated_matches = corpus.find_matching_words(["bud*"], n_max_count=None)

    assert set(initial_matches) == {"budget", "budgeten"}
    assert updated_matches == []


def test_term_frequency_cache_is_invalidated_on_inplace_translate():
    document_index = (
        pd.DataFrame(
            {
                "document_id": [0, 1],
                "document_name": ["doc1", "doc2"],
            }
        )
        .set_index("document_id", drop=False)
        .rename_axis("")
    )
    token2id = {"budget": 0, "budgeten": 1, "debatt": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 1, 0],
            [0, 1, 1],
        ]
    )

    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )

    original = corpus.term_frequency
    corpus.translate_to_vocab({0: "debatt"}, inplace=True)
    translated = corpus.term_frequency
    assert isinstance(original, np.ndarray)
    assert isinstance(translated, np.ndarray)

    assert original.tolist() == [1, 2, 1]
    assert translated.tolist() == [1]
    assert translated is not original
