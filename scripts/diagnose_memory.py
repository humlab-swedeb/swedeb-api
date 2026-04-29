#!/usr/bin/env python
"""Diagnose memory usage of a fully-loaded CorpusLoader instance.

Run from the swedeb-api repo root after activating the virtual environment:

    python scripts/diagnose_memory.py
    python scripts/diagnose_memory.py --config config/config.yml

The script configures the global ConfigStore, instantiates a CorpusLoader,
calls preload() to eagerly resolve all lazy members, then prints a detailed
per-member memory breakdown including per-column DataFrame sizes.
"""

import argparse
import os
import sys

# Ensure package root is importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration.inject import get_config_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose CorpusLoader memory usage")
    parser.add_argument(
        "--config",
        default="config/config.yml",
        help="Path to config file (default: config/config.yml)",
    )
    args = parser.parse_args()

    print(f"Configuring from {args.config} ...")
    get_config_store().configure_context(source=args.config)

    print("Instantiating CorpusLoader and preloading all resources ...")
    loader = CorpusLoader()
    loader.preload()

    print()
    loader.memory_usage()


if __name__ == "__main__":
    main()
