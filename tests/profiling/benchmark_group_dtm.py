"""Benchmark group_DTM_by_indices_mapping optimization.

Compares original vs optimized implementations to measure performance improvement.

Usage:
    python tests/profiling/benchmark_group_dtm.py
"""

import time
from collections import defaultdict

import numpy as np
import scipy.sparse

from api_swedeb.core.dtm.corpus_optimized import (
    group_DTM_by_indices_mapping_optimized,
    group_DTM_by_indices_mapping_original,
)


def create_test_data(n_docs=100000, n_terms=50000, density=0.001, n_groups=1000):
    """Create synthetic DTM and category indices for benchmarking."""
    print(f"Creating test data: {n_docs} docs, {n_terms} terms, {n_groups} groups...")
    
    # Create sparse DTM
    nnz = int(n_docs * n_terms * density)
    row = np.random.randint(0, n_docs, nnz)
    col = np.random.randint(0, n_terms, nnz)
    data = np.random.randint(1, 10, nnz)
    dtm = scipy.sparse.csr_matrix((data, (row, col)), shape=(n_docs, n_terms))
    
    # Create category indices (group documents)
    # Simulate temporal grouping: each group contains ~n_docs/n_groups documents
    category_indices = {}
    docs_per_group = n_docs // n_groups
    
    for group_id in range(n_groups):
        start_doc = group_id * docs_per_group
        end_doc = (group_id + 1) * docs_per_group if group_id < n_groups - 1 else n_docs
        category_indices[group_id] = list(range(start_doc, end_doc))
    
    total_mappings = sum(len(v) for v in category_indices.values())
    print(f"  DTM shape: {dtm.shape}, nnz: {dtm.nnz:,}")
    print(f"  Groups: {len(category_indices)}, total mappings: {total_mappings:,}")
    
    return dtm, category_indices


def benchmark_function(func, dtm, n_docs, category_indices, aggregate, n_runs=5):
    """Benchmark a grouping function."""
    times = []
    
    # Warm-up run
    result = func(dtm, n_docs, category_indices, aggregate)
    
    # Timed runs
    for _ in range(n_runs):
        start = time.perf_counter()
        result = func(dtm, n_docs, category_indices, aggregate)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'mean': np.mean(times),
        'std': np.std(times),
        'min': np.min(times),
        'max': np.max(times),
        'result_shape': result.shape,
        'result_nnz': result.nnz,
    }


def main():
    print("=" * 80)
    print("BENCHMARKING group_DTM_by_indices_mapping OPTIMIZATION")
    print("=" * 80)
    print()
    
    # Test scenarios
    scenarios = [
        # (n_docs, n_terms, density, n_groups, description)
        (10000, 5000, 0.01, 100, "Small: 10K docs → 100 groups"),
        (100000, 50000, 0.001, 1000, "Medium: 100K docs → 1K groups"),
        (1000000, 100000, 0.0001, 10000, "Large: 1M docs → 10K groups"),
    ]
    
    for n_docs, n_terms, density, n_groups, description in scenarios:
        print(f"\n{description}")
        print("-" * 80)
        
        dtm, category_indices = create_test_data(n_docs, n_terms, density, n_groups)
        
        print("\n  Running ORIGINAL implementation...")
        original_stats = benchmark_function(
            group_DTM_by_indices_mapping_original,
            dtm,
            n_groups,
            category_indices,
            "sum",
            n_runs=3,
        )
        
        print("\n  Running OPTIMIZED implementation...")
        optimized_stats = benchmark_function(
            group_DTM_by_indices_mapping_optimized,
            dtm,
            n_groups,
            category_indices,
            "sum",
            n_runs=3,
        )
        
        # Verify results match
        assert original_stats['result_shape'] == optimized_stats['result_shape']
        assert original_stats['result_nnz'] == optimized_stats['result_nnz']
        
        # Calculate speedup
        speedup = original_stats['mean'] / optimized_stats['mean']
        time_saved = (original_stats['mean'] - optimized_stats['mean']) * 1000  # ms
        
        print(f"\n  RESULTS:")
        print(f"    Original:  {original_stats['mean']*1000:7.2f}ms ± {original_stats['std']*1000:.2f}ms")
        print(f"    Optimized: {optimized_stats['mean']*1000:7.2f}ms ± {optimized_stats['std']*1000:.2f}ms")
        print(f"    Speedup:   {speedup:.2f}x faster ({time_saved:.1f}ms saved per call)")
        print(f"    Result:    {optimized_stats['result_shape']} matrix, {optimized_stats['result_nnz']:,} non-zeros")
    
    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
