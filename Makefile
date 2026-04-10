
SHELL := /bin/bash
SOURCE_FOLDERS=api_swedeb penelope tests
PACKAGE_FOLDER=api_swedeb penelope 
PYTEST_ARGS=--durations=0 tests 

#--cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html tests
semantic-release-dryrun:
	@npx semantic-release --dry-run

act-release-dryrun:
	@act push -j release --dryrun

semantic-release-dryrun-verbose:
	@DEBUG=semantic-release:* npx semantic-release --dry-run --no-ci

prepare-release-assets:
	@./.github/scripts/prepare-release-assets.sh 0.5.0-test

force-release-action:
	@git commit --amend -m "fix: force trigger release action"
	@git push --force-with-lease

.PHONY: lint tidy isort black test pylint

run:       
	@uv run uvicorn main:app --reload

.PHONY: lint tidy isort black
lint: tidy ruff pylint

tidy: black isort

isort:
	@uv run isort --profile black --float-to-top --line-length 120 --py 313 $(SOURCE_FOLDERS)

black: 
	@uv run black --version
	@uv run black --line-length 120 --target-version py313 --skip-string-normalization $(SOURCE_FOLDERS)

.PHONY: test coverage notes
test:
	@echo "Running tests..."
	@uv run pytest $(PYTEST_ARGS) tests

coverage:
	@echo "Running tests with coverage..."
	@uv run pytest --durations=0 --cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html --cov-branch tests/ || true

notes:
	@uv run pylint --notes=FIXME,XXX,TODO --disable=all --enable=W0511 -f colorized $(SOURCE_FOLDERS) || true

.PHONY: pylint 
pylint:
	@uv run pylint $(SOURCE_FOLDERS)

.PHONY: ruff
ruff:
	@uv run ruff check --output-format concise --fix $(SOURCE_FOLDERS)

.PHONY: vulture
vulture:
	@uv run vulture api_swedeb penelope --min-confidence 80

requirements.txt: pyproject.toml
	@uv pip compile pyproject.toml -o requirements.txt

# requirements.txt-to-git: requirements.txt
# 	@git add requirements.txt \
# 		&& git commit -m "📌 updated requirements.txt" \
# 			&& git push

.PHONY: build-utils profile-utils-cprofile profile-utils-pyinstrument profile-ngrams-pyinstrument

build-utils:
	@echo "Building lib..."
	@uv run cythonize tests/profiling/utilities.pyx 
	@uv run python setup.py build_ext --inplace


profile-utils-pyinstrument: build-utils
	@echo "Profiling lib..."
	@uv run pyinstrument tests/profiling/profile_utilities.py

TIMESTAMP_IN_ISO_FORMAT=$(shell date -u +"%Y%m%dT%H%M%SZ")

profile-kwic-pyinstrument:
	@echo "Profiling KWIC..."
	@mkdir -p tests/output
	@PYTHONPATH=. pyinstrument --color --show-all \
		-o tests/output/$(TIMESTAMP_IN_ISO_FORMAT)_profile_kwic.html \
			tests/profile_kwic.py

# --- Bootstrap corpus build ---------------------------------------------------
# Required environment variables (set in .env or export before running):
#   TAGGED_FRAMES_FOLDER  - root folder of tagged-frames ZIPs (year sub-dirs)
#   BOOTSTRAP_CORPUS_ROOT - destination root for bootstrap_corpus output
#   CORPUS_VERSION        - corpus version string, e.g. v1.1.0
#   METADATA_VERSION      - metadata version string, e.g. v1.1.0
#   METADATA_DB           - (optional) path to riksprot SQLite DB for speaker enrichment
#   NUM_PROCESSES         - parallel workers (0 = sequential, default)
CORPUS_VERSION		  ?= v1.4.1
METADATA_VERSION      ?= v1.1.3
TAGGED_FRAMES_FOLDER  ?= /home/roger/source/swedeb/sample-data/data/1867-2020/$(CORPUS_VERSION)/tagged_frames/
BOOTSTRAP_CORPUS_ROOT ?= /home/roger/source/swedeb/sample-data/data/1867-2020/$(CORPUS_VERSION)/speeches/bootstrap_corpus
METADATA_DB           ?=
NUM_PROCESSES         ?= 8

