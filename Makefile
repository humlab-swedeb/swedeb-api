
SHELL := /bin/bash
SOURCE_FOLDERS=api_swedeb tests
PYTEST_ARGS=--durations=0 tests 

#--cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html tests

.PHONY: lint tidy isort black test pylint

lint: tidy pylint

tidy: black isort

isort:
	@poetry run isort --profile black --float-to-top --line-length 120 --py 38 $(SOURCE_FOLDERS)

black: 
	@poetry run black --version
	@poetry run black --line-length 120 --target-version py38 --skip-string-normalization $(SOURCE_FOLDERS)

test:
	@echo "Running tests..."
	@poetry run pytest $(PYTEST_ARGS) tests

pylint:
	@poetry run pylint $(SOURCE_FOLDERS)

.PHONY: requirements.txt
requirements.txt: poetry.lock
	@poetry export --without-hashes -f requirements.txt --output requirements.txt

.PHONY: build-utils profile-utils-cprofile profile-utils-pyinstrument profile-ngrams-pyinstrument

build-utils:
	@echo "Building lib..."
	@poetry run cythonize tests/profiling/utilities.pyx 
	@poetry run python setup.py build_ext --inplace

profile-utils-cprofile: build-utils
	@echo "Profiling lib..."
	@poetry run python -m cProfile -o profile.prof tests/profiling/profile_utilities.py
	@poetry run snakeviz profile.prof

profile-utils-pyinstrument: build-utils
	@echo "Profiling lib..."
	@poetry run pyinstrument tests/profiling/profile_utilities.py

TIMESTAMP_IN_ISO_FORMAT=$(shell date -u +"%Y%m%dT%H%M%SZ")

profile-ngrams-pyinstrument:
	@echo "Profiling n-grams..."
	@mkdir -p tests/output
	@PYTHONPATH=. pyinstrument --color --show-all \
		-o tests/output\$(TIMESTAMP_IN_ISO_FORMAT)_profile_ngrams.html \
			tests/profiling/profile_ngrams.py
