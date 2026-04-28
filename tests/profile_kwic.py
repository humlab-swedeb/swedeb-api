"""Standalone pyinstrument profiling script for the KWIC hot path.

Exercises the exact same path that the KWIC API endpoint runs:
  1. Bootstrap config and load CorpusLoader (cold-start cost, done once).
  2. Build a CWB corpus connection.
  3. Call ``KWICService.get_kwic()`` for the target word.

This lets pyinstrument show where time is spent inside ``kwic_with_decode``,
CWB/CQP query execution, and result decoding without HTTP or Celery overhead.

Usage::

    # Quick terminal flamegraph
    uv run pyinstrument tests/profile_kwic.py

    # HTML report via Makefile target
    make profile-kwic-pyinstrument

    # Different word or context window
    uv run pyinstrument tests/profile_kwic.py --word skola --words-before 3 --words-after 3

    # cProfile + snakeviz
    uv run python -m cProfile -o tests/output/kwic.prof tests/profile_kwic.py
    uv run snakeviz tests/output/kwic.prof
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<level>{level}</level>: {message}")

# pylint: disable=import-outside-toplevel


def _parse_bool(v: str) -> bool:
    if v.lower() in ("true", "yes", "1", "y"):
        return True
    if v.lower() in ("false", "no", "0", "n"):
        return False
    raise argparse.ArgumentTypeError(f"Expected true/false, got: {v!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile KWIC query hot path.")
    parser.add_argument("--config", default="config/config.yml", metavar="PATH", help="Config YAML path.")
    parser.add_argument("--word", default="och", help="Search word (default: och).")
    parser.add_argument("--words-before", type=int, default=5, help="Context tokens before keyword (default: 5).")
    parser.add_argument("--words-after", type=int, default=5, help="Context tokens after keyword (default: 5).")
    parser.add_argument("--from-year", type=int, default=None, help="Start year filter.")
    parser.add_argument("--to-year", type=int, default=None, help="End year filter.")
    parser.add_argument(
        "--lemmatized", type=_parse_bool, default=True, metavar="BOOL", help="Search lemmatized form (default: true)."
    )
    parser.add_argument("--cut-off", type=int, default=200_000, help="Max concordance hits (default: 200000).")
    parser.add_argument(
        "--num-processes",
        type=int,
        default=None,
        help="Number of processes for multiprocessing (default: read from config or use cpu_count()).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    use_multiprocessing: bool | None = None if args.num_processes is None else (args.num_processes > 1)

    import ccc

    from api_swedeb.api.params import build_common_query_params
    from api_swedeb.api.services.corpus_loader import CorpusLoader
    from api_swedeb.api.services.kwic_service import KWICService
    from api_swedeb.core.configuration.inject import ConfigValue, get_config_store

    get_config_store().configure_context(source=args.config)

    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()

    print(f"# Profile KWIC: word='{args.word}'  context={args.words_before}+{args.words_after}", flush=True)
    print(f"  corpus={corpus_name}  cut_off={args.cut_off:,}", flush=True)
    print("=" * 72, flush=True)

    # --- Load corpus (mirrors API worker cold-start) -------------------------
    t0 = time.perf_counter()
    print("Loading CorpusLoader…", flush=True)
    loader = CorpusLoader()
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.prebuilt_speech_index
    print(f"  corpus ready in {time.perf_counter() - t0:.2f}s", flush=True)

    kwic_service = KWICService(loader=loader)

    commons = build_common_query_params(
        from_year=args.from_year,
        to_year=args.to_year,
    )

    data_dir = f"/tmp/ccc-profile-kwic-{uuid.uuid4().hex[:8]}"
    corpus = ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)

    # --- Hot path: KWIC query ------------------------------------------------
    print(f"\nRunning get_kwic('{args.word}', before={args.words_before}, after={args.words_after})…", flush=True)
    t1 = time.perf_counter()
    data = kwic_service.get_kwic(
        corpus=corpus,
        commons=commons,
        keywords=args.word,
        lemmatized=args.lemmatized,
        words_before=args.words_before,
        words_after=args.words_after,
        cut_off=args.cut_off,
        use_multiprocessing=use_multiprocessing,
        n_processes=args.num_processes,
    )
    elapsed = time.perf_counter() - t1

    print(f"  done in {elapsed:.2f}s  →  {len(data):,} rows", flush=True)
    print("=" * 72, flush=True)


if __name__ == "__main__":
    main()
