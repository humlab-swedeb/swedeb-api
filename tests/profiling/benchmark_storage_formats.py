"""Benchmark different storage formats for DTM sparse matrices.

Compares:
1. Current NPZ format (scipy.sparse.save_npz/load_npz)
2. Memory-mapped NPZ access
3. Feather/Arrow format (for dense operations)
4. HDF5 format (h5py with compression)

Usage:
    python tests/profiling/benchmark_storage_formats.py
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
import scipy.sparse
from loguru import logger

try:
    import h5py

    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False
    logger.warning("h5py not installed. HDF5 benchmarks will be skipped.")
    logger.warning("Install with: uv pip install h5py")

from api_swedeb.core.configuration import get_config_store
from api_swedeb.core.dtm import VectorizedCorpus

get_config_store().configure_context(source="config/config.yml")


class BenchmarkResult:
    """Store benchmark results."""

    def __init__(self, name: str):
        self.name = name
        self.load_time = 0.0
        self.access_time = 0.0
        self.memory_mb = 0.0
        self.file_size_mb = 0.0
        self.notes = []

    def __repr__(self):
        return (
            f"{self.name:25s} | "
            f"Load: {self.load_time:6.2f}s | "
            f"Access: {self.access_time:6.2f}s | "
            f"Memory: {self.memory_mb:7.1f}MB | "
            f"File: {self.file_size_mb:7.1f}MB"
        )


def get_file_size_mb(filepath: str) -> float:
    """Get file size in MB."""
    if os.path.exists(filepath):
        return os.path.getsize(filepath) / 1024**2
    return 0.0


def estimate_memory_mb(obj: Any) -> float:
    """Estimate memory usage of an object."""
    if isinstance(obj, scipy.sparse.csr_matrix):
        # data + indices + indptr arrays
        return (obj.data.nbytes + obj.indices.nbytes + obj.indptr.nbytes) / 1024**2
    elif isinstance(obj, np.ndarray):
        return obj.nbytes / 1024**2
    elif isinstance(obj, pd.DataFrame):
        return obj.memory_usage(deep=True).sum() / 1024**2
    return 0.0


def benchmark_current_npz(corpus_path: str, tag: str) -> BenchmarkResult:
    """Benchmark current NPZ format (baseline)."""
    result = BenchmarkResult("1. Current NPZ (scipy)")

    npz_file = os.path.join(corpus_path, f"{tag}_vector_data.npz")
    result.file_size_mb = get_file_size_mb(npz_file)

    # Load time
    start = time.perf_counter()
    matrix = scipy.sparse.load_npz(npz_file)
    result.load_time = time.perf_counter() - start

    result.memory_mb = estimate_memory_mb(matrix)

    # Access time: sum a few rows
    start = time.perf_counter()
    for i in range(0, min(1000, matrix.shape[0]), 100):
        _ = matrix[i].sum()
    result.access_time = time.perf_counter() - start

    result.notes.append(f"Shape: {matrix.shape}")
    result.notes.append(f"Non-zeros: {matrix.nnz:,}")
    result.notes.append(f"Density: {matrix.nnz / (matrix.shape[0] * matrix.shape[1]) * 100:.4f}%")

    return result


def benchmark_mmap_npz(corpus_path: str, tag: str, tmpdir: str) -> BenchmarkResult:
    """Benchmark memory-mapped NPZ access."""
    result = BenchmarkResult("2. Memory-mapped NPZ")

    npz_file = os.path.join(corpus_path, f"{tag}_vector_data.npz")

    # NPZ files are ZIP archives, so true mmap isn't possible
    # But we can extract and mmap the components
    try:
        start = time.perf_counter()

        # Extract NPZ components
        with np.load(npz_file, allow_pickle=True) as npz_data:
            # Save components as raw numpy arrays
            data_file = os.path.join(tmpdir, "data.npy")
            indices_file = os.path.join(tmpdir, "indices.npy")
            indptr_file = os.path.join(tmpdir, "indptr.npy")

            np.save(data_file, npz_data['data'])
            np.save(indices_file, npz_data['indices'])
            np.save(indptr_file, npz_data['indptr'])
            shape = npz_data['shape']
            format_str = npz_data.get('format', b'csr').tobytes().decode('latin1')

        # Load with mmap
        data_mmap = np.load(data_file, mmap_mode='r')
        indices_mmap = np.load(indices_file, mmap_mode='r')
        indptr_mmap = np.load(indptr_file, mmap_mode='r')

        # Create sparse matrix (doesn't copy data if mmap arrays)
        matrix = scipy.sparse.csr_matrix((data_mmap, indices_mmap, indptr_mmap), shape=shape)

        result.load_time = time.perf_counter() - start
        result.memory_mb = estimate_memory_mb(matrix)  # Note: may not be accurate for mmap

        # Access time
        start = time.perf_counter()
        for i in range(0, min(1000, matrix.shape[0]), 100):
            _ = matrix[i].sum()
        result.access_time = time.perf_counter() - start

        result.file_size_mb = (
            get_file_size_mb(data_file) + get_file_size_mb(indices_file) + get_file_size_mb(indptr_file)
        )
        result.notes.append("Memory-mapped access to NPZ components")
        result.notes.append("Slower initial setup, but lower memory for large matrices")

    except Exception as e:
        result.notes.append(f"ERROR: {e}")
        logger.error(f"Memory-mapped NPZ failed: {e}")

    return result


def benchmark_hdf5(corpus_path: str, tag: str, tmpdir: str) -> BenchmarkResult:
    """Benchmark HDF5 format."""
    result = BenchmarkResult("3. HDF5 (h5py)")

    if not HAS_H5PY:
        result.notes.append("SKIPPED: h5py not installed")
        return result

    npz_file = os.path.join(corpus_path, f"{tag}_vector_data.npz")
    hdf5_file = os.path.join(tmpdir, "matrix.h5")

    try:
        # Convert NPZ to HDF5
        logger.info("Converting NPZ to HDF5...")
        convert_start = time.perf_counter()

        matrix_orig = scipy.sparse.load_npz(npz_file)

        with h5py.File(hdf5_file, 'w') as f:
            # Store sparse matrix components with compression
            f.create_dataset('data', data=matrix_orig.data, compression='gzip', compression_opts=4)
            f.create_dataset('indices', data=matrix_orig.indices, compression='gzip', compression_opts=4)
            f.create_dataset('indptr', data=matrix_orig.indptr, compression='gzip', compression_opts=4)
            f.attrs['shape'] = matrix_orig.shape
            f.attrs['format'] = 'csr'

        convert_time = time.perf_counter() - convert_start
        result.notes.append(f"Conversion time: {convert_time:.2f}s")

        # Load time
        start = time.perf_counter()
        with h5py.File(hdf5_file, 'r') as f:
            # Can use memory-mapping or load into memory
            data = f['data'][:]
            indices = f['indices'][:]
            indptr = f['indptr'][:]
            shape = tuple(f.attrs['shape'])

        matrix = scipy.sparse.csr_matrix((data, indices, indptr), shape=shape)
        result.load_time = time.perf_counter() - start

        result.memory_mb = estimate_memory_mb(matrix)
        result.file_size_mb = get_file_size_mb(hdf5_file)

        # Access time
        start = time.perf_counter()
        for i in range(0, min(1000, matrix.shape[0]), 100):
            _ = matrix[i].sum()
        result.access_time = time.perf_counter() - start

        result.notes.append("HDF5 with gzip compression (level 4)")
        result.notes.append("Good compression, slower load than NPZ")

    except Exception as e:
        result.notes.append(f"ERROR: {e}")
        logger.error(f"HDF5 benchmark failed: {e}")

    return result


def benchmark_hdf5_mmap(corpus_path: str, tag: str, tmpdir: str) -> BenchmarkResult:
    """Benchmark HDF5 with memory-mapped access."""
    result = BenchmarkResult("4. HDF5 memory-mapped")

    if not HAS_H5PY:
        result.notes.append("SKIPPED: h5py not installed")
        return result

    npz_file = os.path.join(corpus_path, f"{tag}_vector_data.npz")
    hdf5_file = os.path.join(tmpdir, "matrix_mmap.h5")

    try:
        # Convert NPZ to HDF5 without compression for mmap
        logger.info("Converting NPZ to HDF5 (no compression for mmap)...")
        matrix_orig = scipy.sparse.load_npz(npz_file)

        with h5py.File(hdf5_file, 'w') as f:
            # No compression for memory-mapping
            f.create_dataset('data', data=matrix_orig.data)
            f.create_dataset('indices', data=matrix_orig.indices)
            f.create_dataset('indptr', data=matrix_orig.indptr)
            f.attrs['shape'] = matrix_orig.shape
            f.attrs['format'] = 'csr'

        # Load with memory mapping
        start = time.perf_counter()
        f = h5py.File(hdf5_file, 'r')
        # Keep file open for mmap access
        data = f['data']
        indices = f['indices']
        indptr = f['indptr']
        shape = tuple(f.attrs['shape'])

        # Note: h5py datasets support array protocol, can be used directly
        # but scipy.sparse.csr_matrix will copy data
        matrix = scipy.sparse.csr_matrix((data[:], indices[:], indptr[:]), shape=shape)
        result.load_time = time.perf_counter() - start

        result.memory_mb = estimate_memory_mb(matrix)
        result.file_size_mb = get_file_size_mb(hdf5_file)

        # Access time
        start = time.perf_counter()
        for i in range(0, min(1000, matrix.shape[0]), 100):
            _ = matrix[i].sum()
        result.access_time = time.perf_counter() - start

        f.close()

        result.notes.append("HDF5 without compression for memory-mapping")
        result.notes.append("Faster than compressed HDF5, larger file size")

    except Exception as e:
        result.notes.append(f"ERROR: {e}")
        logger.error(f"HDF5 mmap benchmark failed: {e}")

    return result


def benchmark_feather_coo(corpus_path: str, tag: str, tmpdir: str) -> BenchmarkResult:
    """Benchmark Feather format using COO (coordinate) representation."""
    result = BenchmarkResult("5. Feather (COO format)")

    npz_file = os.path.join(corpus_path, f"{tag}_vector_data.npz")
    feather_file = os.path.join(tmpdir, "matrix_coo.feather")

    try:
        # Convert to COO (coordinate) format and save as Feather
        logger.info("Converting sparse matrix to COO Feather...")
        convert_start = time.perf_counter()

        matrix_orig = scipy.sparse.load_npz(npz_file)
        matrix_coo = matrix_orig.tocoo()

        # Create DataFrame with COO representation
        df = pd.DataFrame({'row': matrix_coo.row, 'col': matrix_coo.col, 'data': matrix_coo.data})

        # Save as Feather
        df.to_feather(feather_file, compression='lz4')

        convert_time = time.perf_counter() - convert_start
        result.notes.append(f"Conversion time: {convert_time:.2f}s")

        # Load time
        start = time.perf_counter()
        df_loaded = pd.read_feather(feather_file)

        # Reconstruct sparse matrix
        matrix = scipy.sparse.coo_matrix(
            (df_loaded['data'].values, (df_loaded['row'].values, df_loaded['col'].values)),
            shape=matrix_orig.shape,
        ).tocsr()

        result.load_time = time.perf_counter() - start

        result.memory_mb = estimate_memory_mb(matrix) + estimate_memory_mb(df_loaded)
        result.file_size_mb = get_file_size_mb(feather_file)

        # Access time
        start = time.perf_counter()
        for i in range(0, min(1000, matrix.shape[0]), 100):
            _ = matrix[i].sum()
        result.access_time = time.perf_counter() - start

        result.notes.append("Feather with COO (coordinate) sparse representation")
        result.notes.append("Fast columnar format, good for filtering")

    except Exception as e:
        result.notes.append(f"ERROR: {e}")
        logger.error(f"Feather COO benchmark failed: {e}")

    return result


def print_results(results: list[BenchmarkResult]):
    """Print formatted benchmark results."""
    print("\n" + "=" * 100)
    print("DTM STORAGE FORMAT BENCHMARK RESULTS")
    print("=" * 100)
    print()

    for result in results:
        print(result)
        for note in result.notes:
            print(f"  └─ {note}")
        print()

    print("=" * 100)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 100)

    # Find best for each metric
    valid_results = [r for r in results if r.load_time > 0]

    if valid_results:
        fastest_load = min(valid_results, key=lambda r: r.load_time)
        fastest_access = min(valid_results, key=lambda r: r.access_time)
        smallest_memory = min(valid_results, key=lambda r: r.memory_mb)
        smallest_file = min(valid_results, key=lambda r: r.file_size_mb)

        print(f"\n✓ Fastest load time:    {fastest_load.name} ({fastest_load.load_time:.2f}s)")
        print(f"✓ Fastest access:       {fastest_access.name} ({fastest_access.access_time:.2f}s)")
        print(f"✓ Lowest memory usage:  {smallest_memory.name} ({smallest_memory.memory_mb:.1f}MB)")
        print(f"✓ Smallest file size:   {smallest_file.name} ({smallest_file.file_size_mb:.1f}MB)")

        print("\nRECOMMENDATIONS:")
        print("-" * 100)

        # Calculate improvement over baseline
        baseline = results[0]
        if fastest_load != baseline:
            improvement = ((baseline.load_time - fastest_load.load_time) / baseline.load_time) * 100
            print(f"1. Switch to {fastest_load.name} for {improvement:.1f}% faster load times")

        print(f"2. Current NPZ is reasonable for in-memory serving (good balance)")
        print(f"3. For memory-constrained environments, consider memory-mapped options")
        print(f"4. For cold storage, use compressed HDF5 to save disk space")

        print("\n" + "=" * 100)


def main():
    """Run all benchmarks."""
    from api_swedeb.core.configuration import ConfigValue

    dtm_folder = ConfigValue("dtm.folder").resolve()
    dtm_tag = ConfigValue("dtm.tag").resolve()

    print(f"\nBenchmarking DTM storage formats")
    print(f"Corpus: {dtm_folder}")
    print(f"Tag: {dtm_tag}\n")

    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Run benchmarks
        print("Running benchmark 1/5: Current NPZ format...")
        results.append(benchmark_current_npz(dtm_folder, dtm_tag))

        print("Running benchmark 2/5: Memory-mapped NPZ...")
        results.append(benchmark_mmap_npz(dtm_folder, dtm_tag, tmpdir))

        print("Running benchmark 3/5: HDF5 with compression...")
        results.append(benchmark_hdf5(dtm_folder, dtm_tag, tmpdir))

        print("Running benchmark 4/5: HDF5 memory-mapped...")
        results.append(benchmark_hdf5_mmap(dtm_folder, dtm_tag, tmpdir))

        print("Running benchmark 5/5: Feather COO format...")
        results.append(benchmark_feather_coo(dtm_folder, dtm_tag, tmpdir))

    print_results(results)


if __name__ == "__main__":
    main()
