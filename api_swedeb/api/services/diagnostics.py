from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import pandas as pd
import scipy.sparse

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.dtm.interface import IVectorizedCorpus
from api_swedeb.core.person_codecs import PersonCodecs
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore


@dataclass(frozen=True)
class MemoryUsageEntry:
    label: str
    description: str
    n_bytes: int
    children: tuple["MemoryUsageEntry", ...] = ()


@dataclass(frozen=True)
class MemoryUsageSection:
    label: str
    entries: tuple[MemoryUsageEntry, ...]

    @property
    def total_bytes(self) -> int:
        return sum(entry.n_bytes for entry in self.entries)


@dataclass(frozen=True)
class MemoryUsageReport:
    sections: tuple[MemoryUsageSection, ...]
    note: str = "Note: dict sizes are approximate; process RSS includes Python interpreter overhead."

    @property
    def total_bytes(self) -> int:
        return sum(section.total_bytes for section in self.sections)


def format_megabytes(n_bytes: int) -> str:
    return f"{n_bytes / 1024**2:>10,.1f} MB"


def dict_mem_usage(d: dict) -> int:
    """Estimate size of a flat dict; expands one level of tuple values."""
    total: int = sys.getsizeof(d)
    for k, v in d.items():
        total += sys.getsizeof(k) + sys.getsizeof(v)
        if isinstance(v, tuple):
            total += sum(sys.getsizeof(item) for item in v)
    return total


def dataframe_memory_usage(df: pd.DataFrame, label: str) -> MemoryUsageEntry:
    mem: pd.Series = df.memory_usage(deep=True)
    total: int = int(mem.sum())
    children: list[MemoryUsageEntry] = []
    for col, col_bytes in mem.items():
        if col == "Index":
            dtype = str(df.index.dtype)
        else:
            dtype = str(df[col].dtype)
        children.append(MemoryUsageEntry(label=str(col), description=dtype, n_bytes=int(col_bytes)))
    return MemoryUsageEntry(
        label=label,
        description=f"DataFrame, {len(df):,} rows",
        n_bytes=total,
        children=tuple(children),
    )


def dataframe_mem_usage(df: pd.DataFrame, label: str, indent: str = "  ") -> int:
    del indent
    return dataframe_memory_usage(df, label).n_bytes


def arrow_table_memory_usage(table: Any, label: str) -> MemoryUsageEntry:
    children = tuple(
        MemoryUsageEntry(label=name, description=str(table[name].type), n_bytes=int(table[name].nbytes))
        for name in table.column_names
    )
    return MemoryUsageEntry(
        label=label,
        description=f"Arrow Table, {table.num_rows:,} rows",
        n_bytes=int(table.nbytes),
        children=children,
    )


def tabular_memory_usage(table: Any, label: str) -> MemoryUsageEntry:
    if isinstance(table, pd.DataFrame):
        return dataframe_memory_usage(table, label)
    if all(hasattr(table, attr) for attr in ("column_names", "num_rows", "nbytes")):
        return arrow_table_memory_usage(table, label)
    raise TypeError(f"Unsupported tabular object for memory diagnostics: {type(table).__name__}")


def ndarray_memory_usage(label: str, arr: Any) -> MemoryUsageEntry:
    arr_b = int(arr.nbytes)
    return MemoryUsageEntry(label=label, description=f"ndarray {arr.dtype}, {len(arr):,} entries", n_bytes=arr_b)


def dict_memory_usage_entry(label: str, d: dict, description: str) -> MemoryUsageEntry:
    return MemoryUsageEntry(label=label, description=description, n_bytes=dict_mem_usage(d))


def sparse_matrix_memory_usage(label: str, matrix: Any) -> MemoryUsageEntry:
    data_b = int(matrix.data.nbytes)
    idx_b = int(matrix.indices.nbytes)
    indptr_b = int(matrix.indptr.nbytes)
    matrix_total = data_b + idx_b + indptr_b
    return MemoryUsageEntry(
        label=label,
        description=(f"{type(matrix).__name__}, dtype={matrix.data.dtype}, shape={matrix.shape}, nnz={matrix.nnz:,}"),
        n_bytes=matrix_total,
        children=(
            MemoryUsageEntry(label="data", description="", n_bytes=data_b),
            MemoryUsageEntry(label="indices", description="", n_bytes=idx_b),
            MemoryUsageEntry(label="indptr", description="", n_bytes=indptr_b),
        ),
    )


