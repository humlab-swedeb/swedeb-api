
SHELL := /bin/bash
SOURCE_FOLDERS=api_swedeb tests
PYTEST_ARGS=--durations=0 tests 

#--cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html tests

.PHONY: lint tidy isort black test pylint

run:       
	@poetry run uvicorn main:app --reload

lint: tidy pylint

tidy: black isort

isort:
	@poetry run isort --profile black --float-to-top --line-length 120 --py 311 $(SOURCE_FOLDERS)

black: 
	@poetry run black --version
	@poetry run black --line-length 120 --target-version py311 --skip-string-normalization $(SOURCE_FOLDERS)

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


profile-utils-pyinstrument: build-utils
	@echo "Profiling lib..."
	@poetry run pyinstrument tests/profiling/profile_utilities.py

TIMESTAMP_IN_ISO_FORMAT=$(shell date -u +"%Y%m%dT%H%M%SZ")

profile-kwic-pyinstrument:
	@echo "Profiling KWIC..."
	@mkdir -p tests/output
	@PYTHONPATH=. pyinstrument --color --show-all \
		-o tests/output/$(TIMESTAMP_IN_ISO_FORMAT)_profile_kwic.html \
			tests/profile_kwic.py
