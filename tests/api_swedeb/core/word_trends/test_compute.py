from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from api_swedeb.core.common import utility as pu
from api_swedeb.core.common.keyness import KeynessMetric
from api_swedeb.core.word_trends.compute import (
    SweDebComputeOpts,
    SweDebTrendsData,
    compute_word_trends,
    get_words_per_year,
)


def test_swedeb_compute_opts_clone_preserves_source_folder_and_clones_filter_opts():
    opts = SweDebComputeOpts(
        normalize=True,
        keyness=KeynessMetric.TF,
        temporal_key="year",
        filter_opts=pu.PropertyValueMaskingOpts(party_id=[1, 2]),
        source_folder="/tmp/source",
    )

    cloned = opts.clone

    assert cloned is not opts
    assert cloned.source_folder == "/tmp/source"
    assert cloned.filter_opts is not opts.filter_opts
    assert cloned.filter_opts is not None
    assert opts.filter_opts is not None
    assert cloned.filter_opts.props == opts.filter_opts.props


def test_update_document_index_decodes_and_uses_text_names_in_document_name():
    mock_codecs = Mock()
    mock_codecs.decode = Mock(
        return_value=pd.DataFrame(
            {
                "year": [2020],
                "person_id": [1],
                "person_name": ["Alice"],
                "region": ["North"],
            }
        )
    )
    mock_codecs.decoders = [SimpleNamespace(from_column="person_id", to_column="person_name")]

    trends_data = SweDebTrendsData(corpus=Mock(), person_codecs=mock_codecs)
    opts = SweDebComputeOpts(
        normalize=False,
        keyness=KeynessMetric.TF,
        temporal_key="year",
        pivot_keys_id_names=["person_id", "region"],
    )
    document_index = pd.DataFrame({"year": [2020], "person_id": [1], "region": ["North"]})

    result = trends_data.update_document_index(opts, document_index)

    mock_codecs.decode.assert_called_once_with(document_index, drop=False, ignores=["wiki_id"])
    assert result["document_name"].tolist() == ["Alice_North_2020"]
    assert result["filename"].tolist() == ["Alice_North_2020"]
    assert result["time_period"].tolist() == [2020]


def test_get_words_per_year_returns_cached_dataframe_without_recomputing():
    cached = pd.DataFrame({"n_raw_tokens": [10]}, index=["2020"])
    mock_corpus = Mock()
    mock_corpus.recall = Mock(return_value=cached)
    mock_corpus.remember = Mock()

    result = get_words_per_year(mock_corpus)

    assert result is cached
    mock_corpus.remember.assert_not_called()


@patch("api_swedeb.core.word_trends.compute.SweDebTrendsData")
def test_compute_word_trends_builds_opts_and_omits_total_for_single_metric(mock_trends_class):
    mock_corpus = Mock()
    mock_codecs = Mock()
    mock_codecs.property_values_specs = []

    decoded = pd.DataFrame({"year": [2020, 2021], "count": [3, 5]})
    mock_codecs.decode = Mock(return_value=decoded.copy())

    mock_trends_instance = Mock()
    mock_trends_instance.person_codecs = mock_codecs
    mock_trends_instance.find_word_indices = Mock(return_value=[7])
    mock_trends_instance.extract = Mock(return_value=pd.DataFrame({"year": [2020, 2021], "count": [3, 5]}))
    mock_trends_class.return_value = mock_trends_instance

    result = compute_word_trends(
        vectorized_corpus=mock_corpus,
        person_codecs=mock_codecs,
        search_terms=["demokrati"],
        filter_opts={},
        normalize=True,
    )

    opts = mock_trends_instance.transform.call_args.args[0]
    assert isinstance(opts, SweDebComputeOpts)
    assert opts.normalize is True
    assert opts.words == ["demokrati"]
    assert opts.pivot_keys_id_names == []
    assert isinstance(opts.filter_opts, pu.PropertyValueMaskingOpts)
    assert opts.filter_opts.props == {}
    mock_trends_instance.find_word_indices.assert_called_once_with(opts)
    mock_trends_instance.extract.assert_called_once_with(indices=[7])
    mock_codecs.decode.assert_called_once()
    decode_df = mock_codecs.decode.call_args.args[0]
    pd.testing.assert_frame_equal(decode_df, pd.DataFrame({"year": [2020, 2021], "count": [3, 5]}))
    assert mock_codecs.decode.call_args.kwargs == {"ignores": ["wiki_id", "party"], "drop": True}
    assert result.columns.tolist() == ["count"]
    assert "Totalt" not in result.columns
    assert result.index.tolist() == ["2020", "2021"]


@patch("api_swedeb.core.word_trends.compute.pu.unstack_data")
@patch("api_swedeb.core.word_trends.compute.SweDebTrendsData")
def test_compute_word_trends_unstacks_only_known_pivot_text_columns(mock_trends_class, mock_unstack):
    mock_corpus = Mock()
    mock_codecs = Mock()
    mock_codecs.property_values_specs = [{"text_name": "party"}, {"text_name": "gender"}]

    extracted = pd.DataFrame(
        {
            "year": [2020, 2020],
            "who": ["speaker-1", "speaker-2"],
            "party": ["A", "B"],
            "other": ["x", "y"],
            "count": [10, 15],
        }
    )
    decoded = extracted.rename(columns={"who": "person_id"})
    mock_codecs.decode = Mock(return_value=decoded.copy())

    mock_trends_instance = Mock()
    mock_trends_instance.person_codecs = mock_codecs
    mock_trends_instance.find_word_indices = Mock(return_value=[0, 1])
    mock_trends_instance.extract = Mock(return_value=extracted.copy())
    mock_trends_class.return_value = mock_trends_instance

    mock_unstack.return_value = pd.DataFrame({"A": [10], "B": [15]}, index=["2020"])

    result = compute_word_trends(
        vectorized_corpus=mock_corpus,
        person_codecs=mock_codecs,
        search_terms=["demokrati"],
        filter_opts={"year": (2020, 2021), "party_id": [1, 2], "other_filter": ["x"]},
        normalize=False,
    )

    opts = mock_trends_instance.transform.call_args.args[0]
    assert opts.pivot_keys_id_names == ["party_id", "other_filter"]
    assert opts.filter_opts is not None
    assert opts.filter_opts.props == {"party_id": [1, 2], "other_filter": ["x"]}
    mock_unstack.assert_called_once()
    assert mock_unstack.call_args.args[1] == ["year", "party"]
    assert result.columns.tolist() == ["A", "B", "Totalt"]
    assert result.loc["2020", "Totalt"] == 25