build-speech-corpus:
	@echo "Building bootstrap speech corpus..."
	@echo "  Source : $(TAGGED_FRAMES_FOLDER)"
	@echo "  Output : $(BOOTSTRAP_CORPUS_ROOT)"
	@rm -rf "$(BOOTSTRAP_CORPUS_ROOT)"
	@uv run python -m api_swedeb.workflows.scripts.build_speech_corpus_cli \
		--tagged-frames   "$(TAGGED_FRAMES_FOLDER)" \
		--output-root     "$(BOOTSTRAP_CORPUS_ROOT)" \
		--corpus-version  "$(CORPUS_VERSION)" \
		--metadata-version "$(METADATA_VERSION)" \
		$(if $(METADATA_DB),--metadata-db "$(METADATA_DB)",) \
		--num-processes   $(NUM_PROCESSES)

.PHONY: build-speech-corpus

TEST_TAGGED_FRAMES_FOLDER  = tests/test_data/$(CORPUS_VERSION)/tagged_frames/
TEST_BOOTSTRAP_CORPUS_ROOT = tests/test_data/$(CORPUS_VERSION)/speeches/bootstrap_corpus
TEST_METADATA_DB           = tests/test_data/metadata/riksprot_metadata.$(METADATA_VERSION).db

build-test-speech-corpus:
	@echo "Building bootstrap speech corpus..."
	@echo "  Source : $(TEST_TAGGED_FRAMES_FOLDER)"
	@echo "  Output : $(TEST_BOOTSTRAP_CORPUS_ROOT)"
	@rm -rf "$(TEST_BOOTSTRAP_CORPUS_ROOT)"
	@uv run python -m api_swedeb.workflows.scripts.build_speech_corpus_cli \
		--tagged-frames   "$(TEST_TAGGED_FRAMES_FOLDER)" \
		--output-root     "$(TEST_BOOTSTRAP_CORPUS_ROOT)" \
		--corpus-version  "$(CORPUS_VERSION)" \
		--metadata-version "$(METADATA_VERSION)" \
		$(if $(TEST_METADATA_DB),--metadata-db "$(TEST_METADATA_DB)",) \
		--num-processes 1

.PHONY: build-test-speech-corpus

clean-dev:
	@rm -rf .pytest_cache build dist .eggs *.egg-info
	@rm -rf .coverage coverage.xml htmlcov report.xml .tox
	@find . -type d -name '__pycache__' -exec rm -rf {} +
	@find . -type d -name '*pytest_cache*' -exec rm -rf {} +
	@find . -type d -name '.mypy_cache' -exec rm -rf {} +
	@rm -rf tests/output

.PHONY: release publish ready build tag bump.patch guard-clean-working-repository tidy-to-git

release: ready guard-clean-working-repository bump.patch tag publish

publish:
	@uv build
	@uv publish

ready: clean-dev tidy test lint requirements.txt build

build: requirements.txt
	@uv build

tag:
	@uv build
	@git push
	@git tag $(shell grep "^version \= " pyproject.toml | sed "s/version = //" | sed "s/\"//g") -a
	@git push origin --tags

bump.patch: requirements.txt
	@echo "Manual version bump required - update version in pyproject.toml"
	@git add pyproject.toml requirements.txt
	@git commit -m "📌 bump version patch"
	@git push

guard-clean-working-repository:
	@status="$$(git status --porcelain)"
	@if [[ "$$status" != "" ]]; then \
		echo "error: changes exists, please commit or stash them: " ; \
		echo "$$status" ; \
		exit 65 ; \
	fi
