"""CLI entry point for the pre-merged speech corpus builder.

Typical invocation::

    python -m api_swedeb.workflows.scripts.build_speech_corpus_cli \\
        --tagged-frames   ./data/v1.4.1/tagged_frames \\
        --output-root     ./data/v1.4.1/speeches/bootstrap_corpus \\
        --corpus-version  v1.4.1 \\
        --metadata-version v1.4.1

or via make::

    make build-speech-corpus
"""

from __future__ import annotations

import argparse
import json

from api_swedeb.workflows.prebuilt_speech_index.build import SpeechCorpusBuilder


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the pre-merged speech corpus (bootstrap_corpus) from tagged-frames ZIPs."
    )
    parser.add_argument(
        "--tagged-frames", required=True, help="Root folder of tagged-frames ZIPs (contains year sub-dirs)"
    )
    parser.add_argument("--output-root", required=True, help="Destination root for bootstrap_corpus output")
    parser.add_argument("--corpus-version", required=True, help="Corpus version string (e.g. v1.1.0)")
    parser.add_argument("--metadata-version", required=True, help="Metadata version string (e.g. v1.1.0)")
    parser.add_argument(
        "--metadata-db", required=True, help="Path to riksprot SQLite metadata DB for speaker enrichment"
    )
    parser.add_argument("--num-processes", type=int, default=0, help="Parallel workers (0 = sequential, default)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    builder = SpeechCorpusBuilder(
        tagged_frames_folder=args.tagged_frames,
        output_root=args.output_root,
        corpus_version=args.corpus_version,
        metadata_version=args.metadata_version,
        metadata_db_path=args.metadata_db,
        num_processes=args.num_processes,
    )
    report = builder.build()
    print(json.dumps({k: v for k, v in report.items() if k != "failures_detail"}, indent=2))
    if report["skipped"]:
        print(f"\n{report['skipped']} empty protocol ZIP(s) skipped.")
    if report["failures"]:
        print(f"\n{report['failures']} protocol(s) failed. See manifest.json for details.")


if __name__ == "__main__":
    main()
