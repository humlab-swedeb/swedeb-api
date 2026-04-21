import numpy as np
import pandas as pd
import scipy.sparse

from api_swedeb.core.dtm import VectorizedCorpus, find_matching_words_in_vocabulary


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


# Regression tests for group_DTM_by_indices_mapping optimization
# Tests ensure the optimized version produces identical results to the original


def test_group_DTM_by_indices_mapping_sum_aggregation_preserves_correctness():
    """Regression test: Sum aggregation should produce identical results."""
    document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2, 3, 4, 5],
            "document_name": ["doc0", "doc1", "doc2", "doc3", "doc4", "doc5"],
            "year": [2020, 2020, 2021, 2021, 2022, 2022],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {"word_a": 0, "word_b": 1, "word_c": 2, "word_d": 3}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 2, 0, 0],  # doc0 (2020)
            [0, 3, 4, 0],  # doc1 (2020)
            [5, 0, 6, 0],  # doc2 (2021)
            [0, 1, 0, 2],  # doc3 (2021)
            [3, 0, 0, 1],  # doc4 (2022)
            [0, 2, 1, 0],  # doc5 (2022)
        ]
    )
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Group by year (category_indices maps new_doc_id -> list of old doc_ids)
    category_indices = {
        0: [0, 1],  # year 2020 -> docs 0, 1
        1: [2, 3],  # year 2021 -> docs 2, 3
        2: [4, 5],  # year 2022 -> docs 4, 5
    }
    
    # Create new document index for grouped result
    new_document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2],
            "document_name": ["2020", "2021", "2022"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    
    # Verify result structure
    assert scipy.sparse.isspmatrix_csr(result.bag_term_matrix)
    assert result.shape == (3, 4)  # 3 years, 4 words
    
    # Verify sum aggregation: each year should be sum of its documents
    expected = [
        [1, 5, 4, 0],   # 2020: doc0[1,2,0,0] + doc1[0,3,4,0] = [1,5,4,0]
        [5, 1, 6, 2],   # 2021: doc2[5,0,6,0] + doc3[0,1,0,2] = [5,1,6,2]
        [3, 2, 1, 1],   # 2022: doc4[3,0,0,1] + doc5[0,2,1,0] = [3,2,1,1]
    ]
    np.testing.assert_array_equal(result.bag_term_matrix.toarray(), expected)


def test_group_DTM_by_indices_mapping_mean_aggregation_preserves_correctness():
    """Regression test: Mean aggregation should produce identical results."""
    document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2, 3],
            "document_name": ["doc0", "doc1", "doc2", "doc3"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {"a": 0, "b": 1, "c": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [10, 20, 0],  # doc0
            [30, 40, 0],  # doc1
            [0, 50, 60],  # doc2
            [0, 70, 80],  # doc3
        ],
        dtype=np.float64,
    )
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Group: category 0 has 2 docs, category 1 has 2 docs
    category_indices = {
        0: [0, 1],  # docs 0, 1
        1: [2, 3],  # docs 2, 3
    }
    
    new_document_index = pd.DataFrame(
        {
            "document_id": [0, 1],
            "document_name": ["group0", "group1"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="mean")
    
    # Verify mean aggregation: each category should be mean of its documents
    expected = [
        [20.0, 30.0, 0.0],   # mean([10,20,0], [30,40,0]) = [20,30,0]
        [0.0, 60.0, 70.0],   # mean([0,50,60], [0,70,80]) = [0,60,70]
    ]
    np.testing.assert_allclose(result.bag_term_matrix.toarray(), expected)


def test_group_DTM_by_indices_mapping_handles_empty_groups():
    """Regression test: Empty groups should be handled correctly."""
    document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2],
            "document_name": ["doc0", "doc1", "doc2"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {"a": 0, "b": 1}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 2],
            [3, 4],
            [5, 6],
        ]
    )
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Include empty groups (they should be skipped)
    category_indices = {
        0: [0],      # Single doc
        1: [],       # Empty group
        2: [1, 2],   # Two docs
        3: [],       # Empty group
    }
    
    new_document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2, 3],
            "document_name": ["cat0", "cat1", "cat2", "cat3"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    
    # Empty groups should result in zero rows
    assert result.shape == (4, 2)
    expected = [
        [1, 2],      # category 0: doc0
        [0, 0],      # category 1: empty
        [8, 10],     # category 2: doc1 + doc2
        [0, 0],      # category 3: empty
    ]
    np.testing.assert_array_equal(result.bag_term_matrix.toarray(), expected)


def test_group_DTM_by_indices_mapping_handles_single_element_groups():
    """Regression test: Single-element groups should work correctly."""
    document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2],
            "document_name": ["doc0", "doc1", "doc2"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {"x": 0, "y": 1, "z": 2}
    bag_term_matrix = scipy.sparse.csr_matrix(
        [
            [1, 0, 3],
            [0, 2, 0],
            [4, 5, 6],
        ]
    )
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Each document in its own group
    category_indices = {
        0: [0],
        1: [1],
        2: [2],
    }
    
    new_document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2],
            "document_name": ["doc0_solo", "doc1_solo", "doc2_solo"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    
    # Should be identical to original matrix (just reindexed)
    assert result.shape == (3, 3)
    expected = [
        [1, 0, 3],
        [0, 2, 0],
        [4, 5, 6],
    ]
    np.testing.assert_array_equal(result.bag_term_matrix.toarray(), expected)


def test_group_DTM_by_indices_mapping_preserves_sparsity():
    """Regression test: Sparse matrix structure should be preserved."""
    # Create a large sparse matrix
    n_docs = 1000
    n_terms = 500
    density = 0.01  # 1% non-zero
    
    document_index = pd.DataFrame(
        {
            "document_id": list(range(n_docs)),
            "document_name": [f"doc{i}" for i in range(n_docs)],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {f"word{i}": i for i in range(n_terms)}
    
    # Create sparse matrix with controlled density
    bag_term_matrix = scipy.sparse.random(n_docs, n_terms, density=density, format='csr')
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Group into 100 categories
    docs_per_category = n_docs // 100
    category_indices = {
        cat_id: list(range(cat_id * docs_per_category, (cat_id + 1) * docs_per_category))
        for cat_id in range(100)
    }
    
    new_document_index = pd.DataFrame(
        {
            "document_id": list(range(100)),
            "document_name": [f"cat{i}" for i in range(100)],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    
    # Verify sparsity is maintained
    assert scipy.sparse.isspmatrix_csr(result.bag_term_matrix)
    assert result.shape == (100, n_terms)
    
    # Sparsity should be similar (might increase slightly due to aggregation)
    original_density = corpus.bag_term_matrix.nnz / (n_docs * n_terms)
    result_density = result.bag_term_matrix.nnz / (100 * n_terms)
    assert result_density <= 0.15  # Should stay reasonably sparse


def test_group_DTM_by_indices_mapping_large_scale_correctness():
    """Regression test: Large-scale grouping should maintain correctness."""
    # Simulate realistic corpus: 10K documents grouped into 150 years
    n_docs = 10000
    n_years = 150
    n_terms = 100
    
    document_index = pd.DataFrame(
        {
            "document_id": list(range(n_docs)),
            "document_name": [f"speech_{i}" for i in range(n_docs)],
            "year": [1867 + (i % n_years) for i in range(n_docs)],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {f"term{i}": i for i in range(n_terms)}
    
    # Create realistic sparse matrix (1% density)
    bag_term_matrix = scipy.sparse.random(n_docs, n_terms, density=0.01, format='csr')
    bag_term_matrix.data = np.round(bag_term_matrix.data * 100)  # Integer counts
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    # Group by year
    category_indices = {}
    for year_id in range(n_years):
        doc_ids = document_index[document_index['year'] == 1867 + year_id].index.tolist()
        category_indices[year_id] = doc_ids
    
    new_document_index = pd.DataFrame(
        {
            "document_id": list(range(n_years)),
            "document_name": [f"year_{1867+i}" for i in range(n_years)],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    # Test sum aggregation
    result_sum = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    assert result_sum.shape == (n_years, n_terms)
    assert scipy.sparse.isspmatrix_csr(result_sum.bag_term_matrix)
    
    # Verify a specific year manually
    year_0_docs = category_indices[0]
    expected_year_0_sum = corpus.bag_term_matrix[year_0_docs].sum(axis=0).A1
    actual_year_0_sum = result_sum.bag_term_matrix[0].toarray()[0]
    np.testing.assert_array_equal(actual_year_0_sum, expected_year_0_sum)
    
    # Test mean aggregation
    result_mean = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="mean")
    expected_year_0_mean = corpus.bag_term_matrix[year_0_docs].mean(axis=0).A1
    actual_year_0_mean = result_mean.bag_term_matrix[0].toarray()[0]
    np.testing.assert_allclose(actual_year_0_mean, expected_year_0_mean, rtol=1e-10)


def test_group_DTM_by_indices_mapping_result_format_matches_original():
    """Regression test: Result should have correct structure and types."""
    document_index = pd.DataFrame(
        {
            "document_id": [0, 1, 2, 3],
            "document_name": ["a", "b", "c", "d"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    token2id = {"w1": 0, "w2": 1}
    bag_term_matrix = scipy.sparse.csr_matrix([[1, 2], [3, 4], [5, 6], [7, 8]])
    
    corpus = _create_corpus(
        bag_term_matrix=bag_term_matrix,
        token2id=token2id,
        document_index=document_index,
    )
    
    category_indices = {0: [0, 1], 1: [2, 3]}
    
    new_document_index = pd.DataFrame(
        {
            "document_id": [0, 1],
            "document_name": ["group0", "group1"],
        }
    ).set_index("document_id", drop=False).rename_axis("")
    
    result = corpus.group_by_indices_mapping(new_document_index, category_indices, aggregate="sum")
    
    # Verify result is a VectorizedCorpus with correct attributes
    assert isinstance(result, VectorizedCorpus)
    assert hasattr(result, 'bag_term_matrix')
    assert hasattr(result, 'token2id')
    assert hasattr(result, 'document_index')
    
    # Verify types
    assert scipy.sparse.isspmatrix_csr(result.bag_term_matrix)
    assert isinstance(result.token2id, dict)
    assert isinstance(result.document_index, pd.DataFrame)
    
    # Verify values
    assert result.token2id == token2id
    assert len(result.document_index) == 2
    np.testing.assert_array_equal(
        result.bag_term_matrix.toarray(),
        [[4, 6], [12, 14]]  # [1+3, 2+4], [5+7, 6+8]
    )
