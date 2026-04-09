"""Pre-built speech corpus generation pipeline.

This package contains all logic for building the offline speech corpus
(bootstrap_corpus) from tagged-frames ZIPs.  It is intentionally isolated
from the runtime API services so the pipeline can eventually be moved to
the ``pyriksprot`` library without disturbing the serving layer.

Submodules
----------
merge       – utterance-chain → speech-row merging
enrichment  – speaker metadata enrichment from SQLite
build       – full corpus builder (SpeechCorpusBuilder) and CLI helpers
"""