def array_like_memory_usage(label: str, arr: Any, description_label: str) -> MemoryUsageEntry:
    arr_b = int(arr.nbytes if hasattr(arr, "nbytes") else sys.getsizeof(arr))
    dtype_s: str = str(arr.dtype) if hasattr(arr, "dtype") else type(arr).__name__
    return MemoryUsageEntry(
        label=label,
        description=f"{description_label}, {dtype_s}, {len(arr):,} entries",
        n_bytes=arr_b,
    )


def _format_entry(entry: MemoryUsageEntry, indent: str, label: str | None = None) -> list[str]:
    entry_label = label or entry.label
    if entry.description:
        lines = [f"{indent}{entry_label} ({entry.description}): {format_megabytes(entry.n_bytes)}"]
    else:
        lines = [f"{indent}{entry_label}: {format_megabytes(entry.n_bytes)}"]

    for child in entry.children:
        if child.description:
            lines.append(f"{indent}  {child.label:<35} {child.description:<18} {format_megabytes(child.n_bytes)}")
        else:
            lines.append(f"{indent}  {child.label:<8} {format_megabytes(child.n_bytes)}")

    return lines


def _is_inline_section(section: MemoryUsageSection) -> bool:
    return len(section.entries) == 1 and section.entries[0].label == section.label


def format_memory_usage_report(report: MemoryUsageReport) -> str:
    lines: list[str] = [
        "=" * 72,
        "CorpusLoader Memory Usage",
        "=" * 72,
    ]

    for section in report.sections:
        lines.append("")
        if _is_inline_section(section):
            lines.extend(_format_entry(section.entries[0], indent="", label=f"[{section.label}]"))
            continue

        lines.append(f"[{section.label}]")
        for entry in section.entries:
            lines.extend(_format_entry(entry, indent="  "))

    lines.extend(
        [
            "",
            "=" * 72,
            f"TOTAL (measured):  {format_megabytes(report.total_bytes)}",
            "=" * 72,
            report.note,
        ]
    )
    return "\n".join(lines)


def print_memory_usage_report(report: MemoryUsageReport) -> None:
    print(format_memory_usage_report(report))


def dataframe_memory_usage_section(df: pd.DataFrame, label: str) -> MemoryUsageSection:
    return MemoryUsageSection(label=label, entries=(dataframe_memory_usage(df, label),))


def dict_memory_usage_section(label: str, d: dict, description: str) -> MemoryUsageSection:
    return MemoryUsageSection(label=label, entries=(dict_memory_usage_entry(label, d, description),))


def dtm_memory_usage_report(corpus_loader: CorpusLoader) -> MemoryUsageSection:
    vc: IVectorizedCorpus = corpus_loader._lazy_vectorized_corpus.value
    entries: list[MemoryUsageEntry] = []

    btm = vc.bag_term_matrix
    if scipy.sparse.issparse(btm):
        entries.append(sparse_matrix_memory_usage("bag_term_matrix", btm))

    entries.append(dataframe_memory_usage(vc.document_index, "document_index"))

    t2id: dict[str, int] = vc.token2id
    entries.append(dict_memory_usage_entry("token2id", t2id, f"dict, {len(t2id):,} terms"))

    otf = vc.overridden_term_frequency
    if otf is not None:
        entries.append(array_like_memory_usage("overridden_term_frequency", otf, "ndarray"))

    return MemoryUsageSection(label="vectorized_corpus", entries=tuple(entries))


def speech_repository_memory_usage_report(corpus_loader: CorpusLoader) -> MemoryUsageSection:
    repo: SpeechRepository = corpus_loader._lazy_repository.value
    store: SpeechStore = repo._store
    entries: list[MemoryUsageEntry] = [
        tabular_memory_usage(p, f"_protocol_cache['{k}']") for k, p in store._protocol_cache.items() if p is not None
    ]

    for arr_name in ("_sorted_sids", "_sid_ff_codes", "_sid_fr"):
        arr = getattr(store, arr_name)
        if arr is None:
            continue
        entries.append(ndarray_memory_usage(arr_name, arr))

    catalog_b: int = int(store._feather_files.nbytes)
    entries.append(
        MemoryUsageEntry(
            label="_feather_files",
            description=f"ndarray, {len(store._feather_files)} unique paths",
            n_bytes=catalog_b,
        )
    )
    if "speaker_note_id2note" in repo.__dict__:
        sn: dict[str, str | None] = repo.speaker_note_id2note
        entries.append(dict_memory_usage_entry("speaker_note_id2note", sn, f"dict, {len(sn):,} entries"))

    return MemoryUsageSection(label="repository.SpeechStore", entries=tuple(entries))


