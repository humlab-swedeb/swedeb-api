import pandas as pd
import pyarrow as pa

from api_swedeb.api.services.diagnostics import (
    MemoryUsageEntry,
    MemoryUsageReport,
    MemoryUsageSection,
    arrow_table_memory_usage,
    dataframe_mem_usage,
    dataframe_memory_usage,
    format_memory_usage_report,
    print_memory_usage_report,
)


def test_dataframe_memory_usage_returns_report_without_printing(capsys):
    df = pd.DataFrame({"text": ["alpha", "beta"], "count": [1, 2]})

    usage = dataframe_memory_usage(df, "sample")

    assert capsys.readouterr().out == ""
    assert usage.label == "sample"
    assert usage.description == "DataFrame, 2 rows"
    assert usage.n_bytes == int(df.memory_usage(deep=True).sum())
    assert [child.label for child in usage.children] == ["Index", "text", "count"]


def test_dataframe_mem_usage_compatibility_helper_returns_total_without_printing(capsys):
    df = pd.DataFrame({"text": ["alpha", "beta"]})

    total = dataframe_mem_usage(df, "sample")

    assert capsys.readouterr().out == ""
    assert total == int(df.memory_usage(deep=True).sum())


def test_arrow_table_memory_usage_returns_report_without_printing(capsys):
    table = pa.table({"speech_id": ["a", "b"], "page": [1, 2]})

    usage = arrow_table_memory_usage(table, "_protocol_cache['sample']")

    assert capsys.readouterr().out == ""
    assert usage.label == "_protocol_cache['sample']"
    assert usage.description == "Arrow Table, 2 rows"
    assert usage.n_bytes == table.nbytes
    assert [child.label for child in usage.children] == ["speech_id", "page"]


def test_format_memory_usage_report_uses_precomputed_values(capsys):
    report = MemoryUsageReport(
        sections=(
            MemoryUsageSection(
                label="sample",
                entries=(
                    MemoryUsageEntry(
                        label="sample",
                        description="dict, 1 entry",
                        n_bytes=1024**2,
                    ),
                ),
            ),
        )
    )

    output = format_memory_usage_report(report)

    assert capsys.readouterr().out == ""
    assert "[sample] (dict, 1 entry):" in output
    assert "TOTAL (measured):         1.0 MB" in output


def test_print_memory_usage_report_is_the_output_boundary(capsys):
    report = MemoryUsageReport(
        sections=(
            MemoryUsageSection(
                label="sample",
                entries=(MemoryUsageEntry(label="sample", description="dict, 1 entry", n_bytes=1024**2),),
            ),
        )
    )

    print_memory_usage_report(report)

    assert "[sample] (dict, 1 entry):" in capsys.readouterr().out
