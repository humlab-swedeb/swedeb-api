import sys

import pandas as pd
import scipy.sparse

from api_swedeb.core.dtm.interface import IVectorizedCorpus
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore

from .corpus_loader import CorpusLoader


def format_megabytes(n_bytes: int) -> str:
    return f"{n_bytes / 1024 ** 2:>10,.1f} MB"


def dataframe_mem_usage(df: pd.DataFrame, label: str, indent: str = "  ") -> int:
    mem: pd.Series = df.memory_usage(deep=True)
    total: int = int(mem.sum())
    print(f"{indent}{label} (DataFrame, {len(df):,} rows): {format_megabytes(total)}")
    for col, col_bytes in mem.items():
        if col == "Index":
            dtype = str(df.index.dtype)
        else:
            dtype = str(df[col].dtype)
        print(f"{indent}  {col:<35} {dtype:<18} {format_megabytes(int(col_bytes))}")
    return total


def dict_mem_usage(d: dict) -> int:
    """Estimate size of a flat dict; expands one level of tuple values."""
    total: int = sys.getsizeof(d)
    for k, v in d.items():
        total += sys.getsizeof(k) + sys.getsizeof(v)
        if isinstance(v, tuple):
            total += sum(sys.getsizeof(item) for item in v)
    return total


def dtm_memory_usage(corpus_loader: CorpusLoader) -> int:
    vc: IVectorizedCorpus = corpus_loader.__lazy_vectorized_corpus.value
    print("\n[vectorized_corpus]")
    total: int = 0

    btm = vc.bag_term_matrix
    if scipy.sparse.issparse(btm):
        data_b = btm.data.nbytes
        idx_b = btm.indices.nbytes
        indptr_b = btm.indptr.nbytes
        btm_total = data_b + idx_b + indptr_b
        total += btm_total
        print(
            f"  bag_term_matrix ({type(btm).__name__}, dtype={btm.data.dtype},"
            f" shape={btm.shape}, nnz={btm.nnz:,}): {format_megabytes(btm_total)}"
        )
        print(f"    data    {format_megabytes(data_b)}")
        print(f"    indices {format_megabytes(idx_b)}")
        print(f"    indptr  {format_megabytes(indptr_b)}")

    di: pd.DataFrame = vc.document_index
    total += dataframe_mem_usage(di, "document_index")

    t2id: dict[str, int] = vc.token2id
    t2id_b: int = dict_mem_usage(t2id)
    total += t2id_b
    print(f"  token2id (dict, {len(t2id):,} terms): {format_megabytes(t2id_b)}")

    otf = vc.overridden_term_frequency
    if otf is not None:
        otf_b = otf.nbytes if hasattr(otf, "nbytes") else sys.getsizeof(otf)  # type: ignore
        total += otf_b
        dtype_s: str = str(otf.dtype) if hasattr(otf, "dtype") else type(otf).__name__  # type: ignore
        print(f"  overridden_term_frequency (ndarray, {dtype_s}, {len(otf):,} entries): {format_megabytes(otf_b)}")

    return total


def speech_repository_mem_usage(corpus_loader: CorpusLoader) -> int:
    repo: SpeechRepository = corpus_loader.__lazy_repository.value
    store: SpeechStore = repo._store
    print("\n[repository.SpeechStore]")
    total = 0
    for arr_name in ("_sorted_sids", "_sorted_names", "_sid_ff_codes", "_name_ff_codes", "_sid_fr", "_name_fr"):
        arr = getattr(store, arr_name)
        arr_b = arr.nbytes
        total += arr_b
        print(f"  {arr_name:<28} (ndarray {arr.dtype}, {len(arr):,} entries): {format_megabytes(arr_b)}")
    catalog_b = store._feather_files.nbytes
    total += catalog_b
    print(
        f"  {'_feather_files':<28} (ndarray, {len(store._feather_files)} unique paths): {format_megabytes(catalog_b)}"
    )
    if "speaker_note_id2note" in repo.__dict__:
        sn = repo.speaker_note_id2note
        sn_b: int = dict_mem_usage(sn)
        total += sn_b
        print(f"  speaker_note_id2note (dict, {len(sn):,} entries): {format_megabytes(sn_b)}")

    return total


def person_codec_mem_usage(corpus_loader: CorpusLoader) -> int:
    pc = corpus_loader.__lazy_person_codecs.value
    print("\n[person_codecs]")
    total: int = 0
    for name, table in pc.store.items():
        total += dataframe_mem_usage(table, f"store['{name}']")
    maps_b = sum(dict_mem_usage(v) for v in pc.mappings.values()) + sys.getsizeof(pc.mappings)
    total += maps_b
    print(f"  mappings (dict, {len(pc.mappings)} codec maps): {format_megabytes(maps_b)}")

    return total


def memory_usage(corpus_loader: CorpusLoader) -> None:
    """Print a detailed memory breakdown of all currently-loaded resources.

    Only initialized lazy members are reported.  Call ``preload()`` first
    to measure the fully-loaded footprint.

    DataFrame sections include a per-column breakdown.
    dict sizes are approximate (shallow ``sys.getsizeof`` on keys/values).
    """

    grand_total: int = 0

    print("=" * 72)
    print("CorpusLoader Memory Usage")
    print("=" * 72)

    # ── vectorized_corpus ──────────────────────────────────────────────────
    if corpus_loader.__lazy_vectorized_corpus.is_initialized:  # pylint: disable=using-constant-test
        grand_total += dtm_memory_usage(corpus_loader)

    # ── prebuilt_speech_index ──────────────────────────────────────────────
    if corpus_loader.__lazy_prebuilt_speech_index.is_initialized:  # pylint: disable=using-constant-test
        print()
        grand_total += dataframe_mem_usage(
            corpus_loader.__lazy_prebuilt_speech_index.value, "[prebuilt_speech_index]", indent=""
        )

    # ── person_codecs ──────────────────────────────────────────────────────
    if corpus_loader.__lazy_person_codecs.is_initialized:  # pylint: disable=using-constant-test
        grand_total += person_codec_mem_usage(corpus_loader)

    # ── repository / SpeechStore ───────────────────────────────────────────
    if corpus_loader.__lazy_repository.is_initialized:  # pylint: disable=using-constant-test
        grand_total += speech_repository_mem_usage(corpus_loader)

    # ── decoded_persons ────────────────────────────────────────────────────
    if "decoded_persons" in corpus_loader.__dict__:
        print()
        grand_total += dataframe_mem_usage(corpus_loader.decoded_persons, "[decoded_persons]", indent="")

    # ── prebuilt_page_number_index ─────────────────────────────────────────
    if corpus_loader.__lazy_prebuilt_page_number_index.is_initialized:  # pylint: disable=using-constant-test
        pni = corpus_loader.__lazy_prebuilt_page_number_index.value
        pni_b = dict_mem_usage(pni)
        grand_total += pni_b
        print(f"\n[prebuilt_page_number_index] (dict, {len(pni):,} entries): {format_megabytes(pni_b)}")

    print()
    print("=" * 72)
    print(f"TOTAL (measured):  {format_megabytes(grand_total)}")
    print("=" * 72)
    print("Note: dict sizes are approximate; process RSS includes Python interpreter overhead.")
