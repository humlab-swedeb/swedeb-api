import pytest
import pandas as pd
from unittest.mock import MagicMock
from api_swedeb.core.kwic.complex import kwic
from ccc import Corpus, SubCorpus


@pytest.fixture
def mock_corpus():
    corpus = MagicMock(spec=Corpus)
    subcorpus = MagicMock(spec=SubCorpus)
    subcorpus.concordance.return_value = pd.DataFrame(
        {
            "left_word": ["word1", "word2"],
            "node_word": ["keyword", "keyword"],
            "right_word": ["word3", "word4"],
            "speech_id": ["id1", "id2"],
        }
    )
    corpus.query.return_value = subcorpus
    return corpus


@pytest.fixture
def mock_decoder():
    decoder = MagicMock()
    decoder.decode_speech_index.return_value = None
    decoder.decode.return_value = None
    return decoder


@pytest.fixture
def mock_speech_index():
    return pd.DataFrame({"speech_id": ["id1", "id2"], "speaker": ["Speaker1", "Speaker2"]}).set_index("speech_id")


def test_kwic_basic(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "left_word" in result.columns
    assert "node_word" in result.columns
    assert "right_word" in result.columns


def test_kwic_empty_result(mock_corpus):
    mock_corpus.query.return_value.concordance.return_value = pd.DataFrame()
    opts = {"keyword": "nonexistent", "target": "word"}
    result = kwic(corpus=mock_corpus, opts=opts, words_before=2, words_after=2)
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_kwic_with_speech_index(mock_corpus, mock_decoder, mock_speech_index):
    opts = {"keyword": "test", "target": "word"}
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        speech_index=mock_speech_index,
        decoder=mock_decoder,
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "speaker" in result.columns


def test_kwic_with_rename_columns(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    rename_columns = {"left_word": "before", "node_word": "keyword", "right_word": "after"}
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        rename_columns=rename_columns,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "before" in result.columns
    assert "keyword" in result.columns
    assert "after" in result.columns


def test_kwic_with_cut_off(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    cut_off = 10
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        cut_off=cut_off,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert len(result) <= cut_off


def test_kwic_with_custom_words_before_after(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    words_before = 3
    words_after = 4
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=words_before,
        words_after=words_after,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert len(result) == 2  # Adjust based on your mock data
    assert all(result["left_word"].str.split().str.len() <= words_before)
    assert all(result["right_word"].str.split().str.len() <= words_after)


def test_kwic_with_strip_s_tags(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    strip_s_tags = True
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        strip_s_tags=strip_s_tags,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "left_word" in result.columns
    assert "node_word" in result.columns
    assert "right_word" in result.columns
    assert "s_attr" not in result.columns  # Assuming s_attr is the column to be stripped


def test_kwic_with_s_strip_tags_false(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    strip_s_tags = False
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        strip_s_tags=strip_s_tags,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "left_word" in result.columns
    assert "node_word" in result.columns
    assert "right_word" in result.columns


def test_kwic_with_strip_s_show_and_strip_s_tags_true(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    s_show = ["s_attr"]
    strip_s_tags = True
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        s_show=s_show,
        strip_s_tags=strip_s_tags,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "left_word" in result.columns
    assert "node_word" in result.columns
    assert "right_word" in result.columns
    assert "s_attr" not in result.columns  # Assuming s_attr is the column to be stripped


def test_kwic_with_d_type(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    dtype = {"left_word": str, "node_word": str, "right_word": str}
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        dtype=dtype,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty


@pytest.mark.skip(reason="See #178. `compute_columns` not handled correctly")
def test_kwic_with_compute_columns(mock_corpus):
    opts = {"keyword": "test", "target": "word"}
    compute_columns = {"new_col": lambda x: x["left_word"] + " " + x["node_word"]}
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        compute_columns=compute_columns,
        display_columns=[],  # NOTE: display_columns needs to be set to avoid TypeError. See #177.
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert "new_col" in result.columns
    assert all(result["new_col"] == result["left_word"] + " " + result["node_word"])


def test_kwic_with_display_columns(mock_corpus, person_codecs):
    opts = {"keyword": "test", "target": "word"}
    display_columns = ["left_word", "node_word"]
    result = kwic(
        corpus=mock_corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        decoder=person_codecs,
        display_columns=display_columns,
    )
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert set(result.columns) == set(display_columns)
    assert "left_word" in result.columns
    assert "node_word" in result.columns
    assert "right_word" not in result.columns
    assert "speech_id" not in result.columns
