"""Multiprocessing utilities for KWIC queries.

This module provides helper functions for splitting KWIC queries by year ranges
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def empty_kwic(p_show: str) -> pd.DataFrame:
    return pd.DataFrame(
        index=pd.Index([], name="speech_id"), columns=[f"left_{p_show}", f"node_{p_show}", f"right_{p_show}"]
    )


def extract_year_range(
    opts: dict[str, Any] | list[dict[str, Any]], default_min: int, default_max: int
) -> tuple[int, int]:
    """Extract year range from criteria options.

    Args:
        opts: Query options (single dict or list of dicts)
        default_min: Default minimum year if not specified
        default_max: Default maximum year if not specified

    Returns:
        Tuple of (min_year, max_year)
    """

    if isinstance(opts, dict):
        opts = [opts]

    for opt in opts:
        criterias = opt.get('criterias', [])
        if not criterias:
            continue

        if isinstance(criterias, dict):
            criterias: list[dict[str, Any]] = [criterias]

        for criteria in criterias:
            key: str = criteria.get('key', '')
            if 'year' in key.lower():
                values: Any = criteria.get('values')
                if isinstance(values, tuple) and len(values) == 2:
                    return (int(values[0]), int(values[1]))
                if isinstance(values, list) and len(values) > 0:
                    years: list[int] = [int(v) for v in values]
                    return (min(years), max(years))
                if values is not None and not isinstance(values, (list, tuple)):
                    year = int(values)
                    return (year, year)

    return (default_min, default_max)


def create_year_chunks(min_year: int, max_year: int, num_chunks: int) -> list[tuple[int, int]]:
    """Divide year range into roughly equal chunks.

    Args:
        min_year: Minimum year
        max_year: Maximum year
        num_chunks: Number of chunks to create

    Returns:
        List of (start_year, end_year) tuples
    """
    if num_chunks <= 1:
        return [(min_year, max_year)]

    total_years: int = max_year - min_year + 1
    years_per_chunk: int = max(1, total_years // num_chunks)

    chunks: list[tuple[int, int]] = []
    current_year: int = min_year

    for i in range(num_chunks):
        if i == num_chunks - 1:
            # Last chunk gets all remaining years
            chunks.append((current_year, max_year))
        else:
            end_year: int = min(current_year + years_per_chunk - 1, max_year)
            chunks.append((current_year, end_year))
            current_year = end_year + 1

        if current_year > max_year:
            break

    return chunks


def inject_year_filter(
    opts: dict[str, Any] | list[dict[str, Any]], year_range: tuple[int, int]
) -> list[dict[str, Any]]:
    """Inject or replace year filter in query options.

    Args:
        opts: Original query options
        year_range: (min_year, max_year) to filter by

    Returns:
        Modified query options with year filter
    """
    if isinstance(opts, dict):
        opts = [opts]

    # Deep copy to avoid modifying original
    opts_copy: list[dict[str, Any]] = []
    year_injected = False

    for opt in opts:
        opt_copy: dict[str, Any] = opt.copy()
        criterias = opt_copy.get('criterias', [])

        if isinstance(criterias, dict):
            criterias: list[dict[str, Any]] = [criterias]

        # Create new criterias list
        # Change this to list comprehension
        new_criterias: list[dict[str, Any]] = []
        for criteria in criterias:
            key: str = criteria.get('key', '')
            if 'year' in key.lower():
                # Replace existing year filter
                new_criterias.append({'key': key, 'values': year_range})
                year_injected = True
            else:
                new_criterias.append(criteria)

        # If no year filter existed, add one (use first opt's prefix or 'a')
        if not year_injected:
            prefix: str = opt_copy.get('prefix', 'a')
            year_key: str = f"{prefix}.year_year" if prefix else "year_year"
            new_criterias.append({'key': year_key, 'values': year_range})
            year_injected = True

        opt_copy['criterias'] = new_criterias
        opts_copy.append(opt_copy)

    return opts_copy