def person_codecs_memory_usage_report(corpus_loader: CorpusLoader) -> MemoryUsageSection:
    pc: PersonCodecs = corpus_loader._lazy_person_codecs.value
    entries: list[MemoryUsageEntry] = [
        dataframe_memory_usage(table, f"store['{name}']") for name, table in pc.store.items()
    ]
    maps_b: int = sum(dict_mem_usage(v) for v in pc.mappings.values()) + sys.getsizeof(pc.mappings)
    entries.append(
        MemoryUsageEntry(label="mappings", description=f"dict, {len(pc.mappings)} codec maps", n_bytes=maps_b)
    )
    return MemoryUsageSection(label="person_codecs", entries=tuple(entries))


def compute_memory_usage(corpus_loader: CorpusLoader) -> MemoryUsageReport:
    """Compute a detailed memory breakdown of all currently-loaded resources.

    Only initialized lazy members are reported. Call ``preload()`` first
    to measure the fully-loaded footprint.
    """

    sections: list[MemoryUsageSection] = []

    # ── vectorized_corpus ──────────────────────────────────────────────────
    if corpus_loader._lazy_vectorized_corpus.is_initialized:  # pylint: disable=using-constant-test
        sections.append(dtm_memory_usage_report(corpus_loader))

    # ── prebuilt_speech_index ──────────────────────────────────────────────
    if corpus_loader._lazy_prebuilt_speech_index.is_initialized:  # pylint: disable=using-constant-test
        sections.append(
            dataframe_memory_usage_section(corpus_loader._lazy_prebuilt_speech_index.value, "prebuilt_speech_index")
        )

    # ── person_codecs ──────────────────────────────────────────────────────
    if corpus_loader._lazy_person_codecs.is_initialized:  # pylint: disable=using-constant-test
        sections.append(person_codecs_memory_usage_report(corpus_loader))

    # ── repository / SpeechStore ───────────────────────────────────────────
    if corpus_loader._lazy_repository.is_initialized:  # pylint: disable=using-constant-test
        sections.append(speech_repository_memory_usage_report(corpus_loader))

    # ── decoded_persons ────────────────────────────────────────────────────
    if "decoded_persons" in corpus_loader.__dict__:
        sections.append(dataframe_memory_usage_section(corpus_loader.decoded_persons, "decoded_persons"))

    # ── prebuilt_page_number_index ─────────────────────────────────────────
    if corpus_loader._lazy_prebuilt_page_number_index.is_initialized:  # pylint: disable=using-constant-test
        pni: dict[str, tuple[int, int]] = corpus_loader._lazy_prebuilt_page_number_index.value
        sections.append(dict_memory_usage_section("prebuilt_page_number_index", pni, f"dict, {len(pni):,} entries"))

    return MemoryUsageReport(sections=tuple(sections))


def dtm_memory_usage(corpus_loader: CorpusLoader) -> int:
    return dtm_memory_usage_report(corpus_loader).total_bytes


def speech_repository_mem_usage(corpus_loader: CorpusLoader) -> int:
    return speech_repository_memory_usage_report(corpus_loader).total_bytes


def person_codec_mem_usage(corpus_loader: CorpusLoader) -> int:
    return person_codecs_memory_usage_report(corpus_loader).total_bytes


def memory_usage(corpus_loader: CorpusLoader) -> MemoryUsageReport:
    """Print a detailed memory breakdown of all currently-loaded resources.

    DataFrame sections include a per-column breakdown.
    dict sizes are approximate (shallow ``sys.getsizeof`` on keys/values).
    """

    report: MemoryUsageReport = compute_memory_usage(corpus_loader)
    print_memory_usage_report(report)
    return report
